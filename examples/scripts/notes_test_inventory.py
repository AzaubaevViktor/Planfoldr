"""Record and verify generated notes app test inventory."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _inventory(repository: Path) -> list[str]:
    tests_dir = repository / "tests"
    return sorted(str(path.relative_to(repository)) for path in tests_dir.glob("test_*.py"))


def _record(repository: Path, inventory_path: Path) -> int:
    tests = _inventory(repository)
    if not tests:
        print("no tests found", file=sys.stderr)
        return 1
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(json.dumps({"tests": tests}, indent=2, sort_keys=True), encoding="utf-8")
    print(f"recorded {len(tests)} test file(s)")
    return 0


def _verify(repository: Path, inventory_path: Path) -> int:
    expected = json.loads(inventory_path.read_text(encoding="utf-8"))["tests"]
    missing = [name for name in expected if not (repository / name).exists()]
    if missing:
        print("missing test files: " + ", ".join(missing), file=sys.stderr)
        return 1
    print(f"verified {len(expected)} test file(s)")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[1] not in {"record", "verify"}:
        print("usage: notes_test_inventory.py record|verify REPOSITORY_PATH INVENTORY_PATH", file=sys.stderr)
        return 2
    action = argv[1]
    repository = Path(argv[2]).resolve()
    inventory_path = Path(argv[3]).resolve()
    if action == "record":
        return _record(repository, inventory_path)
    return _verify(repository, inventory_path)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
