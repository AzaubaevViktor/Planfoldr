from pathlib import Path

from planfoldr.executors import ExecutorRegistry, StubModelAdapter
from planfoldr.guards import BudgetTracker, PermissionEngine
from planfoldr.loader import load_scenario
from planfoldr.runtime import run_scenario


FIXTURES = Path(__file__).parent / "fixtures" / "scenarios"


def test_stub_model_and_command_run_through_runtime_path() -> None:
    loaded = load_scenario(FIXTURES / "executor_scenario.yaml")
    cycle = loaded.cycles[0]
    registry = ExecutorRegistry(
        permission_engine=PermissionEngine(loaded.document.constraints, base_dir=FIXTURES),
        budget_tracker=BudgetTracker(loaded.document.budgets),
        prompts=cycle.prompts,
        model_adapter=StubModelAdapter({"ask_model:executor_prompt": {"status": "success"}}),
    )

    result = run_scenario(loaded, registry)

    assert result.status == "success"
    assert [task.task_id for task in result.task_results] == ["ask_model", "run_command"]
    assert result.task_results[0].metadata["prompt"]["hash"].startswith("sha256:")
    assert result.task_results[1].output["stdout"] == "executor ok\n"


def test_disallowed_command_returns_need_permission() -> None:
    loaded = load_scenario(FIXTURES / "executor_scenario.yaml")
    command_task = loaded.cycles[0].document.tasks[1].model_copy(
        update={"executor": loaded.cycles[0].document.tasks[1].executor.model_copy(update={"command": "git push"})}
    )
    registry = ExecutorRegistry(
        permission_engine=PermissionEngine(loaded.document.constraints, base_dir=FIXTURES),
        budget_tracker=BudgetTracker(loaded.document.budgets),
        prompts=loaded.cycles[0].prompts,
    )

    result = registry(command_task)

    assert result.status == "need_permission"
    assert result.request["permission"] == "command"
