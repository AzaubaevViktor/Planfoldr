"""Structured trace writing, task replay and static HTML reports."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from planfoldr.loader import LoadedScenario
from planfoldr.runtime import ScenarioResult, TaskResult, run_scenario


TRACE_SCHEMA_VERSION = "0.1"


def run_and_trace(
    loaded: LoadedScenario,
    executor,
    *,
    output_root: str | Path = "runs",
    run_id: Optional[str] = None,
) -> ScenarioResult:
    run_id = run_id or new_run_id()
    run_dir = Path(output_root) / loaded.document.id / run_id
    trace_dir = run_dir / "trace"
    report_path = run_dir / "report.html"
    logger = ExecutionLogger(run_dir / "logs" / "execution.log")
    logger.write("run_initialized", scenario_id=loaded.document.id, run_id=run_id)
    logger.write("scenario_start", scenario_id=loaded.document.id, cycle_count=len(loaded.cycles))
    try:
        result = run_scenario(loaded, LoggingExecutor(executor, logger))
    except Exception as exc:
        logger.write("scenario_error", error_type=type(exc).__name__, reason=str(exc))
        raise
    logger.write("scenario_finish", status=result.status, reason=result.reason)
    TraceWriter(
        loaded,
        result,
        trace_dir=trace_dir,
        report_path=report_path,
        run_id=run_id,
        execution_log_path=logger.path,
    ).write()
    return result


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


class ExecutionLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: str, **fields: Any) -> None:
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "event": event,
            **fields,
        }
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")


class LoggingExecutor:
    def __init__(self, executor, logger: ExecutionLogger) -> None:
        self.executor = executor
        self.logger = logger

    def __call__(self, task):
        self.logger.write(
            "task_start",
            task_id=task.id,
            task_type=task.type,
            executor_kind=task.executor.kind,
        )
        try:
            result = self.executor(task)
        except Exception as exc:
            self.logger.write(
                "task_error",
                task_id=task.id,
                error_type=type(exc).__name__,
                reason=str(exc),
            )
            raise
        self.logger.write(
            "task_finish",
            task_id=task.id,
            status=result.status,
            reason=result.reason,
        )
        return result


class TraceWriter:
    def __init__(
        self,
        loaded: LoadedScenario,
        result: ScenarioResult,
        *,
        trace_dir: str | Path,
        report_path: str | Path,
        run_id: Optional[str] = None,
        execution_log_path: Optional[str | Path] = None,
        audit_events: Optional[Iterable[Dict[str, Any]]] = None,
        decisions: Optional[Iterable[Dict[str, Any]]] = None,
    ) -> None:
        self.loaded = loaded
        self.result = result
        self.trace_dir = Path(trace_dir)
        self.report_path = Path(report_path)
        self.run_id = run_id
        self.execution_log_path = Path(execution_log_path) if execution_log_path is not None else None
        self.audit_events = list(audit_events or [])
        self.decisions = list(decisions or [])

    def write(self) -> None:
        self._ensure_dirs()
        self._write_json("manifest.json", self._manifest())
        self._write_json("scenario.json", self.loaded.document.model_dump(mode="json"))
        self._write_json("tasks/executions.json", [task.to_dict() for task in self.result.task_results])
        self._write_json("cycles/index.json", [cycle.to_dict() for cycle in self.result.cycle_results])
        self._write_executor_parts()
        self._write_jsonl("audit.jsonl", self.audit_events)
        self._write_jsonl("decisions.jsonl", self.decisions)
        self._write_report()

    def _ensure_dirs(self) -> None:
        for relative in ("cycles", "tasks", "tools", "models", "commands"):
            (self.trace_dir / relative).mkdir(parents=True, exist_ok=True)
        self.report_path.parent.mkdir(parents=True, exist_ok=True)

    def _manifest(self) -> Dict[str, Any]:
        return {
            "schema_version": TRACE_SCHEMA_VERSION,
            "run_id": self.run_id,
            "scenario_id": self.loaded.document.id,
            "status": self.result.status,
            "reason": self.result.reason,
            "inputs": self.loaded.document.inputs,
            "outputs": self.loaded.document.outputs,
            "cycles": ["cycles/index.json"],
            "task_executions": ["tasks/executions.json"],
            "audit_log": "audit.jsonl",
            "decision_log": "decisions.jsonl",
            "execution_log": self._execution_log_manifest_path(),
            "report_path": str(self.report_path),
        }

    def _execution_log_manifest_path(self) -> Optional[str]:
        if self.execution_log_path is None:
            return None
        try:
            return str(self.execution_log_path.relative_to(self.trace_dir))
        except ValueError:
            try:
                return str(self.execution_log_path.relative_to(self.trace_dir.parent))
            except ValueError:
                return str(self.execution_log_path)

    def _write_executor_parts(self) -> None:
        for task in self.result.task_results:
            executor = task.metadata.get("executor")
            if executor == "model":
                self._write_json(f"models/{task.execution_id}.json", task.metadata)
            elif executor == "command":
                self._write_json(
                    f"commands/{task.execution_id}.json",
                    {"metadata": task.metadata, "output": task.output},
                )
            elif executor == "tool":
                self._write_json(
                    f"tools/{task.execution_id}.json",
                    {"metadata": task.metadata, "output": task.output},
                )

    def _write_json(self, relative: str, value: Any) -> None:
        target = self.trace_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")

    def _write_jsonl(self, relative: str, values: Iterable[Dict[str, Any]]) -> None:
        target = self.trace_dir / relative
        target.write_text(
            "".join(json.dumps(value, sort_keys=True) + "\n" for value in values),
            encoding="utf-8",
        )

    def _write_report(self) -> None:
        rows = "\n".join(
            "<tr>"
            f"<td>{html.escape(task.task_id)}</td>"
            f"<td>{html.escape(task.status)}</td>"
            f"<td>{html.escape(task.reason or '')}</td>"
            "</tr>"
            for task in self.result.task_results
        )
        cycles = "\n".join(
            f"<li><button data-cycle='{html.escape(cycle.cycle_id)}'>{html.escape(cycle.cycle_id)}</button>"
            f" <strong>{html.escape(cycle.status)}</strong></li>"
            for cycle in self.result.cycle_results
        )
        document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Planfoldr Report: {html.escape(self.loaded.document.id)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; color: #1f2937; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
    th, td {{ border: 1px solid #d1d5db; padding: 0.5rem; text-align: left; }}
    th {{ background: #f3f4f6; }}
    code {{ background: #f3f4f6; padding: 0.1rem 0.25rem; }}
  </style>
</head>
<body>
  <h1>{html.escape(self.loaded.document.id)}</h1>
  <p>Status: <strong>{html.escape(self.result.status)}</strong></p>
  <p>Trace manifest: <code>{html.escape(str(self.trace_dir / "manifest.json"))}</code></p>
  <p>Execution log: <code>{html.escape(str(self.execution_log_path or ""))}</code></p>
  <h2>Cycles</h2>
  <ul>{cycles}</ul>
  <h2>Execution Log</h2>
  <label>Filter by task <input id="task-filter" type="search"></label>
  <table id="tasks">
    <thead><tr><th>Task</th><th>Status</th><th>Reason</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <script>
    const filter = document.getElementById('task-filter');
    filter.addEventListener('input', () => {{
      const value = filter.value.toLowerCase();
      document.querySelectorAll('#tasks tbody tr').forEach(row => {{
        row.hidden = !row.cells[0].textContent.toLowerCase().includes(value);
      }});
    }});
  </script>
</body>
</html>
"""
        self.report_path.write_text(document, encoding="utf-8")


def replay_task(trace_dir: str | Path, task_id: str) -> TaskResult:
    executions = json.loads((Path(trace_dir) / "tasks" / "executions.json").read_text(encoding="utf-8"))
    for item in executions:
        if item["task_id"] == task_id:
            return TaskResult(**item)
    raise KeyError(f"No task execution found for '{task_id}'")
