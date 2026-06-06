# Agent Instructions

NEVER EVER REMOVE MY PRETTY EXAMPLES

## Git Hygiene

- Commit messages made by AI agents must start with the `[AI]` prefix.
- Changes made by AI agents must be committed.
- Keep commits focused on one task or quest at a time.
- Do not commit local/generated artifacts such as `.venv/`, `.pytest_cache/`, `runs/`, or trace output that is intentionally ignored.
- If an agent changes only ignored local state but the project rule still requires an audit marker, use an empty `[AI]` commit instead of force-adding ignored artifacts.

## Project Workflow

- Read the relevant quest, docs, and nearby tests before editing code.
- Treat quest examples as behavioral and layout contracts, not decorative hints. If an example shows a page, report, trace, CLI output, or artifact shape, make the default output match that shape directly.
- Do not satisfy a flow-shaped example by adding fields to an unrelated existing structure. For report/UI work, if the example is chronological prose or block flow, the primary view must be chronological prose or block flow; tables may only remain as secondary/debug views unless the quest asks for a table.
- When existing implementation notes conflict with a quest example, prefer the example and call out the conflict in implementation notes instead of preserving the old shape by inertia.
- Active implementation work lives in `quests/`; completed quest files move to `quests/done/` in the same commit that finishes the work.
- Follow quest order by default. If the user names a specific quest, do that quest first and keep the change scoped to it.
- When finishing a quest, update its implementation notes or handoff section so the next agent can resume without rereading the whole session history.
- Prefer small, deterministic MVP slices over broad rewrites. Keep models as task executors; the deterministic runtime should own control flow, budgets, permissions, validation, tracing, and reports.

## Local Environment

- Use the local virtualenv `.venv/`; it is ignored by git.
- On this machine, prefer the Homebrew Python at `/opt/homebrew/bin/python3` when recreating the venv:

```bash
/opt/homebrew/bin/python3 -m venv .venv
```

- Install dependencies with:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

- Do not add `.venv/` or other environment files to git.

## Verification

- Run the full test suite before committing code changes:

```bash
.venv/bin/python -m pytest -q
```

- Follow this verification protocol before claiming a quest or fix is done:
  1. Re-read the relevant quest, examples and acceptance/verification bullets; preserve every example unless the user explicitly asks to change it.
  2. Write down the concrete observable behavior that must be true, including what should be visible in generated reports or artifacts.
  3. Add or update focused tests that fail for the exact bug or missing behavior, not only for nearby implementation details.
  4. For report, trace or UI work, inspect the generated HTML/data shape itself and verify important information is visible in the intended default view, not only present somewhere in collapsed JSON or hidden details.
  5. Run focused tests first, then the full default suite with `.venv/bin/python -m pytest -q`.
  6. If any verification step cannot be run, document exactly what was not run and why before committing.
  7. Commit only after the implementation, quest notes and verification evidence agree with the examples and acceptance conditions.
- Optional Ollama coverage is opt-in and may require a local model plus explicit environment variables. Do not run it as part of the default suite unless the user asks or the quest requires it.
- When the user asks for Ollama/model tests or a quest requires them, it is acceptable to run local Ollama models up to and including 12 GB from `ollama list` without trying to conserve GPU, wall-clock time, or token usage. This is a local machine; resource usage for those eligible models is allowed to be effectively unbounded for verification.
- If `compileall` is useful, keep pycache output inside an allowed temp path, for example:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/planfoldr-pycache .venv/bin/python -m compileall src tests
```

## Runtime And Artifacts

- Generated run artifacts belong under `runs/` and stay ignored by git.
- Per-run workspaces must be isolated under each run directory. Use `{{ runtime.run_dir }}` and `{{ runtime.workspace_dir }}` in scenarios instead of shared workspace paths.
- Keep filesystem allowlists aligned with rendered runtime paths before creating permission checks.
- For trace/report work, preserve manifest-backed artifacts and keep `trace/report_data.json` refresh-friendly.
- For model traces, treat raw streaming responses as diagnostics. Prefer human-readable files such as assembled content/thinking output and `stream.jsonl` for replay or inspection.
