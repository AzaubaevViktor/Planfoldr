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
        result = run_scenario(loaded, LoggingExecutor(executor, logger, trace_dir=trace_dir))
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
    def __init__(self, executor, logger: ExecutionLogger, *, trace_dir: str | Path) -> None:
        self.executor = executor
        self.logger = logger
        self.trace_dir = Path(trace_dir)
        self._streams: Dict[str, Dict[str, Any]] = {}

    def __call__(self, task):
        if hasattr(self.executor, "set_model_progress_callback"):
            self.executor.set_model_progress_callback(self._write_model_progress)
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

    def _write_model_progress(self, event: str, fields: Dict[str, Any]) -> None:
        if event == "model_stream_start":
            self._start_model_stream(fields)
        elif event == "model_stream_chunk":
            self._write_model_stream_chunk(fields)
            return
        elif event in {"model_stream_finish", "model_stream_error"}:
            self._finish_model_stream(fields, event=event)
        self.logger.write(event, **_without_stream_text(fields))

    def _start_model_stream(self, fields: Dict[str, Any]) -> None:
        self._stream_state(fields)

    def _write_model_stream_chunk(self, fields: Dict[str, Any]) -> None:
        state = self._stream_state(fields)
        if state is None:
            return
        text = str(fields.get("text", ""))
        if not text:
            return
        kind = str(fields.get("kind", "content"))
        state["sequence"] += 1
        filename = f"{state['sequence']:06d}.{kind}.txt"
        chunk_path = state["chunks_dir"] / filename
        chunk_path.write_text(text, encoding="utf-8")
        state["stream_parts"].append(text)
        if kind == "content":
            state["content_parts"].append(text)
        elif kind == "thinking":
            state["thinking_parts"].append(text)
        self._append_chunk_index(
            state,
            {
                "sequence": state["sequence"],
                "kind": kind,
                "path": f"chunks/{filename}",
                "chars": len(text),
                "cumulative_chars": fields.get("chars"),
                "content_chars": fields.get("content_chars"),
                "thinking_chars": fields.get("thinking_chars"),
            },
        )

    def _finish_model_stream(self, fields: Dict[str, Any], *, event: str) -> None:
        state = self._stream_state(fields)
        if state is None:
            return
        (state["dir"] / "assembled.txt").write_text("".join(state["stream_parts"]), encoding="utf-8")
        (state["dir"] / "content.txt").write_text("".join(state["content_parts"]), encoding="utf-8")
        (state["dir"] / "thinking.txt").write_text("".join(state["thinking_parts"]), encoding="utf-8")
        manifest = {
            "execution_id": state["execution_id"],
            "task_id": state.get("task_id"),
            "attempt": state.get("attempt"),
            "model": state.get("model"),
            "provider": state.get("provider"),
            "finish_event": event,
            "chunk_count": state["sequence"],
            "chars": fields.get("chars"),
            "content_chars": fields.get("content_chars"),
            "thinking_chars": fields.get("thinking_chars"),
            "tokens": fields.get("tokens"),
            "files": {
                "chunks_index": "chunks/index.jsonl",
                "assembled": "assembled.txt",
                "content": "content.txt",
                "thinking": "thinking.txt",
            },
        }
        (state["dir"] / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _stream_state(self, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        execution_id = fields.get("execution_id")
        if not execution_id:
            return None
        key = str(execution_id)
        if key not in self._streams:
            stream_dir = self.trace_dir / "models" / key
            chunks_dir = stream_dir / "chunks"
            chunks_dir.mkdir(parents=True, exist_ok=True)
            self._streams[key] = {
                "execution_id": key,
                "task_id": fields.get("task_id"),
                "attempt": fields.get("attempt"),
                "model": fields.get("model"),
                "provider": fields.get("provider"),
                "dir": stream_dir,
                "chunks_dir": chunks_dir,
                "sequence": 0,
                "stream_parts": [],
                "content_parts": [],
                "thinking_parts": [],
            }
        return self._streams[key]

    def _append_chunk_index(self, state: Dict[str, Any], row: Dict[str, Any]) -> None:
        with (state["chunks_dir"] / "index.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")


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
                self._write_json(f"models/{task.execution_id}.json", self._model_metadata(task))
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

    def _model_metadata(self, task: TaskResult) -> Dict[str, Any]:
        metadata = dict(task.metadata)
        stream_dir = self.trace_dir / "models" / task.execution_id
        if (stream_dir / "manifest.json").exists():
            metadata["stream_artifacts"] = {
                "directory": f"models/{task.execution_id}",
                "manifest": f"models/{task.execution_id}/manifest.json",
                "chunks_index": f"models/{task.execution_id}/chunks/index.jsonl",
                "assembled": f"models/{task.execution_id}/assembled.txt",
                "content": f"models/{task.execution_id}/content.txt",
                "thinking": f"models/{task.execution_id}/thinking.txt",
            }
        return metadata

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
            f"<td>{html.escape(cycle.cycle_id)}</td>"
            f"<td>{html.escape(task.task_id)}</td>"
            f"<td>{html.escape(task.status)}</td>"
            f"<td>{html.escape(task.reason or '')}</td>"
            "</tr>"
            for cycle in self.result.cycle_results
            for task in cycle.task_results
        )
        cycles = "\n".join(
            f"<li><button data-cycle='{html.escape(cycle.cycle_id)}'>{html.escape(cycle.cycle_id)}</button>"
            f" <strong>{html.escape(cycle.status)}</strong></li>"
            for cycle in self.result.cycle_results
        )
        model_sections = self._model_report_sections()
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
    details {{ border: 1px solid #d1d5db; margin: 1rem 0; padding: 0.75rem; }}
    summary {{ cursor: pointer; font-weight: 600; }}
    pre {{ background: #111827; color: #f9fafb; overflow: auto; padding: 0.75rem; white-space: pre-wrap; }}
    .muted {{ color: #6b7280; }}
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
    <thead><tr><th>Cycle</th><th>Task</th><th>Status</th><th>Reason</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <h2>Model Text</h2>
  {model_sections}
  <script>
    const filter = document.getElementById('task-filter');
    filter.addEventListener('input', () => {{
      const value = filter.value.toLowerCase();
      document.querySelectorAll('#tasks tbody tr').forEach(row => {{
        row.hidden = !row.textContent.toLowerCase().includes(value);
      }});
    }});
  </script>
</body>
</html>
"""
        self.report_path.write_text(document, encoding="utf-8")

    def _model_report_sections(self) -> str:
        sections: List[str] = []
        for task in self.result.task_results:
            if task.metadata.get("executor") != "model":
                continue
            stream_dir = self.trace_dir / "models" / task.execution_id
            content = _read_optional_text(stream_dir / "content.txt")
            thinking = _read_optional_text(stream_dir / "thinking.txt")
            assembled = _read_optional_text(stream_dir / "assembled.txt")
            raw_response = "" if any((content, thinking, assembled)) else str(task.metadata.get("raw_response", ""))
            if not any((content, thinking, assembled, raw_response)):
                continue
            sections.append(
                "<details open>"
                f"<summary>{html.escape(task.task_id)} - {html.escape(task.execution_id)}</summary>"
                f"<p class='muted'>Status: {html.escape(task.status)}</p>"
                f"{_report_pre('Content', content)}"
                f"{_report_pre('Thinking', thinking)}"
                f"{_report_pre('Assembled Stream', assembled)}"
                f"{_report_pre('Raw Response', raw_response)}"
                "</details>"
            )
        if not sections:
            return "<p class='muted'>No model text captured.</p>"
        return "\n".join(sections)


def replay_task(trace_dir: str | Path, task_id: str) -> TaskResult:
    executions = json.loads((Path(trace_dir) / "tasks" / "executions.json").read_text(encoding="utf-8"))
    for item in executions:
        if item["task_id"] == task_id:
            return TaskResult(**item)
    raise KeyError(f"No task execution found for '{task_id}'")


def _without_stream_text(fields: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in fields.items() if key != "text"}


def _read_optional_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _report_pre(title: str, text: str) -> str:
    if not text:
        return ""
    return f"<h3>{html.escape(title)}</h3><pre>{html.escape(text)}</pre>"
