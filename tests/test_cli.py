"""Command-line routing and stable exit-code tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pgai_voicebot import cli
from pgai_voicebot.config import Settings
from pgai_voicebot.errors import VoiceBotError
from pgai_voicebot.models import CallManifest


def test_parser_defaults() -> None:
    """Operational defaults remain explicit and conservative."""
    args = cli.build_parser().parse_args(["serve"])
    assert (args.host, args.port) == ("127.0.0.1", 8000)


def test_list_scenarios(capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario discovery does not require credentials."""
    assert cli.main(["list-scenarios"]) == 0
    output = capsys.readouterr().out
    assert "new-patient-scheduling" in output
    assert "urgent-symptom-escalation" in output


def test_validate_exit_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Artifact validation exposes pass and fail as process exit codes."""
    monkeypatch.setattr(cli, "validation_summary", lambda *_: {"status": "pass"})
    assert cli.main(["validate"]) == 0
    monkeypatch.setattr(cli, "validation_summary", lambda *_: {"status": "fail"})
    assert cli.main(["validate"]) == 1


def test_serve_routes_to_uvicorn(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve constructs the app with the requested bind parameters."""
    called: dict[str, object] = {}
    monkeypatch.setattr(cli, "Settings", lambda: settings)
    monkeypatch.setattr(cli, "create_app", lambda value: value)
    monkeypatch.setattr(
        cli.uvicorn,
        "run",
        lambda app, **kwargs: called.update({"app": app, **kwargs}),
    )
    assert cli.main(["serve", "--host", "127.0.0.1", "--port", "9000"]) == 0
    assert called == {"app": settings, "host": "127.0.0.1", "port": 9000, "log_level": "info"}


def test_call_and_batch_route_to_runner(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Call commands preserve the QA option and print JSON manifests."""
    manifest = CallManifest(
        run_id="run-1",
        scenario_id="scenario-1",
        caller_number="+15555550123",
        destination_number="+18054398008",
    )
    calls: list[tuple[str, object, bool]] = []

    class FakeRunner:
        def __init__(self, value: Settings) -> None:
            assert value is settings

        def run(self, scenario_id: str, *, analyze: bool) -> CallManifest:
            calls.append(("call", scenario_id, analyze))
            return manifest

        def run_batch(self, *, minimum: int, analyze: bool) -> list[CallManifest]:
            calls.append(("batch", minimum, analyze))
            return [manifest]

    monkeypatch.setattr(cli, "Settings", lambda: settings)
    monkeypatch.setattr(cli, "AssessmentRunner", FakeRunner)
    assert cli.main(["call", "scenario-1", "--skip-qa"]) == 0
    assert cli.main(["batch", "--minimum", "10"]) == 0
    assert calls == [("call", "scenario-1", False), ("batch", 10, True)]


def test_expected_errors_return_two(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Expected operational failures do not produce an uncontrolled traceback."""
    monkeypatch.setattr(cli, "Settings", lambda: settings)
    monkeypatch.setattr(
        cli,
        "AssessmentRunner",
        lambda _settings: SimpleNamespace(
            run=lambda *_args, **_kwargs: (_ for _ in ()).throw(VoiceBotError("bounded"))
        ),
    )
    assert cli.main(["call", "scenario-1"]) == 2
    assert "error: bounded" in capsys.readouterr().err
