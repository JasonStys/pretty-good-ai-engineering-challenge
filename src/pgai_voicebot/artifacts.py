"""Bounded, atomic persistence for call evidence and generated reports."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .models import CallManifest, QualityReport, TranscriptTurn


def _json_default(value: Any) -> Any:
    """Serialize supported domain and standard-library objects."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, (datetime, Path)):
        return str(value)
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def atomic_write_text(path: Path, text: str) -> None:
    """Write UTF-8 text through a same-directory temporary file then replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


def write_json(path: Path, payload: Any) -> None:
    """Persist deterministic human-readable JSON atomically."""
    serialized = json.dumps(payload, default=_json_default, ensure_ascii=False, indent=2)
    atomic_write_text(path, f"{serialized}\n")


class CallArtifactStore:
    """Own the predictable filesystem layout for one assessment run."""

    def __init__(self, root: Path, run_id: str) -> None:
        self.run_id = run_id
        self.directory = root / run_id
        self.directory.mkdir(parents=True, exist_ok=True)

    @property
    def manifest_path(self) -> Path:
        """Return the manifest location."""
        return self.directory / "manifest.json"

    @property
    def transcript_json_path(self) -> Path:
        """Return the machine-readable transcript location."""
        return self.directory / "transcript.json"

    @property
    def transcript_markdown_path(self) -> Path:
        """Return the reviewer-friendly transcript location."""
        return self.directory / "transcript.md"

    @property
    def recording_path(self) -> Path:
        """Return the challenge-compatible MP3 recording location."""
        return self.directory / "recording.mp3"

    @property
    def qa_report_path(self) -> Path:
        """Return the structured QA report location."""
        return self.directory / "qa-report.json"

    @property
    def metrics_path(self) -> Path:
        """Return the per-call resource metrics location."""
        return self.directory / "metrics.json"

    def write_manifest(self, manifest: CallManifest) -> None:
        """Create or replace the non-secret run manifest."""
        write_json(self.manifest_path, manifest)

    def write_transcript(self, scenario_title: str, turns: Iterable[TranscriptTurn]) -> None:
        """Write role-labelled JSON and Markdown transcripts from one materialized pass."""
        ordered = list(turns)
        write_json(self.transcript_json_path, ordered)
        lines = [
            f"# Call transcript: {scenario_title}",
            "",
            f"- Run ID: `{self.run_id}`",
            f"- Generated: {datetime.now(UTC).isoformat()}",
            "- Data classification: synthetic assessment conversation",
            "",
        ]
        for turn in ordered:
            speaker = "Patient bot" if turn.role == "patient_bot" else "Pretty Good AI agent"
            lines.extend([f"## {turn.sequence}. {speaker}", "", turn.text, ""])
        atomic_write_text(self.transcript_markdown_path, "\n".join(lines))

    def write_quality_report(self, report: QualityReport) -> None:
        """Persist the model-validated QA report."""
        write_json(self.qa_report_path, report)

    def disk_usage_bytes(self) -> int:
        """Return total regular-file bytes for this run in O(file count)."""
        return sum(path.stat().st_size for path in self.directory.iterdir() if path.is_file())


def render_bug_report(root: Path, destination: Path) -> int:
    """Aggregate QA issues with stable severity ordering and return issue count."""
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "observation": 4}
    issues: list[dict[str, Any]] = []
    for report_path in root.glob("*/qa-report.json"):
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        for issue in payload.get("issues", []):
            issue["run_id"] = report_path.parent.name
            issue["scenario_id"] = payload.get("scenario_id", "unknown")
            issues.append(issue)
    issues.sort(key=lambda item: (severity_rank.get(item.get("severity", ""), 99), item["title"]))

    lines = [
        "# Bug and quality report",
        "",
        "Generated from structured post-call QA. Every entry links back to a run artifact.",
        "",
    ]
    if not issues:
        lines.append("No live-call QA reports are present yet.")
    for index, issue in enumerate(issues, start=1):
        timestamp = issue.get("timestamp_seconds")
        location = f" at {timestamp:.1f}s" if isinstance(timestamp, int | float) else ""
        lines.extend(
            [
                f"## {index}. {issue['title']}",
                "",
                f"- Severity: **{str(issue['severity']).upper()}**",
                f"- Scenario: `{issue['scenario_id']}`",
                f"- Evidence: `{issue['run_id']}/transcript.md`{location}",
                f"- Category: {issue['category']}",
                f"- Confidence: {float(issue['confidence']):.0%}",
                "",
                f"**What happened:** {issue['evidence']}",
                "",
                f"**Why it matters:** {issue['impact']}",
                "",
                f"**Expected behavior:** {issue['expected_behavior']}",
                "",
                "**Reproduction:**",
                "",
                *(
                    f"{step_number}. {step}"
                    for step_number, step in enumerate(issue["reproduction_steps"], 1)
                ),
                "",
            ]
        )
    atomic_write_text(destination, "\n".join(lines))
    return len(issues)
