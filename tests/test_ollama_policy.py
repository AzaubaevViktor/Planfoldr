import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from planfoldr.cli import _comparison_run_summary, main
from planfoldr.ollama_policy import (
    classify_ollama_model,
    eligible_ollama_models,
    infer_parameter_b,
    parse_ollama_list,
    validate_ollama_model_name,
)


OLLAMA_LIST = """NAME                                                    ID              SIZE      MODIFIED
gemma3:12b                                              f4031aab637d    8.1 GB    9 hours ago
batiai/qwen3.5-9b:q6                                    43e7bee2201a    7.4 GB    9 hours ago
cleex/gemma-4-31B-it-Claude-Opus-Distill-GGUF:latest    09b1dc54d9c7    19 GB     46 hours ago
devstral-small-2:24b                                    24277f07f62d    15 GB     2 weeks ago
"""


def test_parse_ollama_list_records_policy_decisions() -> None:
    candidates = parse_ollama_list(OLLAMA_LIST)

    accepted = [candidate.name for candidate in eligible_ollama_models(candidates)]
    skipped = {candidate.name: candidate.reason for candidate in candidates if not candidate.accepted}

    assert accepted == ["gemma3:12b", "batiai/qwen3.5-9b:q6"]
    assert candidates[0].size_gb == 8.1
    assert candidates[0].parameter_b == 12
    assert "31B" in skipped["cleex/gemma-4-31B-it-Claude-Opus-Distill-GGUF:latest"]
    assert "installed size 19 GB exceeds 12 GB" in skipped["cleex/gemma-4-31B-it-Claude-Opus-Distill-GGUF:latest"]
    assert "24B" in skipped["devstral-small-2:24b"]


def test_infer_parameter_b_uses_largest_hint() -> None:
    assert infer_parameter_b("qwen3.5:35b-a3b-coding-nvfp4") == 35
    assert infer_parameter_b("gemma3:12b") == 12
    assert infer_parameter_b("hf.co/vendor/model:q4_k_m") is None


def test_validate_ollama_model_name_rejects_obvious_large_model() -> None:
    with pytest.raises(ValueError, match="above the Planfoldr demo limit"):
        validate_ollama_model_name("qwen3-coder:30b")


def test_run_cli_rejects_large_ollama_model(capsys) -> None:
    exit_code = main(
        [
            "run",
            "examples/scenarios/ollama_cli_todo_app.yaml",
            "--ollama-model",
            "qwen3-coder:30b",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "above the Planfoldr demo limit" in captured.err


def test_compare_ollama_models_writes_summary_with_stubbed_runner(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(
        "planfoldr.cli.list_installed_ollama_models",
        lambda: parse_ollama_list(OLLAMA_LIST),
    )

    def fake_run_model_comparison(**kwargs):
        output_root = kwargs["output_root"]
        comparison_id = kwargs["comparison_id"]
        scenario_id = "ollama_cli_todo_app_demo"
        comparison_dir = output_root / scenario_id / comparison_id
        comparison_dir.mkdir(parents=True)
        payload = {
            "comparison_id": comparison_id,
            "summary_path": str(comparison_dir / "model_comparison.json"),
            "report_path": str(comparison_dir / "model_comparison.html"),
            "results": [
                {
                    "model": kwargs["models"][0].name,
                    "status": "success",
                    "reason": None,
                    "report_path": "runs/report.html",
                }
            ],
        }
        (comparison_dir / "model_comparison.json").write_text(json.dumps(payload), encoding="utf-8")
        (comparison_dir / "model_comparison.html").write_text("<html></html>", encoding="utf-8")
        return payload

    monkeypatch.setattr("planfoldr.cli._run_model_comparison", fake_run_model_comparison)

    exit_code = main(
        [
            "compare-ollama-models",
            "examples/scenarios/ollama_cli_todo_app.yaml",
            "--output-root",
            str(tmp_path),
            "--comparison-id",
            "cmp",
            "--max-models",
            "1",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "ollama_cli_todo_app_demo" / "cmp" / "model_comparison.json").exists()
    assert "gemma3:12b" in capsys.readouterr().out


def test_comparison_summary_counts_generated_files_without_local_artifacts(tmp_path: Path) -> None:
    project = tmp_path / "run" / "workspace" / "project"
    (project / ".git" / "hooks").mkdir(parents=True)
    (project / "todo" / "tests").mkdir(parents=True)
    (project / "todo" / "__pycache__").mkdir()
    (project / ".git" / "hooks" / "pre-commit.sample").write_text("", encoding="utf-8")
    (project / "todo" / "__pycache__" / "cached.pyc").write_text("", encoding="utf-8")
    (project / "todo" / "AGENTS.md").write_text("", encoding="utf-8")
    (project / "todo" / "ARCHITECTURE.md").write_text("", encoding="utf-8")
    (project / "todo" / "tests" / "test_todo.py").write_text("", encoding="utf-8")
    (project / "todo" / "cli.py").write_text("", encoding="utf-8")
    result = SimpleNamespace(
        status="success",
        reason=None,
        task_results=[
            SimpleNamespace(
                task_id="run_tests",
                status="success",
                reason=None,
                budget_after={"usage": {"model_calls": 1}},
            )
        ],
    )

    summary = _comparison_run_summary(
        classify_ollama_model("gemma3:12b", size="8.1 GB"),
        run_id="run",
        run_dir=tmp_path / "run",
        result=result,
    )

    assert summary["generated_file_count"] == 4
    assert summary["test_file_count"] == 1
    assert summary["has_agents"] is True
    assert summary["has_architecture"] is True
