"""End-to-end orchestration for recorded assessment calls and post-call QA."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from pydantic import TypeAdapter

from .artifacts import CallArtifactStore, render_bug_report, write_json
from .config import Settings
from .errors import VoiceBotError
from .metrics import build_runtime_metrics, take_snapshot
from .models import CallManifest, TranscriptTurn
from .qa import analyze_transcript, transcribe_recording
from .scenarios import ScenarioCatalog
from .telephony import TwilioGateway

TRANSCRIPT_LIST = TypeAdapter(list[TranscriptTurn])


def create_run_id(scenario_id: str) -> str:
    """Return a sortable collision-resistant directory identifier."""
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{scenario_id}-{uuid4().hex[:8]}"


class AssessmentRunner:
    """Coordinate telephony, evidence collection, transcription, QA, and metrics."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.catalog = ScenarioCatalog.from_yaml(settings.scenario_file)
        self.gateway = TwilioGateway(
            account_sid=settings.twilio_account_sid,
            auth_token=settings.twilio_auth_token.get_secret_value(),
            caller_number=settings.twilio_from_number,
        )

    def verify_service(self) -> None:
        """Fail before placing a paid call when the public bridge is unavailable."""
        health_url = f"{str(self.settings.public_base_url).rstrip('/')}/healthz"
        try:
            response = httpx.get(health_url, timeout=5.0, follow_redirects=False)
            response.raise_for_status()
            if response.json() != {"status": "ok"}:
                raise VoiceBotError("public service returned an unexpected health payload")
        except (httpx.HTTPError, ValueError) as exc:
            raise VoiceBotError(f"public media service is not healthy at {health_url}") from exc

    def run(self, scenario_id: str, *, analyze: bool = True) -> CallManifest:
        """Run one full call; every failure leaves an auditable manifest behind."""
        scenario = self.catalog.get(scenario_id)
        self.verify_service()
        run_id = create_run_id(scenario_id)
        store = CallArtifactStore(self.settings.artifact_dir, run_id)
        manifest = CallManifest(
            run_id=run_id,
            scenario_id=scenario_id,
            caller_number=self.settings.twilio_from_number,
            destination_number=self.settings.target_phone_number,
        )
        store.write_manifest(manifest)
        started = take_snapshot()

        try:
            manifest.call_sid = self.gateway.create_call(
                websocket_url=self.settings.websocket_url,
                scenario_id=scenario_id,
                run_id=run_id,
                maximum_seconds=self.settings.max_call_seconds,
            )
            manifest.status = "in-progress"
            store.write_manifest(manifest)
            status = self.gateway.wait_for_terminal_status(
                manifest.call_sid,
                timeout_seconds=self.settings.max_call_seconds + 60,
            )
            manifest.status = status
            if status != "completed":
                raise VoiceBotError(f"Twilio call ended with status {status}")

            recording = self.gateway.wait_for_recording(
                manifest.call_sid,
                timeout_seconds=self.settings.recording_wait_seconds,
            )
            manifest.recording_sid = str(recording.sid)
            self.gateway.download_recording(manifest.recording_sid, store.recording_path)
            manifest.recording_path = store.recording_path

            diarization = transcribe_recording(
                recording_path=store.recording_path,
                api_key=self.settings.openai_api_key.get_secret_value(),
                model=self.settings.openai_transcription_model,
            )
            write_json(store.directory / "recording-diarization.json", diarization)

            transcript_path = self._wait_for_transcript(store, timeout_seconds=15)
            manifest.transcript_path = transcript_path
            if analyze:
                turns = TRANSCRIPT_LIST.validate_json(
                    store.transcript_json_path.read_text(encoding="utf-8")
                )
                report = analyze_transcript(
                    scenario=scenario,
                    turns=turns,
                    api_key=self.settings.openai_api_key.get_secret_value(),
                    model=self.settings.openai_qa_model,
                )
                store.write_quality_report(report)
                manifest.qa_report_path = store.qa_report_path
                render_bug_report(
                    self.settings.artifact_dir,
                    self.settings.artifact_dir.parent / "bug-report.md",
                )
            manifest.completed_at = datetime.now(UTC)
            store.write_manifest(manifest)
            return manifest
        except Exception:
            manifest.completed_at = datetime.now(UTC)
            if manifest.status in {"created", "in-progress"}:
                manifest.status = "failed"
            store.write_manifest(manifest)
            raise
        finally:
            finished = take_snapshot()
            metrics = build_runtime_metrics(
                run_id=run_id,
                started=started,
                finished=finished,
                run_directory=store.directory,
                recording_path=store.recording_path,
                transcript_path=store.transcript_markdown_path,
            )
            write_json(store.metrics_path, metrics)

    def run_batch(self, *, minimum: int = 10, analyze: bool = True) -> list[CallManifest]:
        """Run distinct scenarios sequentially to preserve natural audio and cost control."""
        scenarios = self.catalog.all()
        if minimum < 10 or minimum > len(scenarios):
            raise VoiceBotError(f"minimum must be between 10 and {len(scenarios)}")
        manifests = []
        for scenario in scenarios[:minimum]:
            manifests.append(self.run(scenario.id, analyze=analyze))
        return manifests

    @staticmethod
    def _wait_for_transcript(store: CallArtifactStore, *, timeout_seconds: float) -> Path:
        """Allow the media service a short bounded interval to finalize its transcript."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if store.transcript_json_path.exists() and store.transcript_markdown_path.exists():
                return store.transcript_markdown_path
            time.sleep(0.25)
        raise TimeoutError("media service did not finalize the transcript")


def load_manifest(path: Path) -> CallManifest:
    """Load one manifest for reporting or validation."""
    return CallManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))
