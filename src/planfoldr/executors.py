"""Command, tool and model executor adapters."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Mapping, Optional

from planfoldr.guards import (
    BudgetExceeded,
    BudgetTracker,
    PermissionDenied,
    PermissionEngine,
    budget_exceeded_result,
    need_permission_result,
)
from planfoldr.loader import LoadedPrompt
from planfoldr.runtime import Outcome, TaskResult, make_task_result
from planfoldr.schema import ModelConfig, Task
from planfoldr.validation import OutputValidationError, VerifierEvidence, validate_task_output


@dataclass(frozen=True)
class PromptMetadata:
    prompt_id: str
    hash: str
    variables: Dict[str, Any]
    rendered_prompt: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "hash": self.hash,
            "variables": self.variables,
            "rendered_prompt": self.rendered_prompt,
        }


@dataclass(frozen=True)
class ModelResponse:
    output: Dict[str, Any]
    raw: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    budget_cost: float = 0.0


class ModelAdapter:
    def generate(
        self,
        *,
        task: Task,
        model: ModelConfig,
        messages: List[Dict[str, str]],
        config: Mapping[str, Any],
        tools: List[str],
    ) -> ModelResponse:
        raise NotImplementedError


class StubModelAdapter(ModelAdapter):
    """Deterministic model adapter keyed by task id, prompt id or sequence."""

    def __init__(self, responses: Mapping[str, List[Dict[str, Any]] | Dict[str, Any]]) -> None:
        self.responses = {
            key: list(value) if isinstance(value, list) else [value]
            for key, value in responses.items()
        }
        self.calls: List[str] = []

    def generate(
        self,
        *,
        task: Task,
        model: ModelConfig,
        messages: List[Dict[str, str]],
        config: Mapping[str, Any],
        tools: List[str],
    ) -> ModelResponse:
        prompt_id = str(config.get("prompt_id", ""))
        key = self._select_key(task.id, prompt_id)
        self.calls.append(key)
        values = self.responses[key]
        value = values.pop(0) if len(values) > 1 else values[0]
        return ModelResponse(output=dict(value), raw=json.dumps(value), metadata={"adapter": "stub"})

    def _select_key(self, task_id: str, prompt_id: str) -> str:
        for key in (f"{task_id}:{prompt_id}", task_id, prompt_id, "*"):
            if key in self.responses:
                return key
        raise KeyError(f"No stub model response for task '{task_id}' and prompt '{prompt_id}'")


class OllamaModelAdapter(ModelAdapter):
    def __init__(self, endpoint: str = "http://127.0.0.1:11434/api/chat", timeout: float = 30) -> None:
        self.endpoint = endpoint
        self.timeout = timeout

    def generate(
        self,
        *,
        task: Task,
        model: ModelConfig,
        messages: List[Dict[str, str]],
        config: Mapping[str, Any],
        tools: List[str],
    ) -> ModelResponse:
        payload = {
            "model": model.name,
            "messages": messages,
            "stream": False,
            "format": "json",
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except (OSError, urllib.error.URLError) as exc:
            return ModelResponse(
                output={"status": Outcome.FAILURE.value, "reason": f"Ollama unavailable: {exc}"},
                raw=str(exc),
                metadata={"adapter": "ollama", "available": False},
            )

        payload = json.loads(raw)
        content = payload.get("message", {}).get("content", "{}")
        try:
            output = json.loads(content)
        except json.JSONDecodeError:
            output = {"status": Outcome.FAILURE.value, "reason": "Ollama returned non-JSON content"}
        return ModelResponse(
            output=output,
            raw=raw,
            metadata={"adapter": "ollama", "available": True, "model": model.name},
        )


@dataclass
class ExecutorRegistry:
    permission_engine: PermissionEngine
    budget_tracker: BudgetTracker
    prompts: Mapping[str, LoadedPrompt] = field(default_factory=dict)
    model_adapter: ModelAdapter = field(default_factory=lambda: StubModelAdapter({"*": {"status": "success"}}))
    task_inputs: Mapping[str, Dict[str, Any]] = field(default_factory=dict)
    prompt_variables: Mapping[str, Any] = field(default_factory=dict)
    invalid_output_retries: int = 0
    task_outputs: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def __call__(self, task: Task) -> TaskResult:
        before = self.budget_tracker.snapshot()
        try:
            if task.executor.kind == "command":
                result = self._execute_command(task)
            elif task.executor.kind == "model":
                result = self._execute_model(task)
            elif task.executor.kind == "tool":
                result = self._execute_tool(task)
            else:
                result = make_task_result(task.id, Outcome.FAILURE.value, reason="Unknown executor kind")
        except BudgetExceeded as exc:
            result = budget_exceeded_result(task.id, exc.report)
        except PermissionDenied as exc:
            result = need_permission_result(task.id, exc.report)

        result = self._validate_non_model_output(task, result)
        self.task_outputs[task.id] = result.output
        after = self.budget_tracker.snapshot()
        return _with_budget_snapshots(result, before, after)

    def _execute_command(self, task: Task) -> TaskResult:
        command = _render_text(task.executor.command or "", self.prompt_variables)
        self.permission_engine.check_command(command)
        self.budget_tracker.consume_tool_call()
        cwd = self.permission_engine.check_read_path(_render_text(task.executor.cwd or ".", self.prompt_variables))
        completed = subprocess.run(
            shlex.split(command),
            cwd=str(cwd),
            env={"PATH": os.environ.get("PATH", "")},
            capture_output=True,
            text=True,
            timeout=self.budget_tracker.configured.max_cpu_time,
            check=False,
        )
        status = Outcome.SUCCESS.value if completed.returncode == 0 else Outcome.FAILURE.value
        return make_task_result(
            task.id,
            status,
            reason=None if status == Outcome.SUCCESS.value else f"Command exited {completed.returncode}",
            output={
                "status": status,
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            },
            evidence=_verifier_evidence(task, status, f"Command exit code {completed.returncode}"),
            metadata={"executor": "command", "command": command, "cwd": str(cwd)},
        )

    def _execute_model(self, task: Task) -> TaskResult:
        attempts = self.invalid_output_retries + 1
        last_error: Optional[OutputValidationError] = None
        for attempt in range(1, attempts + 1):
            result = self._execute_model_once(task, attempt=attempt)
            try:
                validate_task_output(result.output, task.output_schema)
            except OutputValidationError as exc:
                last_error = exc
                if attempt < attempts:
                    continue
                return make_task_result(
                    task.id,
                    Outcome.RETRY_EXCEEDED.value,
                    reason=str(exc),
                    output={
                        "status": Outcome.RETRY_EXCEEDED.value,
                        "validation_error": {
                            "path": exc.path,
                            "expected": exc.expected,
                            "actual": repr(exc.actual),
                        },
                    },
                    evidence=VerifierEvidence(
                        status=Outcome.RETRY_EXCEEDED.value,
                        proof=f"Invalid model output after {attempts} attempt(s): {exc}",
                    ).to_dict(),
                    metadata=result.metadata,
                )
            return result
        raise AssertionError(f"unreachable model retry state: {last_error}")

    def _execute_model_once(self, task: Task, *, attempt: int) -> TaskResult:
        self.budget_tracker.consume_model_call()
        prompt_meta = self._render_prompt(task)
        model = task.executor.model or ModelConfig(provider="stub", name="deterministic")
        response = self.model_adapter.generate(
            task=task,
            model=model,
            messages=[{"role": "user", "content": prompt_meta.rendered_prompt}],
            config={"prompt_id": prompt_meta.prompt_id},
            tools=[],
        )
        if response.budget_cost:
            self.budget_tracker.consume_model_budget(response.budget_cost)
        status = str(response.output.get("status", Outcome.FAILURE.value))
        return make_task_result(
            task.id,
            status,
            reason=response.output.get("reason"),
            output=response.output,
            evidence=_verifier_evidence(task, status, "Model output matched declared schema"),
            metadata={
                "executor": "model",
                "attempt": attempt,
                "model": model.model_dump(mode="json"),
                "prompt": prompt_meta.to_dict(),
                "response": response.metadata,
                "raw_response": response.raw,
            },
        )

    def _execute_tool(self, task: Task) -> TaskResult:
        tool_name = task.executor.tool or ""
        self.permission_engine.check_tool(tool_name)
        self.budget_tracker.consume_tool_call()
        if tool_name == "noop":
            return make_task_result(task.id, Outcome.SUCCESS.value, metadata={"executor": "tool", "tool": tool_name})
        if tool_name == "write_files":
            return self._write_files(task)
        return make_task_result(
            task.id,
            Outcome.FAILURE.value,
            reason=f"Unknown tool '{tool_name}'",
            metadata={"executor": "tool", "tool": tool_name},
        )

    def _write_files(self, task: Task) -> TaskResult:
        payload = self.task_inputs.get(task.id) or self._latest_output_with_files()
        files = payload.get("files", [])
        written: List[str] = []
        for item in files:
            target = self.permission_engine.check_write_path(_render_text(item["path"], self.prompt_variables))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(item.get("content", "")), encoding="utf-8")
            written.append(str(target))
        return make_task_result(
            task.id,
            Outcome.SUCCESS.value,
            output={"status": Outcome.SUCCESS.value, "files": written},
            evidence=_verifier_evidence(task, Outcome.SUCCESS.value, f"Wrote {len(written)} file(s)"),
            metadata={"executor": "tool", "tool": "write_files"},
        )

    def _latest_output_with_files(self) -> Dict[str, Any]:
        for output in reversed(list(self.task_outputs.values())):
            files = output.get("files")
            if isinstance(files, list) and all(isinstance(item, Mapping) and "path" in item for item in files):
                return output
        return {}

    def _render_prompt(self, task: Task) -> PromptMetadata:
        prompt_ref = task.executor.prompt
        if prompt_ref is None:
            rendered = task.task
            prompt_id = task.id
        else:
            loaded = self.prompts[prompt_ref.id]
            rendered = loaded.content
            prompt_id = prompt_ref.id
        rendered = _render_text(rendered, self.prompt_variables)
        digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
        return PromptMetadata(
            prompt_id=prompt_id,
            hash=f"sha256:{digest}",
            variables=dict(self.prompt_variables),
            rendered_prompt=rendered,
        )

    def _validate_non_model_output(self, task: Task, result: TaskResult) -> TaskResult:
        if task.executor.kind == "model" or result.status in {
            Outcome.BUDGET_EXCEEDED.value,
            Outcome.NEED_PERMISSION.value,
            Outcome.RETRY_EXCEEDED.value,
        }:
            return result
        try:
            validate_task_output(result.output, task.output_schema)
        except OutputValidationError as exc:
            return make_task_result(
                task.id,
                Outcome.FAILURE.value,
                reason=str(exc),
                output={
                    "status": Outcome.FAILURE.value,
                    "validation_error": {
                        "path": exc.path,
                        "expected": exc.expected,
                        "actual": repr(exc.actual),
                    },
                },
                evidence=VerifierEvidence(status=Outcome.FAILURE.value, proof=str(exc)).to_dict(),
                metadata=result.metadata,
            )
        return result


def _with_budget_snapshots(result: TaskResult, before: Dict[str, Any], after: Dict[str, Any]) -> TaskResult:
    return TaskResult(
        task_id=result.task_id,
        execution_id=result.execution_id,
        status=result.status,
        reason=result.reason,
        input=result.input,
        output=result.output,
        artifacts=result.artifacts,
        budget_before=before,
        budget_after=after,
        audit_events=result.audit_events,
        evidence=result.evidence,
        request=result.request,
        metadata=result.metadata,
        started_at=result.started_at,
        finished_at=result.finished_at,
    )


def _verifier_evidence(task: Task, status: str, proof: str) -> Optional[Dict[str, Any]]:
    if task.type != "verify":
        return None
    return VerifierEvidence(status=status, proof=proof).to_dict()


def _render_text(template: str, variables: Mapping[str, Any]) -> str:
    rendered = Template(template).safe_substitute({key: str(value) for key, value in variables.items()})

    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        return str(_lookup_variable(variables, key))

    return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", replace, rendered)


def _lookup_variable(variables: Mapping[str, Any], key: str) -> Any:
    if key in variables:
        return variables[key]
    current: Any = variables
    for part in key.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            return f"{{{{ {key} }}}}"
    return current
