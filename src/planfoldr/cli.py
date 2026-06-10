"""Command-line entry point: `python -m planfoldr run <scenario.yaml>`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from planfoldr.scenario import ModelSettings, Scenario, load_scenario


def _build_sink(mode: str):
    if mode == "none":
        return None
    from planfoldr.visibility.terminal import TerminalStream
    return TerminalStream().sink


def cmd_run(args: argparse.Namespace) -> int:
    scenario = load_scenario(args.scenario)
    if args.model or args.provider:
        scenario = Scenario(
            name=scenario.name, goal_text=scenario.goal_text, budget=scenario.budget,
            accesses=scenario.accesses, verification_commands=scenario.verification_commands,
            verification_criteria=scenario.verification_criteria, constraints=scenario.constraints,
            model=ModelSettings(
                provider=args.provider or scenario.model.provider,
            name=args.model or scenario.model.name,
            parameter_count=scenario.model.parameter_count,
            cost_per_token=scenario.model.cost_per_token, options=scenario.model.options),
            extra_models=scenario.extra_models,
        )
    from planfoldr.orchestrator import Orchestrator
    web = None
    if args.visibility == "web":
        from planfoldr.visibility.web import VisibilityServer
        web = VisibilityServer(port=args.port)
        web.start()
        print(f"[visibility] streaming log: http://127.0.0.1:{args.port}/   state view: http://127.0.0.1:{args.port}/state")
    sink = web.sink if web is not None else _build_sink(args.visibility)
    orch = Orchestrator(scenario, runs_dir=args.runs_dir, run_id=args.run_id, stream_sink=sink,
                        max_cycles=args.max_cycles, rotate_worker_models=args.rotate_worker_models)
    if web is not None:
        web.attach_run(orch.run_dir)
    result = orch.run()
    print("\n=== RESULT ===")
    print(json.dumps({"status": result.status, "run_dir": result.run_dir, "cycles": result.cycles_run,
                      "tickets": result.tickets, "tokens": result.budget.get("tokens_used")}, indent=2))
    if web is not None and args.hold:
        input("\n[visibility] server running; press Enter to stop...\n")
    return 0 if result.status == "done" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="planfoldr", description="Phase 3/4 dynamic orchestration runtime")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run a scenario YAML end to end")
    run.add_argument("scenario", help="path to scenario.yaml")
    run.add_argument("--model", default=None, help="override the model name")
    run.add_argument("--provider", default=None, choices=["ollama", "stub"], help="override the provider")
    run.add_argument("--runs-dir", default="runs")
    run.add_argument("--run-id", default=None)
    run.add_argument("--max-cycles", type=int, default=40)
    run.add_argument("--rotate-worker-models", action="store_true",
                     help="round-robin extra_models across research/developer executor cycles")
    run.add_argument("--visibility", default="terminal", choices=["terminal", "web", "none"])
    run.add_argument("--port", type=int, default=8765)
    run.add_argument("--hold", action="store_true", help="keep the web server alive after the run")
    run.set_defaults(func=cmd_run)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
