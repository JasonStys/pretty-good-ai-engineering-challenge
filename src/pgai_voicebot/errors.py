"""Domain exceptions with safe, user-facing messages."""


class VoiceBotError(Exception):
    """Base exception for expected application failures."""


class ConfigurationError(VoiceBotError):
    """Raised when required configuration is absent or unsafe."""


class DestinationBlockedError(VoiceBotError):
    """Raised when any call target differs from the assessment number."""


class ProtocolError(VoiceBotError):
    """Raised when a WebSocket peer sends an invalid media-stream message."""


class ScenarioNotFoundError(VoiceBotError):
    """Raised when a requested scenario identifier is not configured."""
