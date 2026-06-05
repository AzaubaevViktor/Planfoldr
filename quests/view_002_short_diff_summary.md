# Task view_002: Short Diff Summary
File name: `view_002_short_diff_summary.md`

## Status

Current status: ready
Blocked by: none
Description: Follow-up for richer file-change reporting after `view_001` adds basic file change events.

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

## Implementation Notes

Generated after `view_001` added basic file change events.
