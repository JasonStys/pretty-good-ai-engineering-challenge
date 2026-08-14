"""Configuration and allowlist tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pgai_voicebot.config import Settings
from pgai_voicebot.constants import ASSESSMENT_NUMBER
from pgai_voicebot.errors import DestinationBlockedError
from pgai_voicebot.security import enforce_assessment_destination, validate_twilio_signature


def valid_values() -> dict[str, str]:
    """Build a complete synthetic settings mapping."""
    return {
        "openai_api_key": "placeholder-openai-key",
        "twilio_account_sid": "AC00000000000000000000000000000000",
        "twilio_auth_token": "not-a-real-token",
        "twilio_from_number": "+15555550123",
        "public_base_url": "https://example.test/base",
    }


def test_settings_derive_secure_websocket_url() -> None:
    settings = Settings(**valid_values())
    assert settings.websocket_url == "wss://example.test/media-stream"
    assert settings.target_phone_number == ASSESSMENT_NUMBER


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("twilio_account_sid", "bad"),
        ("twilio_from_number", "951-555-0123"),
        ("target_phone_number", "+15555550199"),
        ("public_base_url", "http://example.test"),
        ("log_level", "verbose"),
    ],
)
def test_settings_reject_unsafe_values(field: str, value: str) -> None:
    values = valid_values()
    values[field] = value
    with pytest.raises(ValidationError):
        Settings(**values)


def test_destination_is_hard_allowlisted() -> None:
    assert enforce_assessment_destination(ASSESSMENT_NUMBER) == ASSESSMENT_NUMBER
    with pytest.raises(DestinationBlockedError):
        enforce_assessment_destination("+15555550199")


def test_twilio_signature_requires_a_value() -> None:
    assert not validate_twilio_signature(url="wss://example.test", signature=None, auth_token="x")
