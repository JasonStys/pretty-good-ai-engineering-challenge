"""Scenario schema, coverage, and prompt tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from pgai_voicebot.errors import ConfigurationError, ScenarioNotFoundError
from pgai_voicebot.models import Scenario
from pgai_voicebot.prompting import build_patient_prompt
from pgai_voicebot.scenarios import ScenarioCatalog


def test_catalog_has_diverse_minimum_coverage(catalog: ScenarioCatalog) -> None:
    scenarios = catalog.all()
    assert len(scenarios) == 12
    assert len({scenario.category for scenario in scenarios}) >= 8
    assert catalog.get("new-patient-scheduling").language == "en"


def test_prompt_contains_safety_and_scenario_content(catalog: ScenarioCatalog) -> None:
    scenario = catalog.get("urgent-symptom-escalation")
    prompt = build_patient_prompt(scenario)
    assert "synthetic" in prompt.lower()
    assert "Do not provide medical advice" in prompt
    assert scenario.objective in prompt
    assert "New chest pressure" in prompt


def test_missing_scenario_has_domain_error(catalog: ScenarioCatalog) -> None:
    with pytest.raises(ScenarioNotFoundError):
        catalog.get("missing")


def test_catalog_rejects_duplicates(catalog: ScenarioCatalog) -> None:
    scenario = catalog.all()[0]
    with pytest.raises(ConfigurationError, match="duplicate"):
        ScenarioCatalog([scenario, scenario, *catalog.all()[1:]])


def test_catalog_rejects_too_few_scenarios(catalog: ScenarioCatalog) -> None:
    with pytest.raises(ConfigurationError, match="at least 10"):
        ScenarioCatalog(catalog.all()[:9])


def test_yaml_errors_are_wrapped(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text("- not: [valid", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="invalid scenario file"):
        ScenarioCatalog.from_yaml(path)


def test_scenario_requires_synthetic_marker(catalog: ScenarioCatalog) -> None:
    payload = catalog.all()[0].model_dump()
    payload["synthetic_facts"]["data_classification"] = "real"
    with pytest.raises(ValueError, match="synthetic"):
        Scenario.model_validate(payload)
