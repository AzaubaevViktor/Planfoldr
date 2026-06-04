from pathlib import Path

from planfoldr.cli import main


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
