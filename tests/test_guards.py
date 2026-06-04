from pathlib import Path

import pytest

from planfoldr.guards import (
    BudgetExceeded,
    BudgetTracker,
    PermissionDenied,
    PermissionEngine,
    budget_exceeded_result,
    need_permission_result,
)
from planfoldr.schema import Budgets, Constraints, FilesystemConstraint, ToolsConstraint


def test_budget_tracker_reports_exhaustion() -> None:
    tracker = BudgetTracker(Budgets(max_iterations=1, max_ram=1024))

    tracker.consume_iteration()
    with pytest.raises(BudgetExceeded) as exc_info:
        tracker.consume_iteration()

    report = exc_info.value.report
    assert report.limit == "max_iterations"
    assert report.ram_enforcement == "unsupported"

    result = budget_exceeded_result("task.one", report)
    assert result.status == "budget_exceeded"
    assert result.output["budget_report"]["limit"] == "max_iterations"


def test_model_budget_and_call_limits_are_tracked() -> None:
    tracker = BudgetTracker(Budgets(max_model_calls=2, max_model_budget=1.0))

    tracker.consume_model_call(budget_cost=0.4)
    tracker.consume_model_call(budget_cost=0.6)

    with pytest.raises(BudgetExceeded) as exc_info:
        tracker.consume_model_call(budget_cost=0.1)

    assert exc_info.value.report.limit == "max_model_calls"


def test_tool_allowlist_and_deny_rules_are_enforced() -> None:
    engine = PermissionEngine(
        constraints=Constraints(tools=ToolsConstraint(allow=["pytest", "git"], deny=["git push"])),
        base_dir=Path.cwd(),
    )

    engine.check_tool("pytest")

    with pytest.raises(PermissionDenied):
        engine.check_tool("python")

    with pytest.raises(PermissionDenied):
        engine.check_tool("git push")


def test_filesystem_allowlists_use_resolved_paths(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    engine = PermissionEngine(
        constraints=Constraints(
            filesystem=FilesystemConstraint(
                allow_read=[str(allowed)],
                allow_write=[str(allowed)],
            )
        ),
        base_dir=tmp_path,
    )

    assert engine.check_write_path(allowed / "file.txt") == (allowed / "file.txt").resolve()

    with pytest.raises(PermissionDenied) as exc_info:
        engine.check_write_path(outside / "file.txt")

    result = need_permission_result("task.write", exc_info.value.report)
    assert result.status == "need_permission"
    assert result.request == {
        "permission": "filesystem.write",
        "requested": str((outside / "file.txt").resolve()),
    }
