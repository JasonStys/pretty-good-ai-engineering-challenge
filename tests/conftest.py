"""Shared test fixtures with synthetic credentials only."""

from __future__ import annotations

from pathlib import Path

import pytest

from pgai_voicebot.config import Settings
from pgai_voicebot.scenarios import ScenarioCatalog


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Return valid settings that cannot contact a real service."""
    return Settings(
        openai_api_key="placeholder-openai-key",
        twilio_account_sid="AC00000000000000000000000000000000",
        twilio_auth_token="test-token-not-real",
        twilio_from_number="+15555550123",
        public_base_url="https://voicebot.example.test",
        artifact_dir=tmp_path / "calls",
        scenario_file=Path("scenarios/default.yaml"),
        validate_twilio_signature=False,
    )


@pytest.fixture
def catalog() -> ScenarioCatalog:
    """Load the repository's validated scenario catalog."""
    return ScenarioCatalog.from_yaml(Path("scenarios/default.yaml"))
