from types import SimpleNamespace

from planfoldr import cli
from planfoldr.scenario import ModelSettings, Scenario


def test_cli_extra_model_flags_build_multi_model_scenario(monkeypatch, tmp_path):
    base = Scenario(
        name="demo",
        goal_text="build it",
        budget={},
        model=ModelSettings(provider="ollama", name="gemma4:31b", parameter_count=31e9),
    )
    captured = {}

    def fake_load_scenario(path):
        assert path == "scenario.yaml"
        return base

    class FakeOrchestrator:
        def __init__(self, scenario, **kwargs):
            captured["scenario"] = scenario
            captured["kwargs"] = kwargs
            self.run_dir = tmp_path / "run"

        def run(self):
            return SimpleNamespace(
                status="done",
                run_dir=str(self.run_dir),
                cycles_run=0,
                tickets={},
                budget={},
            )

    monkeypatch.setattr(cli, "load_scenario", fake_load_scenario)
    monkeypatch.setattr("planfoldr.orchestrator.Orchestrator", FakeOrchestrator)

    args = cli.build_parser().parse_args([
        "run",
        "scenario.yaml",
        "--model",
        "devstral-small-2:24b",
        "--extra-model",
        "qwen3:14b",
        "--extra-model",
        "carstenuhlig/omnicoder-9b:latest",
        "--rotate-worker-models",
        "--visibility",
        "none",
    ])

    assert cli.cmd_run(args) == 0
    scenario = captured["scenario"]
    assert scenario.model.name == "devstral-small-2:24b"
    assert scenario.model.parameter_count == 24e9
    assert [m.name for m in scenario.extra_models] == [
        "qwen3:14b",
        "carstenuhlig/omnicoder-9b:latest",
    ]
    assert [m.parameter_count for m in scenario.extra_models] == [14e9, 9e9]
    assert captured["kwargs"]["rotate_worker_models"] is True
