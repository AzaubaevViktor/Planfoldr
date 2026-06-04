from pathlib import Path

from planfoldr.cli import _prompt_variables, _render_runtime_inputs, main


FIXTURES = Path(__file__).parent / "fixtures" / "scenarios"


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
    variables = _prompt_variables({"repository_path": "./project"}, run_id="run-1")

    assert variables["inputs.repository_path"] == "./project"
    assert variables["runtime.python"].endswith("python")
    assert variables["runtime.run_id"] == "run-1"
    assert variables["runtime"]["python"] == variables["runtime.python"]
    assert variables["runtime"]["run_id"] == "run-1"


def test_render_runtime_inputs_expands_run_id() -> None:
    inputs = _render_runtime_inputs(
        {"repository_path": "./runs/demo/{{ runtime.run_id }}/workspace/project"},
        run_id="run-2",
    )

    assert inputs["repository_path"] == "./runs/demo/run-2/workspace/project"
