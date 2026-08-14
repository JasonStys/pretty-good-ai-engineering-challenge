"""Command-line entry point for serving, calling, batching, and validating."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

import uvicorn
from pydantic import ValidationError

from .app import create_app
from .config import Settings
from .errors import VoiceBotError
from .runner import AssessmentRunner
from .scenarios import ScenarioCatalog
from .validation import validation_summary


def build_parser() -> argparse.ArgumentParser:
    """Create the small explicit CLI surface."""
    parser = argparse.ArgumentParser(prog="pgai-voicebot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="serve the Twilio media bridge")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    list_scenarios = subparsers.add_parser("list-scenarios", help="show configured scenarios")
    list_scenarios.add_argument(
        "--scenario-file", type=Path, default=Path("scenarios/default.yaml")
    )

    call = subparsers.add_parser("call", help="run one recorded assessment call")
    call.add_argument("scenario_id")
    call.add_argument("--skip-qa", action="store_true")

    batch = subparsers.add_parser("batch", help="run distinct scenarios sequentially")
    batch.add_argument("--minimum", type=int, default=10)
    batch.add_argument("--skip-qa", action="store_true")

    validate = subparsers.add_parser("validate", help="validate submission artifacts")
    validate.add_argument("--artifact-dir", type=Path, default=Path("artifacts/calls"))
    validate.add_argument("--minimum-calls", type=int, default=10)
    return parser


def configure_logging(level: str) -> None:
    """Enable structured-enough logs without leaking environment values."""
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Execute one command and convert expected failures to stable exit codes."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "list-scenarios":
            catalog = ScenarioCatalog.from_yaml(args.scenario_file)
            for scenario in catalog.all():
                print(f"{scenario.id:32} {scenario.category.value:24} {scenario.title}")
            return 0
        if args.command == "validate":
            summary = validation_summary(args.artifact_dir, args.minimum_calls)
            print(json.dumps(summary, indent=2))
            return 0 if summary["status"] == "pass" else 1

        settings = Settings()  # type: ignore[call-arg]
        configure_logging(settings.log_level)
        if args.command == "serve":
            uvicorn.run(create_app(settings), host=args.host, port=args.port, log_level="info")
            return 0
        runner = AssessmentRunner(settings)
        if args.command == "call":
            manifest = runner.run(args.scenario_id, analyze=not args.skip_qa)
            print(manifest.model_dump_json(indent=2))
            return 0
        manifests = runner.run_batch(minimum=args.minimum, analyze=not args.skip_qa)
        print(json.dumps([manifest.model_dump(mode="json") for manifest in manifests], indent=2))
        return 0
    except (VoiceBotError, ValidationError, OSError, TimeoutError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
