"""Environment-backed configuration with fail-closed validation."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .constants import ASSESSMENT_NUMBER, DEFAULT_SCENARIO_FILE

E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")


class Settings(BaseSettings):
    """Validated runtime settings loaded from environment variables or `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    openai_api_key: SecretStr
    openai_realtime_model: str = "gpt-realtime-2.1"
    openai_transcription_model: str = "gpt-4o-transcribe-diarize"
    openai_qa_model: str = "gpt-5.6-luna"
    openai_voice: str = "ash"

    twilio_account_sid: str
    twilio_auth_token: SecretStr
    twilio_from_number: str
    public_base_url: AnyHttpUrl
    target_phone_number: str = ASSESSMENT_NUMBER

    artifact_dir: Path = Path("artifacts/calls")
    scenario_file: Path = DEFAULT_SCENARIO_FILE
    max_call_seconds: int = Field(default=180, ge=60, le=300)
    recording_wait_seconds: int = Field(default=120, ge=30, le=600)
    validate_twilio_signature: bool = True
    log_level: str = "INFO"

    @field_validator("twilio_account_sid")
    @classmethod
    def validate_account_sid(cls, value: str) -> str:
        """Reject malformed account identifiers before any API request."""
        if not re.fullmatch(r"AC[a-fA-F0-9]{32}", value):
            raise ValueError("TWILIO_ACCOUNT_SID must be an AC-prefixed 34-character SID")
        return value

    @field_validator("twilio_from_number", "target_phone_number")
    @classmethod
    def validate_e164(cls, value: str) -> str:
        """Require the international E.164 number representation."""
        if not E164_PATTERN.fullmatch(value):
            raise ValueError("phone numbers must use E.164 format")
        return value

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        """Restrict log-level strings to supported standard values."""
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("unsupported LOG_LEVEL")
        return normalized

    @model_validator(mode="after")
    def enforce_assessment_destination(self) -> Settings:
        """Make destination changes impossible through environment configuration."""
        if self.target_phone_number != ASSESSMENT_NUMBER:
            raise ValueError(f"TARGET_PHONE_NUMBER must remain {ASSESSMENT_NUMBER}")
        if self.public_base_url.scheme != "https":
            raise ValueError("PUBLIC_BASE_URL must use HTTPS")
        return self

    @property
    def websocket_url(self) -> str:
        """Return the secure media-stream endpoint derived from the public URL."""
        parsed = urlsplit(str(self.public_base_url).rstrip("/"))
        return urlunsplit(("wss", parsed.netloc, "/media-stream", "", ""))
