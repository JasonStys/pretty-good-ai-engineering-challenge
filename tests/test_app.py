"""FastAPI liveness, authentication, and failure-boundary tests."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from pgai_voicebot import app as app_module
from pgai_voicebot.app import create_app
from pgai_voicebot.config import Settings


def test_health_endpoint(settings: Settings) -> None:
    """The liveness endpoint stays dependency-free and hides API docs."""
    with TestClient(create_app(settings)) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        assert client.get("/docs").status_code == 404


def test_invalid_twilio_signature_is_closed(settings: Settings) -> None:
    """An unauthenticated media stream is rejected before allocating a session."""
    secured = settings.model_copy(update={"validate_twilio_signature": True})
    with (
        TestClient(create_app(secured)) as client,
        pytest.raises(WebSocketDisconnect) as disconnected,
        client.websocket_connect("/media-stream"),
    ):
        pass
    assert disconnected.value.code == 1008


def test_media_bridge_runs_and_failure_is_closed(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The route runs its bridge and converts unexpected failures to code 1011."""

    class FailingBridge:
        def __init__(self, *, websocket: Any, **_: Any) -> None:
            self.websocket = websocket

        async def run(self) -> None:
            await self.websocket.accept()
            raise RuntimeError("synthetic failure")

    monkeypatch.setattr(app_module, "MediaBridge", FailingBridge)
    with (
        TestClient(create_app(settings)) as client,
        pytest.raises(WebSocketDisconnect) as disconnected,
        client.websocket_connect("/media-stream") as websocket,
    ):
        websocket.receive_text()
    assert disconnected.value.code == 1011
