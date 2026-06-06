import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

import pytest

from planfoldr.cli import _collect_prompts, _prompt_variables, apply_runtime_context
from planfoldr.executors import ExecutorRegistry, OllamaModelAdapter, StubModelAdapter
from planfoldr.guards import BudgetTracker, PermissionEngine
from planfoldr.loader import load_scenario
from planfoldr.trace import run_and_trace


SCENARIO = Path(__file__).parents[1] / "examples" / "scenarios" / "ollama_notes_app.yaml"
RUNS_ROOT = SCENARIO.parents[2] / "runs"
MODEL_ENV = "PLANFOLDR_OLLAMA_MODEL"
TIMEOUT_ENV = "PLANFOLDR_OLLAMA_TIMEOUT"
RUN_COMPLEX_ENV = "PLANFOLDR_RUN_OLLAMA_COMPLEX_E2E"


def test_complex_notes_stub_scenario_repairs_mixed_case_regression(tmp_path: Path) -> None:
    loaded = load_scenario(SCENARIO)
    runtime = apply_runtime_context(loaded, output_root=tmp_path, run_id="notes-stub")
    repository = Path(loaded.document.inputs["repository_path"])
    registry = ExecutorRegistry(
        permission_engine=PermissionEngine(loaded.document.constraints, base_dir=SCENARIO.parents[2]),
        budget_tracker=BudgetTracker(loaded.document.budgets),
        prompts=_collect_prompts(loaded),
        model_adapter=StubModelAdapter(_stub_notes_responses(repository)),
        prompt_variables=_prompt_variables(loaded.document.inputs, runtime=runtime),
        invalid_output_retries=loaded.document.defaults.retry.invalid_output,
    )

    result = run_and_trace(loaded, registry, output_root=tmp_path, run_id="notes-stub")

    statuses = {task.task_id: task.status for task in result.task_results}
    assert result.status == "success"
    assert statuses["run_initial_tests"] == "success"
    assert statuses["run_regression_tests"] == "failure"
    assert statuses["repair_notes_project"] == "success"
    assert statuses["verify_repaired"] == "success"
    assert statuses["verify_test_inventory"] == "success"
    assert (repository / "tests" / "test_mixed_case_tags_regression.py").exists()
    _assert_notes_project_contract(repository, tmp_path / "notes-contract")

    report = tmp_path / loaded.document.id / "notes-stub" / "report.html"
    report_text = report.read_text(encoding="utf-8")
    assert "ollama_notes_plan: start -&gt; [plan_notes_project] -&gt; finish" in report_text
    assert "cycle up/down to ollama_notes_repair" in report_text
    assert "ollama_notes_repair: record_test_inventory -&gt; [run_regression_tests] -&gt; repair_notes_project" in report_text
    assert "result: failure (Command exited 1)" in report_text
    assert "verify_test_inventory" in report_text


def test_hidden_notes_contract_accepts_reference_project(tmp_path: Path) -> None:
    project = tmp_path / "project"
    for item in _fixed_notes_project_files(project):
        target = Path(item["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item["content"], encoding="utf-8")
    regression = SCENARIO.parents[1] / "scripts" / "inject_notes_regression_test.py"
    completed = subprocess.run(
        [sys.executable, str(regression), str(project)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr

    _assert_notes_project_contract(project, tmp_path / "state")


@pytest.mark.ollama
def test_ollama_notes_complex_repair_demo(tmp_path: Path) -> None:
    if os.environ.get(RUN_COMPLEX_ENV) != "1":
        pytest.skip(f"Set {RUN_COMPLEX_ENV}=1 to run the optional complex Ollama demo")
    if not _ollama_available():
        pytest.skip("Ollama is not available on http://127.0.0.1:11434")

    loaded = load_scenario(SCENARIO)
    model_override = os.environ.get(MODEL_ENV)
    if model_override:
        _override_model_name(loaded, model_override)
    model_name = model_override or _first_model_name(loaded)
    run_id = _test_run_id("notes", model_name)
    runtime = apply_runtime_context(loaded, output_root=RUNS_ROOT, run_id=run_id)
    run_dir = RUNS_ROOT / loaded.document.id / run_id
    registry = ExecutorRegistry(
        permission_engine=PermissionEngine(loaded.document.constraints, base_dir=SCENARIO.parents[2]),
        budget_tracker=BudgetTracker(loaded.document.budgets),
        prompts=_collect_prompts(loaded),
        model_adapter=OllamaModelAdapter(timeout=float(os.environ.get(TIMEOUT_ENV, "180"))),
        prompt_variables=_prompt_variables(loaded.document.inputs, runtime=runtime),
        invalid_output_retries=loaded.document.defaults.retry.invalid_output,
    )

    result = run_and_trace(loaded, registry, output_root=RUNS_ROOT, run_id=run_id)

    generated = Path(loaded.document.inputs["repository_path"])
    assert run_dir.name.startswith("test_run_notes_")
    assert generated == run_dir / "workspace" / "project"
    assert (run_dir / "trace" / "manifest.json").exists()
    assert (run_dir / "report.html").exists()
    assert result.status == "success"
    assert (generated / "AGENTS.md").exists()
    assert (generated / "ARCHITECTURE.md").exists()
    assert (generated / "tests" / "test_mixed_case_tags_regression.py").exists()
    _assert_notes_project_contract(generated, run_dir / "hidden-contract")


def _ollama_available() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2):
            return True
    except (OSError, urllib.error.URLError):
        return False


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


def _test_run_id(prefix: str, model_name: str, *, suffix: str | None = None) -> str:
    return f"test_run_{_slug(prefix)}_{_slug(model_name)}_{suffix or uuid4().hex[:8]}"


def _slug(value: str) -> str:
    chars = [char.lower() if char.isalnum() else "_" for char in value]
    return "_".join("".join(chars).strip("_").split("_")) or "unknown"


def _assert_notes_project_contract(project: Path, state_root: Path) -> None:
    assert (project / "AGENTS.md").exists()
    assert (project / "ARCHITECTURE.md").exists()
    assert (project / "notes_app" / "__main__.py").exists()
    tests = sorted((project / "tests").glob("test_*.py"))
    assert len(tests) >= 2
    assert (project / "tests" / "test_mixed_case_tags_regression.py").exists()

    pytest_result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert pytest_result.returncode == 0, _combined_output(pytest_result)

    state_root.mkdir(parents=True, exist_ok=True)
    env = _notes_contract_env(project, state_root / "primary")
    steps = [
        ("add", "Alpha", "First body", "--tags", "Work,Python"),
        ("add", "Beta", "Second body", "--tags", "Personal"),
        ("list", "--tag", "work"),
        ("search", "python"),
        ("export", str(state_root / "export.json")),
    ]
    results = [_run_notes_cli(project, env, *step) for step in steps]
    for label, result in zip(("add alpha", "add beta", "list tag", "search", "export"), results):
        assert result.returncode == 0, f"{label}: {_combined_output(result)}"
    assert "Alpha" in results[2].stdout
    assert "Beta" not in results[2].stdout
    assert "Alpha" in results[3].stdout

    imported_env = _notes_contract_env(project, state_root / "imported")
    imported = _run_notes_cli(project, imported_env, "import", str(state_root / "export.json"))
    assert imported.returncode == 0, _combined_output(imported)
    listed = _run_notes_cli(project, imported_env, "list", "--tag", "work")
    assert listed.returncode == 0, _combined_output(listed)
    assert "Alpha" in listed.stdout


def _notes_contract_env(project: Path, state_dir: Path) -> dict[str, str]:
    state_dir.mkdir(parents=True, exist_ok=True)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(state_dir),
        "PYTHONPATH": str(project),
        "NOTES_DB": str(state_dir / "notes.json"),
        "NOTES_FILE": str(state_dir / "notes.json"),
        "NOTES_PATH": str(state_dir / "notes.json"),
    }
    return env


def _run_notes_cli(project: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "notes_app", *args],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}".strip()


def _stub_notes_responses(repository: Path) -> dict[str, object]:
    return {
        "plan_notes_project:ollama_plan_notes_app": {
            "status": "success",
            "plan": [
                {"id": "generate", "goal": "write notes app", "evidence": "initial tests pass"},
                {"id": "regression", "goal": "prove mixed-case tag bug", "evidence": "pytest fails"},
                {"id": "repair", "goal": "fix without deleting tests", "evidence": "suite passes"},
            ],
            "evidence_required": [
                "initial generated tests pass",
                "regression fails before repair",
                "test inventory is preserved",
            ],
        },
        "generate_notes_project:ollama_generate_notes_app": {
            "status": "success",
            "files": _buggy_notes_project_files(repository),
        },
        "repair_notes_project:ollama_repair_notes_app": {
            "status": "success",
            "files": _fixed_notes_repair_files(repository),
        },
    }


def _buggy_notes_project_files(repository: Path) -> list[dict[str, str]]:
    return _notes_project_files(repository, case_insensitive_tags=False)


def _fixed_notes_project_files(repository: Path) -> list[dict[str, str]]:
    return _notes_project_files(repository, case_insensitive_tags=True)


def _fixed_notes_repair_files(repository: Path) -> list[dict[str, str]]:
    return [
        {
            "path": str(repository / "notes_app" / "store.py"),
            "content": _store_py(case_insensitive_tags=True),
        }
    ]


def _notes_project_files(repository: Path, *, case_insensitive_tags: bool) -> list[dict[str, str]]:
    return [
        {"path": str(repository / "AGENTS.md"), "content": "Generated notes app. Keep tests.\n"},
        {
            "path": str(repository / "ARCHITECTURE.md"),
            "content": "A small notes_app package with JSON persistence and a CLI.\n",
        },
        {"path": str(repository / "notes_app" / "__init__.py"), "content": _init_py()},
        {"path": str(repository / "notes_app" / "__main__.py"), "content": _main_py()},
        {"path": str(repository / "notes_app" / "cli.py"), "content": _cli_py()},
        {"path": str(repository / "notes_app" / "store.py"), "content": _store_py(case_insensitive_tags=case_insensitive_tags)},
        {"path": str(repository / "tests" / "test_notes_basic.py"), "content": _basic_tests_py()},
    ]


def _init_py() -> str:
    return '''\
from .store import add_note, export_notes, import_notes, list_notes, search_notes

__all__ = ["add_note", "export_notes", "import_notes", "list_notes", "search_notes"]
'''


def _main_py() -> str:
    return '''\
from .cli import main

raise SystemExit(main())
'''


def _cli_py() -> str:
    return '''\
from __future__ import annotations

import argparse
from pathlib import Path

from .store import add_note, export_notes, import_notes, list_notes, search_notes


def _tags(value: str) -> list[str]:
    return [tag.strip() for tag in value.split(",") if tag.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="notes_app")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    add.add_argument("title")
    add.add_argument("body")
    add.add_argument("--tags", default="")
    listing = sub.add_parser("list")
    listing.add_argument("--tag")
    search = sub.add_parser("search")
    search.add_argument("query")
    export = sub.add_parser("export")
    export.add_argument("path")
    import_cmd = sub.add_parser("import")
    import_cmd.add_argument("path")
    args = parser.parse_args(argv)

    if args.command == "add":
        note = add_note(args.title, args.body, _tags(args.tags))
        print(f"added {note['id']}: {note['title']}")
        return 0
    if args.command == "list":
        for note in list_notes(tag=args.tag):
            print(f"{note['id']}. {note['title']} [{', '.join(note['tags'])}] - {note['body']}")
        return 0
    if args.command == "search":
        for note in search_notes(args.query):
            print(f"{note['id']}. {note['title']} [{', '.join(note['tags'])}] - {note['body']}")
        return 0
    if args.command == "export":
        export_notes(Path(args.path))
        print(args.path)
        return 0
    if args.command == "import":
        import_notes(Path(args.path))
        print(args.path)
        return 0
    return 2
'''


def _store_py(*, case_insensitive_tags: bool) -> str:
    matcher = (
        "return tag.lower() in {item.lower() for item in note.get('tags', [])}"
        if case_insensitive_tags
        else "return tag in note.get('tags', [])"
    )
    return f'''\
from __future__ import annotations

import json
import os
from pathlib import Path


def database_path() -> Path:
    for name in ("NOTES_DB", "NOTES_FILE", "NOTES_PATH"):
        if os.environ.get(name):
            return Path(os.environ[name])
    return Path.cwd() / "notes.json"


def load_notes() -> list[dict]:
    path = database_path()
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_notes(notes: list[dict]) -> None:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(notes, indent=2, sort_keys=True), encoding="utf-8")


def _next_id(notes: list[dict]) -> int:
    return max([int(note.get("id", 0)) for note in notes] or [0]) + 1


def add_note(title: str, body: str, tags: list[str]) -> dict:
    notes = load_notes()
    note = {{"id": _next_id(notes), "title": title, "body": body, "tags": list(tags)}}
    notes.append(note)
    save_notes(notes)
    return note


def _matches_tag(note: dict, tag: str | None) -> bool:
    if not tag:
        return True
    {matcher}


def list_notes(tag: str | None = None) -> list[dict]:
    return [note for note in load_notes() if _matches_tag(note, tag)]


def search_notes(query: str) -> list[dict]:
    needle = query.lower()
    found = []
    for note in load_notes():
        haystack = " ".join([note.get("title", ""), note.get("body", ""), *note.get("tags", [])]).lower()
        if needle in haystack:
            found.append(note)
    return found


def export_notes(path: Path) -> None:
    path.write_text(json.dumps(load_notes(), indent=2, sort_keys=True), encoding="utf-8")


def import_notes(path: Path) -> None:
    save_notes(json.loads(path.read_text(encoding="utf-8")))
'''


def _basic_tests_py() -> str:
    return '''\
from notes_app.store import add_note, list_notes, search_notes


def test_add_list_and_search_notes(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTES_DB", str(tmp_path / "notes.json"))
    add_note("Alpha", "First body", ["Work", "Python"])
    add_note("Beta", "Second body", ["Personal"])

    assert [note["title"] for note in list_notes()] == ["Alpha", "Beta"]
    assert [note["title"] for note in list_notes(tag="Work")] == ["Alpha"]
    assert [note["title"] for note in search_notes("python")] == ["Alpha"]
'''
