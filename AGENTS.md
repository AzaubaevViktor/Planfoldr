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
- Treat slash-separated wording in examples, such as `up/down`, as a list of alternatives to choose from, not literal text to copy into output.
- Do not satisfy a flow-shaped example by adding fields to an unrelated existing structure. For report/UI work, if the example is chronological prose or block flow, the primary view must be chronological prose or block flow; tables may only remain as secondary/debug views unless the quest asks for a table.
- When existing implementation notes conflict with a quest example, prefer the example and call out the conflict in implementation notes instead of preserving the old shape by inertia.
- Active implementation work lives in `quests/`; completed quest files move to `quests/done/` in the same commit that finishes the work.
- Follow quest order by default. If the user names a specific quest, do that quest first and keep the change scoped to it.
- When finishing a quest, update its implementation notes or handoff section so the next agent can resume without rereading the whole session history.
- Do not add line-by-line audit sections that merely repeat quest text with `[x]` or "checked and complete"; verification notes must name concrete tests, generated artifacts, inspected files, and observable strings/fields.
- If a previous audit line is found false, do not silently preserve or re-check it. Mark it as a corrected false audit and replace it with concrete current evidence.
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
- Never mark a quest, checklist item, or audit line complete until final verification has actually run and its concrete artifact/output has been inspected. `compileall` is only a syntax/import sanity check; it does not count as final verification and cannot replace focused tests, full tests, real-model tests when required, or generated report/trace inspection.
- Optional Ollama coverage is opt-in and may require a local model plus explicit environment variables. Do not run it as part of the default suite unless the user asks or the quest requires it.
- When the user asks for Ollama/model tests or a quest requires them, it is acceptable to run local Ollama models up to and including 12 GB from `ollama list` without trying to conserve GPU, wall-clock time, or token usage. This is a local machine; resource usage for those eligible models is allowed to be effectively unbounded for verification.
- Ollama e2e test runs must preserve generated run artifacts under `runs/` with a `test_run_` run id prefix so reports, traces, decisions and generated workspaces remain inspectable after pytest exits.
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

---

## User Preferences (synthesized from conversation history)

These rules come directly from user feedback across sessions. Follow them without needing to be reminded.

### TODO / Task Planning Format

- **TODOs must be super-detailed.** Every item = a concrete, unambiguous action with enough detail to execute without asking back.
- **After every TODO item, add a `Verify:` block** — specific, observable steps to confirm it was done correctly (e.g. which command to run, what output to look for, what file to inspect, what field to check).
- **At the end of any TODO list, add a `Final Verification` block** — an end-to-end check that covers the whole set of tasks together, not just individual items.
- **Each user message appends three groups of items to the end of the active TODO list:**
  1. **RnD** — reading relevant files, exploring the codebase, generating the implementation approach, formulating the verification method
  2. **Implementation** — the concrete target result: exactly what to create or change, with enough detail to execute
  3. **Verification** — the formulated check plan; each verification step is its own separate item (run command X, inspect file Y, check field Z, walk through external checklist)

Example structure:
```
TODO:
1. Add date prefix to run folder names (format: YYYY-MM-DD_<run_id>)
   Verify: run a scenario, check that runs/ contains a folder starting with today's date

2. Update interface.md to document run folder naming
   Verify: open interface.md, confirm the naming convention section exists and mentions date prefix

Final Verification:
- Run a full e2e scenario, confirm run folder has date prefix
- Open the generated HTML report, confirm it renders the run_id with the date
- Run pytest -q, all tests pass
```

### Visibility & Output

- Output must look like a coding agent's output — structured, readable, not a wall of JSON.
- **No raw JSON in any user-facing output.** Render it as formatted JSON, a table, or prose.
- For each model call, show: `source`, `context`, `input`.
- During generation: stream output live. If the model is thinking, put it in a **collapsible `thinking` block**, then show the content response below it.
- After generation: show final output, updated context (collapsible), **diff from original context**, status (collapsible), **budget spent / remaining**, **wall-clock time**.
- `stderr` from bash commands must be shown human-readably — not wrapped in a JSON field. See `interface.md`.
- During `model_verification` steps, show what is being checked — not a silent spinner.
- Add a **date prefix** to run folder names (e.g. `2026-06-10_my-run`) so runs are navigable by date in the filesystem.

### Architecture Vision

The system is an agent harness where models execute tickets in nested loops:

- **Basic loop**: context update (model + context interaction) → changes (model + tools) → verification (run something) + verification (model again).
- **Loops are nested**: one loop can spawn batches of sub-loops.
- **Each loop = a ticket.** A ticket has: goal, scope, constraints, budget, links to other tickets, access to specific tools. New tickets can be created while a ticket is being worked.
- **Queues are processed by models with different roles** (e.g. developer, security reviewer). The same code can be handed off: a developer ticket creates a "security" ticket to close auth holes.
- **One role can dynamically create new roles** as the work demands it.

### Example Scenarios

- Test with **real tasks**, not toy problems (calculator is not enough; use todo-list app, file server, SQLite query engine, etc.).
- When building a difficulty ladder, make **10 different projects with increasing complexity** — not 10 variations of the same project.
- Include scenarios at multiple file-count scales: ~1 file, ~10 files, ~20 files, ~100 files.
- Use level suffixes in example filenames: `_l01`, `_l02`, … `_l16`.

### Doc Integrity

- When recompiling or rewriting a document, verify that **every line from the original exists in the output**. Run a diff; do not assume content survived.
- Never silently drop content from PHASE_*.md, interface.md, or quest files when editing them.
