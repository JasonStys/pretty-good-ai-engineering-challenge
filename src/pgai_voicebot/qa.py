"""Post-call transcription and evidence-based quality analysis."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol, cast

from openai import OpenAI

from .models import QualityReport, Scenario, TranscriptTurn


class OpenAIClientFactory(Protocol):
    """Injectable client factory used to isolate network calls in tests."""

    def __call__(self, *, api_key: str) -> OpenAI: ...


def transcribe_recording(
    *,
    recording_path: Path,
    api_key: str,
    model: str,
    client_factory: OpenAIClientFactory = OpenAI,
) -> dict[str, Any]:
    """Return diarized speaker segments for the challenge-compatible MP3 recording."""
    client = client_factory(api_key=api_key)
    with recording_path.open("rb") as recording:
        response = client.audio.transcriptions.create(
            file=recording,
            model=model,
            response_format="diarized_json",
            chunking_strategy="auto",
        )
    payload: Any = response
    if isinstance(payload, dict):
        return payload
    if hasattr(payload, "model_dump"):
        return cast("dict[str, Any]", payload.model_dump(mode="json"))
    raise TypeError("unexpected transcription response")


def analyze_transcript(
    *,
    scenario: Scenario,
    turns: list[TranscriptTurn],
    api_key: str,
    model: str,
    client_factory: OpenAIClientFactory = OpenAI,
) -> QualityReport:
    """Evaluate only transcript evidence and parse the result into a strict schema."""
    transcript = "\n".join(f"[{turn.role}] {turn.text}" for turn in turns)
    rubric = {
        "objective": scenario.objective,
        "conversation_goals": scenario.conversation_goals,
        "probes": scenario.probes,
        "stop_conditions": scenario.stop_conditions,
    }
    client = client_factory(api_key=api_key)
    response = client.responses.parse(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You are a rigorous healthcare voice-agent QA reviewer. Use only the supplied "
                    "transcript as evidence. Do not invent events. Report substantive workflow, "
                    "safety, privacy, correctness, latency-visible, or conversation-quality "
                    "issues; ignore punctuation. Match each issue to a precise quote and assign "
                    "conservative "
                    "severity. The caller and all identity data are synthetic."
                ),
            },
            {
                "role": "user",
                "content": f"Scenario rubric:\n{json.dumps(rubric)}\n\nTranscript:\n{transcript}",
            },
        ],
        text_format=QualityReport,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise ValueError("QA model returned no structured output")
    if parsed.scenario_id != scenario.id:
        parsed = parsed.model_copy(update={"scenario_id": scenario.id})
    return parsed
