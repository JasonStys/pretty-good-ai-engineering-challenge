"""Submission-gate validation for recordings, transcripts, scope, and consistency."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from .constants import ASSESSMENT_NUMBER
from .models import CallManifest, TranscriptTurn

TRANSCRIPT_LIST = TypeAdapter(list[TranscriptTurn])
SECRET_PATTERNS = {
    "OpenAI key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "Twilio auth token": re.compile(r"\b[a-fA-F0-9]{32}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
}


def validate_submission(root: Path, *, minimum_calls: int = 10) -> list[str]:
    """Return all actionable validation errors without failing on the first issue."""
    manifests, errors = _load_manifests(root)
    completed = [manifest for manifest in manifests if manifest.status == "completed"]
    errors.extend(_validate_batch_invariants(completed, minimum_calls))
    for manifest in completed:
        errors.extend(_validate_completed_call(root, manifest))
    errors.extend(scan_secrets(root))
    return errors


def _load_manifests(root: Path) -> tuple[list[CallManifest], list[str]]:
    """Load all manifests while retaining every parse error for one-pass reporting."""
    manifests: list[CallManifest] = []
    errors: list[str] = []
    for manifest_path in sorted(root.glob("*/manifest.json")):
        try:
            manifests.append(CallManifest.model_validate_json(manifest_path.read_text("utf-8")))
        except (OSError, ValidationError) as exc:
            errors.append(f"{manifest_path}: invalid manifest: {exc}")
    return manifests, errors


def _validate_batch_invariants(completed: list[CallManifest], minimum_calls: int) -> list[str]:
    """Check evidence count, scenario diversity, and single-caller consistency."""
    errors: list[str] = []
    if len(completed) < minimum_calls:
        errors.append(f"need at least {minimum_calls} completed calls; found {len(completed)}")
    scenario_counts = Counter(manifest.scenario_id for manifest in completed)
    duplicates = [scenario for scenario, count in scenario_counts.items() if count > 1]
    if duplicates:
        errors.append(f"completed calls must use distinct scenarios; duplicates: {duplicates}")
    callers = {manifest.caller_number for manifest in completed}
    if len(callers) > 1:
        errors.append("all assessment calls must use one caller number")
    return errors


def _validate_completed_call(root: Path, manifest: CallManifest) -> list[str]:
    """Validate the destination and required evidence for one completed call."""
    errors = []
    if manifest.destination_number != ASSESSMENT_NUMBER:
        errors.append(f"{manifest.run_id}: unauthorized destination")
    run_directory = root / manifest.run_id
    recording = run_directory / "recording.mp3"
    if not recording.exists() or recording.stat().st_size < 10_000:
        errors.append(f"{manifest.run_id}: missing or implausibly small MP3 recording")
    errors.extend(_validate_transcript(manifest.run_id, run_directory / "transcript.json"))
    return errors


def _validate_transcript(run_id: str, transcript_path: Path) -> list[str]:
    """Validate transcript schema, participation, and minimum conversational depth."""
    try:
        turns = TRANSCRIPT_LIST.validate_json(transcript_path.read_text("utf-8"))
    except (OSError, ValidationError) as exc:
        return [f"{run_id}: invalid transcript: {exc}"]
    errors = []
    if {turn.role for turn in turns} != {"patient_bot", "pgai_agent"}:
        errors.append(f"{run_id}: transcript must contain both sides")
    if len(turns) < 4:
        errors.append(f"{run_id}: conversation is too short ({len(turns)} turns)")
    return errors


def scan_secrets(root: Path) -> list[str]:
    """Scan reviewable text artifacts for common secret formats."""
    errors = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".json", ".jsonl", ".md", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"{path}: possible {label}")
    return errors


def validation_summary(root: Path, minimum_calls: int) -> dict[str, object]:
    """Return a JSON-serializable gate result for CLI and Actions summaries."""
    errors = validate_submission(root, minimum_calls=minimum_calls)
    completed = 0
    for manifest_path in root.glob("*/manifest.json"):
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        completed += payload.get("status") == "completed"
    return {
        "status": "pass" if not errors else "fail",
        "minimum_calls": minimum_calls,
        "completed_calls": completed,
        "errors": errors,
    }
