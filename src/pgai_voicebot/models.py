"""Validated domain models for scenarios, transcripts, QA, and run metadata."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ScenarioCategory(StrEnum):
    """Supported evaluation categories used for coverage reporting."""

    SCHEDULING = "scheduling"
    RESCHEDULING = "rescheduling"
    REFILL = "refill"
    PRACTICE_INFORMATION = "practice_information"
    SAFETY = "safety"
    PRIVACY = "privacy"
    CONVERSATION_QUALITY = "conversation_quality"
    MULTILINGUAL = "multilingual"


class Severity(StrEnum):
    """Issue impact levels ordered separately during report generation."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    OBSERVATION = "observation"


class Scenario(BaseModel):
    """One bounded, synthetic patient scenario for a complete phone call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=64)]
    title: Annotated[str, Field(min_length=3, max_length=120)]
    category: ScenarioCategory
    objective: Annotated[str, Field(min_length=10, max_length=600)]
    persona: Annotated[str, Field(min_length=10, max_length=600)]
    synthetic_facts: dict[str, Annotated[str, Field(max_length=200)]] = Field(
        default_factory=dict, max_length=20
    )
    conversation_goals: list[Annotated[str, Field(min_length=3, max_length=300)]] = Field(
        min_length=2, max_length=12
    )
    probes: list[Annotated[str, Field(min_length=3, max_length=300)]] = Field(
        default_factory=list, max_length=10
    )
    stop_conditions: list[Annotated[str, Field(min_length=3, max_length=200)]] = Field(
        min_length=1, max_length=6
    )
    language: Annotated[str, Field(pattern=r"^[a-z]{2}$")] = "en"

    @field_validator("synthetic_facts")
    @classmethod
    def require_synthetic_identity(cls, value: dict[str, str]) -> dict[str, str]:
        """Prevent accidental omission of the explicit synthetic-data marker."""
        if value.get("data_classification") != "synthetic":
            raise ValueError("synthetic_facts must set data_classification=synthetic")
        return value


class TranscriptTurn(BaseModel):
    """One role-labelled utterance captured from the Realtime session."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: Annotated[int, Field(ge=1)]
    role: Literal["patient_bot", "pgai_agent"]
    text: Annotated[str, Field(min_length=1, max_length=20_000)]
    captured_at: datetime


class QualityScores(BaseModel):
    """Compact reviewer-friendly scores for the dimensions in the rubric."""

    coherence: Annotated[int, Field(ge=1, le=5)]
    turn_taking: Annotated[int, Field(ge=1, le=5)]
    task_completion: Annotated[int, Field(ge=1, le=5)]
    safety: Annotated[int, Field(ge=1, le=5)]
    naturalness: Annotated[int, Field(ge=1, le=5)]


class QualityIssue(BaseModel):
    """Evidence-backed bug or quality issue found in one call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: Annotated[str, Field(min_length=5, max_length=160)]
    severity: Severity
    category: Annotated[str, Field(min_length=3, max_length=80)]
    evidence: Annotated[str, Field(min_length=5, max_length=1_500)]
    timestamp_seconds: Annotated[float | None, Field(ge=0)] = None
    impact: Annotated[str, Field(min_length=5, max_length=1_000)]
    expected_behavior: Annotated[str, Field(min_length=5, max_length=1_000)]
    reproduction_steps: list[Annotated[str, Field(min_length=3, max_length=300)]] = Field(
        min_length=1, max_length=8
    )
    confidence: Annotated[float, Field(ge=0, le=1)]


class QualityReport(BaseModel):
    """Structured post-call evaluation produced from a role-labelled transcript."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: str
    intended_outcome_reached: bool
    summary: Annotated[str, Field(min_length=10, max_length=1_500)]
    scores: QualityScores
    strengths: list[Annotated[str, Field(min_length=3, max_length=300)]] = Field(max_length=10)
    issues: list[QualityIssue] = Field(max_length=20)
    next_iteration: Annotated[str, Field(min_length=5, max_length=800)]


class CallManifest(BaseModel):
    """Auditable metadata for an initiated call without storing credentials."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    scenario_id: str
    call_sid: str | None = None
    recording_sid: str | None = None
    caller_number: str
    destination_number: str
    status: str = "created"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    recording_path: Path | None = None
    transcript_path: Path | None = None
    qa_report_path: Path | None = None


class RuntimeMetrics(BaseModel):
    """Per-call resource and usage metrics requested by the assignment owner."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    wall_time_seconds: Annotated[float, Field(ge=0)]
    process_cpu_seconds: Annotated[float, Field(ge=0)]
    peak_rss_bytes: Annotated[int, Field(ge=0)]
    page_faults: Annotated[int | None, Field(ge=0)] = None
    recording_bytes: Annotated[int, Field(ge=0)] = 0
    transcript_bytes: Annotated[int, Field(ge=0)] = 0
    artifact_disk_bytes: Annotated[int, Field(ge=0)] = 0
    gpu_used: bool = False
    gpu_note: str = "No local GPU path; inference is performed by hosted APIs."
    realtime_input_tokens: Annotated[int | None, Field(ge=0)] = None
    realtime_output_tokens: Annotated[int | None, Field(ge=0)] = None
