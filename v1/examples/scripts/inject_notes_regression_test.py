"""Inject the notes app mixed-case tag regression test."""

from __future__ import annotations

import sys
from pathlib import Path


REGRESSION_TEST = '''\
import os
import subprocess
import sys
from pathlib import Path


def run_notes(tmp_path, *args):
    env = os.environ.copy()
    env["NOTES_DB"] = str(tmp_path / "notes.json")
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    return subprocess.run(
        [sys.executable, "-m", "notes_app", *args],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_tag_filter_is_case_insensitive(tmp_path):
    added = run_notes(tmp_path, "add", "Alpha", "First body", "--tags", "Work,Python")
    assert added.returncode == 0, added.stderr

    listed = run_notes(tmp_path, "list", "--tag", "work")
    assert listed.returncode == 0, listed.stderr
    assert "Alpha" in listed.stdout


def test_export_import_roundtrip_preserves_notes(tmp_path):
    export_path = tmp_path / "export.json"
    added = run_notes(tmp_path, "add", "Roundtrip", "Portable body", "--tags", "Archive")
    assert added.returncode == 0, added.stderr
    exported = run_notes(tmp_path, "export", str(export_path))
    assert exported.returncode == 0, exported.stderr

    env = os.environ.copy()
    env["NOTES_DB"] = str(tmp_path / "imported.json")
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    imported = subprocess.run(
        [sys.executable, "-m", "notes_app", "import", str(export_path)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert imported.returncode == 0, imported.stderr
    listed = subprocess.run(
        [sys.executable, "-m", "notes_app", "list", "--tag", "archive"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert listed.returncode == 0, listed.stderr
    assert "Roundtrip" in listed.stdout
'''


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: inject_notes_regression_test.py REPOSITORY_PATH", file=sys.stderr)
        return 2
    repository = Path(argv[1]).resolve()
    tests_dir = repository / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    target = tests_dir / "test_mixed_case_tags_regression.py"
    target.write_text(REGRESSION_TEST, encoding="utf-8")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
