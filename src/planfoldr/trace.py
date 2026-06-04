"""Structured trace writing, task replay and static HTML reports."""

from __future__ import annotations

import html
import json
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
) -> ScenarioResult:
    result = run_scenario(loaded, executor)
    trace_dir = Path(output_root) / loaded.document.id / "trace"
    report_path = Path(output_root) / loaded.document.id / "report.html"
    TraceWriter(loaded, result, trace_dir=trace_dir, report_path=report_path).write()
    return result


class TraceWriter:
    def __init__(
        self,
        loaded: LoadedScenario,
        result: ScenarioResult,
        *,
        trace_dir: str | Path,
        report_path: str | Path,
        audit_events: Optional[Iterable[Dict[str, Any]]] = None,
        decisions: Optional[Iterable[Dict[str, Any]]] = None,
    ) -> None:
        self.loaded = loaded
        self.result = result
        self.trace_dir = Path(trace_dir)
        self.report_path = Path(report_path)
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
            "scenario_id": self.loaded.document.id,
            "status": self.result.status,
            "reason": self.result.reason,
            "inputs": self.loaded.document.inputs,
            "outputs": self.loaded.document.outputs,
            "cycles": ["cycles/index.json"],
            "task_executions": ["tasks/executions.json"],
            "audit_log": "audit.jsonl",
            "decision_log": "decisions.jsonl",
            "report_path": str(self.report_path),
        }

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
