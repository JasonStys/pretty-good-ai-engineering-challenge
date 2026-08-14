"""Twilio call creation, status polling, and streamed recording download."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

import httpx
from twilio.rest import Client
from twilio.twiml.voice_response import Connect, Stream, VoiceResponse

from .constants import ASSESSMENT_NUMBER
from .errors import VoiceBotError
from .security import enforce_assessment_destination

TERMINAL_CALL_STATUSES = {"completed", "busy", "failed", "no-answer", "canceled"}


class TwilioClientFactory(Protocol):
    """Injectable Twilio client constructor for network-free testing."""

    def __call__(self, username: str, password: str) -> Client: ...


def build_stream_twiml(*, websocket_url: str, scenario_id: str, run_id: str) -> str:
    """Create a bidirectional media stream with bounded, non-secret parameters."""
    response = VoiceResponse()
    connect = Connect()
    stream = Stream(url=websocket_url)
    stream.parameter(name="scenario_id", value=scenario_id)
    stream.parameter(name="run_id", value=run_id)
    connect.append(stream)
    response.append(connect)
    return str(response)


class TwilioGateway:
    """Minimal telephony adapter that cannot dial outside the assessment line."""

    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        caller_number: str,
        client_factory: TwilioClientFactory = Client,
    ) -> None:
        self.account_sid = account_sid
        self._auth_token = auth_token
        self.caller_number = caller_number
        self._client = client_factory(account_sid, auth_token)

    def create_call(
        self,
        *,
        websocket_url: str,
        scenario_id: str,
        run_id: str,
        maximum_seconds: int,
        destination: str = ASSESSMENT_NUMBER,
    ) -> str:
        """Start one recorded dual-channel call after enforcing the fixed target."""
        safe_destination = enforce_assessment_destination(destination)
        call = self._client.calls.create(
            to=safe_destination,
            from_=self.caller_number,
            twiml=build_stream_twiml(
                websocket_url=websocket_url,
                scenario_id=scenario_id,
                run_id=run_id,
            ),
            record=True,
            recording_channels="dual",
            recording_track="both",
            trim="do-not-trim",
            timeout=20,
            time_limit=maximum_seconds,
        )
        return str(call.sid)

    def wait_for_terminal_status(
        self,
        call_sid: str,
        *,
        timeout_seconds: float,
        poll_seconds: float = 2.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> str:
        """Poll with a monotonic deadline and return the terminal Twilio status."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            status = str(self._client.calls(call_sid).fetch().status)
            if status in TERMINAL_CALL_STATUSES:
                return status
            sleeper(poll_seconds)
        raise TimeoutError(f"call {call_sid} did not finish within {timeout_seconds:.0f} seconds")

    def wait_for_recording(
        self,
        call_sid: str,
        *,
        timeout_seconds: float,
        poll_seconds: float = 2.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> Any:
        """Wait for the first completed recording associated with the call."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            recordings = self._client.recordings.list(call_sid=call_sid, limit=1)
            if recordings and str(recordings[0].status) == "completed":
                return recordings[0]
            sleeper(poll_seconds)
        raise TimeoutError(
            f"recording for {call_sid} was not ready within {timeout_seconds:.0f} seconds"
        )

    def download_recording(self, recording_sid: str, destination: Path) -> Path:
        """Stream an MP3 to disk with authentication and an atomic final replace."""
        if not recording_sid.startswith("RE"):
            raise VoiceBotError("invalid Twilio recording SID")
        url = (
            f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/"
            f"Recordings/{recording_sid}.mp3"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".mp3.tmp")
        with (
            httpx.Client(
                auth=(self.account_sid, self._auth_token),
                follow_redirects=True,
                timeout=httpx.Timeout(60.0),
            ) as client,
            client.stream("GET", url) as response,
        ):
            response.raise_for_status()
            with temporary.open("wb") as output:
                for chunk in response.iter_bytes(64 * 1024):
                    output.write(chunk)
        temporary.replace(destination)
        return destination
