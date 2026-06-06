import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

import pytest

from planfoldr.executors import ExecutorRegistry, OllamaModelAdapter
from planfoldr.guards import BudgetTracker, PermissionEngine
from planfoldr.loader import load_scenario
from planfoldr.cli import apply_runtime_context, _prompt_variables
from planfoldr.trace import run_and_trace


SCENARIO = Path(__file__).parents[1] / "examples" / "scenarios" / "ollama_cli_todo_app.yaml"
RUNS_ROOT = SCENARIO.parents[2] / "runs"
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
    model_name = model_override or _first_model_name(loaded)
    run_id = _test_run_id(model_name)
    runtime = apply_runtime_context(loaded, output_root=RUNS_ROOT, run_id=run_id)
    inputs = loaded.document.inputs
    run_dir = RUNS_ROOT / loaded.document.id / run_id
    registry = ExecutorRegistry(
        permission_engine=PermissionEngine(loaded.document.constraints, base_dir=SCENARIO.parents[2]),
        budget_tracker=BudgetTracker(loaded.document.budgets),
        prompts=loaded.cycles[0].prompts,
        model_adapter=OllamaModelAdapter(timeout=float(os.environ.get(TIMEOUT_ENV, "30"))),
        prompt_variables=_prompt_variables(inputs, runtime=runtime),
        invalid_output_retries=loaded.document.defaults.retry.invalid_output,
    )

    result = run_and_trace(loaded, registry, output_root=RUNS_ROOT, run_id=run_id)

    generated = Path(inputs["repository_path"])
    assert run_dir.name.startswith("test_run_")
    assert generated == run_dir / "workspace" / "project"
    assert result.status == "success"
    assert (generated / "AGENTS.md").exists()
    assert (generated / "ARCHITECTURE.md").exists()
    assert list(generated.glob("tests/test_*.py"))
    _assert_generated_cli_behaves_like_todo_prompt(generated, run_dir / "cli-contract")
    assert (run_dir / "trace" / "manifest.json").exists()
    assert (run_dir / "report.html").exists()


def _override_model_name(loaded, model_name: str) -> None:
    for cycle in loaded.cycles:
        for task in cycle.document.tasks:
            if task.executor.model is not None:
                task.executor.model.name = model_name


def _first_model_name(loaded) -> str:
    for cycle in loaded.cycles:
        for task in cycle.document.tasks:
            if task.executor.model is not None:
                return task.executor.model.name
    return "unknown_model"


def _test_run_id(model_name: str, *, suffix: str | None = None) -> str:
    return f"test_run_{_slug(model_name)}_{suffix or uuid4().hex[:8]}"


def _slug(value: str) -> str:
    chars = [char.lower() if char.isalnum() else "_" for char in value]
    return "_".join("".join(chars).strip("_").split("_")) or "unknown"


def _assert_generated_cli_behaves_like_todo_prompt(project: Path, state_root: Path) -> None:
    failures: list[str] = []
    for entrypoint in _cli_entrypoint_candidates(project):
        for done_ref in ("1", "0"):
            state_dir = state_root / _entrypoint_slug(entrypoint) / f"done-{done_ref}"
            state_dir.mkdir(parents=True, exist_ok=True)
            env = _cli_contract_env(project, state_dir)
            steps = [
                (*entrypoint, "add", "write tests"),
                (*entrypoint, "add", "review output"),
                (*entrypoint, "list"),
                (*entrypoint, "done", done_ref),
                (*entrypoint, "list"),
            ]
            results = [_run_cli_step(step, cwd=state_dir, env=env) for step in steps]
            failure = _cli_contract_failure(results)
            if failure is None:
                return
            failures.append(f"{' '.join(entrypoint)} done {done_ref}: {failure}")

    details = "\n".join(f"  - {failure}" for failure in failures) or "  - no supported CLI entry point found"
    raise AssertionError(f"Generated todo CLI did not satisfy the example prompt contract:\n{details}")


def _cli_entrypoint_candidates(project: Path) -> list[tuple[str, ...]]:
    candidates: list[tuple[str, ...]] = []
    if (project / "todo" / "__main__.py").exists():
        candidates.append((sys.executable, "-m", "todo"))
    if (project / "todo" / "cli.py").exists():
        candidates.append((sys.executable, "-m", "todo.cli"))
    return candidates


def _entrypoint_slug(entrypoint: tuple[str, ...]) -> str:
    return "-".join(part.replace("/", "_").replace(".", "_") for part in entrypoint[-2:])


def _cli_contract_env(project: Path, state_dir: Path) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(state_dir),
        "PYTHONPATH": str(project),
        "TODO_FILE": str(state_dir / "todos.json"),
        "TODO_DB": str(state_dir / "todos.json"),
        "TODO_DB_PATH": str(state_dir / "todos.json"),
    }
    return env


def _run_cli_step(args: tuple[str, ...], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=10, check=False)


def _cli_contract_failure(results: list[subprocess.CompletedProcess[str]]) -> str | None:
    labels = ("add first", "add second", "list before done", "done", "list after done")
    for label, result in zip(labels, results):
        if result.returncode != 0:
            return f"{label} exited {result.returncode}: {_combined_output(result)}"

    before_done = _combined_output(results[2]).lower()
    after_done = _combined_output(results[4]).lower()
    if "write tests" not in before_done or "review output" not in before_done:
        return f"list did not show both added items: {before_done!r}"
    if before_done == after_done:
        return "done command did not change list output"
    if "review output" not in after_done:
        return f"done command removed or hid the wrong item: {after_done!r}"
    if "write tests" in after_done and not _looks_completed(after_done):
        return f"done item is still listed without a completion marker: {after_done!r}"
    return None


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}".strip()


def _looks_completed(output: str) -> bool:
    markers = ("done", "complete", "completed", "finished", "[x]", "(x)", "true", "yes")
    return any(marker in output for marker in markers)


def test_ollama_demo_test_run_id_uses_test_run_prefix() -> None:
    assert _test_run_id("carstenuhlig/omnicoder-9b:latest", suffix="fixed") == (
        "test_run_carstenuhlig_omnicoder_9b_latest_fixed"
    )


def test_hidden_cli_contract_accepts_generated_main_module(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "todo"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "__main__.py").write_text(
        """
import json
import sys
from pathlib import Path

STORE = Path.cwd() / "todos.json"


def load():
    if not STORE.exists():
        return []
    return json.loads(STORE.read_text())


def save(items):
    STORE.write_text(json.dumps(items))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    command = argv.pop(0)
    items = load()
    if command == "add":
        items.append({"text": " ".join(argv), "done": False})
        save(items)
        return 0
    if command == "list":
        for index, item in enumerate(items, start=1):
            marker = "[x]" if item["done"] else "[ ]"
            print(f"{index}. {marker} {item['text']}")
        return 0
    if command == "done":
        items[int(argv[0]) - 1]["done"] = True
        save(items)
        return 0
    return 2


raise SystemExit(main())
""".lstrip(),
        encoding="utf-8",
    )

    _assert_generated_cli_behaves_like_todo_prompt(project, tmp_path / "state")
