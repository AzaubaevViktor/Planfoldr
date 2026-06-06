from pathlib import Path

from planfoldr.cli import _prompt_variables, _render_runtime_inputs, apply_runtime_context, main
from planfoldr.loader import load_scenario


FIXTURES = Path(__file__).parent / "fixtures" / "scenarios"
EXAMPLES = Path(__file__).parents[1] / "examples" / "scenarios"


def test_cli_runs_yaml_scenario_and_writes_artifacts(tmp_path: Path, capsys) -> None:
    exit_code = main(
        [
            "run",
            str(FIXTURES / "executor_scenario.yaml"),
            "--base-dir",
            str(FIXTURES),
            "--output-root",
            str(tmp_path),
            "--run-id",
            "cli-test",
        ]
    )

    output = capsys.readouterr().out
    run_dir = tmp_path / "executor_scenario" / "cli-test"
    assert exit_code == 0
    assert "status=success" in output
    assert (run_dir / "logs" / "execution.log").exists()
    assert (run_dir / "trace" / "manifest.json").exists()
    assert (run_dir / "report.html").exists()


def test_prompt_variables_include_runtime_python() -> None:
    runtime = {
        "python": "python-bin",
        "run_id": "run-1",
        "run_dir": "runs/demo/run-1",
        "workspace_dir": "runs/demo/run-1/workspace",
    }
    variables = _prompt_variables({"repository_path": "./project"}, runtime=runtime)

    assert variables["inputs.repository_path"] == "./project"
    assert variables["runtime.python"] == "python-bin"
    assert variables["runtime.run_id"] == "run-1"
    assert variables["runtime.run_dir"] == "runs/demo/run-1"
    assert variables["runtime.workspace_dir"] == "runs/demo/run-1/workspace"
    assert variables["runtime"]["python"] == variables["runtime.python"]
    assert variables["runtime"]["run_id"] == "run-1"


def test_render_runtime_inputs_expands_run_id() -> None:
    inputs = _render_runtime_inputs(
        {
            "repository_path": "{{ runtime.workspace_dir }}/project",
            "report_path": "{{ runtime.run_dir }}/report.html",
        },
        runtime={
            "python": "python-bin",
            "run_id": "run-2",
            "run_dir": "./runs/demo/run-2",
            "workspace_dir": "./runs/demo/run-2/workspace",
        },
    )

    assert inputs["repository_path"] == "./runs/demo/run-2/workspace/project"
    assert inputs["report_path"] == "./runs/demo/run-2/report.html"


def test_apply_runtime_context_isolates_example_workspaces_per_run(tmp_path: Path) -> None:
    first = load_scenario(EXAMPLES / "ollama_cli_todo_app.yaml")
    second = load_scenario(EXAMPLES / "ollama_cli_todo_app.yaml")

    first_runtime = apply_runtime_context(first, output_root=tmp_path, run_id="first-run")
    second_runtime = apply_runtime_context(second, output_root=tmp_path, run_id="second-run")

    assert first.document.inputs["workspace_root"] == str(tmp_path / first.document.id / "first-run" / "workspace")
    assert second.document.inputs["workspace_root"] == str(tmp_path / second.document.id / "second-run" / "workspace")
    assert first.document.inputs["repository_path"] != second.document.inputs["repository_path"]
    assert first.document.inputs["repository_path"].startswith(first_runtime["workspace_dir"])
    assert second.document.inputs["repository_path"].startswith(second_runtime["workspace_dir"])
    assert first.document.constraints.filesystem.allow_write == [first_runtime["run_dir"]]
    assert second.document.constraints.filesystem.allow_write == [second_runtime["run_dir"]]
