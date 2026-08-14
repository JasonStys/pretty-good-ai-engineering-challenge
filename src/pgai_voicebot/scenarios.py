"""Scenario loading and constant-time lookup."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import yaml
from pydantic import TypeAdapter, ValidationError

from .errors import ConfigurationError, ScenarioNotFoundError
from .models import Scenario

SCENARIO_LIST = TypeAdapter(list[Scenario])


class ScenarioCatalog:
    """Immutable validated scenarios indexed by identifier in expected O(1) time."""

    def __init__(self, scenarios: Iterable[Scenario]) -> None:
        index: dict[str, Scenario] = {}
        for scenario in scenarios:
            if scenario.id in index:
                raise ConfigurationError(f"duplicate scenario id: {scenario.id}")
            index[scenario.id] = scenario
        if len(index) < 10:
            raise ConfigurationError("the challenge requires at least 10 distinct scenarios")
        self._index = index

    @classmethod
    def from_yaml(cls, path: Path) -> ScenarioCatalog:
        """Load a bounded YAML list using the safe parser and strict Pydantic schema."""
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            scenarios = SCENARIO_LIST.validate_python(raw)
        except (OSError, yaml.YAMLError, ValidationError, TypeError) as exc:
            raise ConfigurationError(f"invalid scenario file {path}: {exc}") from exc
        return cls(scenarios)

    def get(self, scenario_id: str) -> Scenario:
        """Return one scenario or a domain-specific missing-scenario error."""
        try:
            return self._index[scenario_id]
        except KeyError as exc:
            raise ScenarioNotFoundError(f"unknown scenario: {scenario_id}") from exc

    def all(self) -> tuple[Scenario, ...]:
        """Return scenarios in source-file insertion order."""
        return tuple(self._index.values())

    def __len__(self) -> int:
        """Return the number of validated scenarios."""
        return len(self._index)
