"""Structured trace writing, task replay and static HTML reports."""

from __future__ import annotations

import html
import json
import difflib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from planfoldr.loader import LoadedScenario
from planfoldr.runtime import ScenarioResult, TaskResult, run_scenario


TRACE_SCHEMA_VERSION = "0.1"
LONG_JSON_STRING_THRESHOLD = 1000


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

    def refresh_live_report() -> None:
        _write_live_report_data(loaded, trace_dir=trace_dir, run_id=run_id, logger=logger)
        _write_live_report_shell(loaded, report_path=report_path, trace_dir=trace_dir, execution_log_path=logger.path)

    status_writer.after_write = refresh_live_report
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
        _write_live_report_data(loaded, trace_dir=trace_dir, run_id=run_id, logger=logger)
        _write_live_report_shell(loaded, report_path=report_path, trace_dir=trace_dir, execution_log_path=logger.path)
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
        self.after_write = None
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
        if self.after_write is not None:
            self.after_write()


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
        self._active_tasks: Dict[str, Any] = {}

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
        self._active_tasks[task.id] = task
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
            self._active_tasks.pop(task.id, None)
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
        self._active_tasks.pop(task.id, None)
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
            task_id = fields.get("task_id")
            cycle_id = self.task_cycle_ids.get(str(task_id))
            live_artifacts = {}
            if event == "model_stream_start":
                live_artifacts = self._write_live_model_task_artifacts(fields)
            self.status_writer.update(
                event,
                current_task_id=task_id,
                current_cycle_id=cycle_id,
                current_attempt=fields.get("attempt"),
                stream={
                    "execution_id": fields.get("execution_id"),
                    "chars": fields.get("chars"),
                    "content_chars": fields.get("content_chars"),
                    "thinking_chars": fields.get("thinking_chars"),
                    "tokens": fields.get("tokens"),
                },
                work_update={
                    "task_id": task_id,
                    "cycle_id": cycle_id,
                    "executor_kind": "model",
                    "status": "running" if event != "model_stream_error" else "failed",
                    "execution_id": fields.get("execution_id"),
                    **live_artifacts,
                },
            )

    def _write_live_model_task_artifacts(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        task_id = str(fields.get("task_id") or "")
        execution_id = str(fields.get("execution_id") or "")
        task = self._active_tasks.get(task_id)
        if not task_id or not execution_id or task is None:
            return {}
        cycle_id = self.task_cycle_ids.get(task_id)
        base = f"live/tasks/{_safe_trace_segment(task.type)}/{execution_id}"
        source = {
            "cycle_id": cycle_id,
            "cycle_path": cycle_id,
            "task_id": task_id,
            "execution_id": execution_id,
            "executor": "model",
            "task_artifact_dir": f"trace/{base}",
            "executor_artifact_dir": f"trace/models/{_safe_trace_segment(str(fields.get('model') or 'unknown_model'))}/{execution_id}",
        }
        started_at = _timestamp()
        status = {
            "task_id": task_id,
            "execution_id": execution_id,
            "cycle_id": cycle_id,
            "cycle_path": cycle_id,
            "task_type": task.type,
            "executor": "model",
            "status": "running",
            "reason": None,
            "started_at": started_at,
            "finished_at": None,
        }
        context = _redact_secrets(
            {
                "task_id": task_id,
                "execution_id": execution_id,
                "cycle_id": cycle_id,
                "cycle_path": cycle_id,
                "task_type": task.type,
                "task": task.task,
                "input_schema": task.input_schema,
                "output_schema": task.output_schema,
                "source": source,
            }
        )
        input_payload = fields.get("input")
        if not isinstance(input_payload, dict):
            input_payload = {
                "task_id": task_id,
                "execution_id": execution_id,
                "executor": "model",
                "declared_input": {},
                "request": None,
                "model": {"provider": fields.get("provider"), "name": fields.get("model")},
                "messages": [],
                "config": {"attempt": fields.get("attempt")},
                "tools": [],
            }
        self._write_live_json(f"{base}/source.json", source)
        self._write_live_json(f"{base}/status.json", status)
        self._write_live_json(f"{base}/context.json", context)
        self._write_live_json(f"{base}/input.json", _redact_secrets(input_payload))
        return {
            "source": source,
            "source_artifact": f"trace/{base}/source.json",
            "status_artifact": f"trace/{base}/status.json",
            "context_artifact": f"trace/{base}/context.json",
            "input_artifact": f"trace/{base}/input.json",
        }

    def _write_live_json(self, relative: str, value: Any) -> None:
        target = self.trace_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")

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
        state["stream_parts"].append(text)
        if kind == "content":
            state["content_parts"].append(text)
        elif kind == "thinking":
            state["thinking_parts"].append(text)
        self._append_stream_row(
            state,
            {
                "sequence": state["sequence"],
                "kind": kind,
                "text": text,
                "chars": len(text),
                "cumulative_chars": fields.get("chars"),
                "content_chars": fields.get("content_chars"),
                "thinking_chars": fields.get("thinking_chars"),
                "tokens": fields.get("tokens"),
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
                "stream": "stream.jsonl",
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
            stream_dir.mkdir(parents=True, exist_ok=True)
            self._streams[key] = {
                "execution_id": key,
                "task_id": fields.get("task_id"),
                "attempt": fields.get("attempt"),
                "model": fields.get("model"),
                "provider": fields.get("provider"),
                "dir": stream_dir,
                "sequence": 0,
                "stream_parts": [],
                "content_parts": [],
                "thinking_parts": [],
            }
        return self._streams[key]

    def _append_stream_row(self, state: Dict[str, Any], row: Dict[str, Any]) -> None:
        with (state["dir"] / "stream.jsonl").open("a", encoding="utf-8") as stream:
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
        self.task_types = _task_types(loaded)

    def write(self) -> None:
        self._ensure_dirs()
        self._write_json("scenario_definition.json", self.loaded.document.model_dump(mode="json"))
        self._write_json("scenario.json", self._scenario_trace())
        self._write_json("tasks/executions.json", self._task_execution_records())
        self._write_json("cycles/index.json", [cycle.to_dict() for cycle in self.result.cycle_results])
        self._write_cycle_parts()
        self._write_task_parts()
        self._write_executor_parts()
        self._write_jsonl("audit.jsonl", self.audit_events)
        self._write_jsonl("decisions.jsonl", self.decisions)
        self._write_final_status()
        self._write_json("artifacts.json", self._artifact_index())
        self._write_json("report_data.json", self._report_data_snapshot())
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
            "cycles": ["cycles/index.json", *self._cycle_artifact_paths()],
            "task_executions": ["tasks/executions.json"],
            "audit_log": "audit.jsonl",
            "decision_log": "decisions.jsonl",
            "execution_log": self._execution_log_manifest_path(),
            "status_file": "status.json",
            "scenario_definition": "scenario_definition.json",
            "artifact_index": "artifacts.json",
            "report_data_file": "report_data.json",
            "report_data": {
                "manifest": "trace/manifest.json",
                "status": "trace/status.json",
                "artifacts": "trace/artifacts.json",
                "report_snapshot": "trace/report_data.json",
                "scenario": "trace/scenario.json",
                "scenario_definition": "trace/scenario_definition.json",
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

    def _scenario_trace(self) -> Dict[str, Any]:
        return {
            "schema_version": TRACE_SCHEMA_VERSION,
            "run_id": self.run_id,
            "scenario_id": self.loaded.document.id,
            "goal": self.loaded.document.goal,
            "status": self.result.status,
            "reason": self.result.reason,
            "cycle_count": len(self.result.cycle_results),
            "task_count": len(self.result.task_results),
            "cycles": [
                {
                    "cycle_id": cycle.cycle_id,
                    "cycle_path": cycle.cycle_path or cycle.cycle_id,
                    "status": cycle.status,
                    "reason": cycle.reason,
                    "artifact": self._cycle_artifact_path(cycle),
                    "task_count": len(cycle.task_results),
                }
                for cycle in self.result.cycle_results
            ],
            "definition": "scenario_definition.json",
            "status_file": "status.json",
            "manifest": "manifest.json",
        }

    def _write_executor_parts(self) -> None:
        for task in self.result.task_results:
            self._write_json(f"inputs/{task.execution_id}.json", self._task_input_artifact(task))
            executor = task.metadata.get("executor")
            if executor == "model":
                self._write_model_raw_response(task)
                self._write_json(f"models/{task.execution_id}.json", self._model_metadata(task))
                self._write_executor_directory_parts(task)
            elif executor == "command":
                self._write_json(
                    f"commands/{task.execution_id}.json",
                    {"metadata": task.metadata, "output": task.output},
                )
                self._write_executor_directory_parts(task)
            elif executor == "tool":
                self._write_json(
                    f"tools/{task.execution_id}.json",
                    {"metadata": task.metadata, "output": task.output},
                )
                self._write_executor_directory_parts(task)

    def _write_executor_directory_parts(self, task: TaskResult) -> None:
        base = self._executor_artifact_dir(task)
        if base is None:
            return
        self._write_json(
            f"{base}/status.json",
            {
                "task_id": task.task_id,
                "execution_id": task.execution_id,
                "executor": task.metadata.get("executor", "unknown"),
                "status": task.status,
                "reason": task.reason,
                "started_at": task.started_at,
                "finished_at": task.finished_at,
                "budget_before": task.budget_before,
                "budget_after": task.budget_after,
            },
        )
        self._write_json(f"{base}/input.json", self._task_input_artifact(task))
        self._write_json(
            f"{base}/context.json",
            _redact_secrets(
                {
                    "task_id": task.task_id,
                    "execution_id": task.execution_id,
                    "request": task.request,
                    "metadata": _model_metadata_without_raw_response(task)
                    if task.metadata.get("executor") == "model"
                    else task.metadata,
                    "artifacts": task.artifacts,
                    "evidence": task.evidence,
                }
            ),
        )
        self._write_json(
            f"{base}/output.json",
            {
                "task_id": task.task_id,
                "execution_id": task.execution_id,
                "status": task.status,
                "reason": task.reason,
                "output": task.output,
            },
        )
        if task.metadata.get("executor") == "model":
            self._copy_model_text_artifacts(task, base)

    def _copy_model_text_artifacts(self, task: TaskResult, base: str) -> None:
        legacy_dir = self.trace_dir / "models" / task.execution_id
        target_dir = self.trace_dir / base
        for name in ("stream.jsonl", "assembled.txt", "content.txt", "thinking.txt", "raw_response.txt"):
            text = _read_optional_text(legacy_dir / name)
            if text:
                target = target_dir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")

    def _write_task_parts(self) -> None:
        for cycle in self.result.cycle_results:
            cycle_path = cycle.cycle_path or cycle.cycle_id
            for task in cycle.task_results:
                task_type = self._task_type(cycle.cycle_id, task.task_id)
                base = self._task_artifact_dir(cycle.cycle_id, task.task_id, task.execution_id)
                self._write_json(
                    f"{base}/status.json",
                    {
                        "task_id": task.task_id,
                        "execution_id": task.execution_id,
                        "cycle_id": cycle.cycle_id,
                        "cycle_path": cycle_path,
                        "task_type": task_type,
                        "executor": task.metadata.get("executor", "unknown"),
                        "status": task.status,
                        "reason": task.reason,
                        "started_at": task.started_at,
                        "finished_at": task.finished_at,
                        "budget_before": task.budget_before,
                        "budget_after": task.budget_after,
                    },
                )
                self._write_json(f"{base}/input.json", self._task_input_artifact(task))
                self._write_json(
                    f"{base}/context.json",
                    _redact_secrets(
                        {
                            "task_id": task.task_id,
                            "execution_id": task.execution_id,
                            "cycle_id": cycle.cycle_id,
                            "cycle_path": cycle_path,
                            "task_type": task_type,
                            "request": task.request,
                            "budget_before": task.budget_before,
                            "budget_after": task.budget_after,
                            "audit_events": task.audit_events,
                            "artifacts": task.artifacts,
                            "evidence": task.evidence,
                        }
                    ),
                )
                self._write_json(
                    f"{base}/output.json",
                    {
                        "task_id": task.task_id,
                        "execution_id": task.execution_id,
                        "status": task.status,
                        "reason": task.reason,
                        "output": task.output,
                        "evidence": task.evidence,
                        "artifacts": task.artifacts,
                    },
                )

    def _write_cycle_parts(self) -> None:
        for cycle in self.result.cycle_results:
            cycle_path = cycle.cycle_path or cycle.cycle_id
            task_summaries = []
            for task in cycle.task_results:
                task_summaries.append(
                    {
                        "task_id": task.task_id,
                        "execution_id": task.execution_id,
                        "task_type": self._task_type(cycle.cycle_id, task.task_id),
                        "executor": task.metadata.get("executor", "unknown"),
                        "status": task.status,
                        "reason": task.reason,
                        "artifact_dir": self._task_artifact_dir(cycle.cycle_id, task.task_id, task.execution_id),
                    }
                )
            self._write_json(
                self._cycle_artifact_path(cycle),
                {
                    "cycle_id": cycle.cycle_id,
                    "cycle_path": cycle_path,
                    "status": cycle.status,
                    "reason": cycle.reason,
                    "request": cycle.request,
                    "task_count": len(cycle.task_results),
                    "tasks": task_summaries,
                },
            )

    def _task_execution_records(self) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        for cycle in self.result.cycle_results:
            cycle_path = cycle.cycle_path or cycle.cycle_id
            for task in cycle.task_results:
                record = task.to_dict()
                if task.metadata.get("executor") == "model":
                    record["metadata"] = _model_metadata_without_raw_response(task)
                record["cycle_id"] = cycle.cycle_id
                record["cycle_path"] = cycle_path
                record["task_type"] = self._task_type(cycle.cycle_id, task.task_id)
                record["task_artifact_dir"] = f"trace/{self._task_artifact_dir(cycle.cycle_id, task.task_id, task.execution_id)}"
                executor_dir = self._executor_artifact_dir(task)
                record["executor_artifact_dir"] = f"trace/{executor_dir}" if executor_dir else None
                records.append(record)
        return records

    def _task_artifact_dir(self, cycle_id: str, task_id: str, execution_id: str) -> str:
        task_type = self._task_type(cycle_id, task_id)
        return f"tasks/{_safe_trace_segment(task_type)}/{execution_id}"

    def _executor_artifact_dir(self, task: TaskResult) -> Optional[str]:
        executor = task.metadata.get("executor")
        if executor == "model":
            model = task.metadata.get("model", {})
            model_name = str(model.get("name") or "unknown_model") if isinstance(model, dict) else "unknown_model"
            return f"models/{_safe_trace_segment(model_name)}/{task.execution_id}"
        if executor == "tool":
            tool_name = str(task.metadata.get("tool") or "unknown_tool")
            return f"tools/{_safe_trace_segment(tool_name)}/{task.execution_id}"
        if executor == "command":
            command = str(task.metadata.get("command") or "unknown_command")
            return f"commands/{_safe_trace_segment(command[:80])}/{task.execution_id}"
        return None

    def _task_type(self, cycle_id: str, task_id: str) -> str:
        return self.task_types.get((cycle_id, task_id)) or self.task_types.get(("", task_id)) or "unknown"

    def _cycle_artifact_paths(self) -> List[str]:
        return [self._cycle_artifact_path(cycle) for cycle in self.result.cycle_results]

    def _cycle_artifact_path(self, cycle: CycleResult) -> str:
        cycle_path = cycle.cycle_path or cycle.cycle_id
        return f"cycles/{_safe_trace_segment(cycle_path)}.json"

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
        metadata = _model_metadata_without_raw_response(task)
        stream_dir = self.trace_dir / "models" / task.execution_id
        if (stream_dir / "manifest.json").exists():
            metadata["stream_artifacts"] = {
                "directory": f"models/{task.execution_id}",
                "manifest": f"models/{task.execution_id}/manifest.json",
                "stream": f"models/{task.execution_id}/stream.jsonl",
                "assembled": f"models/{task.execution_id}/assembled.txt",
                "content": f"models/{task.execution_id}/content.txt",
                "thinking": f"models/{task.execution_id}/thinking.txt",
            }
        return metadata

    def _write_model_raw_response(self, task: TaskResult) -> None:
        raw_response = task.metadata.get("raw_response")
        if not isinstance(raw_response, str) or not raw_response:
            return
        target = self.trace_dir / _raw_response_artifact_path(task.execution_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(raw_response, encoding="utf-8")

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
        report_data_path = "trace/report_data.json"
        if not any(item["path"] == report_data_path for item in artifacts):
            artifacts.append({"kind": "report_data", "path": report_data_path})
        return {
            "schema_version": TRACE_SCHEMA_VERSION,
            "generated_at": _timestamp(),
            "run_id": self.run_id,
            "artifacts": artifacts,
        }

    def _report_data_snapshot(self) -> Dict[str, Any]:
        task_records = self._task_execution_records()
        return {
            "schema_version": TRACE_SCHEMA_VERSION,
            "generated_at": _timestamp(),
            "run_id": self.run_id,
            "scenario_id": self.loaded.document.id,
            "status": _read_json_optional(self.trace_dir / "status.json"),
            "artifacts": _read_json_optional(self.trace_dir / "artifacts.json").get("artifacts", []),
            "scenario": _read_json_optional(self.trace_dir / "scenario.json"),
            "cycles": [cycle.to_dict() for cycle in self.result.cycle_results],
            "cycle_artifacts": [
                {
                    "cycle_id": cycle.cycle_id,
                    "cycle_path": cycle.cycle_path or cycle.cycle_id,
                    "path": f"trace/{self._cycle_artifact_path(cycle)}",
                }
                for cycle in self.result.cycle_results
            ],
            "task_executions": task_records,
            "task_inputs": [
                {
                    "cycle_id": task.get("cycle_id"),
                    "cycle_path": task.get("cycle_path"),
                    "task_id": task.get("task_id"),
                    "execution_id": task.get("execution_id"),
                    "task_artifact_dir": "trace/"
                    + self._task_artifact_dir(
                        str(task.get("cycle_id")),
                        str(task.get("task_id")),
                        str(task.get("execution_id")),
                    ),
                    "executor_artifact_dir": (
                        f"trace/{executor_dir}" if (executor_dir := self._executor_artifact_dir_from_record(task)) else None
                    ),
                    "path": f"trace/inputs/{task.get('execution_id')}.json",
                }
                for task in task_records
            ],
            "model_outputs": [
                {
                    "cycle_id": task.get("cycle_id"),
                    "cycle_path": task.get("cycle_path"),
                    "task_id": task.get("task_id"),
                    "execution_id": task.get("execution_id"),
                    "model_artifact_dir": (
                        f"trace/{executor_dir}" if (executor_dir := self._executor_artifact_dir_from_record(task)) else None
                    ),
                    "stream": f"trace/models/{task.get('execution_id')}/stream.jsonl",
                    "assembled": f"trace/models/{task.get('execution_id')}/assembled.txt",
                    "content": f"trace/models/{task.get('execution_id')}/content.txt",
                    "thinking": f"trace/models/{task.get('execution_id')}/thinking.txt",
                    "raw_response": f"trace/{metadata.get('raw_response_artifact')}"
                    if (metadata := task.get("metadata", {})).get("raw_response_artifact")
                    else None,
                    "raw_response_chars": metadata.get("raw_response_chars"),
                    "raw_response_lines": metadata.get("raw_response_lines"),
                    "retry_feedback": metadata.get("retry_feedback"),
                }
                for task in task_records
                if task.get("metadata", {}).get("executor") == "model"
            ],
            "execution_log": _run_relative_path(self.trace_dir, self.execution_log_path),
        }

    def _executor_artifact_dir_from_record(self, task: Dict[str, Any]) -> Optional[str]:
        metadata = task.get("metadata", {})
        if not isinstance(metadata, dict):
            return None
        pseudo_task = TaskResult(
            task_id=str(task.get("task_id") or ""),
            execution_id=str(task.get("execution_id") or ""),
            status=str(task.get("status") or ""),
            metadata=metadata,
        )
        return self._executor_artifact_dir(pseudo_task)

    def _write_json(self, relative: str, value: Any) -> None:
        _write_json_with_long_artifacts(self.trace_dir, relative, value)

    def _write_jsonl(self, relative: str, values: Iterable[Dict[str, Any]]) -> None:
        target = self.trace_dir / relative
        target.write_text(
            "".join(json.dumps(value, sort_keys=True) + "\n" for value in values),
            encoding="utf-8",
        )

    def _write_report(self) -> None:
        status_snapshot = _read_json_optional(self.trace_dir / "status.json")
        document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Planfoldr Report: {html.escape(self.loaded.document.id)}</title>
  <style>
{_report_styles()}
    .result-success {{ color: #166534; }}
    .result-failure, .result-error {{ color: #991b1b; }}
    .diff {{ font-weight: 600; }}
  </style>
</head>
<body>
  <main class="flow">
    <h1>Starting <code>{html.escape(self.loaded.document.id)}</code></h1>
    <details>
      <summary>additional info</summary>
      <p>Status: <strong>{html.escape(self.result.status)}</strong></p>
      <p>Trace manifest: <code>{html.escape(str(self.trace_dir / "manifest.json"))}</code></p>
      <p>Execution log: <code>{html.escape(str(self.execution_log_path or ""))}</code></p>
      {_report_pre('status.json', json.dumps(status_snapshot, indent=2, sort_keys=True))}
    </details>
    <section id="execution-flow">{self._execution_flow_html()}</section>
  </main>
</body>
</html>
"""
        self.report_path.write_text(document, encoding="utf-8")

    def _execution_flow_html(self) -> str:
        blocks: List[str] = []
        previous_cycle: Optional[str] = None
        for cycle in self.result.cycle_results:
            cycle_path = cycle.cycle_path or cycle.cycle_id
            if previous_cycle is not None and previous_cycle != cycle_path:
                blocks.append(
                    "<p class='line muted'>"
                    f"{html.escape(_cycle_transition_text(previous_cycle, cycle_path))}"
                    "</p>"
                )
            previous_cycle = cycle_path
            for index, task in enumerate(cycle.task_results):
                blocks.append(self._task_flow_block_html(cycle, task, index))
        if not blocks:
            return "<p class='muted'>No task executions captured.</p>"
        return "\n".join(blocks)

    def _task_flow_block_html(self, cycle: CycleResult, task: TaskResult, index: int) -> str:
        result_class = "result-success" if task.status == "success" else "result-failure"
        reason = f" ({task.reason})" if task.reason else ""
        retry_feedback = task.metadata.get("retry_feedback")
        retry_html = ""
        if isinstance(retry_feedback, dict):
            retry_html = (
                "<p class='line'>"
                f"retry {html.escape(str(retry_feedback.get('failed_attempt')))}"
                f"/{html.escape(str(retry_feedback.get('max_attempts')))} with additional message to model"
                "</p>"
                "<details><summary>additional info</summary>"
                f"{_report_pre('Retry Feedback', json.dumps(retry_feedback, indent=2, sort_keys=True))}"
                "</details>"
            )
        diff_html = _short_diff_summary_html(task.output.get("diff_summary"))
        diff_line = f"<p class='line diff'>{diff_html}</p>" if diff_html else ""
        return (
            "<article class='task'>"
            f"<p class='line'>{html.escape(_task_flow_text(cycle, index))}</p>"
            f"<p class='line'>{html.escape(_task_summary_text(task))}</p>"
            f"{self._task_process_detail_html(cycle, task)}"
            f"<p class='line {result_class}'>result: {html.escape(task.status)}{html.escape(reason)}</p>"
            f"{diff_line}"
            f"{self._task_diff_detail_html(task)}"
            f"{retry_html}"
            "</article>"
        )

    def _task_process_detail_html(self, cycle: CycleResult, task: TaskResult) -> str:
        base = self._task_artifact_dir(cycle.cycle_id, task.task_id, task.execution_id)
        files = [
            ("Status", "status.json"),
            ("Context", "context.json"),
            ("Input", "input.json"),
            ("Output", "output.json"),
        ]
        links = " ".join(
            f"<a href='trace/{html.escape(base)}/{name}'>{html.escape(label)}</a>"
            for label, name in files
        )
        model_text = self._task_model_text_html(task)
        context_text = _read_optional_text(self.trace_dir / base / "context.json")
        input_text = _read_optional_text(self.trace_dir / base / "input.json")
        output_text = _read_optional_text(self.trace_dir / base / "output.json")
        status_text = _read_optional_text(self.trace_dir / base / "status.json")
        original_context = _loads_json_object(context_text)
        updated_context = _updated_task_context(original_context, task)
        source = _task_source_payload(
            cycle,
            task,
            task_artifact_dir=f"trace/{base}",
            executor_artifact_dir=_executor_artifact_dir_for_task(task),
        )
        budget_spent_html = _report_pre("Budget Spent", json.dumps(_budget_spent(task.budget_before, task.budget_after), indent=2, sort_keys=True))
        budget_remaining_html = _report_pre("Budget Remaining", json.dumps((task.budget_after or {}).get("remaining", {}), indent=2, sort_keys=True))
        duration_html = _report_pre("Duration", json.dumps(_task_duration(task), indent=2, sort_keys=True))
        if task.metadata.get("executor") == "model":
            return (
                f"<p>{links}</p>"
                f"{_report_pre('Source', json.dumps(source, indent=2, sort_keys=True))}"
                f"{_report_pre('Context', context_text)}"
                f"{_report_pre('Input', input_text)}"
                f"{model_text}"
                f"{_report_pre('Final Output', output_text)}"
                f"{_report_detail('updated context', _report_json('Updated Context', updated_context))}"
                f"{_report_detail('context diff', _report_pre('Context Diff', _json_diff(original_context, updated_context)))}"
                f"{_report_detail('status', _report_pre('Status', status_text))}"
                f"{budget_spent_html}"
                f"{budget_remaining_html}"
                f"{duration_html}"
            )
        return (
            "<details>"
            "<summary>additional info</summary>"
            f"<p>{links}</p>"
            f"{_report_pre('Source', json.dumps(source, indent=2, sort_keys=True))}"
            f"{_report_pre('Context', context_text)}"
            f"{_report_pre('Input', input_text)}"
            f"{model_text}"
            f"{_report_pre('Final Output', output_text)}"
            f"{_report_detail('updated context', _report_json('Updated Context', updated_context))}"
            f"{_report_detail('context diff', _report_pre('Context Diff', _json_diff(original_context, updated_context)))}"
            f"{_report_detail('status', _report_pre('Status', status_text))}"
            f"{budget_spent_html}"
            f"{budget_remaining_html}"
            f"{duration_html}"
            "</details>"
        )

    def _task_diff_detail_html(self, task: TaskResult) -> str:
        details = _file_changes_html(task.output.get("file_changes"), task.output.get("diff_summary"))
        if not details:
            return ""
        return f"<details><summary>additional info</summary>{details}</details>"

    def _task_model_text_html(self, task: TaskResult) -> str:
        if task.metadata.get("executor") != "model":
            return ""
        stream_dir = self.trace_dir / "models" / task.execution_id
        content = _read_optional_text(stream_dir / "content.txt")
        thinking = _read_optional_text(stream_dir / "thinking.txt")
        assembled = _read_optional_text(stream_dir / "assembled.txt")
        raw_response = (
            ""
            if any((content, thinking, assembled))
            else _raw_response_report_text(
                _read_model_raw_response(self.trace_dir, task),
                artifact=f"trace/{_raw_response_artifact_path(task.execution_id)}",
            )
        )
        retry_feedback = task.metadata.get("retry_feedback")
        retry_feedback_text = (
            json.dumps(retry_feedback, indent=2, sort_keys=True)
            if isinstance(retry_feedback, dict)
            else ""
        )
        if not any((content, thinking, assembled, raw_response, retry_feedback_text)):
            return ""
        return (
            _report_pre("Retry Feedback", retry_feedback_text)
            + (_report_detail("thinking", _report_pre("Thinking", thinking)) if thinking else "")
            + _report_pre("Content", content or raw_response)
        )

    def _request_route_html(self, cycle: CycleResult, task: TaskResult) -> str:
        executor_dir = self._executor_artifact_dir(task)
        route = {
            "source": {
                "cycle_id": cycle.cycle_id,
                "cycle_path": cycle.cycle_path or cycle.cycle_id,
                "task_id": task.task_id,
            },
            "destination": {
                "executor": task.metadata.get("executor", "unknown"),
                "artifact_dir": f"trace/{executor_dir}" if executor_dir else None,
            },
        }
        return _report_pre("Source", json.dumps(route, indent=2, sort_keys=True))

def replay_task(trace_dir: str | Path, task_id: str) -> TaskResult:
    trace_path = Path(trace_dir)
    executions = json.loads((trace_path / "tasks" / "executions.json").read_text(encoding="utf-8"))
    task_fields = set(TaskResult.__dataclass_fields__)
    for item in executions:
        if item["task_id"] == task_id:
            resolved = _resolve_extracted_artifact_refs(item, trace_path)
            return TaskResult(**{key: value for key, value in resolved.items() if key in task_fields})
    raise KeyError(f"No task execution found for '{task_id}'")


def _without_stream_text(fields: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in fields.items() if key != "text"}


def _task_flow_text(cycle: CycleResult, index: int) -> str:
    tasks = cycle.task_results
    previous_task = tasks[index - 1].task_id if index > 0 else "start"
    current_task = tasks[index].task_id if 0 <= index < len(tasks) else "unknown"
    next_task = tasks[index + 1].task_id if index + 1 < len(tasks) else "finish"
    return f"{cycle.cycle_path or cycle.cycle_id}: {previous_task} -> [{current_task}] -> {next_task}"


def _task_flow_line_html(
    cycle_id: Any,
    previous_task: Any,
    current_task: Any,
    next_task: Any,
    *,
    is_active_level: bool = True,
    is_active_task: bool = False,
) -> str:
    level_class = "task-level-current" if is_active_level else "task-level-muted"
    current_text = html.escape(str(current_task))
    current_html = f"<strong>{current_text}</strong>" if is_active_task else current_text
    return (
        f"<p class='line {level_class}'>"
        f"{html.escape(str(cycle_id))}: {html.escape(str(previous_task))} -&gt; "
        f"[{current_html}] -&gt; {html.escape(str(next_task))}"
        "</p>"
    )


def _cycle_transition_text(previous_cycle: str, cycle_path: str) -> str:
    if cycle_path.startswith(f"{previous_cycle}/"):
        return f"cycle down from {previous_cycle} to {cycle_path}"
    if previous_cycle.startswith(f"{cycle_path}/"):
        return f"cycle up from {previous_cycle} to {cycle_path}"
    return f"cycle down from {previous_cycle} to {cycle_path}"


def _task_summary_text(task: TaskResult) -> str:
    executor = task.metadata.get("executor")
    if executor == "command":
        command = str(task.metadata.get("command") or "")
        cwd = str(task.metadata.get("cwd") or ".")
        return f"command: {command} in {cwd}"
    if executor == "model":
        model = task.metadata.get("model", {})
        model_name = str(model.get("name") or "unknown_model") if isinstance(model, dict) else "unknown_model"
        prompt = task.metadata.get("prompt", {})
        prompt_id = str(prompt.get("prompt_id") or task.task_id) if isinstance(prompt, dict) else task.task_id
        retry_feedback = task.metadata.get("retry_feedback")
        retry = ""
        if isinstance(retry_feedback, dict):
            retry = f" retry {retry_feedback.get('failed_attempt')}/{retry_feedback.get('max_attempts')}"
        return f"model: {model_name} goal {prompt_id}{retry}"
    if executor == "tool":
        return f"tool: {task.metadata.get('tool') or 'unknown_tool'}"
    return f"task: {task.task_id}"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _task_cycle_ids(loaded: LoadedScenario) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for cycle in loaded.cycles:
        for task in cycle.document.tasks:
            mapping.setdefault(task.id, cycle.document.id)
    return mapping


def _task_types(loaded: LoadedScenario) -> Dict[tuple[str, str], str]:
    mapping: Dict[tuple[str, str], str] = {}
    for cycle in loaded.cycles:
        for task in cycle.document.tasks:
            mapping[(cycle.document.id, task.id)] = task.type
            mapping.setdefault(("", task.id), task.type)
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
                    "model_tokens": 0,
                    "model_cost_usd": 0.0,
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
        "max_model_tokens": "model_tokens",
        "max_model_cost_usd": "model_cost_usd",
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
    (trace_dir / "scenario_definition.json").write_text(
        json.dumps(loaded.document.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (trace_dir / "scenario.json").write_text(
        json.dumps(
            {
                "schema_version": TRACE_SCHEMA_VERSION,
                "run_id": run_id,
                "scenario_id": loaded.document.id,
                "goal": loaded.document.goal,
                "status": "running",
                "reason": None,
                "cycle_count": len(loaded.cycles),
                "task_count": sum(len(cycle.document.tasks) for cycle in loaded.cycles),
                "cycles": [
                    {
                        "cycle_id": cycle.document.id,
                        "cycle_path": cycle.document.id,
                        "status": "queued",
                        "reason": None,
                        "artifact": f"cycles/{_safe_trace_segment(cycle.document.id)}.json",
                        "task_count": len(cycle.document.tasks),
                    }
                    for cycle in loaded.cycles
                ],
                "definition": "scenario_definition.json",
                "status_file": "status.json",
                "manifest": "manifest.json",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": TRACE_SCHEMA_VERSION,
        "run_id": run_id,
        "scenario_id": loaded.document.id,
        "status": "running",
        "reason": None,
        "inputs": loaded.document.inputs,
        "outputs": loaded.document.outputs,
        "status_file": "status.json",
        "scenario_definition": "scenario_definition.json",
        "artifact_index": "artifacts.json",
        "report_data_file": "report_data.json",
        "execution_log": _run_relative_path(trace_dir, logger.path),
        "report_data": {
            "manifest": "trace/manifest.json",
            "status": "trace/status.json",
            "artifacts": "trace/artifacts.json",
            "report_snapshot": "trace/report_data.json",
            "scenario": "trace/scenario.json",
            "scenario_definition": "trace/scenario_definition.json",
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
                    {"kind": "scenario", "path": "trace/scenario.json"},
                    {"kind": "scenario_definition", "path": "trace/scenario_definition.json"},
                    {"kind": "status", "path": "trace/status.json"},
                    {"kind": "report_data", "path": "trace/report_data.json"},
                    {"kind": "execution_log", "path": _run_relative_path(trace_dir, logger.path)},
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    _write_live_report_data(loaded, trace_dir=trace_dir, run_id=run_id, logger=logger)


def _write_live_report_data(
    loaded: LoadedScenario,
    *,
    trace_dir: Path,
    run_id: str,
    logger: ExecutionLogger,
) -> None:
    (trace_dir / "report_data.json").write_text(
        json.dumps(
            {
                "schema_version": TRACE_SCHEMA_VERSION,
                "generated_at": _timestamp(),
                "run_id": run_id,
                "scenario_id": loaded.document.id,
                "status": _read_json_optional(trace_dir / "status.json"),
                "artifacts": _read_json_optional(trace_dir / "artifacts.json").get("artifacts", []),
                "cycles": [],
                "task_executions": [],
                "task_inputs": [],
                "model_outputs": [],
                "execution_log": _run_relative_path(trace_dir, logger.path),
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
    live_refresh = _live_report_refresh_script(status)
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Planfoldr Report: {html.escape(loaded.document.id)}</title>
  <style>
{_report_styles()}
    .status-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr)); gap: 0.75rem; }}
    .metric {{ border: 1px solid #d1d5db; padding: 0.75rem; }}
    .streaming {{ border-left: 3px solid #2563eb; padding-left: 0.75rem; }}
    .streaming pre {{ max-height: 24rem; }}
  </style>
</head>
<body>
  <main class="flow">
    <h1>Starting <code>{html.escape(loaded.document.id)}</code></h1>
    <details open data-live-summary>
      <summary>additional info</summary>
      <div id="live-status">{_status_html(status)}</div>
    </details>
    <section id="execution-flow">{_status_work_flow_html(status, trace_dir=trace_dir)}</section>
    {live_refresh}
  </main>
</body>
</html>
"""
    report_path.write_text(document, encoding="utf-8")


def _live_report_refresh_script(status: Dict[str, Any]) -> str:
    if status.get("status") != "running":
        return ""
    return """<script>
(function () {
  var detailsKey = "planfoldr-live-open-details";
  var scrollKey = "planfoldr-live-scroll-y";

  function detailsList() {
    return Array.prototype.slice.call(document.querySelectorAll("details"));
  }

  function saveOpenDetails() {
    var open = [];
    detailsList().forEach(function (detail, index) {
      if (detail.open) {
        open.push(index);
      }
    });
    sessionStorage.setItem(detailsKey, JSON.stringify(open));
  }

  function restoreOpenDetails() {
    try {
      var open = JSON.parse(sessionStorage.getItem(detailsKey) || "[]");
      detailsList().forEach(function (detail, index) {
        if (open.indexOf(index) !== -1) {
          detail.open = true;
        }
      });
    } catch (error) {
      return;
    }
  }

  function restoreScroll() {
    var saved = Number(sessionStorage.getItem(scrollKey) || "0");
    if (saved > 0) {
      window.scrollTo(0, saved);
    }
  }

  restoreOpenDetails();
  restoreScroll();

  document.addEventListener("toggle", function (event) {
    if (event.target && event.target.tagName === "DETAILS") {
      saveOpenDetails();
    }
  }, true);

  window.addEventListener("scroll", function () {
    sessionStorage.setItem(scrollKey, String(window.scrollY || 0));
  }, { passive: true });

  window.addEventListener("beforeunload", function () {
    saveOpenDetails();
    sessionStorage.setItem(scrollKey, String(window.scrollY || 0));
  });

  window.setTimeout(function () {
    saveOpenDetails();
    sessionStorage.setItem(scrollKey, String(window.scrollY || 0));
    window.location.reload();
  }, 1500);
}());
</script>"""


def _read_optional_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _write_json_with_long_artifacts(
    trace_dir: Path,
    relative: str,
    value: Any,
    *,
    threshold: int = LONG_JSON_STRING_THRESHOLD,
) -> None:
    target = trace_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    prepared = _extract_long_json_strings(
        value,
        trace_dir=trace_dir,
        json_target=target,
        path=(),
        threshold=threshold,
    )
    target.write_text(json.dumps(prepared, indent=2, sort_keys=True), encoding="utf-8")


def _extract_long_json_strings(
    value: Any,
    *,
    trace_dir: Path,
    json_target: Path,
    path: tuple[str, ...],
    threshold: int,
) -> Any:
    if isinstance(value, dict):
        return {
            key: _extract_long_json_strings(
                item,
                trace_dir=trace_dir,
                json_target=json_target,
                path=(*path, str(key)),
                threshold=threshold,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _extract_long_json_strings(
                item,
                trace_dir=trace_dir,
                json_target=json_target,
                path=(*path, str(index)),
                threshold=threshold,
            )
            for index, item in enumerate(value)
        ]
    if isinstance(value, str) and len(value) > threshold:
        artifact_path = _write_long_string_artifact(trace_dir, json_target, path, value)
        return str(artifact_path.relative_to(trace_dir))
    return value


def _write_long_string_artifact(trace_dir: Path, json_target: Path, path: tuple[str, ...], text: str) -> Path:
    field_path = ".".join(_safe_artifact_path_part(part) for part in path) or "value"
    suffix, content = _long_string_artifact_payload(path, text)
    artifact_path = json_target.with_name(f"{json_target.stem}.{field_path}{suffix}")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(content, encoding="utf-8")
    return artifact_path


def _long_string_artifact_payload(path: tuple[str, ...], text: str) -> tuple[str, str]:
    field_name = path[-1].lower() if path else ""
    if field_name.endswith("_md") or "markdown" in field_name:
        return ".md", text
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return ".txt", text
    if isinstance(parsed, (dict, list)):
        return ".json", json.dumps(parsed, indent=2, sort_keys=True)
    return ".txt", text


def _safe_artifact_path_part(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)
    return cleaned.strip("_") or "field"


def _safe_trace_segment(value: str) -> str:
    return _safe_artifact_path_part(value)


def _resolve_extracted_artifact_refs(value: Any, trace_dir: Path) -> Any:
    if isinstance(value, dict):
        return {key: _resolve_extracted_artifact_refs(item, trace_dir) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_extracted_artifact_refs(item, trace_dir) for item in value]
    if isinstance(value, str) and _looks_like_extracted_artifact_ref(value):
        target = trace_dir / value
        try:
            target.relative_to(trace_dir)
        except ValueError:
            return value
        try:
            return target.read_text(encoding="utf-8")
        except FileNotFoundError:
            return value
    return value


def _looks_like_extracted_artifact_ref(value: str) -> bool:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return False
    if path.suffix not in {".json", ".md", ".txt"}:
        return False
    return len(path.name.split(".")) > 2


def _read_json_optional(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _report_styles() -> str:
    return """
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; color: #1f2937; line-height: 1.45; }
    code { background: #f3f4f6; padding: 0.1rem 0.25rem; }
    details { border-left: 3px solid #d1d5db; margin: 0.5rem 0 1rem; padding: 0.5rem 0 0.5rem 0.75rem; }
    summary { cursor: pointer; font-weight: 600; }
    pre { background: #f3f4f6; color: #111827; overflow: auto; padding: 0.75rem; white-space: pre-wrap; }
    .muted { color: #6b7280; }
    .flow { max-width: 90rem; }
    .task { border-top: 1px solid #e5e7eb; padding: 1rem 0; }
    .line { margin: 0.25rem 0; }
    .task-level-muted { color: #6b7280; }
    .task-level-current { color: #111827; }
    .report-pre, .json-block { border: 1px solid #d1d5db; background: #f3f4f6; color: #111827; overflow: auto; padding: 0.75rem; }
    .json-block { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; font-size: 0.9rem; line-height: 1.5; }
    .json-block summary, .json-node summary { font-weight: 500; }
    .json-view { margin-top: 0.35rem; }
    .json-node { border-left: 2px solid #d1d5db; margin: 0.15rem 0; padding: 0.1rem 0 0.1rem 0.75rem; }
    .json-children { margin-left: 1rem; }
    .json-row { min-height: 1.35rem; }
    .json-key { color: #7c2d12; font-weight: 600; }
    .json-punctuation { color: #4f46e5; font-weight: 700; }
    .json-string { color: #166534; }
    .json-number { color: #1d4ed8; }
    .json-boolean { color: #9333ea; font-weight: 600; }
    .json-null { color: #6b7280; font-weight: 600; }
    .json-link { text-decoration: underline; text-underline-offset: 0.15rem; }
"""


def _report_pre(title: str, text: str) -> str:
    if not text:
        return ""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return f"<h3>{html.escape(title)}</h3><pre class='report-pre'>{html.escape(text)}</pre>"
    if not isinstance(parsed, (dict, list)):
        return f"<h3>{html.escape(title)}</h3><pre class='report-pre'>{html.escape(text)}</pre>"
    return _report_json(title, parsed)


def _report_json(title: str, value: Any) -> str:
    return (
        f"<h3>{html.escape(title)}</h3>"
        f"<details open class='json-block'>"
        f"<summary>{html.escape(title)} {_json_summary_html(value)}</summary>"
        f"<div class='json-view'>{_json_value_html(value)}</div>"
        "</details>"
    )


def _report_detail(summary: str, body: str) -> str:
    if not body:
        return ""
    return f"<details><summary>{html.escape(summary)}</summary>{body}</details>"


def _loads_json_object(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _task_source_payload(
    cycle: CycleResult,
    task: TaskResult,
    *,
    task_artifact_dir: Optional[str] = None,
    executor_artifact_dir: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "cycle_id": cycle.cycle_id,
        "cycle_path": cycle.cycle_path or cycle.cycle_id,
        "task_id": task.task_id,
        "execution_id": task.execution_id,
        "executor": task.metadata.get("executor", "unknown"),
        "task_artifact_dir": task_artifact_dir,
        "executor_artifact_dir": executor_artifact_dir,
    }


def _executor_artifact_dir_for_task(task: TaskResult) -> Optional[str]:
    executor = task.metadata.get("executor")
    if executor == "model":
        model = task.metadata.get("model", {})
        model_name = str(model.get("name") or "unknown_model") if isinstance(model, dict) else "unknown_model"
        return f"trace/models/{_safe_trace_segment(model_name)}/{task.execution_id}"
    if executor == "tool":
        tool_name = str(task.metadata.get("tool") or "unknown_tool")
        return f"trace/tools/{_safe_trace_segment(tool_name)}/{task.execution_id}"
    if executor == "command":
        command = str(task.metadata.get("command") or "unknown_command")
        return f"trace/commands/{_safe_trace_segment(command[:80])}/{task.execution_id}"
    return None


def _updated_task_context(original_context: Dict[str, Any], task: TaskResult) -> Dict[str, Any]:
    updated = json.loads(json.dumps(original_context, sort_keys=True)) if original_context else {}
    updated["result"] = {
        "status": task.status,
        "reason": task.reason,
        "output": task.output,
        "evidence": task.evidence,
        "artifacts": task.artifacts,
    }
    updated["budget_after"] = task.budget_after
    updated["finished_at"] = task.finished_at
    return updated


def _json_diff(before: Dict[str, Any], after: Dict[str, Any]) -> str:
    before_lines = json.dumps(before, indent=2, sort_keys=True).splitlines()
    after_lines = json.dumps(after, indent=2, sort_keys=True).splitlines()
    diff = "\n".join(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile="context",
            tofile="updated_context",
            lineterm="",
        )
    )
    return diff or "No context changes."


def _budget_spent(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    before_usage = before.get("usage", {}) if isinstance(before, dict) else {}
    after_usage = after.get("usage", {}) if isinstance(after, dict) else {}
    keys = sorted(set(before_usage) | set(after_usage))
    spent: Dict[str, Any] = {}
    for key in keys:
        before_value = before_usage.get(key, 0)
        after_value = after_usage.get(key, 0)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            spent[key] = after_value - before_value
    return spent


def _task_duration(task: TaskResult) -> Dict[str, Any]:
    started_at = _parse_timestamp(task.started_at)
    finished_at = _parse_timestamp(task.finished_at)
    elapsed = None
    if started_at is not None and finished_at is not None:
        elapsed = max(0.0, (finished_at - started_at).total_seconds())
    return {
        "started_at": task.started_at,
        "finished_at": task.finished_at,
        "elapsed_seconds": elapsed,
    }


def _parse_timestamp(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _json_value_html(value: Any, *, key: Optional[str] = None, trailing_comma: bool = False) -> str:
    if isinstance(value, dict):
        return _json_collection_html(value, key=key, opener="{", closer="}", trailing_comma=trailing_comma)
    if isinstance(value, list):
        return _json_collection_html(value, key=key, opener="[", closer="]", trailing_comma=trailing_comma)
    prefix = f"{_json_key_html(key)}<span class='json-punctuation'>: </span>" if key is not None else ""
    comma = "<span class='json-punctuation'>,</span>" if trailing_comma else ""
    return f"<div class='json-row'>{prefix}{_json_scalar_html(value)}{comma}</div>"


def _json_collection_html(
    value: Dict[str, Any] | List[Any],
    *,
    key: Optional[str],
    opener: str,
    closer: str,
    trailing_comma: bool,
) -> str:
    prefix = f"{_json_key_html(key)}<span class='json-punctuation'>: </span>" if key is not None else ""
    comma = "<span class='json-punctuation'>,</span>" if trailing_comma else ""
    if not value:
        return (
            "<div class='json-row'>"
            f"{prefix}<span class='json-punctuation'>{html.escape(opener + closer)}</span>{comma}"
            "</div>"
        )
    rows = []
    items = list(value.items()) if isinstance(value, dict) else list(enumerate(value))
    for index, item in enumerate(items):
        child_key: Optional[str]
        child_value: Any
        if isinstance(value, dict):
            child_key, child_value = str(item[0]), item[1]
        else:
            child_key, child_value = None, item[1]
        rows.append(_json_value_html(child_value, key=child_key, trailing_comma=index < len(items) - 1))
    return (
        f"<details open class='json-node json-collection'>"
        f"<summary>{prefix}<span class='json-punctuation'>{html.escape(opener)}</span>"
        f" <span class='muted'>{_json_count_text(value)}</span> "
        f"<span class='json-punctuation'>{html.escape(closer)}</span>{comma}</summary>"
        f"<div class='json-children'>{''.join(rows)}</div>"
        "</details>"
    )


def _json_summary_html(value: Any) -> str:
    if isinstance(value, dict):
        return (
            "<span class='json-punctuation'>{</span> "
            f"<span class='muted'>{_json_count_text(value)}</span> "
            "<span class='json-punctuation'>}</span>"
        )
    if isinstance(value, list):
        return (
            "<span class='json-punctuation'>[</span> "
            f"<span class='muted'>{_json_count_text(value)}</span> "
            "<span class='json-punctuation'>]</span>"
        )
    return ""


def _json_count_text(value: Dict[str, Any] | List[Any]) -> str:
    count = len(value)
    unit = "key" if isinstance(value, dict) else "item"
    suffix = "" if count == 1 else "s"
    return f"{count} {unit}{suffix}"


def _json_key_html(key: str) -> str:
    return f"<span class='json-key'>{html.escape(json.dumps(key))}</span>"


def _json_scalar_html(value: Any) -> str:
    if isinstance(value, str):
        escaped = html.escape(json.dumps(value))
        href = _json_path_href(value)
        if href:
            return f"<a class='json-string json-link' href='{html.escape(href, quote=True)}'>{escaped}</a>"
        return f"<span class='json-string'>{escaped}</span>"
    if isinstance(value, bool):
        return f"<span class='json-boolean'>{str(value).lower()}</span>"
    if value is None:
        return "<span class='json-null'>null</span>"
    if isinstance(value, (int, float)):
        return f"<span class='json-number'>{html.escape(json.dumps(value))}</span>"
    return f"<span class='json-string'>{html.escape(json.dumps(str(value)))}</span>"


def _json_path_href(value: str) -> Optional[str]:
    if not value or any(char in value for char in "\n\r\t"):
        return None
    if value.startswith(("http://", "https://")):
        return value
    path = Path(value)
    if path.is_absolute():
        return value
    parts = path.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        return None
    if parts[0] in {"trace", "logs"}:
        return value
    if parts[0] in {"commands", "cycles", "inputs", "models", "tasks", "tools"}:
        return f"trace/{value}"
    if value in {"artifacts.json", "manifest.json", "report_data.json", "scenario.json", "scenario_definition.json", "status.json"}:
        return f"trace/{value}"
    if "/" in value and path.suffix in {".json", ".jsonl", ".log", ".md", ".txt"}:
        return value
    return None


def _file_changes_html(value: Any, summary: Any = None) -> str:
    if not isinstance(value, list) or not value:
        return ""
    rows = []
    for item in value:
        if not isinstance(item, dict):
            continue
        lines_added = int(item.get("lines_added") or 0)
        lines_removed = int(item.get("lines_removed") or 0)
        before_sha = str(item.get("before_sha256") or "none")
        after_sha = str(item.get("after_sha256") or "none")
        byte_span = f"{int(item.get('before_bytes') or 0)}->{int(item.get('after_bytes') or item.get('bytes') or 0)} byte(s)"
        rows.append(
            "<li>"
            f"<strong>{html.escape(str(item.get('action') or 'changed'))}</strong> "
            f"<code>{html.escape(str(item.get('path') or ''))}</code> "
            f"<span class='muted'>{html.escape(str(item.get('bytes') or 0))} byte(s), "
            f"+{lines_added} -{lines_removed}, {html.escape(byte_span)}, "
            f"{html.escape(before_sha)} -> {html.escape(after_sha)}</span>"
            "</li>"
        )
    if not rows:
        return ""
    summary = summary if isinstance(summary, dict) else _file_change_summary(value)
    summary_text = (
        f"short diff: {int(summary.get('files_changed') or 0)} files changed, "
        f"{int(summary.get('files_deleted') or 0)} deleted, "
        f"+{int(summary.get('lines_added') or 0)} -{int(summary.get('lines_removed') or 0)}"
    )
    return f"<h3>File Changes</h3><p>{html.escape(summary_text)}</p><ul>{''.join(rows)}</ul>"


def _short_diff_summary_html(summary: Any) -> str:
    if not isinstance(summary, dict):
        return ""
    files_changed = int(summary.get("files_changed") or 0)
    files_deleted = int(summary.get("files_deleted") or 0)
    lines_added = int(summary.get("lines_added") or 0)
    lines_removed = int(summary.get("lines_removed") or 0)
    if files_changed == 0 and files_deleted == 0 and lines_added == 0 and lines_removed == 0:
        return ""
    return html.escape(
        "short diff: "
        f"{files_changed} files changed, "
        f"{files_deleted} deleted, "
        f"+{lines_added} -{lines_removed}"
    )


def _file_change_summary(value: List[Any]) -> Dict[str, int]:
    changes = [item for item in value if isinstance(item, dict)]
    return {
        "files_changed": len(changes),
        "files_deleted": sum(1 for item in changes if item.get("action") == "deleted"),
        "lines_added": sum(int(item.get("lines_added") or 0) for item in changes),
        "lines_removed": sum(int(item.get("lines_removed") or 0) for item in changes),
    }


def _model_metadata_without_raw_response(task: TaskResult) -> Dict[str, Any]:
    metadata = dict(task.metadata)
    raw_response = metadata.pop("raw_response", None)
    if isinstance(raw_response, str) and raw_response:
        metadata["raw_response_artifact"] = _raw_response_artifact_path(task.execution_id)
        metadata["raw_response_chars"] = len(raw_response)
        metadata["raw_response_bytes"] = len(raw_response.encode("utf-8"))
        metadata["raw_response_lines"] = len(raw_response.splitlines())
    return metadata


def _raw_response_artifact_path(execution_id: str) -> str:
    return f"models/{execution_id}/raw_response.txt"


def _read_model_raw_response(trace_dir: Path, task: TaskResult) -> str:
    raw_response = _read_optional_text(trace_dir / _raw_response_artifact_path(task.execution_id))
    if raw_response:
        return raw_response
    value = task.metadata.get("raw_response", "")
    return value if isinstance(value, str) else ""


def _raw_response_report_text(raw_response: str, *, artifact: str = "the raw response artifact") -> str:
    if not raw_response:
        return ""
    lines = raw_response.splitlines()
    if _looks_like_ollama_stream(raw_response):
        return (
            "Raw response omitted from HTML: this is Ollama provider streaming JSONL, "
            f"not assembled model text ({len(lines)} line(s), {len(raw_response)} character(s)). "
            "Inspect content.txt, thinking.txt, assembled.txt and stream.jsonl for human-readable output."
        )
    if len(raw_response) > 4000:
        return (
            "Raw response omitted from HTML because it is too large "
            f"({len(raw_response)} character(s)). Inspect {artifact} for provider diagnostics."
        )
    return raw_response


def _looks_like_ollama_stream(raw_response: str) -> bool:
    for line in raw_response.splitlines()[:5]:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return False
        if isinstance(payload, dict) and {"model", "message", "done"}.issubset(payload):
            return True
        return False
    return False


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


def _status_work_flow_html(status: Dict[str, Any], *, trace_dir: Optional[Path] = None) -> str:
    work = [item for item in status.get("work", []) if isinstance(item, dict)]
    visible_work = [item for item in work if item.get("status") != "queued"]
    if not visible_work:
        return "<p class='muted'>No task executions captured yet.</p>"
    active_stream = status.get("stream") if isinstance(status.get("stream"), dict) else {}
    active_cycle_id = status.get("current_cycle_id")
    active_task_id = status.get("current_task_id")
    blocks = []
    for index, item in enumerate(visible_work):
        previous_task = _adjacent_work_task_id(visible_work, index, direction=-1, default="start")
        next_task = _adjacent_work_task_id(visible_work, index, direction=1, default="finish")
        current_task = item.get("task_id") or "unknown"
        cycle_id = item.get("cycle_id") or "unknown"
        executor = item.get("executor_kind") or item.get("task_type") or "task"
        reason = f" ({item.get('reason')})" if item.get("reason") else ""
        stream = active_stream if current_task == status.get("current_task_id") else {}
        stream_execution_id = item.get("execution_id") or stream.get("execution_id")
        show_stream = item.get("status") == "running" or current_task == status.get("current_task_id")
        stream_html = _live_stream_preview_html(stream_execution_id, trace_dir=trace_dir) if show_stream else ""
        detail_html = _live_task_detail_html(item, trace_dir=trace_dir, stream_html=stream_html)
        blocks.append(
            "<article class='task'>"
            f"{_task_flow_line_html(cycle_id, previous_task, current_task, next_task, is_active_level=cycle_id == active_cycle_id, is_active_task=current_task == active_task_id)}"
            f"<p class='line'>{html.escape(str(executor))}: {html.escape(str(current_task))}</p>"
            f"{detail_html}"
            f"<p class='line'>result: {html.escape(str(item.get('status') or 'queued'))}{html.escape(reason)}</p>"
            "</article>"
        )
    return "\n".join(blocks)


def _live_task_detail_html(item: Dict[str, Any], *, trace_dir: Optional[Path], stream_html: str) -> str:
    executor = item.get("executor_kind") or item.get("task_type") or "task"
    if executor != "model":
        return (
            "<details><summary>additional info</summary>"
            f"{_report_pre('Work Status', json.dumps(item, indent=2, sort_keys=True))}"
            "</details>"
        )
    source = item.get("source") if isinstance(item.get("source"), dict) else {}
    source_text = json.dumps(source, indent=2, sort_keys=True) if source else _read_report_artifact_text(
        trace_dir, item.get("source_artifact")
    )
    context_text = _read_report_artifact_text(trace_dir, item.get("context_artifact"))
    input_text = _read_report_artifact_text(trace_dir, item.get("input_artifact"))
    status_text = _read_report_artifact_text(trace_dir, item.get("status_artifact"))
    budget_after = item.get("budget_after") if isinstance(item.get("budget_after"), dict) else {}
    budget_html = ""
    if budget_after:
        budget_html = (
            f"{_report_pre('Budget Spent', json.dumps(budget_after.get('usage', {}), indent=2, sort_keys=True))}"
            f"{_report_pre('Budget Remaining', json.dumps(budget_after.get('remaining', {}), indent=2, sort_keys=True))}"
        )
    return (
        f"{_report_pre('Source', source_text)}"
        f"{_report_pre('Context', context_text)}"
        f"{_report_pre('Input', input_text)}"
        f"{stream_html}"
        f"{_report_detail('status', _report_pre('Status', status_text))}"
        f"{budget_html}"
    )


def _read_report_artifact_text(trace_dir: Optional[Path], value: Any) -> str:
    if trace_dir is None or not value:
        return ""
    path = Path(str(value))
    if path.is_absolute() or ".." in path.parts:
        return ""
    target = trace_dir.parent / path if path.parts and path.parts[0] == "trace" else trace_dir / path
    try:
        target.relative_to(trace_dir.parent)
    except ValueError:
        return ""
    return _read_optional_text(target)


def _adjacent_work_task_id(work: List[Dict[str, Any]], index: int, *, direction: int, default: str) -> Any:
    current_cycle_id = work[index].get("cycle_id")
    cursor = index + direction
    while 0 <= cursor < len(work):
        item = work[cursor]
        if item.get("cycle_id") == current_cycle_id:
            return item.get("task_id") or "unknown"
        cursor += direction
    return default


def _live_stream_preview_html(
    execution_id: Any,
    *,
    trace_dir: Optional[Path],
) -> str:
    if trace_dir is None or not execution_id:
        return ""
    stream_path = trace_dir / "models" / str(execution_id) / "stream.jsonl"
    rows = _read_stream_rows(stream_path)
    content = "".join(str(row.get("text", "")) for row in rows if row.get("kind") == "content")
    thinking = "".join(str(row.get("text", "")) for row in rows if row.get("kind") == "thinking")
    preview = _tail_text(content, 5000)
    thinking_preview = _tail_text(thinking, 2000) if thinking else ""
    thinking_html = _report_detail("thinking", _report_pre("Thinking", thinking_preview)) if thinking_preview else ""
    generation_html = (
        _report_pre("Generation", preview)
        if preview
        else "<h3>Generation</h3><pre class='report-pre'></pre>"
    )
    return (
        "<div class='streaming'>"
        f"{thinking_html}"
        f"{generation_html}"
        "</div>"
    )


def _read_stream_rows(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return rows
    for line in lines[-200:]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _tail_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"...\n{text[-limit:]}"


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
    if path.name == "scenario.json":
        return "scenario"
    if path.name == "scenario_definition.json":
        return "scenario_definition"
    if path.name == "report_data.json":
        return "report_data"
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
