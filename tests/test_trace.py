import json
from pathlib import Path

import pytest

from planfoldr.executors import ExecutorRegistry, ModelResponse, StubModelAdapter
from planfoldr.guards import BudgetTracker, PermissionEngine
from planfoldr.loader import load_scenario
from planfoldr.runtime import Outcome, ScenarioResult, CycleResult, make_task_result
from planfoldr.trace import TraceWriter, _status_work_flow_html, replay_task, run_and_trace


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
    assert (trace_dir / "scenario.json").exists()
    assert (trace_dir / "scenario_definition.json").exists()
    assert (trace_dir / "status.json").exists()
    assert (trace_dir / "artifacts.json").exists()
    assert (trace_dir / "report_data.json").exists()
    assert (trace_dir / "tasks" / "executions.json").exists()
    assert (trace_dir / "cycles" / "executor_cycle.json").exists()
    assert list((trace_dir / "tasks" / "model").glob("*/status.json"))
    assert list((trace_dir / "tasks" / "model").glob("*/input.json"))
    assert list((trace_dir / "tasks" / "model").glob("*/context.json"))
    assert list((trace_dir / "tasks" / "model").glob("*/output.json"))
    assert list((trace_dir / "tasks" / "command").glob("*/status.json"))
    assert log_path.exists()
    assert list((trace_dir / "models").glob("*.json"))
    assert list((trace_dir / "commands").glob("*.json"))
    assert list((trace_dir / "models" / "deterministic").glob("*/status.json"))
    assert list((trace_dir / "models" / "deterministic").glob("*/input.json"))
    assert list((trace_dir / "models" / "deterministic").glob("*/context.json"))
    assert list((trace_dir / "models" / "deterministic").glob("*/output.json"))
    assert list((trace_dir / "commands").glob("*/*/status.json"))
    assert list((trace_dir / "inputs").glob("*.json"))
    status = json.loads((trace_dir / "status.json").read_text(encoding="utf-8"))
    scenario_trace = json.loads((trace_dir / "scenario.json").read_text(encoding="utf-8"))
    scenario_definition = json.loads((trace_dir / "scenario_definition.json").read_text(encoding="utf-8"))
    assert status["status"] == "success"
    assert scenario_trace["status"] == "success"
    assert scenario_trace["definition"] == "scenario_definition.json"
    assert scenario_trace["cycles"][0]["artifact"] == "cycles/executor_cycle.json"
    assert scenario_definition["id"] == "executor_scenario"
    assert status["budget"]["usage"]["iterations"] == 2
    assert status["budget"]["remaining"]["max_model_calls"] == 2
    assert any(item["status"] == "succeeded" for item in status["work"])
    manifest = json.loads((trace_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["report_data"]["status"] == "trace/status.json"
    assert manifest["report_data"]["report_snapshot"] == "trace/report_data.json"
    assert manifest["report_data"]["scenario_definition"] == "trace/scenario_definition.json"
    assert "cycles/executor_cycle.json" in manifest["cycles"]
    artifacts = json.loads((trace_dir / "artifacts.json").read_text(encoding="utf-8"))
    assert any(item["kind"] == "task_input" for item in artifacts["artifacts"])
    assert any(item["kind"] == "report_data" for item in artifacts["artifacts"])
    report_data = json.loads((trace_dir / "report_data.json").read_text(encoding="utf-8"))
    assert report_data["execution_log"] == "logs/execution.log"
    assert report_data["scenario"]["status"] == "success"
    assert report_data["cycle_artifacts"][0]["path"] == "trace/cycles/executor_cycle.json"
    assert report_data["task_executions"][0]["cycle_id"] == "executor_cycle"
    assert report_data["task_executions"][0]["budget_after"]["usage"]["iterations"] == 1
    assert report_data["task_executions"][0]["task_artifact_dir"].startswith("trace/tasks/model/")
    assert report_data["task_inputs"][0]["path"].startswith("trace/inputs/")
    assert report_data["task_inputs"][0]["task_artifact_dir"].startswith("trace/tasks/model/")
    assert report_data["task_inputs"][0]["executor_artifact_dir"].startswith("trace/models/deterministic/")
    assert report_data["model_outputs"][0]["model_artifact_dir"].startswith("trace/models/deterministic/")
    assert report_data["model_outputs"][0]["stream"].startswith("trace/models/")
    report_text = report.read_text(encoding="utf-8")
    assert "Starting <code>executor_scenario</code>" in report_text
    assert "additional info" in report_text
    assert "executor_cycle: start -&gt; [ask_model] -&gt; run_command" in report_text
    assert "model: deterministic goal executor_prompt" in report_text
    assert "command: python3 -c &quot;print(&#x27;executor ok&#x27;)&quot; in " in report_text
    assert "tests/fixtures/scenarios" in report_text
    assert "result: success" in report_text
    assert "Source" in report_text
    assert "Context" in report_text
    assert "Input" in report_text
    assert "Model Content" in report_text
    assert "Final Output" in report_text
    assert "Updated Context" in report_text
    assert "Context Diff" in report_text
    assert "Status" in report_text
    assert "Budget Spent" in report_text
    assert "Budget Remaining" in report_text
    assert "Duration" in report_text
    assert "&quot;iterations&quot;" in report_text
    assert "&quot;model_tokens&quot;" in report_text
    assert "&quot;model_cost_usd&quot;" in report_text
    assert "trace/tasks/model/" in report_text
    assert "<table" not in report_text
    assert "Task Executions" not in report_text
    assert "Refresh Report Data" not in report_text
    assert "cut with" not in report_text
    assert "<script" not in report_text
    assert report_text.rstrip().endswith("</main>\n</body>\n</html>")
    log_events = [json.loads(line)["event"] for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert log_events[:3] == ["run_initialized", "scenario_start", "task_start"]
    assert "task_finish" in log_events


def test_trace_records_cycle_membership_for_repeated_task_ids(tmp_path: Path) -> None:
    loaded = load_scenario(FIXTURES / "multi_cycle_report_scenario.yaml")

    run_and_trace(loaded, _registry(loaded), output_root=tmp_path, run_id="cycle-report")

    trace_dir = tmp_path / "multi_cycle_report_scenario" / "cycle-report" / "trace"
    task_records = json.loads((trace_dir / "tasks" / "executions.json").read_text(encoding="utf-8"))
    assert [
        (record["cycle_id"], record["cycle_path"], record["task_id"])
        for record in task_records
    ] == [
        ("report_first_cycle", "report_first_cycle", "shared_task"),
        ("report_second_cycle", "report_second_cycle", "shared_task"),
    ]
    cycle_records = json.loads((trace_dir / "cycles" / "index.json").read_text(encoding="utf-8"))
    assert [record["cycle_path"] for record in cycle_records] == [
        "report_first_cycle",
        "report_second_cycle",
    ]
    report_text = (tmp_path / "multi_cycle_report_scenario" / "cycle-report" / "report.html").read_text(
        encoding="utf-8"
    )
    assert "report_first_cycle: start -&gt; [shared_task] -&gt; finish" in report_text
    assert "cycle down from report_first_cycle to report_second_cycle" in report_text
    assert "report_second_cycle: start -&gt; [shared_task] -&gt; finish" in report_text


def test_live_work_flow_marks_active_cycle_level_and_task() -> None:
    report_text = _status_work_flow_html(
        {
            "current_cycle_id": "ollama_notes_repair",
            "current_task_id": "setup_repo",
            "work": [
                {
                    "cycle_id": "ollama_notes_plan",
                    "task_id": "plan_notes_project",
                    "executor_kind": "model",
                    "status": "succeeded",
                },
                {
                    "cycle_id": "ollama_notes_repair",
                    "task_id": "setup_workspace",
                    "executor_kind": "command",
                    "status": "succeeded",
                },
                {
                    "cycle_id": "ollama_notes_repair",
                    "task_id": "setup_repo",
                    "executor_kind": "command",
                    "status": "running",
                },
                {
                    "cycle_id": "ollama_notes_repair",
                    "task_id": "generate_notes_project",
                    "executor_kind": "model",
                    "status": "queued",
                },
            ],
        }
    )

    assert (
        "<p class='line task-level-muted'>ollama_notes_plan: start -&gt; "
        "[plan_notes_project] -&gt; finish</p>"
    ) in report_text
    assert (
        "<p class='line task-level-current'>ollama_notes_repair: setup_workspace -&gt; "
        "[<strong>setup_repo</strong>] -&gt; generate_notes_project</p>"
    ) in report_text
    assert "result: queued" not in report_text
    assert "ollama_notes_plan: plan_notes_project -&gt; [setup_workspace]" not in report_text


def test_report_labels_cycle_down_and_cycle_up_transitions(tmp_path: Path) -> None:
    loaded = load_scenario(FIXTURES / "multi_cycle_report_scenario.yaml")
    result = ScenarioResult(
        scenario_id=loaded.document.id,
        status=Outcome.SUCCESS.value,
        cycle_results=[
            CycleResult(
                cycle_id="parent",
                cycle_path="parent",
                status=Outcome.SUCCESS.value,
                task_results=[make_task_result("root_task", Outcome.SUCCESS.value)],
            ),
            CycleResult(
                cycle_id="child",
                cycle_path="parent/child",
                status=Outcome.SUCCESS.value,
                task_results=[make_task_result("child_task", Outcome.SUCCESS.value)],
            ),
            CycleResult(
                cycle_id="parent",
                cycle_path="parent",
                status=Outcome.SUCCESS.value,
                task_results=[make_task_result("return_task", Outcome.SUCCESS.value)],
            ),
        ],
    )

    TraceWriter(
        loaded,
        result,
        trace_dir=tmp_path / "cycle-direction" / "trace",
        report_path=tmp_path / "cycle-direction" / "report.html",
    ).write()

    report_text = (tmp_path / "cycle-direction" / "report.html").read_text(encoding="utf-8")
    assert "cycle down from parent to parent/child" in report_text
    assert "cycle up from parent/child to parent" in report_text
    assert "cycle up/down" not in report_text


def test_trace_writes_report_readable_task_inputs(tmp_path: Path) -> None:
    loaded = load_scenario(FIXTURES / "executor_scenario.yaml")

    run_and_trace(loaded, _registry(loaded), output_root=tmp_path, run_id="inputs-test")

    trace_dir = tmp_path / "executor_scenario" / "inputs-test" / "trace"
    input_artifacts = {
        json.loads(path.read_text(encoding="utf-8"))["executor"]: json.loads(path.read_text(encoding="utf-8"))
        for path in (trace_dir / "inputs").glob("*.json")
    }
    assert input_artifacts["model"]["messages"][0]["content"]
    assert input_artifacts["model"]["config"]["prompt_id"] == "executor_prompt"
    assert input_artifacts["command"]["command"] == "python3 -c \"print('executor ok')\""
    assert input_artifacts["command"]["env"] == {"PATH": "<inherited>"}


def test_report_renders_json_blocks_with_highlighted_links_and_collapsible_nodes(tmp_path: Path) -> None:
    loaded = load_scenario(FIXTURES / "executor_scenario.yaml")

    run_and_trace(loaded, _registry(loaded), output_root=tmp_path, run_id="json-view")

    report_text = (tmp_path / "executor_scenario" / "json-view" / "report.html").read_text(encoding="utf-8")
    assert ".report-pre, .json-block { border: 1px solid #d1d5db; background: #f3f4f6;" in report_text
    assert "<details open class='json-block'>" in report_text
    assert "<details open class='json-node json-collection'>" in report_text
    assert "<span class='json-key'>&quot;status&quot;</span>" in report_text
    assert "<span class='json-punctuation'>{</span>" in report_text
    assert "<span class='json-string'>&quot;success&quot;</span>" in report_text
    assert "class='json-string json-link' href='trace/models/deterministic/" in report_text


def test_trace_persists_model_retry_feedback_in_task_input(tmp_path: Path) -> None:
    loaded = load_scenario(FIXTURES / "validation_scenario.yaml")
    registry = ExecutorRegistry(
        permission_engine=PermissionEngine(loaded.document.constraints, base_dir=FIXTURES),
        budget_tracker=BudgetTracker(loaded.document.budgets),
        prompts=loaded.cycles[0].prompts,
        model_adapter=StubModelAdapter({"validate_model:validation_prompt": [{"oops": True}, {"status": "success"}]}),
        invalid_output_retries=1,
    )

    run_and_trace(loaded, registry, output_root=tmp_path, run_id="retry-feedback")

    trace_dir = tmp_path / "validation_scenario" / "retry-feedback" / "trace"
    input_path = next((trace_dir / "tasks" / "model").glob("*/input.json"))
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    assert payload["prompt"]["retry_feedback"]["category"] == "output_validation"
    assert payload["prompt"]["retry_feedback"]["path"] == "$.status"
    assert "Previous attempt failed" in payload["messages"][0]["content"]
    report_text = (tmp_path / "validation_scenario" / "retry-feedback" / "report.html").read_text(encoding="utf-8")
    assert "Retry Feedback" in report_text
    assert "output_validation" in report_text


def test_trace_writes_model_raw_response_as_separate_artifact(tmp_path: Path) -> None:
    loaded = load_scenario(FIXTURES / "executor_scenario.yaml")

    run_and_trace(loaded, _registry(loaded), output_root=tmp_path, run_id="raw-artifact")

    trace_dir = tmp_path / "executor_scenario" / "raw-artifact" / "trace"
    task_records = json.loads((trace_dir / "tasks" / "executions.json").read_text(encoding="utf-8"))
    model_record = next(record for record in task_records if record["task_id"] == "ask_model")
    execution_id = model_record["execution_id"]
    raw_artifact = trace_dir / "models" / execution_id / "raw_response.txt"
    model_metadata = json.loads((trace_dir / "models" / f"{execution_id}.json").read_text(encoding="utf-8"))
    report_data = json.loads((trace_dir / "report_data.json").read_text(encoding="utf-8"))

    assert raw_artifact.read_text(encoding="utf-8") == '{"status": "success"}'
    assert "raw_response" not in model_record["metadata"]
    assert "raw_response" not in model_metadata
    assert model_metadata["raw_response_artifact"] == f"models/{execution_id}/raw_response.txt"
    assert model_metadata["raw_response_chars"] == len('{"status": "success"}')
    assert model_record["metadata"]["raw_response_artifact"] == f"models/{execution_id}/raw_response.txt"
    assert report_data["model_outputs"][0]["raw_response"] == f"trace/models/{execution_id}/raw_response.txt"
    assert '{"status": "success"}' not in (trace_dir / "tasks" / "executions.json").read_text(encoding="utf-8")
    assert '{"status": "success"}' not in (trace_dir / "report_data.json").read_text(encoding="utf-8")


def test_trace_extracts_large_json_strings_to_adjacent_artifacts(tmp_path: Path) -> None:
    loaded = load_scenario(FIXTURES / "executor_scenario.yaml")
    long_stdout = "large output\n" * 120
    task = make_task_result(
        "run_command",
        Outcome.SUCCESS.value,
        execution_id="exec_large_stdout",
        output={"status": "success", "stdout": long_stdout, "stderr": ""},
        metadata={"executor": "command", "command": "python3 -c ...", "cwd": "."},
    )
    tool_task = make_task_result(
        "write_files",
        Outcome.SUCCESS.value,
        execution_id="exec_tool",
        output={
            "status": "success",
            "files": ["demo.txt"],
            "file_changes": [
                {
                    "path": "demo.txt",
                    "action": "created",
                    "bytes": 12,
                    "lines_added": 1,
                    "lines_removed": 0,
                    "before_bytes": 0,
                    "after_bytes": 12,
                    "before_sha256": None,
                    "after_sha256": "sha256:demo-after",
                }
            ],
            "diff_summary": {
                "files_changed": 1,
                "files_deleted": 0,
                "lines_added": 1,
                "lines_removed": 0,
            },
        },
        metadata={"executor": "tool", "tool": "write_files"},
    )
    result = ScenarioResult(
        scenario_id=loaded.document.id,
        status=Outcome.SUCCESS.value,
        cycle_results=[
            CycleResult(
                cycle_id=loaded.cycles[0].document.id,
                cycle_path=loaded.cycles[0].document.id,
                status=Outcome.SUCCESS.value,
                task_results=[task, tool_task],
            )
        ],
    )

    TraceWriter(
        loaded,
        result,
        trace_dir=tmp_path / "large" / "trace",
        report_path=tmp_path / "large" / "report.html",
    ).write()

    trace_dir = tmp_path / "large" / "trace"
    task_records = json.loads((trace_dir / "tasks" / "executions.json").read_text(encoding="utf-8"))
    command_metadata = json.loads((trace_dir / "commands" / "exec_large_stdout.json").read_text(encoding="utf-8"))

    task_stdout_path = task_records[0]["output"]["stdout"]
    command_stdout_path = command_metadata["output"]["stdout"]
    assert task_stdout_path == "tasks/executions.0.output.stdout.txt"
    assert command_stdout_path == "commands/exec_large_stdout.output.stdout.txt"
    assert (trace_dir / task_stdout_path).read_text(encoding="utf-8") == long_stdout
    assert (trace_dir / command_stdout_path).read_text(encoding="utf-8") == long_stdout
    assert long_stdout not in (trace_dir / "tasks" / "executions.json").read_text(encoding="utf-8")
    assert long_stdout not in (trace_dir / "commands" / "exec_large_stdout.json").read_text(encoding="utf-8")
    assert replay_task(trace_dir, "run_command").output["stdout"] == long_stdout
    artifacts = json.loads((trace_dir / "artifacts.json").read_text(encoding="utf-8"))["artifacts"]
    assert {"kind": "task_execution", "path": f"trace/{task_stdout_path}"} in artifacts
    assert {"kind": "command", "path": f"trace/{command_stdout_path}"} in artifacts
    assert (trace_dir / "tools" / "write_files" / "exec_tool" / "status.json").exists()
    assert (trace_dir / "tools" / "write_files" / "exec_tool" / "output.json").exists()
    report_text = (tmp_path / "large" / "report.html").read_text(encoding="utf-8")
    assert "File Changes" in report_text
    assert "short diff: 1 files changed, 0 deleted, +1 -0" in report_text
    assert "tool: write_files" in report_text
    assert "result: success" in report_text
    assert "File Changes" in report_text
    assert "additional info" in report_text
    assert "0-&gt;12 byte(s), none -> sha256:demo-after" in report_text
    assert "demo.txt" in report_text


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

    trace_dir = tmp_path / "executor_scenario" / "error-run" / "trace"
    log_path = tmp_path / "executor_scenario" / "error-run" / "logs" / "execution.log"
    status = json.loads((trace_dir / "status.json").read_text(encoding="utf-8"))
    report_data = json.loads((trace_dir / "report_data.json").read_text(encoding="utf-8"))
    assert status["status"] == "error"
    assert report_data["status"]["status"] == "error"
    report_text = (tmp_path / "executor_scenario" / "error-run" / "report.html").read_text(encoding="utf-8")
    assert "Starting <code>executor_scenario</code>" in report_text
    assert "Status</strong><br>error" in report_text
    assert "executor_cycle: start -&gt; [ask_model] -&gt; run_command" in report_text
    assert "result: failed (boom in ask_model)" in report_text
    assert "<table" not in report_text
    assert "Refresh Report Data" not in report_text
    assert "cut with" not in report_text
    assert "<script" not in report_text
    assert report_text.rstrip().endswith("</main>\n</body>\n</html>")
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
    assert "partial content" not in log_path.read_text(encoding="utf-8")

    execution_id = next(event["execution_id"] for event in events if event["event"] == "model_stream_start")
    stream_dir = tmp_path / "executor_scenario" / "stream-run" / "trace" / "models" / execution_id
    stream_rows = [
        json.loads(line)
        for line in (stream_dir / "stream.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert stream_rows == [
        {
            "chars": 9,
            "content_chars": 0,
            "cumulative_chars": 9,
            "kind": "thinking",
            "sequence": 1,
            "text": "thinking ",
            "thinking_chars": 9,
            "tokens": None,
        },
        {
            "chars": 15,
            "content_chars": 15,
            "cumulative_chars": 24,
            "kind": "content",
            "sequence": 2,
            "text": "partial content",
            "thinking_chars": 9,
            "tokens": None,
        },
    ]
    assert not (stream_dir / "chunks").exists()
    assert (stream_dir / "assembled.txt").read_text(encoding="utf-8") == "thinking partial content"
    assert (stream_dir / "content.txt").read_text(encoding="utf-8") == "partial content"
    report_text = (tmp_path / "executor_scenario" / "stream-run" / "report.html").read_text(encoding="utf-8")
    assert "model: deterministic goal executor_prompt" in report_text
    assert "Generation" in report_text
    assert "<summary>thinking</summary>" in report_text
    assert "partial content" in report_text
    assert "thinking " in report_text
    model_metadata = json.loads(
        (tmp_path / "executor_scenario" / "stream-run" / "trace" / "models" / f"{execution_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert model_metadata["stream_artifacts"]["content"] == f"models/{execution_id}/content.txt"
    assert model_metadata["stream_artifacts"]["stream"] == f"models/{execution_id}/stream.jsonl"


def test_live_report_shows_streaming_output_before_model_finishes(tmp_path: Path) -> None:
    loaded = load_scenario(FIXTURES / "executor_scenario.yaml")
    report_path = tmp_path / "executor_scenario" / "live-stream-run" / "report.html"
    adapter = InspectingStreamingModelAdapter(report_path)
    registry = ExecutorRegistry(
        permission_engine=PermissionEngine(loaded.document.constraints, base_dir=FIXTURES),
        budget_tracker=BudgetTracker(loaded.document.budgets),
        prompts=loaded.cycles[0].prompts,
        model_adapter=adapter,
    )

    run_and_trace(loaded, registry, output_root=tmp_path, run_id="live-stream-run")

    assert adapter.live_report_snapshots
    live_report = adapter.live_report_snapshots[0]
    assert '<meta http-equiv="refresh"' not in live_report
    assert "planfoldr-live-pause-until" in live_report
    assert "window.clearTimeout(reloadTimer)" in live_report
    assert "window.location.reload()" in live_report
    assert "data-live-summary" in live_report
    assert '!event.target.hasAttribute("data-live-summary")' not in live_report
    assert "executor_cycle / ask_model" in live_report
    assert "streaming output is updating" in live_report
    assert "Generation" in live_report
    assert "live partial content" in live_report
    assert "result: running" in live_report
    assert (
        "executor_cycle: start -&gt; [<strong>ask_model</strong>] -&gt; run_command"
        in live_report
    )
    assert "queued" not in live_report


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


def test_report_summarizes_ollama_raw_response_jsonl(tmp_path: Path) -> None:
    loaded = load_scenario(FIXTURES / "executor_scenario.yaml")
    task = make_task_result(
        "ask_model",
        Outcome.SUCCESS.value,
        execution_id="exec_raw",
        metadata={
            "executor": "model",
            "model": {"provider": "ollama", "name": "carstenuhlig/omnicoder-9b:latest"},
            "raw_response": "\n".join(
                [
                    '{"model":"carstenuhlig/omnicoder-9b:latest","message":{"content":"{"},"done":false}',
                    '{"model":"carstenuhlig/omnicoder-9b:latest","message":{"content":"}"},"done":true}',
                ]
            ),
        },
    )
    result = ScenarioResult(
        scenario_id=loaded.document.id,
        status=Outcome.SUCCESS.value,
        cycle_results=[
            CycleResult(
                cycle_id=loaded.cycles[0].document.id,
                cycle_path=loaded.cycles[0].document.id,
                status=Outcome.SUCCESS.value,
                task_results=[task],
            )
        ],
    )

    TraceWriter(
        loaded,
        result,
        trace_dir=tmp_path / "raw" / "trace",
        report_path=tmp_path / "raw" / "report.html",
    ).write()

    report = (tmp_path / "raw" / "report.html").read_text(encoding="utf-8")
    assert "Raw response omitted from HTML: this is Ollama provider streaming JSONL" in report
    assert "&quot;message&quot;" not in report


class FakeStreamingModelAdapter:
    def generate(self, *, task, model, messages, config, tools, progress_callback=None):
        if progress_callback is not None:
            progress_callback(
                "model_stream_chunk",
                {"kind": "thinking", "text": "thinking ", "chars": 9, "thinking_chars": 9, "content_chars": 0},
            )
            progress_callback(
                "model_stream_chunk",
                {
                    "kind": "content",
                    "text": "partial content",
                    "chars": 24,
                    "thinking_chars": 9,
                    "content_chars": 15,
                },
            )
            progress_callback(
                "model_stream_progress",
                {
                    "chars": 640,
                    "thinking_chars": 9,
                    "content_chars": 15,
                    "tokens": {"generated": 160, "source": "approximate"},
                },
            )
            progress_callback(
                "model_stream_finish",
                {
                    "chars": 780,
                    "thinking_chars": 9,
                    "content_chars": 15,
                    "tokens": {"generated": 195, "source": "provider"},
                },
            )
        return ModelResponse(
            output={"status": "success"},
            raw='{"status":"success"}',
            metadata={"adapter": "fake-streaming", "streaming": True},
        )


class InspectingStreamingModelAdapter:
    def __init__(self, report_path: Path) -> None:
        self.report_path = report_path
        self.live_report_snapshots: list[str] = []

    def generate(self, *, task, model, messages, config, tools, progress_callback=None):
        if progress_callback is not None:
            progress_callback(
                "model_stream_chunk",
                {
                    "kind": "content",
                    "text": "live partial content",
                    "chars": 20,
                    "thinking_chars": 0,
                    "content_chars": 20,
                },
            )
            self.live_report_snapshots.append(self.report_path.read_text(encoding="utf-8"))
            progress_callback(
                "model_stream_finish",
                {
                    "chars": 20,
                    "thinking_chars": 0,
                    "content_chars": 20,
                    "tokens": {"generated": 5, "source": "provider"},
                },
            )
        return ModelResponse(
            output={"status": "success"},
            raw='{"status":"success"}',
            metadata={"adapter": "inspecting-streaming", "streaming": True},
        )
