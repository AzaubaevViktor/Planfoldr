"""Budget and permission checks shared by runtime executors."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from planfoldr.runtime import Outcome, TaskResult, make_task_result
from planfoldr.schema import Budgets, Constraints


class BudgetExceeded(RuntimeError):
    def __init__(self, report: "BudgetReport") -> None:
        self.report = report
        super().__init__(report.reason)


class PermissionDenied(RuntimeError):
    def __init__(self, report: "PermissionReport") -> None:
        self.report = report
        super().__init__(report.reason)


@dataclass(frozen=True)
class BudgetReport:
    limit: str
    used: float
    maximum: float
    reason: str
    ram_enforcement: str = "unsupported"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "limit": self.limit,
            "used": self.used,
            "maximum": self.maximum,
            "reason": self.reason,
            "ram_enforcement": self.ram_enforcement,
        }


@dataclass
class BudgetUsage:
    iterations: int = 0
    tool_calls: int = 0
    model_calls: int = 0
    model_budget: float = 0.0
    cpu_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iterations": self.iterations,
            "tool_calls": self.tool_calls,
            "model_calls": self.model_calls,
            "model_budget": self.model_budget,
            "cpu_time": self.cpu_time,
        }


@dataclass
class BudgetTracker:
    configured: Budgets
    usage: BudgetUsage = field(default_factory=BudgetUsage)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "configured": self.configured.model_dump(mode="json"),
            "usage": self.usage.to_dict(),
            "ram_enforcement": "unsupported" if self.configured.max_ram is not None else None,
        }

    def consume_iteration(self, amount: int = 1) -> None:
        self.usage.iterations += amount
        self._check("max_iterations", self.usage.iterations, self.configured.max_iterations)

    def consume_tool_call(self, amount: int = 1) -> None:
        self.usage.tool_calls += amount
        self._check("max_tool_calls", self.usage.tool_calls, self.configured.max_tool_calls)

    def consume_model_call(self, *, budget_cost: float = 0.0) -> None:
        self.usage.model_calls += 1
        self.usage.model_budget += budget_cost
        self._check("max_model_calls", self.usage.model_calls, self.configured.max_model_calls)
        self._check("max_model_budget", self.usage.model_budget, self.configured.max_model_budget)

    def consume_model_budget(self, budget_cost: float) -> None:
        self.usage.model_budget += budget_cost
        self._check("max_model_budget", self.usage.model_budget, self.configured.max_model_budget)

    def consume_cpu_time(self, seconds: float) -> None:
        self.usage.cpu_time += seconds
        self._check("max_cpu_time", self.usage.cpu_time, self.configured.max_cpu_time)

    def _check(self, limit: str, used: float, maximum: Optional[float]) -> None:
        if maximum is not None and used > maximum:
            raise BudgetExceeded(
                BudgetReport(
                    limit=limit,
                    used=used,
                    maximum=maximum,
                    reason=f"{limit} exceeded: used {used}, maximum {maximum}",
                )
            )


@dataclass(frozen=True)
class PermissionReport:
    permission: str
    requested: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "permission": self.permission,
            "requested": self.requested,
            "reason": self.reason,
        }


@dataclass
class PermissionEngine:
    constraints: Constraints
    base_dir: Path

    def check_tool(self, tool_name: str) -> None:
        tools = self.constraints.tools
        if tools is None:
            raise PermissionDenied(
                PermissionReport("tool", tool_name, "No tool allowlist is configured")
            )
        if any(re.search(pattern, tool_name) for pattern in tools.deny):
            raise PermissionDenied(PermissionReport("tool", tool_name, "Tool matched deny rule"))
        if not any(re.search(pattern, tool_name) for pattern in tools.allow):
            raise PermissionDenied(PermissionReport("tool", tool_name, "Tool is not allowed"))

    def check_command(self, command: str) -> None:
        tools = self.constraints.tools
        if tools is None:
            raise PermissionDenied(
                PermissionReport("command", command, "No command allowlist is configured")
            )
        if any(re.search(pattern, command) for pattern in tools.deny):
            raise PermissionDenied(PermissionReport("command", command, "Command matched deny rule"))
        if not any(re.search(pattern, command) for pattern in tools.allow):
            raise PermissionDenied(PermissionReport("command", command, "Command is not allowed"))

    def check_read_path(self, path: str | Path) -> Path:
        return self._check_path(path, mode="read")

    def check_write_path(self, path: str | Path) -> Path:
        return self._check_path(path, mode="write")

    def _check_path(self, path: str | Path, *, mode: str) -> Path:
        filesystem = self.constraints.filesystem
        if filesystem is None:
            raise PermissionDenied(
                PermissionReport(f"filesystem.{mode}", str(path), "No filesystem allowlist is configured")
            )
        candidate = _resolve(self.base_dir, path)
        raw_allowed = filesystem.allow_read if mode == "read" else filesystem.allow_write
        allowed = [_resolve(self.base_dir, item) for item in raw_allowed]
        if not any(_is_relative_to(candidate, root) for root in allowed):
            raise PermissionDenied(
                PermissionReport(
                    f"filesystem.{mode}",
                    str(candidate),
                    f"Path is outside allowed {mode} roots",
                )
            )
        return candidate


def budget_exceeded_result(task_id: str, report: BudgetReport) -> TaskResult:
    return make_task_result(
        task_id,
        Outcome.BUDGET_EXCEEDED.value,
        reason=report.reason,
        output={"status": Outcome.BUDGET_EXCEEDED.value, "budget_report": report.to_dict()},
    )


def need_permission_result(task_id: str, report: PermissionReport) -> TaskResult:
    return make_task_result(
        task_id,
        Outcome.NEED_PERMISSION.value,
        reason=report.reason,
        output={"status": Outcome.NEED_PERMISSION.value, "permission_report": report.to_dict()},
        request={"permission": report.permission, "requested": report.requested},
    )


def _resolve(base_dir: Path, path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    return candidate.resolve()


def _is_relative_to(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True
