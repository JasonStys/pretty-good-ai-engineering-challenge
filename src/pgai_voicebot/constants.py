"""Security-sensitive constants shared across the application."""

from pathlib import Path

# The challenge explicitly authorizes calls only to this assessment line.
ASSESSMENT_NUMBER = "+18054398008"
DEFAULT_SCENARIO_FILE = Path("scenarios/default.yaml")
MAX_WEBSOCKET_MESSAGE_BYTES = 64 * 1024
MEDIA_CHUNK_SECONDS = 0.05
TWILIO_SAMPLE_RATE_HZ = 8_000
MEDIA_CHUNK_BYTES = int(TWILIO_SAMPLE_RATE_HZ * MEDIA_CHUNK_SECONDS)
