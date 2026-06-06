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
        manifest_snapshot = self._manifest()
        document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Planfoldr Report: {html.escape(self.loaded.document.id)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; color: #1f2937; line-height: 1.45; }}
    code {{ background: #f3f4f6; padding: 0.1rem 0.25rem; }}
    details {{ border-left: 3px solid #d1d5db; margin: 0.5rem 0 1rem; padding: 0.5rem 0 0.5rem 0.75rem; }}
    summary {{ cursor: pointer; font-weight: 600; }}
    pre {{ background: #111827; color: #f9fafb; overflow: auto; padding: 0.75rem; white-space: pre-wrap; }}
    .muted {{ color: #6b7280; }}
    .flow {{ max-width: 90rem; }}
    .task {{ border-top: 1px solid #e5e7eb; padding: 1rem 0; }}
    .line {{ margin: 0.25rem 0; }}
    .result-success {{ color: #166534; }}
    .result-failure, .result-error {{ color: #991b1b; }}
    .diff {{ font-weight: 600; }}
  </style>
</head>
<body>
  <main class="flow">
    <h1>Starting <code>{html.escape(self.loaded.document.id)}</code></h1>
    <details>
      <summary>cut with additional human-readable info</summary>
      <p>Status: <strong>{html.escape(self.result.status)}</strong></p>
      <p>Trace manifest: <code>{html.escape(str(self.trace_dir / "manifest.json"))}</code></p>
      <p>Execution log: <code>{html.escape(str(self.execution_log_path or ""))}</code></p>
      {_report_pre('status.json', json.dumps(status_snapshot, indent=2, sort_keys=True))}
    </details>
    <section id="execution-flow">{self._execution_flow_html()}</section>
    <details>
      <summary>cut with execution log</summary>
      <pre id="execution-log">{html.escape(_read_optional_text(self.execution_log_path) if self.execution_log_path is not None else "")}</pre>
    </details>
  </main>
  <script id="report-snapshot" type="application/json">{html.escape(json.dumps({"manifest": manifest_snapshot, "status": status_snapshot}, sort_keys=True))}</script>
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
                    f"cycle up/down to {html.escape(cycle_path)}"
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
                "<details><summary>cut with additional message</summary>"
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
        previews = "".join(
            _report_pre(label, _read_optional_text(self.trace_dir / base / name))
            for label, name in files
        )
        model_text = self._task_model_text_html(task)
        return (
            "<details>"
            "<summary>cut with additional human-readable info about execution process</summary>"
            f"<p>{links}</p>"
            f"{self._request_route_html(cycle, task)}"
            f"{model_text}"
            f"{previews}"
            "</details>"
        )

    def _task_diff_detail_html(self, task: TaskResult) -> str:
        details = _file_changes_html(task.output.get("file_changes"), task.output.get("diff_summary"))
        if not details:
            return ""
        return f"<details><summary>cut with additional diff info</summary>{details}</details>"

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
            + _report_pre("Content", content)
            + _report_pre("Thinking", thinking)
            + _report_pre("Assembled Stream", assembled)
            + _report_pre("Raw Response", raw_response)
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
        return _report_pre("Source / Destination", json.dumps(route, indent=2, sort_keys=True))

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
    manifest = _read_json_optional(trace_dir / "manifest.json")
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Planfoldr Report: {html.escape(loaded.document.id)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; color: #1f2937; line-height: 1.45; }}
    code {{ background: #f3f4f6; padding: 0.1rem 0.25rem; }}
    details {{ border-left: 3px solid #d1d5db; margin: 0.5rem 0 1rem; padding: 0.5rem 0 0.5rem 0.75rem; }}
    pre {{ background: #111827; color: #f9fafb; overflow: auto; padding: 0.75rem; white-space: pre-wrap; }}
    .muted {{ color: #6b7280; }}
    .flow {{ max-width: 90rem; }}
    .task {{ border-top: 1px solid #e5e7eb; padding: 1rem 0; }}
    .line {{ margin: 0.25rem 0; }}
    .status-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr)); gap: 0.75rem; }}
    .metric {{ border: 1px solid #d1d5db; padding: 0.75rem; }}
  </style>
</head>
<body>
  <main class="flow">
    <h1>Starting <code>{html.escape(loaded.document.id)}</code></h1>
    <button id="refresh-report" type="button">Refresh Report Data</button>
    <details open>
      <summary>cut with additional human-readable info</summary>
      <div id="live-status">{_status_html(status)}</div>
    </details>
    <section id="execution-flow">{_status_work_flow_html(status)}</section>
    <details>
      <summary>cut with execution log</summary>
      <pre id="execution-log">{html.escape(_read_optional_text(execution_log_path))}</pre>
    </details>
  </main>
  <script id="report-snapshot" type="application/json">{_script_json({"manifest": manifest, "status": status})}</script>
  {_report_refresh_script(auto_refresh_condition="true")}
</body>
</html>
"""
    report_path.write_text(document, encoding="utf-8")


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


def _report_pre(title: str, text: str) -> str:
    if not text:
        return ""
    return f"<h3>{html.escape(title)}</h3><pre>{html.escape(text)}</pre>"


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


def _status_work_flow_html(status: Dict[str, Any]) -> str:
    work = [item for item in status.get("work", []) if isinstance(item, dict)]
    if not work:
        return "<p class='muted'>No task executions captured yet.</p>"
    blocks = []
    for index, item in enumerate(work):
        previous_task = work[index - 1].get("task_id") if index > 0 else "start"
        next_task = work[index + 1].get("task_id") if index + 1 < len(work) else "finish"
        current_task = item.get("task_id") or "unknown"
        cycle_id = item.get("cycle_id") or "unknown"
        executor = item.get("executor_kind") or item.get("task_type") or "task"
        reason = f" ({item.get('reason')})" if item.get("reason") else ""
        blocks.append(
            "<article class='task'>"
            f"<p class='line'>{html.escape(str(cycle_id))}: {html.escape(str(previous_task))} -&gt; [{html.escape(str(current_task))}] -&gt; {html.escape(str(next_task))}</p>"
            f"<p class='line'>{html.escape(str(executor))}: {html.escape(str(current_task))}</p>"
            "<details><summary>cut with additional human-readable info about execution process</summary>"
            f"{_report_pre('Work Status', json.dumps(item, indent=2, sort_keys=True))}"
            "</details>"
            f"<p class='line'>result: {html.escape(str(item.get('status') or 'queued'))}{html.escape(reason)}</p>"
            "</article>"
        )
    return "\n".join(blocks)

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


def _script_json(value: Any) -> str:
    return html.escape(json.dumps(value, sort_keys=True).replace("</", "<\\/"))


def _report_refresh_script(*, auto_refresh_condition: str) -> str:
    script = r"""<script>
    const snapshot = JSON.parse(document.getElementById('report-snapshot').textContent);
    async function readJson(path) {
      const response = await fetch(path + '?t=' + Date.now());
      if (!response.ok) throw new Error(response.statusText);
      return await response.json();
    }
    async function readText(path) {
      const response = await fetch(path + '?t=' + Date.now());
      if (!response.ok) throw new Error(response.statusText);
      return await response.text();
    }
    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
    }
    function renderStatus(status) {
      const budget = status.budget || {};
      const usage = budget.usage || {};
      const remaining = budget.remaining || {};
      const target = document.getElementById('live-status');
      if (!target) return;
      target.innerHTML = `
        <div class="status-grid">
          <div class="metric"><strong>Status</strong><br>${escapeHtml(status.status)}</div>
          <div class="metric"><strong>Current Task</strong><br>${escapeHtml(status.current_cycle_id || '')} / ${escapeHtml(status.current_task_id || '')}</div>
          <div class="metric"><strong>Attempt</strong><br>${escapeHtml(status.current_attempt || '')}</div>
          <div class="metric"><strong>Last Event</strong><br>${escapeHtml(status.last_event || '')}<br><span class="muted">${escapeHtml(status.last_event_at || '')}</span></div>
        </div>
        <pre>${escapeHtml(JSON.stringify({usage, remaining}, null, 2))}</pre>
      `;
    }
    function renderTasks(tasks) {
      const target = document.getElementById('execution-flow');
      if (!target || !Array.isArray(tasks) || tasks.length === 0) return;
      target.innerHTML = tasks.map((task, index) => `
        <article class="task">
          <p class="line">${escapeHtml(taskFlowText(tasks, index))}</p>
          <p class="line">${escapeHtml(taskSummaryText(task))}</p>
          ${taskProcessDetails(task)}
          <p class="line">result: ${escapeHtml(task.status || '')}${task.reason ? ` (${escapeHtml(task.reason)})` : ''}</p>
          ${diffSummaryText(task) ? `<p class="line diff">${escapeHtml(diffSummaryText(task))}</p>` : ''}
          ${taskDiffDetails(task)}
          ${taskRetryDetails(task)}
        </article>
      `).join('');
    }
    function taskFlowText(tasks, index) {
      const task = tasks[index] || {};
      const prev = index > 0 ? (tasks[index - 1].task_id || 'unknown') : 'start';
      const next = index + 1 < tasks.length ? (tasks[index + 1].task_id || 'unknown') : 'finish';
      const cycle = task.cycle_path || task.cycle_id || 'unknown';
      return `${cycle}: ${prev} -> [${task.task_id || 'unknown'}] -> ${next}`;
    }
    function taskSummaryText(task) {
      const metadata = task.metadata || {};
      const executor = metadata.executor || task.executor_kind || task.task_type || '';
      if (executor === 'command') {
        return `command: ${metadata.command || ''} in ${metadata.cwd || '.'}`;
      }
      if (executor === 'model') {
        const model = metadata.model || {};
        const prompt = metadata.prompt || {};
        const retry = metadata.retry_feedback ? ` retry ${metadata.retry_feedback.failed_attempt}/${metadata.retry_feedback.max_attempts}` : '';
        return `model: ${model.name || 'unknown_model'} goal ${prompt.prompt_id || task.task_id || 'unknown'}${retry}`;
      }
      if (executor === 'tool') return `tool: ${metadata.tool || task.executor_kind || 'unknown_tool'}`;
      return `${executor || 'task'}: ${task.task_id || ''}`;
    }
    function diffSummaryText(task) {
      const output = task.output || {};
      const summary = output.diff_summary || task.diff_summary;
      if (!summary || typeof summary !== 'object') return '';
      const changed = Number(summary.files_changed || 0);
      const deleted = Number(summary.files_deleted || 0);
      const added = Number(summary.lines_added || 0);
      const removed = Number(summary.lines_removed || 0);
      if (changed === 0 && deleted === 0 && added === 0 && removed === 0) return '';
      return `short diff: ${changed} files changed, ${deleted} deleted, +${added} -${removed}`;
    }
    function renderStatusWork(status) {
      if (Array.isArray(status.work) && status.work.length > 0) {
        renderTasks(status.work);
      }
    }
    function taskProcessDetails(task) {
      const dir = task.task_artifact_dir;
      const links = dir ? [['Status', 'status.json'], ['Context', 'context.json'], ['Input', 'input.json'], ['Output', 'output.json']]
        .map(([label, name]) => `<a href="${escapeHtml(dir)}/${name}">${escapeHtml(label)}</a>`)
        .join(' ') : '';
      const metadata = task.metadata || {};
      const route = {
        source: {cycle_id: task.cycle_id || null, cycle_path: task.cycle_path || task.cycle_id || null, task_id: task.task_id || null},
        destination: {executor: metadata.executor || task.executor_kind || 'unknown', artifact_dir: task.executor_artifact_dir || null},
      };
      const status = task.status_artifact ? '' : `<h3>Work Status</h3><pre>${escapeHtml(JSON.stringify(task, null, 2))}</pre>`;
      return `<details><summary>cut with additional human-readable info about execution process</summary><p>${links}</p><h3>Source / Destination</h3><pre>${escapeHtml(JSON.stringify(route, null, 2))}</pre>${status}</details>`;
    }
    function taskDiffDetails(task) {
      const output = task.output || {};
      const changes = Array.isArray(output.file_changes) ? output.file_changes : [];
      if (changes.length === 0) return '';
      const rows = changes.map(change => `<li><strong>${escapeHtml(change.action || 'changed')}</strong> <code>${escapeHtml(change.path || '')}</code> <span class="muted">${escapeHtml(change.bytes || 0)} byte(s), +${escapeHtml(change.lines_added || 0)} -${escapeHtml(change.lines_removed || 0)}</span></li>`).join('');
      return `<details><summary>cut with additional diff info</summary><h3>File Changes</h3><p>${escapeHtml(diffSummaryText(task))}</p><ul>${rows}</ul></details>`;
    }
    function taskRetryDetails(task) {
      const feedback = (task.metadata || {}).retry_feedback;
      if (!feedback || typeof feedback !== 'object') return '';
      return `<p class="line">retry ${escapeHtml(feedback.failed_attempt)}/${escapeHtml(feedback.max_attempts)} with additional message to model</p><details><summary>cut with additional message</summary><h3>Retry Feedback</h3><pre>${escapeHtml(JSON.stringify(feedback, null, 2))}</pre></details>`;
    }
    async function refreshReport() {
      let manifest = snapshot.manifest || {};
      try { manifest = await readJson('trace/manifest.json'); } catch (error) {}
      const data = (manifest || {}).report_data || {};
      let report = null;
      try { report = await readJson(data.report_snapshot || 'trace/report_data.json'); } catch (error) {}
      try {
        const status = await readJson(data.status || 'trace/status.json');
        renderStatus(status);
        if (!report || !Array.isArray(report.task_executions) || report.task_executions.length === 0) {
          renderStatusWork(status);
        }
      } catch (error) {
        if (report?.status) {
          renderStatus(report.status);
          if (!Array.isArray(report.task_executions) || report.task_executions.length === 0) {
            renderStatusWork(report.status);
          }
        }
      }
      if (report) {
        if (Array.isArray(report.task_executions) && report.task_executions.length > 0) {
          renderTasks(report.task_executions);
        }
      } else {
        try { renderTasks(await readJson(data.task_executions || 'trace/tasks/executions.json')); } catch (error) {}
      }
      const logPath = (report && report.execution_log) || data.execution_log;
      if (logPath) {
        try { document.getElementById('execution-log').textContent = await readText(logPath); } catch (error) {}
      }
      const loadedAt = document.getElementById('snapshot-loaded-at');
      if (loadedAt) loadedAt.textContent = new Date().toISOString();
    }
    document.getElementById('refresh-report').addEventListener('click', refreshReport);
    if (__AUTO_REFRESH_CONDITION__) {
      setInterval(refreshReport, 3000);
    }
  </script>"""
    return script.replace("__AUTO_REFRESH_CONDITION__", auto_refresh_condition)
