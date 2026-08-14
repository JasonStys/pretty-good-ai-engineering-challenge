"""Submission-gate validation tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pgai_voicebot.artifacts import CallArtifactStore
from pgai_voicebot.models import CallManifest, TranscriptTurn
from pgai_voicebot.validation import scan_secrets, validate_submission, validation_summary


def create_completed_run(root: Path, index: int) -> None:
    """Create one minimal but structurally valid synthetic call artifact."""
    run_id = f"run-{index}"
    store = CallArtifactStore(root, run_id)
    store.write_manifest(
        CallManifest(
            run_id=run_id,
            scenario_id=f"scenario-{index}",
            call_sid=f"CA{index:032d}",
            caller_number="+15555550123",
            destination_number="+18054398008",
            status="completed",
        )
    )
    now = datetime.now(UTC)
    turns = [
        TranscriptTurn(
            sequence=1, role="pgai_agent", text="Hello, how may I help?", captured_at=now
        ),
        TranscriptTurn(
            sequence=2, role="patient_bot", text="I need an appointment.", captured_at=now
        ),
        TranscriptTurn(sequence=3, role="pgai_agent", text="What day works?", captured_at=now),
        TranscriptTurn(sequence=4, role="patient_bot", text="Friday afternoon.", captured_at=now),
    ]
    store.write_transcript(f"Scenario {index}", turns)
    store.recording_path.write_bytes(b"0" * 10_001)


def test_submission_gate_passes_ten_complete_calls(tmp_path: Path) -> None:
    for index in range(10):
        create_completed_run(tmp_path, index)
    assert validate_submission(tmp_path, minimum_calls=10) == []
    assert validation_summary(tmp_path, 10)["status"] == "pass"


def test_submission_gate_reports_missing_calls_and_bad_artifacts(tmp_path: Path) -> None:
    create_completed_run(tmp_path, 0)
    (tmp_path / "run-0" / "recording.mp3").write_bytes(b"small")
    errors = validate_submission(tmp_path, minimum_calls=10)
    assert any("need at least 10" in error for error in errors)
    assert any("implausibly small" in error for error in errors)


def test_secret_scanner_reports_api_key(tmp_path: Path) -> None:
    simulated_key = "sk-" + "abcdefghijklmnopqrstuvwxyz123456"
    (tmp_path / "log.txt").write_text(simulated_key, encoding="utf-8")
    assert any("OpenAI key" in error for error in scan_secrets(tmp_path))
