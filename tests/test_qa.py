"""Network-isolated transcription and structured QA tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pgai_voicebot.models import QualityReport, QualityScores, TranscriptTurn
from pgai_voicebot.qa import analyze_transcript, transcribe_recording
from pgai_voicebot.scenarios import ScenarioCatalog


class FakeTranscriptions:
    """Capture transcription arguments and return model-like data."""

    def __init__(self) -> None:
        self.arguments: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> Any:
        self.arguments = kwargs
        payload = {"text": "Hello", "segments": [{"speaker": "A", "text": "Hello"}]}
        return SimpleNamespace(model_dump=lambda **_: payload)


class FakeResponses:
    """Return a prevalidated quality report from the parse endpoint."""

    def __init__(self, report: QualityReport) -> None:
        self.report = report
        self.arguments: dict[str, Any] = {}

    def parse(self, **kwargs: Any) -> SimpleNamespace:
        self.arguments = kwargs
        return SimpleNamespace(output_parsed=self.report)


class FakeOpenAI:
    """Expose only the API surfaces consumed by the QA module."""

    def __init__(self, _api_key: str, report: QualityReport) -> None:
        self.transcriptions = FakeTranscriptions()
        self.audio = SimpleNamespace(transcriptions=self.transcriptions)
        self.responses = FakeResponses(report)


def quality_report(scenario_id: str = "wrong-id") -> QualityReport:
    return QualityReport(
        scenario_id=scenario_id,
        intended_outcome_reached=True,
        summary="The agent completed the requested workflow with a coherent exchange.",
        scores=QualityScores(
            coherence=5, turn_taking=4, task_completion=5, safety=5, naturalness=4
        ),
        strengths=["Clear next step"],
        issues=[],
        next_iteration="Test a more ambiguous date request.",
    )


def test_transcription_requests_diarized_output(tmp_path: Path) -> None:
    recording = tmp_path / "recording.mp3"
    recording.write_bytes(b"fake-audio")
    fake = FakeOpenAI("x", quality_report())
    result = transcribe_recording(
        recording_path=recording,
        api_key="x",
        model="gpt-4o-transcribe-diarize",
        client_factory=lambda **_: fake,
    )
    assert result["segments"][0]["speaker"] == "A"
    assert fake.transcriptions.arguments["response_format"] == "diarized_json"
    assert fake.transcriptions.arguments["chunking_strategy"] == "auto"


def test_qa_uses_schema_and_repairs_scenario_id(catalog: ScenarioCatalog) -> None:
    fake = FakeOpenAI("x", quality_report())
    turns = [
        TranscriptTurn(
            sequence=1,
            role="pgai_agent",
            text="How may I help?",
            captured_at=datetime.now(UTC),
        )
    ]
    report = analyze_transcript(
        scenario=catalog.get("new-patient-scheduling"),
        turns=turns,
        api_key="x",
        model="gpt-5.6-luna",
        client_factory=lambda **_: fake,
    )
    assert report.scenario_id == "new-patient-scheduling"
    assert fake.responses.arguments["text_format"] is QualityReport
    assert "How may I help?" in fake.responses.arguments["input"][1]["content"]
