import os
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from planfoldr.executors import ExecutorRegistry, OllamaModelAdapter
from planfoldr.guards import BudgetTracker, PermissionEngine
from planfoldr.loader import load_scenario
from planfoldr.cli import apply_runtime_context, _prompt_variables
from planfoldr.trace import run_and_trace


SCENARIO = Path(__file__).parents[1] / "examples" / "scenarios" / "ollama_cli_todo_app.yaml"
MODEL_ENV = "PLANFOLDR_OLLAMA_MODEL"
TIMEOUT_ENV = "PLANFOLDR_OLLAMA_TIMEOUT"


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
    model_override = os.environ.get(MODEL_ENV)
    if model_override:
        _override_model_name(loaded, model_override)
    runtime = apply_runtime_context(loaded, output_root=tmp_path, run_id="ollama-test")
    inputs = loaded.document.inputs
    registry = ExecutorRegistry(
        permission_engine=PermissionEngine(loaded.document.constraints, base_dir=SCENARIO.parents[2]),
        budget_tracker=BudgetTracker(loaded.document.budgets),
        prompts=loaded.cycles[0].prompts,
        model_adapter=OllamaModelAdapter(timeout=float(os.environ.get(TIMEOUT_ENV, "30"))),
        prompt_variables=_prompt_variables(inputs, runtime=runtime),
        invalid_output_retries=loaded.document.defaults.retry.invalid_output,
    )

    result = run_and_trace(loaded, registry, output_root=tmp_path, run_id="ollama-test")

    generated = Path(inputs["repository_path"])
    assert result.status == "success"
    assert (generated / "AGENTS.md").exists()
    assert (generated / "ARCHITECTURE.md").exists()
    assert list(generated.glob("tests/test_*.py"))
    assert (tmp_path / loaded.document.id / "ollama-test" / "trace" / "manifest.json").exists()
    assert (tmp_path / loaded.document.id / "ollama-test" / "report.html").exists()


def _override_model_name(loaded, model_name: str) -> None:
    for cycle in loaded.cycles:
        for task in cycle.document.tasks:
            if task.executor.model is not None:
                task.executor.model.name = model_name
