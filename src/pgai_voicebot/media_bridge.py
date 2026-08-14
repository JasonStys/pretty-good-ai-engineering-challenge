"""Memory-bounded bidirectional relay between Twilio and OpenAI Realtime."""

from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import json
import logging
import time
from pathlib import Path
from typing import Any

from agents.realtime import (
    RealtimeAgent,
    RealtimePlaybackTracker,
    RealtimeRunner,
    RealtimeSession,
    RealtimeSessionEvent,
)
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from .artifacts import CallArtifactStore
from .constants import MAX_WEBSOCKET_MESSAGE_BYTES, MEDIA_CHUNK_BYTES, MEDIA_CHUNK_SECONDS
from .errors import ProtocolError
from .models import Scenario
from .prompting import build_patient_prompt
from .scenarios import ScenarioCatalog
from .transcript import history_to_turns

LOGGER = logging.getLogger(__name__)


class MediaBridge:
    """Own one Realtime session and deterministically release all tasks and buffers."""

    def __init__(
        self,
        *,
        websocket: WebSocket,
        catalog: ScenarioCatalog,
        artifact_root: Path,
        openai_api_key: str,
        realtime_model: str,
        voice: str,
    ) -> None:
        self.websocket = websocket
        self.catalog = catalog
        self.artifact_root = artifact_root
        self.scenario: Scenario | None = None
        self.store: CallArtifactStore | None = None
        self.openai_api_key = openai_api_key
        self.realtime_model = realtime_model
        self.voice = voice
        self.playback_tracker = RealtimePlaybackTracker()
        self.session: RealtimeSession | None = None
        self.stream_sid: str | None = None
        self._audio_buffer = bytearray()
        self._last_flush = time.monotonic()
        self._mark_counter = 0
        self._mark_data: dict[str, tuple[str, int, int]] = {}
        self._latest_history: list[Any] = []

    async def run(self) -> None:
        """Accept, handshake, relay until either peer closes, then persist history."""
        await self.websocket.accept()
        await self._read_handshake()
        assert self.scenario is not None
        assert self.store is not None
        agent = RealtimeAgent(
            name=f"Synthetic Patient - {self.scenario.id}",
            instructions=build_patient_prompt(self.scenario),
        )
        runner = RealtimeRunner(
            starting_agent=agent,
            config={
                "model_settings": {
                    "model_name": self.realtime_model,
                    "max_output_tokens": 512,
                    "audio": {
                        "input": {
                            "format": "g711_ulaw",
                            "transcription": {
                                "model": "gpt-4o-mini-transcribe",
                                "language": self.scenario.language,
                            },
                            "turn_detection": {
                                "type": "semantic_vad",
                                "interrupt_response": True,
                                "create_response": True,
                            },
                        },
                        "output": {"format": "g711_ulaw", "voice": self.voice},
                    },
                },
                "tracing_disabled": False,
            },
        )
        self.session = await runner.run(
            model_config={
                "api_key": self.openai_api_key,
                "playback_tracker": self.playback_tracker,
            }
        )
        await self.session.enter()

        tasks = [
            asyncio.create_task(self._twilio_loop(), name="twilio-media-input"),
            asyncio.create_task(self._realtime_loop(), name="openai-realtime-output"),
            asyncio.create_task(self._flush_loop(), name="media-buffer-flush"),
        ]
        try:
            done, _ = await asyncio.wait(tasks[:2], return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            if self.session is not None:
                await self.session.close()
            self._audio_buffer.clear()
            self._mark_data.clear()
            turns = history_to_turns(self._latest_history)
            self.store.write_transcript(self.scenario.title, turns)

    async def _read_handshake(self) -> None:
        """Require Twilio's connected/start sequence and matching custom parameters."""
        saw_connected = False
        for _ in range(4):
            message = await self._receive_json()
            event = message.get("event")
            if event == "connected":
                saw_connected = True
                continue
            if event == "start" and saw_connected:
                start = message.get("start", {})
                parameters = start.get("customParameters", {})
                scenario_id = str(parameters.get("scenario_id") or "")
                run_id = str(parameters.get("run_id") or "")
                if not scenario_id or not run_id:
                    raise ProtocolError("media stream is missing run context")
                self.scenario = self.catalog.get(scenario_id)
                self.store = CallArtifactStore(self.artifact_root, run_id)
                self.stream_sid = str(start.get("streamSid") or "")
                if not self.stream_sid.startswith("MZ"):
                    raise ProtocolError("missing Twilio stream SID")
                return
        raise ProtocolError("Twilio did not send a valid media-stream handshake")

    async def _receive_json(self) -> dict[str, Any]:
        """Receive one bounded JSON object from the WebSocket."""
        text = await self.websocket.receive_text()
        if len(text.encode("utf-8")) > MAX_WEBSOCKET_MESSAGE_BYTES:
            raise ProtocolError("WebSocket message exceeded the configured limit")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProtocolError("invalid WebSocket JSON") from exc
        if not isinstance(payload, dict):
            raise ProtocolError("WebSocket payload must be an object")
        return payload

    async def _twilio_loop(self) -> None:
        """Forward inbound μ-law audio and stop when Twilio ends the stream."""
        try:
            while True:
                message = await self._receive_json()
                event = message.get("event")
                if event == "media":
                    await self._handle_media(message)
                elif event == "mark":
                    self._handle_mark(message)
                elif event == "stop":
                    return
        except WebSocketDisconnect:
            return

    async def _handle_media(self, message: dict[str, Any]) -> None:
        """Decode and buffer only valid, bounded Twilio media payloads."""
        payload = str(message.get("media", {}).get("payload", ""))
        if not payload or len(payload) > MAX_WEBSOCKET_MESSAGE_BYTES:
            return
        try:
            audio = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ProtocolError("invalid base64 media payload") from exc
        self._audio_buffer.extend(audio)
        if len(self._audio_buffer) >= MEDIA_CHUNK_BYTES:
            await self._flush_audio()

    async def _flush_audio(self) -> None:
        """Move the current byte buffer to the SDK and immediately release its storage."""
        if not self._audio_buffer or self.session is None:
            return
        audio = bytes(self._audio_buffer)
        self._audio_buffer.clear()
        self._last_flush = time.monotonic()
        await self.session.send_audio(audio)

    async def _flush_loop(self) -> None:
        """Flush partial media chunks so latency stays bounded during quiet periods."""
        while True:
            await asyncio.sleep(MEDIA_CHUNK_SECONDS)
            if self._audio_buffer and time.monotonic() - self._last_flush >= MEDIA_CHUNK_SECONDS:
                await self._flush_audio()

    async def _realtime_loop(self) -> None:
        """Forward generated audio, track playback, and retain the latest compact history."""
        assert self.session is not None
        async for event in self.session:
            await self._handle_realtime_event(event)

    async def _handle_realtime_event(self, event: RealtimeSessionEvent) -> None:
        """Handle only events that affect playback, history, or reliability."""
        if event.type == "audio":
            await self._send_audio(event.audio.data, event.item_id, event.content_index)
        elif event.type == "audio_interrupted":
            await self._send_twilio({"event": "clear", "streamSid": self.stream_sid})
        elif event.type == "history_updated":
            self._latest_history = list(event.history)
        elif event.type == "history_added":
            self._latest_history.append(event.item)
        elif event.type == "error":
            LOGGER.error("Realtime session error: %s", event.error)

    async def _send_audio(self, audio: bytes, item_id: str, content_index: int) -> None:
        """Send one base64 audio chunk and a matching playback marker to Twilio."""
        if self.stream_sid is None:
            return
        await self._send_twilio(
            {
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {"payload": base64.b64encode(audio).decode("ascii")},
            }
        )
        self._mark_counter += 1
        mark_id = str(self._mark_counter)
        self._mark_data[mark_id] = (item_id, content_index, len(audio))
        await self._send_twilio(
            {"event": "mark", "streamSid": self.stream_sid, "mark": {"name": mark_id}}
        )

    async def _send_twilio(self, payload: dict[str, Any]) -> None:
        """Serialize compact JSON for the Twilio WebSocket."""
        with contextlib.suppress(WebSocketDisconnect, RuntimeError):
            await self.websocket.send_text(json.dumps(payload, separators=(",", ":")))

    def _handle_mark(self, message: dict[str, Any]) -> None:
        """Advance the SDK playback tracker when Twilio confirms playback."""
        mark_id = str(message.get("mark", {}).get("name", ""))
        tracked = self._mark_data.pop(mark_id, None)
        if tracked is None:
            return
        item_id, content_index, byte_count = tracked
        self.playback_tracker.on_play_bytes(item_id, content_index, bytes(byte_count))
