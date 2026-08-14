"""Reproducible microbenchmarks for hot local paths and resource reporting."""

from __future__ import annotations

import argparse
import gc
import json
import math
import statistics
import time
import tracemalloc
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import psutil

from pgai_voicebot.prompting import build_patient_prompt
from pgai_voicebot.scenarios import ScenarioCatalog
from pgai_voicebot.transcript import history_to_turns

Benchmark = Callable[[], object]


def _page_faults() -> int | None:
    """Return this process's page-fault counter when the OS exposes it."""
    return getattr(psutil.Process().memory_info(), "num_page_faults", None)


def measure(name: str, operation: Benchmark, *, repetitions: int) -> dict[str, Any]:
    """Measure a callable with GC between samples and traced allocation accounting."""
    timings: list[float] = []
    process = psutil.Process()
    start_cpu = sum(process.cpu_times()[:2])
    start_faults = _page_faults()
    gc.collect()
    tracemalloc.start()
    operation()
    for _ in range(repetitions):
        started = time.perf_counter_ns()
        operation()
        timings.append((time.perf_counter_ns() - started) / 1_000)
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    finish_cpu = sum(process.cpu_times()[:2])
    finish_faults = _page_faults()
    return {
        "name": name,
        "repetitions": repetitions,
        "median_microseconds": round(statistics.median(timings), 3),
        "p95_microseconds": round(sorted(timings)[int(0.95 * (len(timings) - 1))], 3),
        "cpu_seconds": round(max(0.0, finish_cpu - start_cpu), 6),
        "peak_traced_bytes": peak_bytes,
        "page_fault_delta": (
            max(0, finish_faults - start_faults)
            if finish_faults is not None and start_faults is not None
            else None
        ),
    }


def _slope(samples: list[tuple[int, float]]) -> float:
    """Estimate the exponent in time ~= n^k using log-log least squares."""
    xs = [math.log(size) for size, _ in samples]
    ys = [math.log(max(duration, 1e-9)) for _, duration in samples]
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(ys)
    denominator = sum((value - x_mean) ** 2 for value in xs)
    return sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True)) / denominator


def empirical_history_growth() -> dict[str, Any]:
    """Measure the one-pass transcript converter at increasing input sizes."""
    samples: list[tuple[int, float]] = []
    for size in (100, 500, 2_000):
        history = [
            SimpleNamespace(
                role="assistant" if index % 2 else "user",
                content=[SimpleNamespace(transcript=f"Synthetic utterance {index}")],
            )
            for index in range(size)
        ]
        started = time.perf_counter()
        history_to_turns(history)
        samples.append((size, time.perf_counter() - started))
    exponent = _slope(samples)
    return {
        "operation": "history_to_turns",
        "expected_big_o": "O(n + total transcript characters)",
        "empirical_exponent": round(exponent, 3),
        "classification": "linear" if 0.6 <= exponent <= 1.4 else "review",
        "samples": [
            {"items": size, "wall_time_seconds": round(duration, 6)} for size, duration in samples
        ],
    }


def main() -> int:
    """Run local-only benchmarks and write a deterministic JSON report."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("build/reports/performance.json"))
    args = parser.parse_args()
    catalog = ScenarioCatalog.from_yaml(Path("scenarios/default.yaml"))
    scenario = catalog.get("new-patient-scheduling")
    lookup = measure(
        "hash-indexed scenario lookup",
        lambda: catalog.get("new-patient-scheduling"),
        repetitions=10_000,
    )
    lookup["expected_big_o"] = "O(1) average; O(n) adversarial worst case"
    prompt = measure(
        "bounded patient prompt construction",
        lambda: build_patient_prompt(scenario),
        repetitions=2_000,
    )
    prompt["expected_big_o"] = "O(total scenario text length)"
    process = psutil.Process()
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "python_runtime": __import__("platform").python_version(),
        "logical_cpu_count": psutil.cpu_count(logical=True),
        "process_rss_bytes": process.memory_info().rss,
        "gpu": {
            "used": False,
            "note": "No local GPU path; speech and model inference use hosted APIs.",
        },
        "benchmarks": [lookup, prompt],
        "growth_analysis": empirical_history_growth(),
        "budgets": {
            "scenario_lookup_median_microseconds_max": 250,
            "prompt_peak_traced_bytes_max": 2_000_000,
            "history_growth_exponent_max": 1.4,
        },
    }
    failures = []
    if lookup["median_microseconds"] > 250:
        failures.append("scenario lookup latency budget exceeded")
    if prompt["peak_traced_bytes"] > 2_000_000:
        failures.append("prompt allocation budget exceeded")
    if report["growth_analysis"]["empirical_exponent"] > 1.4:
        failures.append("transcript conversion is super-linear")
    report["status"] = "pass" if not failures else "fail"
    report["failures"] = failures
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
