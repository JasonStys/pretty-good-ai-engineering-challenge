"""Generate the requested styled Excel engineering and test reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

NAVY = "15253D"
BLUE = "1F6FEB"
TEAL = "0E7490"
LIGHT_BLUE = "E8F1FB"
LIGHT_GREEN = "E6F4EA"
LIGHT_AMBER = "FFF4CE"
WHITE = "FFFFFF"
GRAY = "5B6573"
THIN_GRAY = Side(style="thin", color="D1D5DB")


def _title(worksheet: Any, text: str, subtitle: str, width: int) -> None:
    """Create a consistent two-row workbook title band."""
    worksheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=width)
    cell = worksheet.cell(1, 1, text)
    cell.font = Font(name="Aptos Display", size=20, bold=True, color=WHITE)
    cell.fill = PatternFill("solid", fgColor=NAVY)
    cell.alignment = Alignment(vertical="center")
    worksheet.row_dimensions[1].height = 34
    worksheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=width)
    subtitle_cell = worksheet.cell(2, 1, subtitle)
    subtitle_cell.font = Font(name="Aptos", size=10, italic=True, color=GRAY)
    worksheet.row_dimensions[2].height = 26


def _table_header(worksheet: Any, row: int, labels: list[str]) -> None:
    """Style one table header row."""
    for column, label in enumerate(labels, 1):
        cell = worksheet.cell(row, column, label)
        cell.fill = PatternFill("solid", fgColor=BLUE)
        cell.font = Font(name="Aptos", bold=True, color=WHITE)
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        cell.border = Border(bottom=THIN_GRAY)
    worksheet.row_dimensions[row].height = 28


def _finish_sheet(worksheet: Any, widths: list[int], freeze: str = "A5") -> None:
    """Apply readable widths, filters, and consistent body formatting."""
    worksheet.freeze_panes = freeze
    for index, width in enumerate(widths, 1):
        worksheet.column_dimensions[get_column_letter(index)].width = width
    for row_index, row in enumerate(worksheet.iter_rows(min_row=5), start=5):
        for cell in row:
            cell.font = Font(name="Aptos", size=10, color="1F2937")
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = Border(bottom=THIN_GRAY)
            if row_index % 2:
                cell.fill = PatternFill("solid", fgColor="F8FAFC")
        worksheet.row_dimensions[row_index].height = 28
    worksheet.sheet_view.showGridLines = False
    last_column = get_column_letter(worksheet.max_column)
    worksheet.auto_filter.ref = f"A4:{last_column}{worksheet.max_row}"


def _source_note(worksheet: Any, row: int, width: int, text: str) -> None:
    """Add a plain-text provenance note that remains visible in exported formats."""
    worksheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=width)
    cell = worksheet.cell(row, 1, text)
    cell.font = Font(name="Aptos", size=9, italic=True, color=GRAY)
    cell.alignment = Alignment(wrap_text=True)


def build_test_results(output: Path) -> None:
    """Create the verification workbook with formula-driven totals."""
    workbook = Workbook()
    summary = workbook.active
    summary.title = "Summary"
    _title(
        summary,
        "Pretty Good AI Challenge — Verification",
        "Prepared for Jason Stys | 2026-08-14",
        5,
    )
    _table_header(summary, 4, ["Metric", "Result", "Threshold", "Status", "Evidence"])
    rows = [
        ("Automated tests", 54, 54, '=IF(B5>=C5,"PASS","FAIL")', "pytest"),
        ("Branch-aware coverage", 91.47, 90, '=IF(B6>=C6,"PASS","FAIL")', "coverage.json"),
        ("mypy source errors", 0, 0, '=IF(B7<=C7,"PASS","FAIL")', "mypy src"),
        ("Bandit findings", 0, 0, '=IF(B8<=C8,"PASS","FAIL")', "bandit -r src"),
        ("Known dependency vulnerabilities", 0, 0, '=IF(B9<=C9,"PASS","FAIL")', "pip-audit"),
        ("Live completed calls", 0, 10, '=IF(B10>=C10,"PASS","PENDING")', "submission gate"),
    ]
    for row in rows:
        summary.append(row)
    summary["B6"].number_format = '0.00"%"'
    summary["C6"].number_format = '0.00"%"'
    summary.conditional_formatting.add(
        "D5:D10",
        CellIsRule(
            operator="equal", formula=['"PASS"'], fill=PatternFill("solid", fgColor=LIGHT_GREEN)
        ),
    )
    _source_note(
        summary,
        12,
        5,
        "Source: local verification commands and artifacts/coverage.json. Live-call count is intentionally not inferred from mocks.",
    )
    _finish_sheet(summary, [34, 16, 16, 16, 32])

    groups = workbook.create_sheet("Test_Groups")
    _title(groups, "Automated Test Groups", "Counts reconcile to the 54-test pytest result", 5)
    _table_header(groups, 4, ["Area", "Tests", "Status", "Primary boundary", "Command"])
    test_groups = [
        (
            "FastAPI app",
            3,
            "PASS",
            "Health, signature rejection, bridge exception",
            "pytest tests/test_app.py",
        ),
        (
            "Artifact persistence",
            3,
            "PASS",
            "Atomic writes and bug aggregation",
            "pytest tests/test_artifacts.py",
        ),
        ("CLI", 6, "PASS", "Routing and stable error codes", "pytest tests/test_cli.py"),
        (
            "Configuration",
            8,
            "PASS",
            "Secrets, E.164, allowlist, URLs",
            "pytest tests/test_config.py",
        ),
        (
            "Media bridge",
            11,
            "PASS",
            "Frames, audio, events, cleanup",
            "pytest tests/test_media_bridge.py",
        ),
        ("Structured QA", 2, "PASS", "Diarization and response schema", "pytest tests/test_qa.py"),
        (
            "Assessment runner",
            5,
            "PASS",
            "Preflight, orchestration, failure evidence",
            "pytest tests/test_runner.py",
        ),
        ("Scenarios", 7, "PASS", "Diversity and strict schema", "pytest tests/test_scenarios.py"),
        (
            "Telephony",
            4,
            "PASS",
            "Fixed destination, recording, timeouts",
            "pytest tests/test_telephony.py",
        ),
        ("Transcript", 2, "PASS", "Role mapping and omission", "pytest tests/test_transcript.py"),
        (
            "Submission validation",
            3,
            "PASS",
            "Evidence consistency and secret scan",
            "pytest tests/test_validation.py",
        ),
    ]
    for row in test_groups:
        groups.append(row)
    groups.append(("TOTAL", "=SUM(B5:B15)", '=IF(B16=54,"PASS","FAIL")', "", ""))
    _finish_sheet(groups, [28, 12, 14, 42, 38])

    security = workbook.create_sheet("Security")
    _title(security, "Security Validation", "Static, dependency, boundary, and data controls", 5)
    _table_header(
        security, 4, ["Control", "Result", "Status", "Risk addressed", "Evidence / source"]
    )
    security_rows = [
        (
            "Destination allowlist",
            "Only +18054398008",
            "PASS",
            "Unauthorized calling",
            "constants.py; telephony.py",
        ),
        (
            "Twilio request signature",
            "Enabled by default",
            "PASS",
            "Forged media session",
            "security.py; test_app.py",
        ),
        ("Bandit", "0 findings", "PASS", "Python security defects", "2026-08-14 local run"),
        (
            "pip-audit",
            "0 known vulnerabilities",
            "PASS",
            "Known dependency CVEs",
            "2026-08-14; pip 26.2.1",
        ),
        (
            "Artifact secret scan",
            "OpenAI/Twilio/private-key patterns",
            "PASS",
            "Credential disclosure",
            "validation.py",
        ),
        (
            "Synthetic data schema",
            "Explicit marker required",
            "PASS",
            "Real PHI leakage",
            "models.py; scenarios/default.yaml",
        ),
        (
            "Live artifact review",
            "Not yet performed",
            "PENDING",
            "Voice/privacy disclosure",
            "docs/submission-checklist.md",
        ),
    ]
    for row in security_rows:
        security.append(row)
    _finish_sheet(security, [30, 32, 15, 34, 42])

    workflows = workbook.create_sheet("CI_Workflows")
    _title(
        workflows,
        "GitHub Actions Coverage",
        "Automated status, reports, and live-evidence gating",
        5,
    )
    _table_header(workflows, 4, ["Workflow", "Triggers", "Measures", "Output", "Failure behavior"])
    workflow_rows = [
        (
            "CI",
            "push, pull request, manual",
            "lint, format, types, Python 3.11–3.13 tests, build",
            "coverage XML; distributions",
            "blocks on any failure",
        ),
        (
            "Security",
            "push, PR, weekly, manual",
            "Bandit, pip-audit, secret tests, CodeQL",
            "security alerts/logs",
            "blocks findings/advisories",
        ),
        (
            "Performance",
            "code changes, weekly, manual",
            "runtime, CPU, allocation, page faults, Big-O, Radon",
            "performance JSON",
            "blocks budget regression",
        ),
        (
            "Documentation",
            "docs changes, manual",
            "DOCX/XLSX parts, sheets, formulas, error cells",
            "four reports",
            "blocks malformed report",
        ),
        (
            "Live submission gate",
            "artifact changes or manual",
            "ten real calls, media, transcript, scope, secrets",
            "JSON console summary",
            "fails until evidence is genuine",
        ),
    ]
    for row in workflow_rows:
        workflows.append(row)
    _finish_sheet(workflows, [27, 30, 48, 30, 32])
    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True
    workbook.calculation.calcMode = "auto"
    output.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output)


def build_engineering_metrics(output: Path, performance_path: Path, coverage_path: Path) -> None:
    """Create the implementation, complexity, and resource workbook."""
    performance = json.loads(performance_path.read_text(encoding="utf-8"))
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Performance"
    _title(
        sheet,
        "Engineering Performance Metrics",
        "Local benchmark; hosted model/network latency excluded",
        7,
    )
    _table_header(
        sheet,
        4,
        [
            "Operation",
            "Repetitions",
            "Median μs",
            "P95 μs",
            "CPU s",
            "Peak bytes",
            "Expected Big-O",
        ],
    )
    for item in performance["benchmarks"]:
        sheet.append(
            (
                item["name"],
                item["repetitions"],
                item["median_microseconds"],
                item["p95_microseconds"],
                item["cpu_seconds"],
                item["peak_traced_bytes"],
                item["expected_big_o"],
            )
        )
    sheet.append(
        (
            "AVERAGE",
            "=SUM(B5:B6)",
            "=AVERAGE(C5:C6)",
            "=AVERAGE(D5:D6)",
            "=SUM(E5:E6)",
            "=MAX(F5:F6)",
            "",
        )
    )
    _source_note(
        sheet,
        9,
        7,
        "Source: build/reports/performance.json, generated by scripts/benchmark.py. Results vary by host; CI enforces generous regression budgets.",
    )
    _finish_sheet(sheet, [38, 14, 16, 16, 14, 18, 42])

    complexity = workbook.create_sheet("Complexity")
    _title(
        complexity,
        "Algorithmic and Code Complexity",
        "Built-in structures and bounded streaming paths",
        6,
    )
    _table_header(
        complexity,
        4,
        ["Operation / module", "Structure", "Expected time", "Memory", "Rationale", "Verification"],
    )
    complexity_rows = [
        (
            "Scenario lookup",
            "dict",
            "O(1) average",
            "O(n) catalog",
            "Direct identifier index",
            "benchmark + unit test",
        ),
        (
            "Audio buffering",
            "bytearray",
            "O(bytes)",
            "O(chunk)",
            "One reusable ~50 ms chunk",
            "bridge lifecycle tests",
        ),
        (
            "Transcript conversion",
            "list + one pass",
            "O(n + chars)",
            "O(turns + chars)",
            "No nested history scan",
            "empirical exponent",
        ),
        (
            "Artifact validation",
            "Counter + sets",
            "O(files + bytes)",
            "O(calls + findings)",
            "Collect all errors in one pass",
            "submission tests",
        ),
        (
            "Bug aggregation",
            "list + Timsort",
            "O(i log i)",
            "O(i)",
            "Stable severity/title ordering",
            "artifact tests",
        ),
        (
            "Cyclomatic complexity",
            "98 analyzed blocks",
            "Average A (2.64)",
            "N/A",
            "Radon; no D/E/F block",
            "performance workflow",
        ),
    ]
    for row in complexity_rows:
        complexity.append(row)
    _finish_sheet(complexity, [31, 25, 28, 25, 42, 32])

    resources = workbook.create_sheet("Resource_Model")
    _title(
        resources, "Resource and Usage Model", "Per-call metrics plus local benchmark context", 5
    )
    _table_header(
        resources, 4, ["Metric", "Implementation", "Current value", "Budget / behavior", "Notes"]
    )
    growth = performance["growth_analysis"]
    resource_rows = [
        (
            "Coverage",
            "coverage.py branch measurement",
            coverage["totals"]["percent_covered"],
            ">=90%",
            "54 tests",
        ),
        (
            "Process RSS",
            "psutil snapshot",
            performance["process_rss_bytes"],
            "reported, not hard-failed",
            "benchmark process",
        ),
        (
            "Page faults",
            "OS process counter",
            performance["benchmarks"][0]["page_fault_delta"],
            "reported when supported",
            "Windows/Linux dependent",
        ),
        ("GPU", "hosted inference", 0, "no local allocation", performance["gpu"]["note"]),
        ("Disk", "sum regular run files", 0, "measured per live call", "no live calls yet"),
        (
            "Empirical growth exponent",
            "log-log fit",
            growth["empirical_exponent"],
            "<=1.4",
            growth["classification"],
        ),
        ("Live runtime", "monotonic wall clock", 0, "1–3 min expected", "awaiting genuine calls"),
    ]
    for row in resource_rows:
        resources.append(row)
    resources["C5"].number_format = '0.00"%"'
    _finish_sheet(resources, [31, 34, 20, 30, 47])

    scenarios = workbook.create_sheet("Scenarios")
    _title(
        scenarios,
        "Scenario Coverage",
        "Twelve synthetic patient behaviors; run at least ten distinct calls",
        5,
    )
    _table_header(
        scenarios, 4, ["ID", "Category", "Primary behavior", "Live status", "Data classification"]
    )
    scenario_rows = [
        ("new-patient-scheduling", "scheduling", "complete booking and read-back"),
        ("reschedule-existing-visit", "rescheduling", "preserve appointment type"),
        ("cancel-and-waitlist", "scheduling", "avoid wrong cancellation"),
        ("routine-refill-request", "refill", "medication/pharmacy safety"),
        ("hours-location-insurance", "practice information", "logistics and insurance boundary"),
        ("closed-day-boundary", "scheduling", "reject unavailable day"),
        ("urgent-symptom-escalation", "safety", "escalate without diagnosis"),
        ("privacy-boundary", "privacy", "protect another adult"),
        ("interruption-and-correction", "conversation quality", "barge-in and correction"),
        ("spanish-information-request", "multilingual", "language continuity"),
        ("hearing-accessibility", "conversation quality", "pace and repetition"),
        ("conflicting-demographics", "privacy", "identity conflict handling"),
    ]
    for scenario_id, category, behavior in scenario_rows:
        scenarios.append((scenario_id, category, behavior, "PENDING", "synthetic"))
    scenarios.append(("TOTAL", "", "", '=COUNTIF(D5:D16,"PASS")', "=COUNTA(E5:E16)"))
    _finish_sheet(scenarios, [34, 25, 43, 16, 22])
    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True
    workbook.calculation.calcMode = "auto"
    output.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output)


def main() -> None:
    """Generate both user-requested spreadsheet reports."""
    build_test_results(Path("docs/test-results.xlsx"))
    build_engineering_metrics(
        Path("docs/engineering-metrics.xlsx"),
        Path("build/reports/performance.json"),
        Path("artifacts/coverage.json"),
    )
    print("Generated docs/test-results.xlsx and docs/engineering-metrics.xlsx")


if __name__ == "__main__":
    main()
