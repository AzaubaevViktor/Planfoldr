from pathlib import Path

from planfoldr.executors import ExecutorRegistry, StubModelAdapter
from planfoldr.guards import BudgetTracker, PermissionEngine
from planfoldr.loader import load_scenario
from planfoldr.trace import run_and_trace


FIXTURES = Path(__file__).parent / "fixtures" / "scenarios"


def _run_stub(name: str, tmp_path: Path, responses, retries: int = 0):
    loaded = load_scenario(FIXTURES / name)
    registry = ExecutorRegistry(
        permission_engine=PermissionEngine(loaded.document.constraints, base_dir=FIXTURES),
        budget_tracker=BudgetTracker(loaded.document.budgets),
        prompts=loaded.cycles[0].prompts,
        model_adapter=StubModelAdapter(responses),
        invalid_output_retries=retries,
    )
    result = run_and_trace(loaded, registry, output_root=tmp_path)
    trace_dir = tmp_path / loaded.document.id / "trace"
    report = tmp_path / loaded.document.id / "report.html"
    assert trace_dir.exists()
    assert (trace_dir / "manifest.json").exists()
    assert report.exists()
    return result, trace_dir, report


def test_successful_stub_e2e_scenario(tmp_path: Path) -> None:
    result, trace_dir, report = _run_stub(
        "e2e_success_scenario.yaml",
        tmp_path,
        {"plan:e2e_stub_prompt": {"status": "success"}},
    )

    assert result.status == "success"
    assert [task.task_id for task in result.task_results] == ["plan", "verify"]
    assert "e2e_success_scenario" in report.read_text(encoding="utf-8")


def test_command_failure_stub_e2e_scenario(tmp_path: Path) -> None:
    result, _trace_dir, _report = _run_stub(
        "e2e_command_failure_scenario.yaml",
        tmp_path,
        {"*": {"status": "success"}},
    )

    assert result.status == "failure"
    assert result.task_results[0].task_id == "verify_failure"
    assert result.task_results[0].status == "failure"


def test_budget_exhaustion_stub_e2e_scenario(tmp_path: Path) -> None:
    result, _trace_dir, _report = _run_stub(
        "e2e_budget_scenario.yaml",
        tmp_path,
        {"model_task:e2e_stub_prompt": {"status": "success"}},
    )

    assert result.status == "failure"
    assert result.task_results[0].status == "budget_exceeded"


def test_retry_exhaustion_stub_e2e_scenario(tmp_path: Path) -> None:
    result, _trace_dir, _report = _run_stub(
        "e2e_retry_scenario.yaml",
        tmp_path,
        {"invalid_model:e2e_stub_prompt": [{"oops": True}, {"still": "bad"}]},
        retries=1,
    )

    assert result.status == "failure"
    assert result.task_results[0].status == "retry_exceeded"


def test_patch_loop_stub_e2e_scenario(tmp_path: Path) -> None:
    result, _trace_dir, _report = _run_stub(
        "e2e_patch_loop_scenario.yaml",
        tmp_path,
        {
            "create_initial:e2e_stub_prompt": {"status": "success"},
            "repair:e2e_stub_prompt": {"status": "success"},
        },
    )

    assert result.status == "success"
    assert [task.task_id for task in result.task_results] == [
        "create_initial",
        "verify_initial",
        "repair",
        "verify_repaired",
    ]
    assert result.task_results[1].status == "failure"
    assert result.task_results[-1].status == "success"
