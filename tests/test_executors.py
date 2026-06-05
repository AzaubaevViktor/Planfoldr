from pathlib import Path

from planfoldr.executors import ExecutorRegistry, ModelResponse, StubModelAdapter
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
    assert result.output["file_changes"][0]["action"] == "created"
    assert result.output["file_changes"][0]["bytes"] == len("# Generated\n".encode("utf-8"))


def test_write_files_ignores_tool_file_lists_when_finding_latest_model_output(tmp_path: Path) -> None:
    target = tmp_path / "project" / "ARCHITECTURE.md"
    loaded = load_scenario(FIXTURES / "executor_scenario.yaml")
    constraints = loaded.document.constraints.model_copy(deep=True)
    constraints.filesystem.allow_write.append(str(tmp_path))
    registry = ExecutorRegistry(
        permission_engine=PermissionEngine(constraints, base_dir=tmp_path),
        budget_tracker=BudgetTracker(loaded.document.budgets),
        task_outputs={
            "repair_project": {
                "status": "success",
                "files": [{"path": str(target), "content": "# Architecture\n"}],
            },
            "create_files": {
                "status": "success",
                "files": [str(tmp_path / "project" / "old.txt")],
            },
        },
    )
    task = Task(
        id="apply_repair",
        type="tool",
        task="Apply repaired files.",
        executor=Executor(kind="tool", tool="write_files"),
        input_schema={"type": "object"},
        output_schema={"type": "object", "required": ["status"]},
    )

    result = registry(task)

    assert result.status == "success"
    assert target.read_text(encoding="utf-8") == "# Architecture\n"


def test_command_templates_can_read_previous_task_outputs() -> None:
    loaded = load_scenario(FIXTURES / "executor_scenario.yaml")
    registry = ExecutorRegistry(
        permission_engine=PermissionEngine(loaded.document.constraints, base_dir=FIXTURES),
        budget_tracker=BudgetTracker(loaded.document.budgets),
        task_outputs={"previous": {"message": "from prior task"}},
    )
    task = Task(
        id="echo_previous",
        type="command",
        task="Echo previous output.",
        executor=Executor(
            kind="command",
            command="python3 -c \"print('{{ tasks.previous.output.message }}')\"",
            cwd=".",
        ),
        input_schema={"type": "object"},
        output_schema={"type": "object", "required": ["status"]},
    )

    result = registry(task)

    assert result.status == "success"
    assert result.output["stdout"] == "from prior task\n"


def test_model_tool_call_syntax_returns_need_tool_call() -> None:
    loaded = load_scenario(FIXTURES / "executor_scenario.yaml")
    registry = ExecutorRegistry(
        permission_engine=PermissionEngine(loaded.document.constraints, base_dir=FIXTURES),
        budget_tracker=BudgetTracker(loaded.document.budgets),
        model_adapter=RawTextModelAdapter(
            '<tool_call>{"name":"write_files","arguments":{"files":[{"path":"demo.txt"}]}}</tool_call>'
        ),
    )
    task = Task(
        id="call_tool",
        type="model",
        task="Ask for a tool call.",
        executor=Executor(kind="model"),
        input_schema={"type": "object"},
        output_schema={
            "type": "object",
            "required": ["status", "tool_call"],
            "properties": {"status": {"enum": ["need_tool_call"]}},
        },
    )

    result = registry(task)

    assert result.status == "need_tool_call"
    assert result.output["tool_call"]["name"] == "write_files"
    assert result.output["tool_call"]["arguments"]["files"][0]["path"] == "demo.txt"
    assert result.metadata["raw_response"].startswith("<tool_call>")


def test_malformed_model_tool_call_syntax_returns_diagnostic_failure() -> None:
    loaded = load_scenario(FIXTURES / "executor_scenario.yaml")
    registry = ExecutorRegistry(
        permission_engine=PermissionEngine(loaded.document.constraints, base_dir=FIXTURES),
        budget_tracker=BudgetTracker(loaded.document.budgets),
        model_adapter=RawTextModelAdapter("<tool_call>{not json}</tool_call>"),
    )
    task = Task(
        id="bad_tool_call",
        type="model",
        task="Ask for a bad tool call.",
        executor=Executor(kind="model"),
        input_schema={"type": "object"},
        output_schema={
            "type": "object",
            "required": ["status", "reason"],
            "properties": {"status": {"enum": ["failure"]}},
        },
    )

    result = registry(task)

    assert result.status == "failure"
    assert "Malformed <tool_call> JSON" in result.reason
    assert result.output["tool_call_error"]["category"] == "malformed_tool_call"


class RawTextModelAdapter:
    def __init__(self, text: str) -> None:
        self.text = text

    def generate(self, *, task, model, messages, config, tools, progress_callback=None):
        return ModelResponse(
            output={"status": "failure", "reason": "raw text"},
            raw=self.text,
            metadata={"adapter": "raw-text"},
        )
