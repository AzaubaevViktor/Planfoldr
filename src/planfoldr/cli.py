"""CLI for running YAML-described Planfoldr scenarios."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable, Optional

from planfoldr.executors import ExecutorRegistry, OllamaModelAdapter, StubModelAdapter
from planfoldr.guards import BudgetTracker, PermissionEngine
from planfoldr.loader import load_scenario
from planfoldr.ollama_policy import (
    OllamaModelCandidate,
    classify_ollama_model,
    eligible_ollama_models,
    list_installed_ollama_models,
    validate_ollama_model_name,
)
from planfoldr.schema import ModelConfig
from planfoldr.trace import new_run_id, run_and_trace


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "run":
        return _run(args)
    if args.command == "ollama-models":
        return _ollama_models(args)
    if args.command == "compare-ollama-models":
        return _compare_ollama_models(args)
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
    subparsers.add_parser("ollama-models", help="list local Ollama models allowed for demo runs")

    compare_parser = subparsers.add_parser(
        "compare-ollama-models",
        help="run one scenario across eligible local Ollama models",
    )
    compare_parser.add_argument("scenario", type=Path, help="root scenario YAML file")
    compare_parser.add_argument("--output-root", type=Path, default=Path("runs"))
    compare_parser.add_argument("--comparison-id", default=None)
    compare_parser.add_argument("--base-dir", type=Path, default=Path.cwd())
    compare_parser.add_argument("--ollama-timeout", type=float, default=180)
    compare_parser.add_argument("--max-models", type=int, default=None)
    compare_parser.add_argument("--model", action="append", default=[], help="specific installed model to try")
    return parser


def _run(args: argparse.Namespace) -> int:
    loaded = load_scenario(args.scenario)
    if args.ollama_model:
        _override_model_name(loaded, args.ollama_model)
    try:
        _validate_loaded_ollama_models(loaded)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

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


def _ollama_models(args: argparse.Namespace) -> int:
    try:
        candidates = list_installed_ollama_models()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print("accepted\tname\tsize\tparameter_b\treason")
    for candidate in candidates:
        status = "yes" if candidate.accepted else "no"
        parameter = "" if candidate.parameter_b is None else f"{candidate.parameter_b:g}"
        print(f"{status}\t{candidate.name}\t{candidate.size}\t{parameter}\t{candidate.reason}")
    return 0


def _compare_ollama_models(args: argparse.Namespace) -> int:
    try:
        installed = list_installed_ollama_models()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    try:
        selected = _select_comparison_models(installed, names=args.model, max_models=args.max_models)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    comparison = _run_model_comparison(
        scenario_path=args.scenario,
        output_root=args.output_root,
        base_dir=args.base_dir,
        comparison_id=args.comparison_id or f"comparison-{new_run_id()}",
        models=selected,
        timeout=args.ollama_timeout,
    )
    print(f"comparison_id={comparison['comparison_id']}")
    print(f"summary={comparison['summary_path']}")
    print(f"report={comparison['report_path']}")
    for item in comparison["results"]:
        print(f"{item['model']}\t{item['status']}\t{item.get('reason') or ''}\t{item['report_path']}")
    return 0 if any(item["status"] == "success" for item in comparison["results"]) else 1


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


def _validate_loaded_ollama_models(loaded) -> None:
    for model in _loaded_models(loaded):
        if model.provider == "ollama":
            validate_ollama_model_name(model.name)


def _loaded_models(loaded) -> list[ModelConfig]:
    models: list[ModelConfig] = []
    if loaded.document.defaults is not None and loaded.document.defaults.model is not None:
        models.append(loaded.document.defaults.model)
    for cycle in loaded.cycles:
        for task in cycle.document.tasks:
            if task.executor.model is not None:
                models.append(task.executor.model)
    return models


def _select_comparison_models(
    installed: list[OllamaModelCandidate],
    *,
    names: list[str],
    max_models: Optional[int],
) -> list[OllamaModelCandidate]:
    by_name = {candidate.name: candidate for candidate in installed}
    if names:
        selected = [by_name.get(name, classify_ollama_model(name=name)) for name in names]
    else:
        selected = eligible_ollama_models(installed)
    skipped = [candidate for candidate in selected if not candidate.accepted]
    if skipped:
        names_text = ", ".join(f"{candidate.name} ({candidate.reason})" for candidate in skipped)
        raise ValueError(f"Refusing models outside the <=12B demo policy: {names_text}")
    if max_models is not None:
        selected = selected[:max_models]
    if not selected:
        raise ValueError("No eligible installed Ollama models found")
    return selected


def _run_model_comparison(
    *,
    scenario_path: Path,
    output_root: Path,
    base_dir: Path,
    comparison_id: str,
    models: list[OllamaModelCandidate],
    timeout: float,
) -> dict:
    scenario_id = load_scenario(scenario_path).document.id
    comparison_dir = output_root / scenario_id / comparison_id
    comparison_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for candidate in models:
        run_id = f"{comparison_id}-{_slug(candidate.name)}"
        loaded = load_scenario(scenario_path)
        _override_model_name(loaded, candidate.name)
        runtime = apply_runtime_context(loaded, output_root=output_root, run_id=run_id)
        registry = ExecutorRegistry(
            permission_engine=PermissionEngine(loaded.document.constraints, base_dir=base_dir),
            budget_tracker=BudgetTracker(loaded.document.budgets),
            prompts=_collect_prompts(loaded),
            model_adapter=OllamaModelAdapter(timeout=timeout),
            prompt_variables=_prompt_variables(loaded.document.inputs, runtime=runtime),
            invalid_output_retries=_invalid_output_retries(loaded),
        )
        run_dir = Path(runtime["run_dir"])
        try:
            result = run_and_trace(loaded, registry, output_root=output_root, run_id=run_id)
            summary = _comparison_run_summary(candidate, run_id=run_id, run_dir=run_dir, result=result)
        except Exception as exc:
            summary = _comparison_error_summary(candidate, run_id=run_id, run_dir=run_dir, exc=exc)
        results.append(summary)
    comparison = {
        "comparison_id": comparison_id,
        "scenario_id": scenario_id,
        "scenario_path": str(scenario_path),
        "policy": {"max_model_gb": 12, "max_parameter_b": 12},
        "summary_path": str(comparison_dir / "model_comparison.json"),
        "report_path": str(comparison_dir / "model_comparison.html"),
        "results": results,
    }
    (comparison_dir / "model_comparison.json").write_text(
        json.dumps(comparison, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (comparison_dir / "model_comparison.html").write_text(_comparison_report_html(comparison), encoding="utf-8")
    return comparison


def _comparison_run_summary(candidate, *, run_id: str, run_dir: Path, result) -> dict:
    generated = run_dir / "workspace" / "project"
    generated_files = _generated_summary_files(generated)
    task_statuses = [
        {"task_id": task.task_id, "status": task.status, "reason": task.reason}
        for task in result.task_results
    ]
    budget = result.task_results[-1].budget_after if result.task_results else {}
    return {
        **candidate.to_dict(),
        "model": candidate.name,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "trace_path": str(run_dir / "trace"),
        "report_path": str(run_dir / "report.html"),
        "status": result.status,
        "reason": result.reason,
        "budget": budget,
        "generated_file_count": len(generated_files),
        "test_file_count": len([path for path in generated_files if path.name.startswith("test_") and path.suffix == ".py"]),
        "has_agents": any(path.name == "AGENTS.md" for path in generated_files),
        "has_architecture": any(path.name == "ARCHITECTURE.md" for path in generated_files),
        "task_statuses": task_statuses,
    }


def _comparison_error_summary(candidate, *, run_id: str, run_dir: Path, exc: Exception) -> dict:
    return {
        **candidate.to_dict(),
        "model": candidate.name,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "trace_path": str(run_dir / "trace"),
        "report_path": str(run_dir / "report.html"),
        "status": "error",
        "reason": f"{type(exc).__name__}: {exc}",
        "budget": {},
        "generated_file_count": 0,
        "test_file_count": 0,
        "has_agents": False,
        "has_architecture": False,
        "task_statuses": [],
    }


def _comparison_report_html(comparison: dict) -> str:
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(item['model'])}</td>"
        f"<td>{html.escape(str(item.get('size') or ''))}</td>"
        f"<td>{html.escape(str(item.get('parameter_b') or ''))}</td>"
        f"<td>{html.escape(item['status'])}</td>"
        f"<td>{html.escape(item.get('reason') or '')}</td>"
        f"<td>{html.escape(str(item.get('generated_file_count', 0)))}</td>"
        f"<td>{html.escape(str(item.get('test_file_count', 0)))}</td>"
        f"<td><a href='../{html.escape(item['run_id'])}/report.html'>report</a></td>"
        f"<td><a href='../{html.escape(item['run_id'])}/trace/report_data.json'>report data</a></td>"
        "</tr>"
        for item in comparison["results"]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Planfoldr Ollama Model Comparison</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; color: #1f2937; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
    th, td {{ border: 1px solid #d1d5db; padding: 0.5rem; text-align: left; vertical-align: top; }}
    th {{ background: #f3f4f6; }}
    code {{ background: #f3f4f6; padding: 0.1rem 0.25rem; }}
  </style>
</head>
<body>
  <h1>Ollama Model Comparison</h1>
  <p>Scenario: <code>{html.escape(comparison['scenario_id'])}</code></p>
  <p>Policy: up to 12B parameters and up to 12 GB installed size for recommended demo runs.</p>
  <p>JSON summary: <code>model_comparison.json</code></p>
  <table>
    <thead>
      <tr><th>Model</th><th>Size</th><th>Parameter B</th><th>Status</th><th>Reason</th><th>Files</th><th>Tests</th><th>Report</th><th>Data</th></tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>
"""


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-").lower()[:80]


def _generated_summary_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    ignored_parts = {".git", ".pytest_cache", "__pycache__"}
    return [
        path
        for path in root.rglob("*")
        if path.is_file() and not any(part in ignored_parts for part in path.relative_to(root).parts)
    ]
