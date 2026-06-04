import os
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from planfoldr.executors import ExecutorRegistry, OllamaModelAdapter
from planfoldr.guards import BudgetTracker, PermissionEngine
from planfoldr.loader import load_scenario
from planfoldr.trace import run_and_trace


SCENARIO = Path(__file__).parents[1] / "examples" / "scenarios" / "ollama_cli_todo_app.yaml"


def _ollama_available() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2):
            return True
    except (OSError, urllib.error.URLError):
        return False


@pytest.mark.ollama
def test_ollama_cli_todo_demo(tmp_path: Path) -> None:
    if os.environ.get("PLANFOLDR_RUN_OLLAMA_E2E") != "1":
        pytest.skip("Set PLANFOLDR_RUN_OLLAMA_E2E=1 to run the optional Ollama demo")
    if not _ollama_available():
        pytest.skip("Ollama is not available on http://127.0.0.1:11434")

    loaded = load_scenario(SCENARIO)
    inputs = loaded.document.inputs
    registry = ExecutorRegistry(
        permission_engine=PermissionEngine(loaded.document.constraints, base_dir=SCENARIO.parents[2]),
        budget_tracker=BudgetTracker(loaded.document.budgets),
        prompts=loaded.cycles[0].prompts,
        model_adapter=OllamaModelAdapter(),
        prompt_variables={"inputs": inputs, **{f"inputs.{key}": value for key, value in inputs.items()}},
        invalid_output_retries=loaded.document.defaults.retry.invalid_output,
    )

    result = run_and_trace(loaded, registry, output_root=tmp_path)

    generated = SCENARIO.parents[2] / inputs["repository_path"]
    assert result.status == "success"
    assert (generated / "AGENTS.md").exists()
    assert (generated / "ARCHITECTURE.md").exists()
    assert list(generated.glob("tests/test_*.py"))
    assert (tmp_path / loaded.document.id / "trace" / "manifest.json").exists()
    assert (tmp_path / loaded.document.id / "report.html").exists()
