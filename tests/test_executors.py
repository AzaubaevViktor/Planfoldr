from pathlib import Path

from planfoldr.executors import ExecutorRegistry, StubModelAdapter
from planfoldr.guards import BudgetTracker, PermissionEngine
from planfoldr.loader import load_scenario
from planfoldr.runtime import run_scenario
from planfoldr.schema import Executor, Task


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


def test_write_files_uses_latest_model_output(tmp_path: Path) -> None:
    target = tmp_path / "project" / "AGENTS.md"
    loaded = load_scenario(FIXTURES / "executor_scenario.yaml")
    constraints = loaded.document.constraints.model_copy(deep=True)
    constraints.filesystem.allow_write.append(str(tmp_path))
    registry = ExecutorRegistry(
        permission_engine=PermissionEngine(
            constraints,
            base_dir=tmp_path,
        ),
        budget_tracker=BudgetTracker(loaded.document.budgets),
        task_outputs={
            "generate_project": {
                "status": "success",
                "files": [{"path": str(target), "content": "# Generated\n"}],
            }
        },
    )
    registry.permission_engine.constraints.filesystem.allow_write.append(str(tmp_path))
    task = Task(
        id="create_files",
        type="tool",
        task="Write generated files.",
        executor=Executor(kind="tool", tool="write_files"),
        input_schema={"type": "object"},
        output_schema={"type": "object", "required": ["status"]},
    )

    result = registry(task)

    assert result.status == "success"
    assert target.read_text(encoding="utf-8") == "# Generated\n"
