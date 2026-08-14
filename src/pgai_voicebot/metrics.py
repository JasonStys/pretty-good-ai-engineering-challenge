"""Low-overhead runtime and artifact metric collection."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import psutil

from .models import RuntimeMetrics


@dataclass(frozen=True)
class MetricSnapshot:
    """Process counters captured at one instant."""

    monotonic_seconds: float
    process_cpu_seconds: float
    rss_bytes: int
    page_faults: int | None


def take_snapshot() -> MetricSnapshot:
    """Read process counters once without retaining OS handles."""
    process = psutil.Process()
    memory = process.memory_info()
    cpu = process.cpu_times()
    page_faults = getattr(memory, "num_page_faults", None)
    return MetricSnapshot(
        monotonic_seconds=time.monotonic(),
        process_cpu_seconds=cpu.user + cpu.system,
        rss_bytes=memory.rss,
        page_faults=page_faults,
    )


def build_runtime_metrics(
    *,
    run_id: str,
    started: MetricSnapshot,
    finished: MetricSnapshot,
    run_directory: Path,
    recording_path: Path | None = None,
    transcript_path: Path | None = None,
) -> RuntimeMetrics:
    """Calculate deltas and disk sizes in O(number of run files)."""
    artifact_bytes = sum(path.stat().st_size for path in run_directory.iterdir() if path.is_file())
    return RuntimeMetrics(
        run_id=run_id,
        wall_time_seconds=max(0.0, finished.monotonic_seconds - started.monotonic_seconds),
        process_cpu_seconds=max(0.0, finished.process_cpu_seconds - started.process_cpu_seconds),
        peak_rss_bytes=max(started.rss_bytes, finished.rss_bytes),
        page_faults=(
            max(0, finished.page_faults - started.page_faults)
            if finished.page_faults is not None and started.page_faults is not None
            else None
        ),
        recording_bytes=(
            recording_path.stat().st_size if recording_path and recording_path.exists() else 0
        ),
        transcript_bytes=(
            transcript_path.stat().st_size if transcript_path and transcript_path.exists() else 0
        ),
        artifact_disk_bytes=artifact_bytes,
    )
