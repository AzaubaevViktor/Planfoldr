"""Drive one scenario through the live Ollama path across several models and report
how the *harness* holds up (not the model's IQ): does it crash, parse actions, drive
the loop, terminate, and persist artifacts. Independent of model competence, we also
re-run the scenario's verification command against the produced workspace.

Usage:
    .venv/bin/python _experiments/model_sweep.py examples/calc_local.yaml model_a model_b ...
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = str(ROOT / ".venv" / "bin" / "python")
RUNS = ROOT / "runs"
MAX_CYCLES = "25"
PER_MODEL_TIMEOUT = 1200  # seconds


def safe(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name)


def verify(run_dir: Path, scenario_path: Path) -> tuple[bool, str]:
    """Re-run the scenario's verification commands against the run workspace, harness-independent."""
    import yaml  # provided by the project deps
    scen = yaml.safe_load(scenario_path.read_text())
    cmds = (scen.get("verification") or {}).get("commands") or []
    ws = run_dir / "workspace"
    if not cmds:
        return False, "no commands"
    for cmd in cmds:
        try:
            p = subprocess.run(cmd, shell=True, cwd=ws, capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            return False, f"verify timeout: {cmd}"
        if p.returncode != 0:
            return False, f"verify FAIL rc={p.returncode}: {(p.stderr or p.stdout).strip()[:200]}"
    return True, "all verification commands pass"


def resolve_run_dir(run_id: str) -> Path:
    """Run dirs are timestamp-prefixed (`<date>__<run_id>`); pick the most recent for this id,
    falling back to the legacy bare name."""
    matches = sorted(RUNS.glob(f"*__{run_id}"))
    return matches[-1] if matches else RUNS / run_id


def run_one(scenario_path: Path, model: str) -> dict:
    run_id = f"sweep_{scenario_path.stem}_{safe(model)}"
    started = time.time()
    record: dict = {"model": model, "run_id": run_id}
    try:
        proc = subprocess.run(
            [PY, "-m", "planfoldr", "run", str(scenario_path),
             "--model", model, "--provider", "ollama",
             "--run-id", run_id, "--visibility", "none", "--max-cycles", MAX_CYCLES],
            cwd=ROOT, capture_output=True, text=True, timeout=PER_MODEL_TIMEOUT,
        )
        record["returncode"] = proc.returncode
        record["stderr_tail"] = (proc.stderr or "").strip()[-800:]
        record["crashed"] = "Traceback (most recent call last)" in (proc.stderr or "")
    except subprocess.TimeoutExpired:
        record["returncode"] = None
        record["crashed"] = False
        record["timed_out"] = True
        record["stderr_tail"] = f"timed out after {PER_MODEL_TIMEOUT}s"
    record["wall_seconds"] = round(time.time() - started, 1)

    run_dir = resolve_run_dir(run_id)
    record["run_dir"] = str(run_dir)
    result_path = run_dir / "result.json"
    if result_path.exists():
        res = json.loads(result_path.read_text())
        record["status"] = res.get("status")
        record["cycles_run"] = res.get("cycles_run")
        record["tickets"] = res.get("tickets")
        record["reason"] = res.get("reason")
        budget = res.get("budget") or {}
        record["tokens_used"] = budget.get("tokens_used")
    else:
        record["status"] = "NO_RESULT_JSON"
    # Artifact persistence is a harness contract regardless of model outcome.
    record["artifacts_ok"] = all((run_dir / n).exists() for n in
                                 ["audit.jsonl", "graph.json", "scores.json", "tickets.json", "result.json"])
    ok, why = verify(run_dir, scenario_path)
    record["verify_pass"] = ok
    record["verify_detail"] = why
    return record


def main() -> int:
    # Resolve the scenario path against the project root so the driver is cwd-independent (the
    # managed background runner does not launch from ROOT) and survives a mid-run rename.
    raw = Path(sys.argv[1])
    scenario_path = (raw if raw.is_absolute() else ROOT / raw).resolve()
    models = sys.argv[2:]
    summary_path = ROOT / "_experiments" / f"sweep_summary_{scenario_path.stem}.json"
    summary = []
    for model in models:
        print(f"\n===== {model} =====", flush=True)
        rec = run_one(scenario_path, model)
        summary.append(rec)
        summary_path.write_text(json.dumps(summary, indent=2))  # incremental, survives a kill
        print(json.dumps({k: rec.get(k) for k in
                          ["status", "verify_pass", "crashed", "cycles_run",
                           "tokens_used", "wall_seconds", "artifacts_ok"]}, indent=2), flush=True)
    print("\n===== SWEEP DONE =====", flush=True)
    print(f"summary -> {summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
