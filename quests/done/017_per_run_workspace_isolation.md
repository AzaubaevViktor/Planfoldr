# Task 017: Per-Run Workspace Isolation

## Goal

Keep generated workspaces inside each run directory so every test run starts from a clean state.

## Concept

Generated projects should live under the current run timestamp rather than a shared workspace path. This preserves old logs, makes reports self-contained and prevents one run from contaminating the next.

## Necessary Conditions

- Generated workspace path is inside `runs/<scenario_id>/<run_id>/workspace/`.
- Example scenarios use runtime variables for run-specific workspace paths.
- Re-running a scenario creates a fresh workspace.
- Old run directories are not deleted automatically.
- Reports and traces reference the run-local workspace.

## Constraints

- Do not write generated projects outside the active run directory.
- Keep existing old runs inspectable.
- Do not require manual cleanup before reruns.

## Subtasks

- Audit example scenario workspace paths.
- Ensure CLI exposes runtime run id/path variables to YAML.
- Update Ollama demo workspace path.
- Add tests proving two runs use separate workspaces.
- Document the run-local workspace convention.

## Done

Every generated project for test/demo runs lives under its own `runs/<scenario_id>/<run_id>/workspace/` directory.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Subtasks and Done line is complete.
- ✅ Evidence: runtime variables in CLI context, example scenario workspace paths, `tests/test_cli.py` and run-local workspace docs in `docs/GETTING_STARTED.md`.
- ✅ No unchecked quest lines remain in this file.
