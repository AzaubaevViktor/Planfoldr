"""Deterministic scenario, cycle and task execution core."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, Optional
from uuid import uuid4

from planfoldr.loader import LoadedCycle, LoadedScenario
from planfoldr.schema import Task


class Outcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    BUDGET_EXCEEDED = "budget_exceeded"
    NEED_CONTEXT = "need_context"
    NEED_DECISION = "need_decision"
    NEED_ANSWER = "need_answer"
    NEED_INNER_CYCLE = "need_inner_cycle"
    NEED_PERMISSION = "need_permission"
    NEED_TOOL = "need_tool"
    RETRY_EXCEEDED = "retry_exceeded"


TERMINAL_SUCCESS = "success"
TERMINAL_FAIL = "fail"
PARENT_TARGET = "parent"


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    execution_id: str
    status: str
    reason: Optional[str] = None
    input: Dict[str, Any] = field(default_factory=dict)
    output: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    budget_before: Dict[str, Any] = field(default_factory=dict)
    budget_after: Dict[str, Any] = field(default_factory=dict)
    audit_events: List[Dict[str, Any]] = field(default_factory=list)
    evidence: Optional[Dict[str, Any]] = None
    request: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "execution_id": self.execution_id,
            "status": self.status,
            "reason": self.reason,
            "input": self.input,
            "output": self.output,
            "artifacts": self.artifacts,
            "budget_before": self.budget_before,
            "budget_after": self.budget_after,
            "audit_events": self.audit_events,
            "evidence": self.evidence,
            "request": self.request,
            "metadata": self.metadata,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass(frozen=True)
class CycleResult:
    cycle_id: str
    status: str
    task_results: List[TaskResult]
    reason: Optional[str] = None
    request: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "status": self.status,
            "reason": self.reason,
            "request": self.request,
            "task_results": [result.to_dict() for result in self.task_results],
        }


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    status: str
    cycle_results: List[CycleResult]
    reason: Optional[str] = None

    @property
    def task_results(self) -> List[TaskResult]:
        return [task for cycle in self.cycle_results for task in cycle.task_results]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "status": self.status,
            "reason": self.reason,
            "cycle_results": [result.to_dict() for result in self.cycle_results],
        }


ExecutorFn = Callable[[Task], TaskResult]


class RuntimeErrorBase(RuntimeError):
    """Base class for deterministic runtime failures."""


class MissingLinkError(RuntimeErrorBase):
    """Raised when a task outcome has no declared link."""


class MissingTaskError(RuntimeErrorBase):
    """Raised when an entrypoint or link target names an unknown task."""


def run_scenario(loaded: LoadedScenario, executor: ExecutorFn) -> ScenarioResult:
    cycle_results: List[CycleResult] = []
    for cycle in loaded.cycles:
        result = run_cycle(cycle, executor)
        cycle_results.append(result)
        if result.status != Outcome.SUCCESS.value:
            return ScenarioResult(
                scenario_id=loaded.document.id,
                status=result.status,
                reason=result.reason,
                cycle_results=cycle_results,
            )
    return ScenarioResult(
        scenario_id=loaded.document.id,
        status=Outcome.SUCCESS.value,
        cycle_results=cycle_results,
    )


def run_cycle(loaded: LoadedCycle, executor: ExecutorFn) -> CycleResult:
    cycle = loaded.document
    tasks_by_id = {task.id: task for task in cycle.tasks}
    current_id = cycle.entrypoint
    task_results: List[TaskResult] = []

    while True:
        task = tasks_by_id.get(current_id)
        if task is None:
            raise MissingTaskError(f"Task '{current_id}' is not defined in cycle '{cycle.id}'")

        result = executor(task)
        task_results.append(result)
        links = cycle.links.get(task.id, {})
        target = links.get(result.status)
        if target is None:
            raise MissingLinkError(
                f"Task '{task.id}' outcome '{result.status}' has no link in cycle '{cycle.id}'"
            )
        if target == TERMINAL_SUCCESS:
            return CycleResult(cycle_id=cycle.id, status=Outcome.SUCCESS.value, task_results=task_results)
        if target == TERMINAL_FAIL:
            return CycleResult(
                cycle_id=cycle.id,
                status=Outcome.FAILURE.value,
                reason=result.reason,
                task_results=task_results,
            )
        if target == PARENT_TARGET:
            return CycleResult(
                cycle_id=cycle.id,
                status=result.status,
                reason=result.reason,
                request=result.request,
                task_results=task_results,
            )
        current_id = target


def new_execution_id() -> str:
    return f"exec_{uuid4().hex}"


def make_task_result(
    task_id: str,
    status: str,
    *,
    execution_id: Optional[str] = None,
    reason: Optional[str] = None,
    output: Optional[Mapping[str, Any]] = None,
    request: Optional[Mapping[str, Any]] = None,
    metadata: Optional[Mapping[str, Any]] = None,
    evidence: Optional[Mapping[str, Any]] = None,
) -> TaskResult:
    now = _now()
    return TaskResult(
        task_id=task_id,
        execution_id=execution_id or new_execution_id(),
        status=status,
        reason=reason,
        output=dict(output or {"status": status}),
        request=dict(request) if request is not None else None,
        metadata=dict(metadata or {}),
        evidence=dict(evidence) if evidence is not None else None,
        started_at=now,
        finished_at=now,
    )


class StubExecutor:
    """Deterministic executor for runtime tests and fixtures."""

    def __init__(self, outcomes: Mapping[str, str | TaskResult]) -> None:
        self.outcomes = outcomes
        self.calls: List[str] = []

    def __call__(self, task: Task) -> TaskResult:
        self.calls.append(task.id)
        configured = self.outcomes.get(task.id, Outcome.SUCCESS.value)
        if isinstance(configured, TaskResult):
            return configured
        return make_task_result(task.id, configured)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
