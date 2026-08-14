"""TwiML and fixed-destination telephony tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pgai_voicebot.constants import ASSESSMENT_NUMBER
from pgai_voicebot.errors import DestinationBlockedError
from pgai_voicebot.telephony import TwilioGateway, build_stream_twiml


class FakeCalls:
    """Record call creation arguments and expose a programmable status."""

    def __init__(self) -> None:
        self.created: dict[str, object] = {}
        self.statuses = iter(["queued", "in-progress", "completed"])

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.created = kwargs
        return SimpleNamespace(sid="CA00000000000000000000000000000000")

    def __call__(self, _call_sid: str) -> SimpleNamespace:
        return SimpleNamespace(fetch=lambda: SimpleNamespace(status=next(self.statuses)))


class FakeRecordings:
    """Return one completed recording for polling tests."""

    def list(self, **_kwargs: object) -> list[SimpleNamespace]:
        return [SimpleNamespace(sid="RE00000000000000000000000000000000", status="completed")]


class FakeClient:
    """Minimal Twilio client surface used by the gateway."""

    def __init__(self, _username: str, _password: str) -> None:
        self.calls = FakeCalls()
        self.recordings = FakeRecordings()


def make_gateway() -> TwilioGateway:
    return TwilioGateway(
        account_sid="AC00000000000000000000000000000000",
        auth_token="token",
        caller_number="+15555550123",
        client_factory=FakeClient,
    )


def test_twiml_contains_stream_and_non_secret_context() -> None:
    twiml = build_stream_twiml(
        websocket_url="wss://example.test/media-stream",
        scenario_id="new-patient-scheduling",
        run_id="run-1",
    )
    assert '<Connect><Stream url="wss://example.test/media-stream">' in twiml
    assert 'name="scenario_id" value="new-patient-scheduling"' in twiml
    assert 'name="run_id" value="run-1"' in twiml


def test_gateway_records_dual_channel_assessment_call() -> None:
    gateway = make_gateway()
    sid = gateway.create_call(
        websocket_url="wss://example.test/media-stream",
        scenario_id="new-patient-scheduling",
        run_id="run-1",
        maximum_seconds=180,
    )
    assert sid.startswith("CA")
    assert gateway._client.calls.created["to"] == ASSESSMENT_NUMBER
    assert gateway._client.calls.created["recording_channels"] == "dual"
    assert gateway._client.calls.created["time_limit"] == 180


def test_gateway_blocks_alternative_number() -> None:
    gateway = make_gateway()
    with pytest.raises(DestinationBlockedError):
        gateway.create_call(
            websocket_url="wss://example.test/media-stream",
            scenario_id="new-patient-scheduling",
            run_id="run-1",
            maximum_seconds=180,
            destination="+15555550199",
        )


def test_pollers_return_terminal_call_and_recording() -> None:
    gateway = make_gateway()
    assert (
        gateway.wait_for_terminal_status("CA0", timeout_seconds=5, sleeper=lambda _: None)
        == "completed"
    )
    recording = gateway.wait_for_recording("CA0", timeout_seconds=5, sleeper=lambda _: None)
    assert recording.sid.startswith("RE")
