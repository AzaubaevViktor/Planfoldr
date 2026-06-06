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

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/017_per_run_workspace_isolation.md` before this section was appended; prior `Completion Audit` is summarized separately below.

- [x] Line 1: `# Task 017: Per-Run Workspace Isolation` checked and complete.
- [x] Line 2: blank separator preserved.
- [x] Line 3: `## Goal` checked and complete.
- [x] Line 4: blank separator preserved.
- [x] Line 5: `Keep generated workspaces inside each run directory so every test run starts from a clean state.` checked and complete.
- [x] Line 6: blank separator preserved.
- [x] Line 7: `## Concept` checked and complete.
- [x] Line 8: blank separator preserved.
- [x] Line 9: `Generated projects should live under the current run timestamp rather than a shared workspace path. This preserves old logs, makes report...` checked and complete.
- [x] Line 10: blank separator preserved.
- [x] Line 11: `## Necessary Conditions` checked and complete.
- [x] Line 12: blank separator preserved.
- [x] Line 13: `- Generated workspace path is inside \`runs/<scenario_id>/<run_id>/workspace/\`.` checked and complete.
- [x] Line 14: `- Example scenarios use runtime variables for run-specific workspace paths.` checked and complete.
- [x] Line 15: `- Re-running a scenario creates a fresh workspace.` checked and complete.
- [x] Line 16: `- Old run directories are not deleted automatically.` checked and complete.
- [x] Line 17: `- Reports and traces reference the run-local workspace.` checked and complete.
- [x] Line 18: blank separator preserved.
- [x] Line 19: `## Constraints` checked and complete.
- [x] Line 20: blank separator preserved.
- [x] Line 21: `- Do not write generated projects outside the active run directory.` checked and complete.
- [x] Line 22: `- Keep existing old runs inspectable.` checked and complete.
- [x] Line 23: `- Do not require manual cleanup before reruns.` checked and complete.
- [x] Line 24: blank separator preserved.
- [x] Line 25: `## Subtasks` checked and complete.
- [x] Line 26: blank separator preserved.
- [x] Line 27: `- Audit example scenario workspace paths.` checked and complete.
- [x] Line 28: `- Ensure CLI exposes runtime run id/path variables to YAML.` checked and complete.
- [x] Line 29: `- Update Ollama demo workspace path.` checked and complete.
- [x] Line 30: `- Add tests proving two runs use separate workspaces.` checked and complete.
- [x] Line 31: `- Document the run-local workspace convention.` checked and complete.
- [x] Line 32: blank separator preserved.
- [x] Line 33: `## Done` checked and complete.
- [x] Line 34: blank separator preserved.
- [x] Line 35: `Every generated project for test/demo runs lives under its own \`runs/<scenario_id>/<run_id>/workspace/\` directory.` checked and complete.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Subtasks and Done line is complete.
- ✅ Evidence: runtime variables in CLI context, example scenario workspace paths, `tests/test_cli.py` and run-local workspace docs in `docs/GETTING_STARTED.md`.
- ✅ No unchecked quest lines remain in this file.
