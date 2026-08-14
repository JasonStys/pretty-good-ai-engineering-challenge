"""Bounded media parsing and Twilio handshake tests."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from starlette.websockets import WebSocketDisconnect

from pgai_voicebot.constants import MEDIA_CHUNK_BYTES
from pgai_voicebot.errors import ProtocolError
from pgai_voicebot.media_bridge import MediaBridge
from pgai_voicebot.scenarios import ScenarioCatalog


class FakeWebSocket:
    """Queue incoming texts and collect outgoing texts."""

    def __init__(self, incoming: list[dict[str, Any] | str]) -> None:
        self.incoming = [item if isinstance(item, str) else json.dumps(item) for item in incoming]
        self.outgoing: list[str] = []

    async def receive_text(self) -> str:
        return self.incoming.pop(0)

    async def send_text(self, text: str) -> None:
        self.outgoing.append(text)


class FakeSession:
    """Collect audio forwarded to the SDK."""

    def __init__(self) -> None:
        self.audio: list[bytes] = []

    async def send_audio(self, audio: bytes) -> None:
        self.audio.append(audio)

    async def __aiter__(self):
        if False:
            yield None


def make_bridge(websocket: FakeWebSocket, catalog: ScenarioCatalog, tmp_path: Path) -> MediaBridge:
    return MediaBridge(
        websocket=websocket,  # type: ignore[arg-type]
        catalog=catalog,
        artifact_root=tmp_path,
        openai_api_key="test",
        realtime_model="gpt-realtime-2.1",
        voice="ash",
    )


@pytest.mark.asyncio
async def test_handshake_resolves_scenario_and_run(
    catalog: ScenarioCatalog, tmp_path: Path
) -> None:
    websocket = FakeWebSocket(
        [
            {"event": "connected"},
            {
                "event": "start",
                "start": {
                    "streamSid": "MZ00000000000000000000000000000000",
                    "customParameters": {
                        "scenario_id": "new-patient-scheduling",
                        "run_id": "run-1",
                    },
                },
            },
        ]
    )
    bridge = make_bridge(websocket, catalog, tmp_path)
    await bridge._read_handshake()
    assert bridge.scenario is not None
    assert bridge.scenario.id == "new-patient-scheduling"
    assert bridge.store is not None and bridge.store.run_id == "run-1"


@pytest.mark.asyncio
async def test_invalid_handshake_is_rejected(catalog: ScenarioCatalog, tmp_path: Path) -> None:
    bridge = make_bridge(FakeWebSocket([{"event": "start"}] * 4), catalog, tmp_path)
    with pytest.raises(ProtocolError, match="handshake"):
        await bridge._read_handshake()


@pytest.mark.asyncio
async def test_media_is_decoded_and_flushed(catalog: ScenarioCatalog, tmp_path: Path) -> None:
    bridge = make_bridge(FakeWebSocket([]), catalog, tmp_path)
    session = FakeSession()
    bridge.session = session  # type: ignore[assignment]
    audio = bytes([127]) * MEDIA_CHUNK_BYTES
    await bridge._handle_media(
        {"event": "media", "media": {"payload": base64.b64encode(audio).decode("ascii")}}
    )
    assert session.audio == [audio]
    assert not bridge._audio_buffer


@pytest.mark.asyncio
async def test_invalid_media_base64_is_rejected(catalog: ScenarioCatalog, tmp_path: Path) -> None:
    bridge = make_bridge(FakeWebSocket([]), catalog, tmp_path)
    with pytest.raises(ProtocolError, match="base64"):
        await bridge._handle_media({"event": "media", "media": {"payload": "%%%"}})


def test_playback_mark_is_consumed(catalog: ScenarioCatalog, tmp_path: Path) -> None:
    bridge = make_bridge(FakeWebSocket([]), catalog, tmp_path)
    played: list[tuple[str, int, bytes]] = []
    bridge.playback_tracker = SimpleNamespace(
        on_play_bytes=lambda item, index, audio: played.append((item, index, audio))
    )
    bridge._mark_data["1"] = ("item-1", 0, 4)
    bridge._handle_mark({"mark": {"name": "1"}})
    assert played == [("item-1", 0, bytes(4))]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("incoming", "message"),
    [
        (["not-json"], "invalid WebSocket JSON"),
        ([json.dumps([1, 2])], "must be an object"),
        (["x" * 70_000], "exceeded"),
    ],
)
async def test_receive_json_rejects_bad_frames(
    incoming: list[str], message: str, catalog: ScenarioCatalog, tmp_path: Path
) -> None:
    """Malformed and oversized frames fail before consuming memory downstream."""
    bridge = make_bridge(FakeWebSocket(incoming), catalog, tmp_path)
    with pytest.raises(ProtocolError, match=message):
        await bridge._receive_json()


@pytest.mark.asyncio
async def test_twilio_loop_stops_and_handles_disconnect(
    catalog: ScenarioCatalog, tmp_path: Path
) -> None:
    """The inbound loop terminates cleanly on stop or WebSocket disconnect."""
    bridge = make_bridge(FakeWebSocket([{"event": "stop"}]), catalog, tmp_path)
    await bridge._twilio_loop()

    class DisconnectedSocket(FakeWebSocket):
        async def receive_text(self) -> str:
            raise WebSocketDisconnect()

    disconnected = make_bridge(DisconnectedSocket([]), catalog, tmp_path)
    await disconnected._twilio_loop()


@pytest.mark.asyncio
async def test_audio_send_flush_and_realtime_events(
    catalog: ScenarioCatalog, tmp_path: Path
) -> None:
    """Audio, playback marks, interruptions, and history are routed correctly."""
    websocket = FakeWebSocket([])
    bridge = make_bridge(websocket, catalog, tmp_path)
    bridge._audio_buffer.extend(b"partial")
    await bridge._flush_audio()
    assert bridge._audio_buffer == b"partial"

    session = FakeSession()
    bridge.session = session  # type: ignore[assignment]
    await bridge._flush_audio()
    assert session.audio == [b"partial"]

    await bridge._send_audio(b"ignored", "item", 0)
    assert not websocket.outgoing
    bridge.stream_sid = "MZ00000000000000000000000000000000"
    await bridge._send_audio(b"voice", "item", 1)
    assert len(websocket.outgoing) == 2
    assert "media" in websocket.outgoing[0]

    await bridge._handle_realtime_event(
        SimpleNamespace(type="audio_interrupted", audio=None, item_id="", content_index=0)
    )
    await bridge._handle_realtime_event(SimpleNamespace(type="history_updated", history=["first"]))
    await bridge._handle_realtime_event(SimpleNamespace(type="history_added", item="second"))
    await bridge._handle_realtime_event(SimpleNamespace(type="error", error="synthetic"))
    assert bridge._latest_history == ["first", "second"]
    assert any("clear" in item for item in websocket.outgoing)


@pytest.mark.asyncio
async def test_full_bridge_run_releases_resources(
    catalog: ScenarioCatalog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The top-level bridge always closes its Realtime session and writes evidence."""
    websocket = FakeWebSocket(
        [
            {"event": "connected"},
            {
                "event": "start",
                "start": {
                    "streamSid": "MZ00000000000000000000000000000000",
                    "customParameters": {
                        "scenario_id": "new-patient-scheduling",
                        "run_id": "run-full",
                    },
                },
            },
            {"event": "stop"},
        ]
    )

    async def accept() -> None:
        return None

    websocket.accept = accept  # type: ignore[attr-defined]

    class CompleteSession(FakeSession):
        def __init__(self) -> None:
            super().__init__()
            self.entered = False
            self.closed = False

        async def enter(self) -> None:
            self.entered = True

        async def close(self) -> None:
            self.closed = True

    complete = CompleteSession()

    class FakeRealtimeRunner:
        def __init__(self, **_: Any) -> None:
            pass

        async def run(self, **_: Any) -> CompleteSession:
            return complete

    monkeypatch.setattr("pgai_voicebot.media_bridge.RealtimeAgent", lambda **_: object())
    monkeypatch.setattr("pgai_voicebot.media_bridge.RealtimeRunner", FakeRealtimeRunner)
    bridge = make_bridge(websocket, catalog, tmp_path)
    await bridge.run()
    assert complete.entered and complete.closed
    assert (tmp_path / "run-full" / "transcript.json").exists()
