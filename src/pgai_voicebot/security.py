"""Destination and WebSocket request controls."""

from __future__ import annotations

import hmac
from collections.abc import Mapping

from twilio.request_validator import RequestValidator

from .constants import ASSESSMENT_NUMBER
from .errors import DestinationBlockedError


def enforce_assessment_destination(number: str) -> str:
    """Return the only authorized target and reject every alternative."""
    if not hmac.compare_digest(number, ASSESSMENT_NUMBER):
        raise DestinationBlockedError(
            f"blocked destination {number!r}; only {ASSESSMENT_NUMBER} is authorized"
        )
    return ASSESSMENT_NUMBER


def validate_twilio_signature(
    *,
    url: str,
    signature: str | None,
    auth_token: str,
    parameters: Mapping[str, str] | None = None,
) -> bool:
    """Validate Twilio's signed request without logging tokens or signatures."""
    if not signature:
        return False
    validator = RequestValidator(auth_token)
    return bool(validator.validate(url, dict(parameters or {}), signature))
