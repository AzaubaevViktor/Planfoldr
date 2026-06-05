"""CLI for running YAML-described Planfoldr scenarios."""

from __future__ import annotations

import argparse
import os
import sys
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
    runtime = apply_runtime_context(loaded, output_root=args.output_root, run_id=run_id)
    registry = ExecutorRegistry(
        permission_engine=PermissionEngine(loaded.document.constraints, base_dir=args.base_dir),
        budget_tracker=BudgetTracker(loaded.document.budgets),
        prompts=_collect_prompts(loaded),
        model_adapter=_select_model_adapter(loaded, timeout=args.ollama_timeout),
        prompt_variables=_prompt_variables(loaded.document.inputs, runtime=runtime),
        invalid_output_retries=_invalid_output_retries(loaded),
    )
    result = run_and_trace(loaded, registry, output_root=args.output_root, run_id=run_id)
    run_dir = Path(runtime["run_dir"])
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


def apply_runtime_context(loaded, *, output_root: str | Path, run_id: str) -> dict:
    runtime = _runtime_context(
        scenario_id=loaded.document.id,
        output_root=output_root,
        run_id=run_id,
    )
    loaded.document.inputs = _render_runtime_inputs(loaded.document.inputs, runtime=runtime)
    loaded.document.outputs = _render_runtime_inputs(loaded.document.outputs, runtime=runtime)
    _render_runtime_constraints(loaded.document.constraints, runtime=runtime)
    for cycle in loaded.cycles:
        _render_runtime_cycle(cycle, runtime=runtime)
    return runtime


def _runtime_context(*, scenario_id: str, output_root: str | Path, run_id: str) -> dict:
    run_dir = Path(output_root) / scenario_id / run_id
    workspace_dir = run_dir / "workspace"
    return {
        "python": sys.executable,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "workspace_dir": str(workspace_dir),
    }


def _prompt_variables(inputs: dict, *, runtime: Optional[dict] = None, run_id: str = "") -> dict:
    runtime = runtime or {
        "python": sys.executable,
        "run_id": run_id,
        "run_dir": "",
        "workspace_dir": "",
    }
    return {
        "inputs": inputs,
        "runtime": runtime,
        "runtime.python": runtime["python"],
        "runtime.run_id": runtime["run_id"],
        "runtime.run_dir": runtime["run_dir"],
        "runtime.workspace_dir": runtime["workspace_dir"],
        **{f"inputs.{key}": value for key, value in inputs.items()},
    }


def _render_runtime_inputs(inputs: dict, *, runtime: Optional[dict] = None, run_id: str = "") -> dict:
    runtime = runtime or {
        "python": sys.executable,
        "run_id": run_id,
        "run_dir": "",
        "workspace_dir": "",
    }
    runtime_values = {
        "{{ runtime.python }}": runtime["python"],
        "{{ runtime.run_id }}": runtime["run_id"],
        "{{ runtime.run_dir }}": runtime["run_dir"],
        "{{ runtime.workspace_dir }}": runtime["workspace_dir"],
    }
    return {
        key: _replace_runtime_placeholders(value, runtime_values)
        for key, value in inputs.items()
    }


def _render_runtime_constraints(constraints, *, runtime: dict) -> None:
    if constraints is None or constraints.filesystem is None:
        return
    constraints.filesystem.allow_read = _render_runtime_list(constraints.filesystem.allow_read, runtime=runtime)
    constraints.filesystem.allow_write = _render_runtime_list(constraints.filesystem.allow_write, runtime=runtime)


def _render_runtime_cycle(cycle, *, runtime: dict) -> None:
    _render_runtime_constraints(cycle.document.constraints, runtime=runtime)
    for task in cycle.document.tasks:
        _render_runtime_constraints(task.executor.constraints, runtime=runtime)
    for nested in cycle.nested_cycles:
        _render_runtime_cycle(nested, runtime=runtime)


def _render_runtime_list(values: list[str], *, runtime: dict) -> list[str]:
    return [
        _replace_runtime_placeholders(
            value,
            {
                "{{ runtime.python }}": runtime["python"],
                "{{ runtime.run_id }}": runtime["run_id"],
                "{{ runtime.run_dir }}": runtime["run_dir"],
                "{{ runtime.workspace_dir }}": runtime["workspace_dir"],
            },
        )
        for value in values
    ]


def _replace_runtime_placeholders(value, runtime_values: dict):
    if isinstance(value, str):
        rendered = value
        for placeholder, replacement in runtime_values.items():
            rendered = rendered.replace(placeholder, replacement)
        return rendered
    if isinstance(value, dict):
        return {key: _replace_runtime_placeholders(item, runtime_values) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_runtime_placeholders(item, runtime_values) for item in value]
    return value


def _override_model_name(loaded, model_name: str) -> None:
    for cycle in loaded.cycles:
        for task in cycle.document.tasks:
            if task.executor.model is not None:
                task.executor.model.name = model_name
