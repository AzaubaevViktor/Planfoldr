import json
from pathlib import Path

import pytest

from planfoldr.executors import ExecutorRegistry, ModelResponse, StubModelAdapter
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

    result = run_and_trace(loaded, _registry(loaded), output_root=tmp_path, run_id="trace-test")

    trace_dir = tmp_path / "executor_scenario" / "trace-test" / "trace"
    report = tmp_path / "executor_scenario" / "trace-test" / "report.html"
    log_path = tmp_path / "executor_scenario" / "trace-test" / "logs" / "execution.log"
    assert result.status == "success"
    assert (trace_dir / "manifest.json").exists()
    assert (trace_dir / "tasks" / "executions.json").exists()
    assert log_path.exists()
    assert list((trace_dir / "models").glob("*.json"))
    assert list((trace_dir / "commands").glob("*.json"))
    assert "Execution Log" in report.read_text(encoding="utf-8")
    log_events = [json.loads(line)["event"] for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert log_events[:3] == ["run_initialized", "scenario_start", "task_start"]
    assert "task_finish" in log_events


def test_task_replay_restores_captured_result(tmp_path: Path) -> None:
    loaded = load_scenario(FIXTURES / "executor_scenario.yaml")
    result = run_and_trace(loaded, _registry(loaded), output_root=tmp_path, run_id="replay-test")

    replayed = replay_task(tmp_path / "executor_scenario" / "replay-test" / "trace", "ask_model")

    assert replayed.task_id == "ask_model"
    assert replayed.output == result.task_results[0].output


def test_run_and_trace_keeps_multiple_run_directories(tmp_path: Path) -> None:
    loaded = load_scenario(FIXTURES / "executor_scenario.yaml")

    run_and_trace(loaded, _registry(loaded), output_root=tmp_path, run_id="first-run")
    run_and_trace(loaded, _registry(loaded), output_root=tmp_path, run_id="second-run")

    scenario_dir = tmp_path / "executor_scenario"
    assert (scenario_dir / "first-run" / "trace" / "manifest.json").exists()
    assert (scenario_dir / "second-run" / "trace" / "manifest.json").exists()


def test_run_and_trace_writes_execution_log_before_task_error(tmp_path: Path) -> None:
    loaded = load_scenario(FIXTURES / "executor_scenario.yaml")

    def failing_executor(task):
        raise RuntimeError(f"boom in {task.id}")

    with pytest.raises(RuntimeError):
        run_and_trace(loaded, failing_executor, output_root=tmp_path, run_id="error-run")

    log_path = tmp_path / "executor_scenario" / "error-run" / "logs" / "execution.log"
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert [event["event"] for event in events] == [
        "run_initialized",
        "scenario_start",
        "task_start",
        "task_error",
        "scenario_error",
    ]
    assert events[3]["task_id"] == "ask_model"


def test_run_and_trace_writes_model_stream_progress_events(tmp_path: Path) -> None:
    loaded = load_scenario(FIXTURES / "executor_scenario.yaml")
    registry = ExecutorRegistry(
        permission_engine=PermissionEngine(loaded.document.constraints, base_dir=FIXTURES),
        budget_tracker=BudgetTracker(loaded.document.budgets),
        prompts=loaded.cycles[0].prompts,
        model_adapter=FakeStreamingModelAdapter(),
    )

    run_and_trace(loaded, registry, output_root=tmp_path, run_id="stream-run")

    log_path = tmp_path / "executor_scenario" / "stream-run" / "logs" / "execution.log"
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    progress = [event for event in events if event["event"] == "model_stream_progress"]
    assert progress
    assert progress[0]["task_id"] == "ask_model"
    assert progress[0]["tokens"]["source"] == "approximate"
    assert any(event["event"] == "model_stream_finish" for event in events)


def test_trace_writer_accepts_audit_and_decision_logs(tmp_path: Path) -> None:
    loaded = load_scenario(FIXTURES / "executor_scenario.yaml")
    result = run_and_trace(loaded, _registry(loaded), output_root=tmp_path / "first", run_id="manual-source")
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


class FakeStreamingModelAdapter:
    def generate(self, *, task, model, messages, config, tools, progress_callback=None):
        if progress_callback is not None:
            progress_callback(
                "model_stream_progress",
                {"chars": 640, "tokens": {"generated": 160, "source": "approximate"}},
            )
            progress_callback(
                "model_stream_finish",
                {"chars": 780, "tokens": {"generated": 195, "source": "provider"}},
            )
        return ModelResponse(
            output={"status": "success"},
            raw='{"status":"success"}',
            metadata={"adapter": "fake-streaming", "streaming": True},
        )
