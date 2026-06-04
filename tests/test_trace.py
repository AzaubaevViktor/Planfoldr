from pathlib import Path

from planfoldr.executors import ExecutorRegistry, StubModelAdapter
from planfoldr.guards import BudgetTracker, PermissionEngine
from planfoldr.loader import load_scenario
from planfoldr.trace import TraceWriter, replay_task, run_and_trace


FIXTURES = Path(__file__).parent / "fixtures" / "scenarios"


def _registry(loaded):
    return ExecutorRegistry(
        permission_engine=PermissionEngine(loaded.document.constraints, base_dir=FIXTURES),
        budget_tracker=BudgetTracker(loaded.document.budgets),
        prompts=loaded.cycles[0].prompts,
        model_adapter=StubModelAdapter({"ask_model:executor_prompt": {"status": "success"}}),
    )


def test_run_and_trace_writes_manifest_task_parts_and_report(tmp_path: Path) -> None:
    loaded = load_scenario(FIXTURES / "executor_scenario.yaml")

    result = run_and_trace(loaded, _registry(loaded), output_root=tmp_path)

    trace_dir = tmp_path / "executor_scenario" / "trace"
    report = tmp_path / "executor_scenario" / "report.html"
    assert result.status == "success"
    assert (trace_dir / "manifest.json").exists()
    assert (trace_dir / "tasks" / "executions.json").exists()
    assert list((trace_dir / "models").glob("*.json"))
    assert list((trace_dir / "commands").glob("*.json"))
    assert "Execution Log" in report.read_text(encoding="utf-8")


def test_task_replay_restores_captured_result(tmp_path: Path) -> None:
    loaded = load_scenario(FIXTURES / "executor_scenario.yaml")
    result = run_and_trace(loaded, _registry(loaded), output_root=tmp_path)

    replayed = replay_task(tmp_path / "executor_scenario" / "trace", "ask_model")

    assert replayed.task_id == "ask_model"
    assert replayed.output == result.task_results[0].output


def test_trace_writer_accepts_audit_and_decision_logs(tmp_path: Path) -> None:
    loaded = load_scenario(FIXTURES / "executor_scenario.yaml")
    result = run_and_trace(loaded, _registry(loaded), output_root=tmp_path / "first")
    writer = TraceWriter(
        loaded,
        result,
        trace_dir=tmp_path / "manual" / "trace",
        report_path=tmp_path / "manual" / "report.html",
        audit_events=[{"event_id": "audit_1"}],
        decisions=[{"decision_id": "decision_1"}],
    )

    writer.write()

    assert "audit_1" in (tmp_path / "manual" / "trace" / "audit.jsonl").read_text(encoding="utf-8")
    assert "decision_1" in (tmp_path / "manual" / "trace" / "decisions.jsonl").read_text(encoding="utf-8")
