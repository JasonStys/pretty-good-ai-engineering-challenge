"""FastAPI application factory for health checks and Twilio Media Streams."""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketState

from .config import Settings
from .media_bridge import MediaBridge
from .scenarios import ScenarioCatalog
from .security import validate_twilio_signature

LOGGER = logging.getLogger(__name__)


def create_app(settings: Settings) -> FastAPI:
    """Create one configured app without import-time credential loading."""
    catalog = ScenarioCatalog.from_yaml(settings.scenario_file)
    semaphore = asyncio.Semaphore(1)
    app = FastAPI(title="PGAI Patient Simulator", version="1.0.0", docs_url=None, redoc_url=None)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        """Return a dependency-free liveness response."""
        return {"status": "ok"}

    @app.websocket("/media-stream")
    async def media_stream(websocket: WebSocket) -> None:
        """Authenticate and bridge exactly one assessment call at a time."""
        signature = websocket.headers.get("x-twilio-signature")
        if settings.validate_twilio_signature and not validate_twilio_signature(
            url=settings.websocket_url,
            signature=signature,
            auth_token=settings.twilio_auth_token.get_secret_value(),
        ):
            await websocket.close(code=1008, reason="invalid request signature")
            return
        bridge = MediaBridge(
            websocket=websocket,
            catalog=catalog,
            artifact_root=settings.artifact_dir,
            openai_api_key=settings.openai_api_key.get_secret_value(),
            realtime_model=settings.openai_realtime_model,
            voice=settings.openai_voice,
        )
        try:
            async with semaphore:
                await bridge.run()
        except Exception:
            LOGGER.exception("Media stream failed")
            if websocket.application_state != WebSocketState.DISCONNECTED:
                await websocket.close(code=1011, reason="media stream failed")

    return app
