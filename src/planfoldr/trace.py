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
    status_writer = StatusWriter(trace_dir / "status.json", _initial_status(loaded, run_id))
    _write_live_manifest(loaded, trace_dir=trace_dir, report_path=report_path, run_id=run_id, logger=logger)
    _write_live_report_shell(loaded, report_path=report_path, trace_dir=trace_dir, execution_log_path=logger.path)
    logger.write("run_initialized", scenario_id=loaded.document.id, run_id=run_id)
    logger.write("scenario_start", scenario_id=loaded.document.id, cycle_count=len(loaded.cycles))
    try:
        result = run_scenario(
            loaded,
            LoggingExecutor(
                executor,
                logger,
                trace_dir=trace_dir,
                status_writer=status_writer,
                task_cycle_ids=_task_cycle_ids(loaded),
            ),
        )
    except Exception as exc:
        logger.write("scenario_error", error_type=type(exc).__name__, reason=str(exc))
        status_writer.update("scenario_error", status="error", reason=str(exc), current_task_id=None)
        raise
    logger.write("scenario_finish", status=result.status, reason=result.reason)
    status_writer.update("scenario_finish", status=result.status, reason=result.reason, current_task_id=None)
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


class StatusWriter:
    def __init__(self, path: str | Path, initial: Dict[str, Any]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state = dict(initial)
        self._write()

    def update(self, event: str, **fields: Any) -> None:
        work_update = fields.pop("work_update", None)
        budget = fields.pop("budget", None)
        clearable = {"current_task_id", "current_cycle_id", "current_attempt", "reason"}
        self.state.update(
            {
                key: value
                for key, value in fields.items()
                if value is not None or key in clearable
            }
        )
        self.state["last_event"] = event
        self.state["last_event_at"] = _timestamp()
        if budget is not None:
            self.state["budget"] = _budget_with_remaining(budget)
        if work_update is not None:
            self._update_work(work_update)
        self._write()

    def _update_work(self, update: Dict[str, Any]) -> None:
        key = _work_key(update.get("cycle_id"), update.get("task_id"))
        for item in self.state.get("work", []):
            if item.get("key") == key:
                item.update({name: value for name, value in update.items() if value is not None})
                return
        item = {"key": key, **{name: value for name, value in update.items() if value is not None}}
        self.state.setdefault("work", []).append(item)

    def _write(self) -> None:
        self.path.write_text(json.dumps(self.state, indent=2, sort_keys=True), encoding="utf-8")


class LoggingExecutor:
    def __init__(
        self,
        executor,
        logger: ExecutionLogger,
        *,
        trace_dir: str | Path,
        status_writer: Optional[StatusWriter] = None,
        task_cycle_ids: Optional[Dict[str, str]] = None,
    ) -> None:
        self.executor = executor
        self.logger = logger
        self.trace_dir = Path(trace_dir)
        self.status_writer = status_writer
        self.task_cycle_ids = dict(task_cycle_ids or {})
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
        cycle_id = self.task_cycle_ids.get(task.id)
        if self.status_writer is not None:
            self.status_writer.update(
                "task_start",
                status="running",
                current_task_id=task.id,
                current_cycle_id=cycle_id,
                work_update={
                    "task_id": task.id,
                    "cycle_id": cycle_id,
                    "task_type": task.type,
                    "executor_kind": task.executor.kind,
                    "status": "running",
                },
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
            if self.status_writer is not None:
                self.status_writer.update(
                    "task_error",
                    current_task_id=task.id,
                    current_cycle_id=cycle_id,
                    work_update={
                        "task_id": task.id,
                        "cycle_id": cycle_id,
                        "status": "failed",
                        "reason": str(exc),
                    },
                )
            raise
        self.logger.write(
            "task_finish",
            task_id=task.id,
            status=result.status,
            reason=result.reason,
        )
        if self.status_writer is not None:
            self.status_writer.update(
                "task_finish",
                current_task_id=None,
                current_cycle_id=cycle_id,
                budget=result.budget_after,
                work_update={
                    "task_id": task.id,
                    "cycle_id": cycle_id,
                    "execution_id": result.execution_id,
                    "status": _work_status(result.status),
                    "reason": result.reason,
                    "budget_after": result.budget_after,
                },
            )
        return result

    def _write_model_progress(self, event: str, fields: Dict[str, Any]) -> None:
        if event == "model_stream_start":
            self._start_model_stream(fields)
        elif event == "model_stream_chunk":
            self._write_model_stream_chunk(fields)
            self._update_model_status(event, fields)
            return
        elif event in {"model_stream_finish", "model_stream_error"}:
            self._finish_model_stream(fields, event=event)
        self._update_model_status(event, fields)
        self.logger.write(event, **_without_stream_text(fields))

    def _update_model_status(self, event: str, fields: Dict[str, Any]) -> None:
        if self.status_writer is not None:
            self.status_writer.update(
                event,
                current_task_id=fields.get("task_id"),
                current_cycle_id=self.task_cycle_ids.get(str(fields.get("task_id"))),
                current_attempt=fields.get("attempt"),
                stream={
                    "execution_id": fields.get("execution_id"),
                    "chars": fields.get("chars"),
                    "content_chars": fields.get("content_chars"),
                    "thinking_chars": fields.get("thinking_chars"),
                    "tokens": fields.get("tokens"),
                },
            )

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
        self._write_json("scenario.json", self.loaded.document.model_dump(mode="json"))
        self._write_json("tasks/executions.json", [task.to_dict() for task in self.result.task_results])
        self._write_json("cycles/index.json", [cycle.to_dict() for cycle in self.result.cycle_results])
        self._write_executor_parts()
        self._write_jsonl("audit.jsonl", self.audit_events)
        self._write_jsonl("decisions.jsonl", self.decisions)
        self._write_final_status()
        self._write_json("artifacts.json", self._artifact_index())
        self._write_json("manifest.json", self._manifest())
        self._write_report()

    def _ensure_dirs(self) -> None:
        for relative in ("cycles", "tasks", "tools", "models", "commands", "inputs"):
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
            "status_file": "status.json",
            "artifact_index": "artifacts.json",
            "report_data": {
                "manifest": "trace/manifest.json",
                "status": "trace/status.json",
                "artifacts": "trace/artifacts.json",
                "scenario": "trace/scenario.json",
                "cycles": "trace/cycles/index.json",
                "task_executions": "trace/tasks/executions.json",
                "execution_log": _run_relative_path(self.trace_dir, self.execution_log_path),
            },
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
            self._write_json(f"inputs/{task.execution_id}.json", self._task_input_artifact(task))
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

    def _task_input_artifact(self, task: TaskResult) -> Dict[str, Any]:
        executor = task.metadata.get("executor", "unknown")
        artifact: Dict[str, Any] = {
            "task_id": task.task_id,
            "execution_id": task.execution_id,
            "executor": executor,
            "declared_input": task.input,
            "request": task.request,
        }
        if executor == "model":
            prompt = task.metadata.get("prompt", {})
            rendered_prompt = str(prompt.get("rendered_prompt", ""))
            artifact.update(
                {
                    "model": task.metadata.get("model"),
                    "prompt": prompt,
                    "messages": [{"role": "user", "content": rendered_prompt}] if rendered_prompt else [],
                    "config": {
                        "prompt_id": prompt.get("prompt_id"),
                        "attempt": task.metadata.get("attempt"),
                    },
                    "tools": [],
                }
            )
        elif executor == "command":
            artifact.update(
                {
                    "command": task.metadata.get("command"),
                    "cwd": task.metadata.get("cwd"),
                    "env": {"PATH": "<inherited>"},
                    "stdin": None,
                }
            )
        elif executor == "tool":
            artifact.update(
                {
                    "tool": task.metadata.get("tool"),
                    "parameters": task.input or task.output,
                }
            )
        return _redact_secrets(artifact)

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

    def _write_final_status(self) -> None:
        status_path = self.trace_dir / "status.json"
        if status_path.exists():
            status = json.loads(status_path.read_text(encoding="utf-8"))
        else:
            status = _initial_status(self.loaded, self.run_id or "")
        status.update(
            {
                "status": self.result.status,
                "reason": self.result.reason,
                "current_task_id": None,
                "current_cycle_id": None,
                "current_attempt": None,
                "last_event": "scenario_finish",
                "last_event_at": _timestamp(),
            }
        )
        if self.result.task_results:
            status["budget"] = _budget_with_remaining(self.result.task_results[-1].budget_after)
        work_by_key = {
            item.get("key"): dict(item)
            for item in status.get("work", [])
        }
        for cycle in self.result.cycle_results:
            for task in cycle.task_results:
                key = _work_key(cycle.cycle_id, task.task_id)
                work_by_key[key] = {
                    "key": key,
                    "cycle_id": cycle.cycle_id,
                    "task_id": task.task_id,
                    "execution_id": task.execution_id,
                    "status": _work_status(task.status),
                    "reason": task.reason,
                    "budget_after": task.budget_after,
                }
        status["work"] = list(work_by_key.values())
        self._write_json("status.json", status)

    def _artifact_index(self) -> Dict[str, Any]:
        artifacts: List[Dict[str, str]] = []
        run_dir = self.trace_dir.parent
        if self.execution_log_path is not None and self.execution_log_path.exists():
            artifacts.append({"kind": "execution_log", "path": str(self.execution_log_path.relative_to(run_dir))})
        for path in sorted(self.trace_dir.rglob("*")):
            if path.is_file():
                artifacts.append({"kind": _artifact_kind(path), "path": str(path.relative_to(run_dir))})
        return {
            "schema_version": TRACE_SCHEMA_VERSION,
            "generated_at": _timestamp(),
            "run_id": self.run_id,
            "artifacts": artifacts,
        }

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
        input_sections = self._input_report_sections()
        status_snapshot = _read_json_optional(self.trace_dir / "status.json")
        manifest_snapshot = self._manifest()
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
    .toolbar {{ display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; margin: 1rem 0; }}
    .status-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr)); gap: 0.75rem; }}
    .metric {{ border: 1px solid #d1d5db; padding: 0.75rem; }}
    button {{ cursor: pointer; }}
  </style>
</head>
<body>
  <h1>{html.escape(self.loaded.document.id)}</h1>
  <div class="toolbar">
    <button id="refresh-report" type="button">Refresh Report Data</button>
    <span class="muted">Snapshot loaded at <span id="snapshot-loaded-at">{html.escape(_timestamp())}</span></span>
  </div>
  <p>Status: <strong>{html.escape(self.result.status)}</strong></p>
  <p>Trace manifest: <code>{html.escape(str(self.trace_dir / "manifest.json"))}</code></p>
  <p>Execution log: <code>{html.escape(str(self.execution_log_path or ""))}</code></p>
  <h2>Live Status</h2>
  <div id="live-status">{_status_html(status_snapshot)}</div>
  <h2>Cycles</h2>
  <ul>{cycles}</ul>
  <h2>Task Executions</h2>
  <label>Filter by task <input id="task-filter" type="search"></label>
  <table id="tasks">
    <thead><tr><th>Cycle</th><th>Task</th><th>Status</th><th>Reason</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <h2>Task Inputs</h2>
  {input_sections}
  <h2>Model Text</h2>
  {model_sections}
  <h2>Execution Log</h2>
  <pre id="execution-log">{html.escape(_read_optional_text(self.execution_log_path) if self.execution_log_path is not None else "")}</pre>
  <script id="report-snapshot" type="application/json">{html.escape(json.dumps({"manifest": manifest_snapshot, "status": status_snapshot}, sort_keys=True))}</script>
  <script>
    const snapshot = JSON.parse(document.getElementById('report-snapshot').textContent);
    const filter = document.getElementById('task-filter');
    filter.addEventListener('input', () => {{
      const value = filter.value.toLowerCase();
      document.querySelectorAll('#tasks tbody tr').forEach(row => {{
        row.hidden = !row.textContent.toLowerCase().includes(value);
      }});
    }});
    async function readJson(path) {{
      const response = await fetch(path + '?t=' + Date.now());
      if (!response.ok) throw new Error(response.statusText);
      return await response.json();
    }}
    async function readText(path) {{
      const response = await fetch(path + '?t=' + Date.now());
      if (!response.ok) throw new Error(response.statusText);
      return await response.text();
    }}
    function escapeHtml(value) {{
      return String(value ?? '').replace(/[&<>"']/g, char => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[char]));
    }}
    function renderStatus(status) {{
      const budget = status.budget || {{}};
      const usage = budget.usage || {{}};
      const remaining = budget.remaining || {{}};
      document.getElementById('live-status').innerHTML = `
        <div class="status-grid">
          <div class="metric"><strong>Status</strong><br>${{escapeHtml(status.status)}}</div>
          <div class="metric"><strong>Current Task</strong><br>${{escapeHtml(status.current_cycle_id || '')}} / ${{escapeHtml(status.current_task_id || '')}}</div>
          <div class="metric"><strong>Attempt</strong><br>${{escapeHtml(status.current_attempt || '')}}</div>
          <div class="metric"><strong>Last Event</strong><br>${{escapeHtml(status.last_event || '')}}<br><span class="muted">${{escapeHtml(status.last_event_at || '')}}</span></div>
        </div>
        <pre>${{escapeHtml(JSON.stringify({{usage, remaining}}, null, 2))}}</pre>
      `;
    }}
    async function refreshReport() {{
      let manifest = snapshot.manifest;
      try {{ manifest = await readJson('trace/manifest.json'); }} catch (error) {{}}
      const data = manifest.report_data || {{}};
      try {{
        const status = await readJson(data.status || 'trace/status.json');
        renderStatus(status);
        document.getElementById('snapshot-loaded-at').textContent = new Date().toISOString();
      }} catch (error) {{}}
      if (data.execution_log) {{
        try {{
          document.getElementById('execution-log').textContent = await readText(data.execution_log);
        }} catch (error) {{}}
      }}
    }}
    document.getElementById('refresh-report').addEventListener('click', refreshReport);
    if ((snapshot.status || {{}}).status === 'running') {{
      setInterval(refreshReport, 3000);
    }}
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

    def _input_report_sections(self) -> str:
        sections: List[str] = []
        for task in self.result.task_results:
            path = self.trace_dir / "inputs" / f"{task.execution_id}.json"
            payload = _read_optional_text(path)
            if not payload:
                continue
            sections.append(
                "<details>"
                f"<summary>{html.escape(task.task_id)} - {html.escape(task.execution_id)}</summary>"
                f"{_report_pre('Input Artifact', payload)}"
                "</details>"
            )
        if not sections:
            return "<p class='muted'>No task inputs captured.</p>"
        return "\n".join(sections)


def replay_task(trace_dir: str | Path, task_id: str) -> TaskResult:
    executions = json.loads((Path(trace_dir) / "tasks" / "executions.json").read_text(encoding="utf-8"))
    for item in executions:
        if item["task_id"] == task_id:
            return TaskResult(**item)
    raise KeyError(f"No task execution found for '{task_id}'")


def _without_stream_text(fields: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in fields.items() if key != "text"}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _task_cycle_ids(loaded: LoadedScenario) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for cycle in loaded.cycles:
        for task in cycle.document.tasks:
            mapping.setdefault(task.id, cycle.document.id)
    return mapping


def _work_key(cycle_id: Any, task_id: Any) -> str:
    return f"{cycle_id or 'unknown'}:{task_id or 'unknown'}"


def _initial_status(loaded: LoadedScenario, run_id: str) -> Dict[str, Any]:
    work = []
    for cycle in loaded.cycles:
        for task in cycle.document.tasks:
            work.append(
                {
                    "key": _work_key(cycle.document.id, task.id),
                    "cycle_id": cycle.document.id,
                    "task_id": task.id,
                    "task_type": task.type,
                    "executor_kind": task.executor.kind,
                    "status": "queued",
                }
            )
    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "run_id": run_id,
        "scenario_id": loaded.document.id,
        "status": "running",
        "reason": None,
        "current_task_id": None,
        "current_cycle_id": None,
        "current_attempt": None,
        "last_event": "run_initialized",
        "last_event_at": _timestamp(),
        "budget": _budget_with_remaining(
            {
                "configured": loaded.document.budgets.model_dump(mode="json"),
                "usage": {
                    "iterations": 0,
                    "tool_calls": 0,
                    "model_calls": 0,
                    "model_budget": 0.0,
                    "cpu_time": 0.0,
                },
                "ram_enforcement": "unsupported" if loaded.document.budgets.max_ram is not None else None,
            }
        ),
        "work": work,
    }


def _budget_with_remaining(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    configured = dict(snapshot.get("configured") or {})
    usage = dict(snapshot.get("usage") or {})
    remaining: Dict[str, Any] = {}
    pairs = {
        "max_iterations": "iterations",
        "max_tool_calls": "tool_calls",
        "max_model_calls": "model_calls",
        "max_model_budget": "model_budget",
        "max_cpu_time": "cpu_time",
    }
    for limit, used_key in pairs.items():
        maximum = configured.get(limit)
        used = usage.get(used_key, 0)
        remaining[limit] = None if maximum is None else max(0, maximum - used)
    return {
        "configured": configured,
        "usage": usage,
        "remaining": remaining,
        "ram_enforcement": snapshot.get("ram_enforcement"),
    }


def _work_status(status: str) -> str:
    if status == "budget_exceeded":
        return "budget_exhausted"
    if status in {"success", "failure"}:
        return "succeeded" if status == "success" else "failed"
    return status


def _write_live_manifest(
    loaded: LoadedScenario,
    *,
    trace_dir: Path,
    report_path: Path,
    run_id: str,
    logger: ExecutionLogger,
) -> None:
    trace_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": TRACE_SCHEMA_VERSION,
        "run_id": run_id,
        "scenario_id": loaded.document.id,
        "status": "running",
        "reason": None,
        "inputs": loaded.document.inputs,
        "outputs": loaded.document.outputs,
        "status_file": "status.json",
        "artifact_index": "artifacts.json",
        "execution_log": _run_relative_path(trace_dir, logger.path),
        "report_data": {
            "manifest": "trace/manifest.json",
            "status": "trace/status.json",
            "artifacts": "trace/artifacts.json",
            "scenario": "trace/scenario.json",
            "cycles": "trace/cycles/index.json",
            "task_executions": "trace/tasks/executions.json",
            "execution_log": _run_relative_path(trace_dir, logger.path),
        },
        "report_path": str(report_path),
    }
    (trace_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    (trace_dir / "artifacts.json").write_text(
        json.dumps(
            {
                "schema_version": TRACE_SCHEMA_VERSION,
                "generated_at": _timestamp(),
                "run_id": run_id,
                "artifacts": [
                    {"kind": "manifest", "path": "trace/manifest.json"},
                    {"kind": "status", "path": "trace/status.json"},
                    {"kind": "execution_log", "path": _run_relative_path(trace_dir, logger.path)},
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _write_live_report_shell(
    loaded: LoadedScenario,
    *,
    report_path: Path,
    trace_dir: Path,
    execution_log_path: Path,
) -> None:
    status = _read_json_optional(trace_dir / "status.json")
    manifest = _read_json_optional(trace_dir / "manifest.json")
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Planfoldr Report: {html.escape(loaded.document.id)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; color: #1f2937; }}
    pre {{ background: #111827; color: #f9fafb; overflow: auto; padding: 0.75rem; white-space: pre-wrap; }}
    .muted {{ color: #6b7280; }}
    .status-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr)); gap: 0.75rem; }}
    .metric {{ border: 1px solid #d1d5db; padding: 0.75rem; }}
  </style>
</head>
<body>
  <h1>{html.escape(loaded.document.id)}</h1>
  <button id="refresh-report" type="button">Refresh Report Data</button>
  <p class="muted">This report is live. Final task, input and model sections appear as trace files are written.</p>
  <h2>Live Status</h2>
  <div id="live-status">{_status_html(status)}</div>
  <h2>Execution Log</h2>
  <pre id="execution-log">{html.escape(_read_optional_text(execution_log_path))}</pre>
  <script id="report-snapshot" type="application/json">{_script_json({"manifest": manifest, "status": status})}</script>
  <script>
    const snapshot = JSON.parse(document.getElementById('report-snapshot').textContent);
    async function readJson(path) {{
      const response = await fetch(path + '?t=' + Date.now());
      if (!response.ok) throw new Error(response.statusText);
      return await response.json();
    }}
    async function readText(path) {{
      const response = await fetch(path + '?t=' + Date.now());
      if (!response.ok) throw new Error(response.statusText);
      return await response.text();
    }}
    function escapeHtml(value) {{
      return String(value ?? '').replace(/[&<>"']/g, char => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[char]));
    }}
    function renderStatus(status) {{
      const budget = status.budget || {{}};
      const usage = budget.usage || {{}};
      const remaining = budget.remaining || {{}};
      document.getElementById('live-status').innerHTML = `
        <div class="status-grid">
          <div class="metric"><strong>Status</strong><br>${{escapeHtml(status.status)}}</div>
          <div class="metric"><strong>Current Task</strong><br>${{escapeHtml(status.current_cycle_id || '')}} / ${{escapeHtml(status.current_task_id || '')}}</div>
          <div class="metric"><strong>Attempt</strong><br>${{escapeHtml(status.current_attempt || '')}}</div>
          <div class="metric"><strong>Last Event</strong><br>${{escapeHtml(status.last_event || '')}}<br><span class="muted">${{escapeHtml(status.last_event_at || '')}}</span></div>
        </div>
        <pre>${{escapeHtml(JSON.stringify({{usage, remaining}}, null, 2))}}</pre>
      `;
    }}
    async function refreshReport() {{
      let manifest = snapshot.manifest;
      try {{ manifest = await readJson('trace/manifest.json'); }} catch (error) {{}}
      const data = (manifest || {{}}).report_data || {{}};
      try {{ renderStatus(await readJson(data.status || 'trace/status.json')); }} catch (error) {{}}
      try {{ document.getElementById('execution-log').textContent = await readText(data.execution_log || 'logs/execution.log'); }} catch (error) {{}}
    }}
    document.getElementById('refresh-report').addEventListener('click', refreshReport);
    setInterval(refreshReport, 3000);
  </script>
</body>
</html>
"""
    report_path.write_text(document, encoding="utf-8")


def _read_optional_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _read_json_optional(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _report_pre(title: str, text: str) -> str:
    if not text:
        return ""
    return f"<h3>{html.escape(title)}</h3><pre>{html.escape(text)}</pre>"


def _status_html(status: Dict[str, Any]) -> str:
    budget = status.get("budget", {})
    current_cycle = status.get("current_cycle_id") or ""
    current_task = status.get("current_task_id") or ""
    current_attempt = status.get("current_attempt") or ""
    return (
        "<div class='status-grid'>"
        f"<div class='metric'><strong>Status</strong><br>{html.escape(str(status.get('status', 'unknown')))}</div>"
        f"<div class='metric'><strong>Current Task</strong><br>{html.escape(str(current_cycle))} / {html.escape(str(current_task))}</div>"
        f"<div class='metric'><strong>Attempt</strong><br>{html.escape(str(current_attempt))}</div>"
        f"<div class='metric'><strong>Last Event</strong><br>{html.escape(str(status.get('last_event', '')))}"
        f"<br><span class='muted'>{html.escape(str(status.get('last_event_at', '')))}</span></div>"
        "</div>"
        f"{_report_pre('Budget', json.dumps({'usage': budget.get('usage', {}), 'remaining': budget.get('remaining', {})}, indent=2, sort_keys=True))}"
    )


def _run_relative_path(trace_dir: Path, path: Optional[Path]) -> Optional[str]:
    if path is None:
        return None
    try:
        return str(path.relative_to(trace_dir.parent))
    except ValueError:
        return str(path)


def _artifact_kind(path: Path) -> str:
    parent = path.parent.name
    if path.name == "status.json":
        return "status"
    if path.name == "manifest.json":
        return "manifest"
    if parent == "inputs":
        return "task_input"
    if parent == "models" or "models" in path.parts:
        return "model"
    if parent == "commands":
        return "command"
    if parent == "tools":
        return "tool"
    if parent == "tasks":
        return "task_execution"
    if parent == "cycles":
        return "cycle"
    return "trace"


def _redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if any(marker in str(key).lower() for marker in ("secret", "token", "password", "api_key", "apikey")):
                redacted[key] = "<redacted>"
            else:
                redacted[key] = _redact_secrets(item)
        return redacted
    if isinstance(value, list):
        return [_redact_secrets(item) for item in value]
    return value


def _script_json(value: Any) -> str:
    return html.escape(json.dumps(value, sort_keys=True).replace("</", "<\\/"))
