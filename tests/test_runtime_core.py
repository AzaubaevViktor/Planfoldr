from pathlib import Path

import pytest

from planfoldr.loader import load_scenario
from planfoldr.runtime import (
    MissingLinkError,
    Outcome,
    StubExecutor,
    make_task_result,
    run_cycle,
    run_scenario,
)


FIXTURES = Path(__file__).parent / "fixtures" / "scenarios"


def test_scenario_runner_returns_success_for_linked_tasks() -> None:
    loaded = load_scenario(FIXTURES / "runtime_scenario.yaml")
    executor = StubExecutor({"first": Outcome.SUCCESS.value, "second": Outcome.SUCCESS.value})

    result = run_scenario(loaded, executor)

    assert result.status == "success"
    assert executor.calls == ["first", "second"]
    assert result.task_results[0].to_dict()["status"] == "success"


def test_cycle_runner_returns_failure_terminal_status() -> None:
    loaded = load_scenario(FIXTURES / "runtime_failure_scenario.yaml")
    executor = StubExecutor({"first": Outcome.FAILURE.value})

    result = run_scenario(loaded, executor)

    assert result.status == "failure"
    assert result.cycle_results[0].status == "failure"


def test_cycle_runner_rejects_missing_link_for_outcome() -> None:
    loaded = load_scenario(FIXTURES / "runtime_missing_link_scenario.yaml")
    executor = StubExecutor({"first": Outcome.NEED_CONTEXT.value})

    with pytest.raises(MissingLinkError):
        run_cycle(loaded.cycles[0], executor)


def test_parent_target_propagates_typed_request() -> None:
    loaded = load_scenario(FIXTURES / "runtime_parent_scenario.yaml")
    task_result = make_task_result(
        "first",
        Outcome.NEED_PERMISSION.value,
        request={"permission": "tool:git"},
    )
    executor = StubExecutor({"first": task_result})

    result = run_cycle(loaded.cycles[0], executor)

    assert result.status == "need_permission"
    assert result.request == {"permission": "tool:git"}
