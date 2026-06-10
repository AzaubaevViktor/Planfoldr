"""Validate the todo_local scenario's verification commands against a known-correct reference
implementation, BEFORE spending GPU on a model sweep. If the reference passes every command, the
checks are correct and achievable; if it fails, the scenario (not the model) is at fault.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "examples" / "todo_local.yaml"

REFERENCE = '''
import json, os, sys


def _load(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def _save(path, tasks):
    with open(path, "w") as f:
        json.dump(tasks, f)


def add(title, path="todos.json"):
    tasks = _load(path)
    new_id = max([t["id"] for t in tasks], default=0) + 1
    tasks.append({"id": new_id, "title": title, "done": False})
    _save(path, tasks)
    return new_id


def list_tasks(path="todos.json"):
    return _load(path)


def complete(task_id, path="todos.json"):
    tasks = _load(path)
    found = False
    for t in tasks:
        if t["id"] == task_id:
            t["done"] = True
            found = True
    _save(path, tasks)
    return found


def remove(task_id, path="todos.json"):
    tasks = _load(path)
    kept = [t for t in tasks if t["id"] != task_id]
    found = len(kept) != len(tasks)
    _save(path, kept)
    return found


def _cli(argv):
    if not argv:
        print("usage: todo.py [add|list|done|rm] ...")
        return 1
    cmd, rest = argv[0], argv[1:]
    if cmd == "add":
        print(add(rest[0]))
    elif cmd == "list":
        for t in list_tasks():
            print(f"[{'x' if t['done'] else ' '}] {t['id']} {t['title']}")
    elif cmd == "done":
        complete(int(rest[0]))
    elif cmd == "rm":
        remove(int(rest[0]))
    else:
        print("unknown command: " + cmd)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
'''


def main() -> int:
    commands = (yaml.safe_load(SCENARIO.read_text())["verification"]["commands"])
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        (ws / "todo.py").write_text(REFERENCE)
        all_ok = True
        for i, cmd in enumerate(commands, 1):
            p = subprocess.run(cmd, shell=True, cwd=ws, capture_output=True, text=True, timeout=60)
            ok = p.returncode == 0
            all_ok &= ok
            print(f"[{'PASS' if ok else 'FAIL'}] cmd {i}: rc={p.returncode}")
            if p.stdout.strip():
                print("   stdout:", p.stdout.strip())
            if not ok and p.stderr.strip():
                print("   stderr:", p.stderr.strip()[-400:])
    print("\nRESULT:", "reference satisfies the scenario ✓" if all_ok else "SCENARIO BROKEN ✗")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
