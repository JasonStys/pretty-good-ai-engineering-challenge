"""Artifact persistence, aggregation, and metric tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pgai_voicebot.artifacts import CallArtifactStore, render_bug_report
from pgai_voicebot.metrics import MetricSnapshot, build_runtime_metrics
from pgai_voicebot.models import (
    CallManifest,
    QualityIssue,
    QualityReport,
    QualityScores,
    Severity,
    TranscriptTurn,
)


def sample_turns() -> list[TranscriptTurn]:
    now = datetime.now(UTC)
    return [
        TranscriptTurn(sequence=1, role="pgai_agent", text="Hello", captured_at=now),
        TranscriptTurn(
            sequence=2, role="patient_bot", text="I need an appointment", captured_at=now
        ),
    ]


def sample_report() -> QualityReport:
    return QualityReport(
        scenario_id="new-patient-scheduling",
        intended_outcome_reached=False,
        summary="The call remained coherent but did not complete the requested booking.",
        scores=QualityScores(
            coherence=4, turn_taking=4, task_completion=2, safety=5, naturalness=4
        ),
        strengths=["Clear greeting"],
        issues=[
            QualityIssue(
                title="Appointment was not confirmed",
                severity=Severity.HIGH,
                category="task completion",
                evidence="The agent ended without a date or time.",
                impact="The patient cannot rely on having an appointment.",
                expected_behavior="Confirm a slot or provide a concrete escalation path.",
                reproduction_steps=["Request the earliest afternoon appointment."],
                confidence=0.9,
            )
        ],
        next_iteration="Ask one concise follow-up before ending.",
    )


def test_store_writes_manifest_and_both_transcript_formats(tmp_path: Path) -> None:
    store = CallArtifactStore(tmp_path, "run-1")
    manifest = CallManifest(
        run_id="run-1",
        scenario_id="new-patient-scheduling",
        caller_number="+15555550123",
        destination_number="+18054398008",
    )
    store.write_manifest(manifest)
    store.write_transcript("Schedule a visit", sample_turns())
    assert json.loads(store.manifest_path.read_text("utf-8"))["run_id"] == "run-1"
    assert len(json.loads(store.transcript_json_path.read_text("utf-8"))) == 2
    assert "Pretty Good AI agent" in store.transcript_markdown_path.read_text("utf-8")
    assert store.disk_usage_bytes() > 0


def test_bug_report_aggregates_qa(tmp_path: Path) -> None:
    store = CallArtifactStore(tmp_path / "calls", "run-1")
    store.write_quality_report(sample_report())
    destination = tmp_path / "bug-report.md"
    assert render_bug_report(tmp_path / "calls", destination) == 1
    text = destination.read_text("utf-8")
    assert "Appointment was not confirmed" in text
    assert "HIGH" in text


def test_metrics_capture_deltas_and_disk(tmp_path: Path) -> None:
    (tmp_path / "recording.mp3").write_bytes(b"audio")
    (tmp_path / "transcript.md").write_text("words", encoding="utf-8")
    metrics = build_runtime_metrics(
        run_id="run-1",
        started=MetricSnapshot(1.0, 2.0, 100, 5),
        finished=MetricSnapshot(4.0, 2.5, 200, 9),
        run_directory=tmp_path,
        recording_path=tmp_path / "recording.mp3",
        transcript_path=tmp_path / "transcript.md",
    )
    assert metrics.wall_time_seconds == 3
    assert metrics.process_cpu_seconds == 0.5
    assert metrics.peak_rss_bytes == 200
    assert metrics.page_faults == 4
    assert metrics.recording_bytes == 5
