# Task view_002: Short Diff Summary
File name: `view_002_short_diff_summary.md`

## Status

Current status: done
Blocked by: none
Description: Completed richer file-change reporting after `view_001` added basic file change events.

## Goal

Show concise diff summaries for file-changing tasks, including changed file counts, deleted file counts and line additions/removals.

## Concept

`view_001` surfaces file creation/modification events with action, path and byte count. For larger repairs, a reader also needs a compact diff-level summary such as `X files changed, Y deleted, +200 -100` with optional expanded details.

## Necessary Conditions

- File-changing tasks can report created, modified and deleted paths.
- Report view shows a short diff summary without expanding raw artifacts.
- Expanded details can show per-file additions and removals when available.
- The implementation remains deterministic and does not require git state unless explicitly available.

## Constraints

- Do not rely on repository git history for generated workspaces.
- Do not inline huge diffs by default.
- Keep old file change event data compatible.

## Subtasks

- Capture before/after file text or hashes for file-changing tools where practical.
- Compute line additions/removals for modified text files.
- Add deleted-file support when runtime tools can delete files.
- Render compact and expanded diff summaries in `report.html`.
- Add focused tests for created, modified and deleted files.

## Outcome

Report pages show concise diff summaries for file-changing tasks while keeping detailed diff content collapsed.

### Examples

То есть как это должно выглядеть:
```
Starting `ollama_cli_todo_app_demo`
cut with additional human-readable info

cycle_name: prev_task -> [active task] -> next task
command: command args in cwd
cut with additional human-readable info about execution process
result: success (reason)
short diff (X files changed, Y delted, +200 lines -100)
cut with additional diff info

cycle_name: prev_task -> [active task] -> next task
command: command args in cwd
cut with additional human-readable info about execution process
result: success (reason)
short diff (X files changed, Y delted, +200 lines -100)
cut with additional diff info

cycle_name: prev_task -> [active task] -> next task
model: goal with X НУ
cut with additional human readable info about model message (if it works now, with generated part of text)
result: failure (wrong format)

retry 1/3 with additional message to model
cut with additional message

cycle_name: prev_task -> [active task] -> next task
model: goal with X НУ with retry info
cut with additional human readable info about model message (if it works now, with generated part of text)
result: success

cycle up/down to new_cycle_name

...

```

## Verification

- Does a created file appear in the summary?
- Does a modified file show line additions/removals?
- Are large diffs kept collapsed or linked as artifacts?
- Does cycle and tasks structure shows in report.html?
- Does current tasks show's correctly?
- Does streamed output show's in HTML?
- Does tasks type is understandable in HTML?
- We see two parts in report.html
    - current status from status.json
    - flow with addition info from all other files like in example

## Implementation Notes

Generated after `view_001` added basic file change events.
- Added `write_files` diff summaries for created, modified and deleted files, including line additions/removals.
- Report task details now show a compact `short diff` summary and expanded per-file action/path/+/- data.
- Follow-up verification replaced the old task table with the visible example-style flow, so `short diff` is readable without opening details; expanded per-file action/path/+/- data remains collapsed.
- Line-by-line audit added visible flow blocks for cycle/task context, command summaries and model summaries matching the example flow.
- Line-by-line audit added `before_bytes`, `after_bytes`, `before_sha256` and `after_sha256` to file change records, with expanded report details showing byte/hash transitions.
- Added minimal `write_files` delete support through file items with `delete: true`.
- Completed and moved to `quests/done/`.
- Verified with `.venv/bin/python -m pytest -q`.

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/view_002_short_diff_summary.md` before this section was appended.

- [x] Lines 1-2: Task title and file name still match `view_002_short_diff_summary.md`.
- [x] Lines 3, 5, 9, 11, 13, 15, 17, 19, 24, 26, 30, 32, 38, 40, 42, 44, 49, 56, 63, 68, 71, 76, 78, 80, 82, 84, 95, 97: Blank/separator lines preserved for readability.
- [x] Line 4: `Status` section remains present.
- [x] Line 6: Status remains `done`; this audit found and fixed missing visible flow/hash coverage before keeping it checked.
- [x] Line 7: Blocked by remains `none`; no unresolved blocker remains.
- [x] Line 8: Richer file-change reporting is implemented by `write_files` `file_changes`, `diff_summary`, visible report flow, and expanded details.
- [x] Line 10: `Goal` section remains present.
- [x] Line 12: Concise summaries include changed files, deleted files, additions and removals via `diff_summary`.
- [x] Line 14: `Concept` section remains present.
- [x] Line 16: The report keeps `action`, `path`, `bytes`, compact diff text and optional expanded details.
- [x] Line 18: `Necessary Conditions` section remains present.
- [x] Line 20: Created, modified and deleted paths are reported by focused executor tests.
- [x] Line 21: `short diff` is visible in the default execution flow without opening details.
- [x] Line 22: Expanded `File Changes` details show per-file `+/-`, byte span and hash span.
- [x] Line 23: Diff computation uses before/after text from the filesystem at execution time and does not require git state.
- [x] Line 25: `Constraints` section remains present.
- [x] Line 27: No repository git history is used for generated workspace diff summaries.
- [x] Line 28: Raw large diffs are not inlined; large JSON/text artifacts remain extracted and linked.
- [x] Line 29: Existing `file_changes` fields remain compatible; new hash/byte-span fields are additive.
- [x] Line 31: `Subtasks` section remains present.
- [x] Line 33: Before/after hashes and byte counts are captured for `write_files` changes where text is available.
- [x] Line 34: Modified text files compute line additions/removals with `_line_change_counts`.
- [x] Line 35: `write_files` supports `delete: true` and reports deleted files.
- [x] Line 36: `report.html` renders compact `short diff` plus expanded `File Changes`.
- [x] Line 37: Focused tests cover created, modified and deleted file reporting.
- [x] Line 39: `Outcome` section remains present.
- [x] Line 41: Report pages show concise summaries while expanded details stay collapsed.
- [x] Line 43: `Examples` heading and the example block are preserved.
- [x] Lines 45-48: Scenario start and human-readable context are covered by report heading, live status and execution log.
- [x] Lines 50-55: Command flow, command summary, result, visible short diff and expanded diff details are rendered and tested.
- [x] Lines 57-62: Repeated command/change flow is supported by the same flow renderer and focused diff fixture.
- [x] Lines 64-67: Model flow, model summary, model text/failure status paths and readable model details are covered by trace/report tests.
- [x] Lines 69-70: Retry feedback and the additional retry message are persisted and rendered in report model details.
- [x] Lines 72-75: Retry-success model flow, retry summary/details and final success are covered by validation retry report tests.
- [x] Line 77: Cycle transitions/paths are visible through flow blocks and cycle transition lines.
- [x] Line 79: Ellipsis remains as example continuation, not implementation text.
- [x] Line 81: Example code fence remains closed.
- [x] Line 83: `Verification` section remains present.
- [x] Line 85: Created files appear in summary and details.
- [x] Line 86: Modified files show line additions/removals in focused tests.
- [x] Line 87: Large outputs/diffs stay collapsed or artifact-backed; focused trace extraction test verifies this.
- [x] Line 88: Cycle and task structure appears in `report.html` through example-style flow blocks.
- [x] Line 89: Current task/live status is shown from `status.json` in the live report shell.
- [x] Line 90: Streamed model output appears in task details as content/thinking/assembled text.
- [x] Line 91: Task type is persisted in trace data and visible in task details/status artifacts.
- [x] Lines 92-94: `report.html` has both current status from `status.json` and the main execution flow with extra info.
- [x] Line 96: `Implementation Notes` section remains present.
- [x] Lines 98-104: Implementation notes remain accurate after replacing the old table with example-style flow blocks.
- [x] Verification command: `tests/test_trace.py` passed with `12 passed`.
- [x] Verification command: focused flow/diff/error/stream tests passed with `5 passed`.
- [x] Verification command: full default suite passed with `64 passed, 1 skipped`.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Status, Goal, Concept, Necessary Conditions, Constraints, Subtasks, Outcome, Examples, Verification and Implementation Notes line is complete.
- ✅ Evidence: write-file diff summaries/delete support and example-style report rendering in `src/planfoldr/executors.py` and `src/planfoldr/trace.py`, with focused report tests and inspected generated HTML.
- ✅ No unchecked quest lines remain in this file.
