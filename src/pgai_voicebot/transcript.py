"""Realtime history conversion into a compact role-labelled transcript."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from .models import TranscriptTurn

TranscriptRole = Literal["patient_bot", "pgai_agent"]
ROLE_MAP: dict[str, TranscriptRole] = {"assistant": "patient_bot", "user": "pgai_agent"}


def _content_text(content: Any) -> str:
    """Extract a transcript or text field from a Pydantic content item."""
    transcript = getattr(content, "transcript", None)
    text = getattr(content, "text", None)
    return str(transcript or text or "").strip()


def history_to_turns(history: list[Any]) -> list[TranscriptTurn]:
    """Convert SDK history in one pass, omitting system and function-call items."""
    turns: list[TranscriptTurn] = []
    for item in history:
        role = ROLE_MAP.get(getattr(item, "role", ""))
        if role is None:
            continue
        text = " ".join(
            segment
            for content in getattr(item, "content", [])
            if (segment := _content_text(content))
        )
        if text:
            turns.append(
                TranscriptTurn(
                    sequence=len(turns) + 1,
                    role=role,
                    text=text,
                    captured_at=datetime.now(UTC),
                )
            )
    return turns
