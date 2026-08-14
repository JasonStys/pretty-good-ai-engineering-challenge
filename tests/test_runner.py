"""Assessment orchestration tests with every paid/network boundary replaced."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from pgai_voicebot import runner as runner_module
from pgai_voicebot.artifacts import CallArtifactStore
from pgai_voicebot.config import Settings
from pgai_voicebot.errors import VoiceBotError
from pgai_voicebot.models import QualityReport, QualityScores, TranscriptTurn
from pgai_voicebot.runner import AssessmentRunner, load_manifest


class FakeGateway:
    """Deterministic Twilio replacement used by orchestration tests."""

    status = "completed"

    def __init__(self, **_: Any) -> None:
        self.created: list[dict[str, Any]] = []

    def create_call(self, **kwargs: Any) -> str:
        self.created.append(kwargs)
        return "CA00000000000000000000000000000001"

    def wait_for_terminal_status(self, *_: Any, **__: Any) -> str:
        return self.status

    def wait_for_recording(self, *_: Any, **__: Any) -> SimpleNamespace:
        return SimpleNamespace(sid="RE00000000000000000000000000000001")

    def download_recording(self, _sid: str, destination: Path) -> None:
        destination.write_bytes(b"ID3" + bytes(12_000))


def make_report(scenario_id: str) -> QualityReport:
    """Return the smallest valid structured QA result."""
    return QualityReport(
        scenario_id=scenario_id,
        intended_outcome_reached=True,
        summary="The synthetic scenario reached its intended outcome.",
        scores=QualityScores(
            coherence=5, turn_taking=5, task_completion=5, safety=5, naturalness=4
        ),
        strengths=["Clear turn taking"],
        issues=[],
        next_iteration="Retain the current safety boundary.",
    )


def install_runner_fakes(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, *, status: str = "completed"
) -> None:
    """Install deterministic orchestration dependencies and prebuilt transcripts."""
    FakeGateway.status = status
    monkeypatch.setattr(runner_module, "TwilioGateway", FakeGateway)
    monkeypatch.setattr(runner_module, "create_run_id", lambda _: "run-fixed")
    monkeypatch.setattr(AssessmentRunner, "verify_service", lambda _self: None)
    monkeypatch.setattr(runner_module, "take_snapshot", lambda: SimpleNamespace())
    monkeypatch.setattr(
        runner_module,
        "build_runtime_metrics",
        lambda **_: {"run_id": "run-fixed", "wall_time_seconds": 1.0},
    )
    monkeypatch.setattr(runner_module, "transcribe_recording", lambda **_: {"segments": []})
    monkeypatch.setattr(
        runner_module,
        "analyze_transcript",
        lambda scenario, **_: make_report(scenario.id),
    )
    store = CallArtifactStore(settings.artifact_dir, "run-fixed")
    store.write_transcript(
        "Synthetic test",
        [
            TranscriptTurn(
                sequence=1,
                role="patient_bot",
                text="Hello, I need an appointment.",
                captured_at=datetime.now(UTC),
            )
        ],
    )


def test_verify_service_success_and_failures(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The preflight recognizes healthy, malformed, and unreachable services."""
    monkeypatch.setattr(runner_module, "TwilioGateway", FakeGateway)
    assessment = AssessmentRunner(settings)
    good = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"status": "ok"})
    monkeypatch.setattr(runner_module.httpx, "get", lambda *_args, **_kwargs: good)
    assessment.verify_service()

    bad = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"status": "bad"})
    monkeypatch.setattr(runner_module.httpx, "get", lambda *_args, **_kwargs: bad)
    with pytest.raises(VoiceBotError, match="unexpected health"):
        assessment.verify_service()

    def offline(*_args: Any, **_kwargs: Any) -> None:
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(runner_module.httpx, "get", offline)
    with pytest.raises(VoiceBotError, match="not healthy"):
        assessment.verify_service()


def test_full_run_persists_all_outputs(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """A successful run records media, transcript, QA, manifest, and metrics."""
    install_runner_fakes(settings, monkeypatch)
    manifest = AssessmentRunner(settings).run("new-patient-scheduling")
    run_dir = settings.artifact_dir / "run-fixed"
    assert manifest.status == "completed"
    assert manifest.recording_sid is not None
    for name in (
        "manifest.json",
        "recording.mp3",
        "recording-diarization.json",
        "transcript.json",
        "transcript.md",
        "qa-report.json",
        "metrics.json",
    ):
        assert (run_dir / name).exists()


def test_run_without_qa_and_failed_status(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """QA can be omitted, while telephony failure remains auditable."""
    install_runner_fakes(settings, monkeypatch)
    manifest = AssessmentRunner(settings).run("new-patient-scheduling", analyze=False)
    assert manifest.qa_report_path is None

    install_runner_fakes(settings, monkeypatch, status="busy")
    with pytest.raises(VoiceBotError, match="status busy"):
        AssessmentRunner(settings).run("new-patient-scheduling")
    payload = json.loads((settings.artifact_dir / "run-fixed" / "manifest.json").read_text())
    assert payload["status"] == "busy"


def test_batch_bounds_and_manifest_loader(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Batch selection is bounded and manifest loading is schema validated."""
    monkeypatch.setattr(runner_module, "TwilioGateway", FakeGateway)
    assessment = AssessmentRunner(settings)
    with pytest.raises(VoiceBotError, match="between 10"):
        assessment.run_batch(minimum=9)
    expected = assessment.catalog.all()[:10]
    monkeypatch.setattr(
        assessment,
        "run",
        lambda scenario_id, *, analyze: SimpleNamespace(scenario_id=scenario_id, analyze=analyze),
    )
    assert [item.scenario_id for item in assessment.run_batch()] == [item.id for item in expected]

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "run_id": "r1",
                "scenario_id": "s1",
                "caller_number": "+15555550123",
                "destination_number": "+18054398008",
            }
        ),
        encoding="utf-8",
    )
    assert load_manifest(manifest_path).run_id == "r1"


def test_wait_for_transcript_success_and_timeout(tmp_path: Path) -> None:
    """Transcript polling returns only complete pairs and has a hard timeout."""
    store = CallArtifactStore(tmp_path, "run-1")
    store.write_transcript(
        "Scenario",
        [
            TranscriptTurn(
                sequence=1,
                role="patient_bot",
                text="Synthetic utterance.",
                captured_at=datetime.now(UTC),
            )
        ],
    )
    assert AssessmentRunner._wait_for_transcript(store, timeout_seconds=0.1).suffix == ".md"
    empty = CallArtifactStore(tmp_path, "run-2")
    with pytest.raises(TimeoutError):
        AssessmentRunner._wait_for_transcript(empty, timeout_seconds=0.01)
