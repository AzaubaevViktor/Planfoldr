"""CLI for running YAML-described Planfoldr scenarios."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable, Optional

from planfoldr.executors import ExecutorRegistry, OllamaModelAdapter, StubModelAdapter
from planfoldr.guards import BudgetTracker, PermissionEngine
from planfoldr.loader import load_scenario
from planfoldr.schema import ModelConfig
from planfoldr.trace import new_run_id, run_and_trace


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "run":
        return _run(args)
    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="planfoldr")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="run a YAML scenario")
    run_parser.add_argument("scenario", type=Path, help="root scenario YAML file")
    run_parser.add_argument("--output-root", type=Path, default=Path("runs"))
    run_parser.add_argument("--run-id", default=None)
    run_parser.add_argument("--base-dir", type=Path, default=Path.cwd())
    run_parser.add_argument("--ollama-model", default=os.environ.get("PLANFOLDR_OLLAMA_MODEL"))
    run_parser.add_argument(
        "--ollama-timeout",
        type=float,
        default=float(os.environ.get("PLANFOLDR_OLLAMA_TIMEOUT", "30")),
    )
    return parser


def _run(args: argparse.Namespace) -> int:
    loaded = load_scenario(args.scenario)
    if args.ollama_model:
        _override_model_name(loaded, args.ollama_model)

    run_id = args.run_id or new_run_id()
    registry = ExecutorRegistry(
        permission_engine=PermissionEngine(loaded.document.constraints, base_dir=args.base_dir),
        budget_tracker=BudgetTracker(loaded.document.budgets),
        prompts=_collect_prompts(loaded),
        model_adapter=_select_model_adapter(loaded, timeout=args.ollama_timeout),
        prompt_variables=_prompt_variables(loaded.document.inputs),
        invalid_output_retries=_invalid_output_retries(loaded),
    )
    result = run_and_trace(loaded, registry, output_root=args.output_root, run_id=run_id)
    run_dir = args.output_root / loaded.document.id / run_id
    print(f"scenario={loaded.document.id}")
    print(f"status={result.status}")
    print(f"run_dir={run_dir}")
    print(f"execution_log={run_dir / 'logs' / 'execution.log'}")
    print(f"report={run_dir / 'report.html'}")
    return 0 if result.status == "success" else 1


def _collect_prompts(loaded) -> dict:
    prompts = {}
    for cycle in loaded.cycles:
        prompts.update(cycle.prompts)
    return prompts


def _select_model_adapter(loaded, *, timeout: float):
    model = _default_model(loaded)
    if model is not None and model.provider == "ollama":
        return OllamaModelAdapter(timeout=timeout)
    return StubModelAdapter({"*": {"status": "success"}})


def _default_model(loaded) -> Optional[ModelConfig]:
    if loaded.document.defaults is not None and loaded.document.defaults.model is not None:
        return loaded.document.defaults.model
    for cycle in loaded.cycles:
        for task in cycle.document.tasks:
            if task.executor.model is not None:
                return task.executor.model
    return None


def _invalid_output_retries(loaded) -> int:
    defaults = loaded.document.defaults
    if defaults is None or defaults.retry is None:
        return 0
    return defaults.retry.invalid_output


def _prompt_variables(inputs: dict) -> dict:
    return {"inputs": inputs, **{f"inputs.{key}": value for key, value in inputs.items()}}


def _override_model_name(loaded, model_name: str) -> None:
    for cycle in loaded.cycles:
        for task in cycle.document.tasks:
            if task.executor.model is not None:
                task.executor.model.name = model_name
