# Task view_001: More Precise Report View
File name: `view_001_more_precise_report_view.md`

## Status

Current status: in_progress
Blocked by: none
Description: Building the readable report view on top of the structured artifact layout completed in `report_001`.

## Goal

Make `report.html` a transparent, readable execution debugger that shows progress, cycle structure, task context, inputs, outputs, budgets and retry history while a run is still active.

## Concept

The current report can look empty even when the runtime and `stream.jsonl` show that work is already happening. That makes live debugging difficult: before a model starts, the report should already show scenario startup, cycle entry, task scheduling and any earlier deterministic work.

The report should present the run as a chronological, human-readable execution story with expandable detail. A reader should be able to understand where each request came from, where it went, what context was available, what changed, why retries happened and what budget remained at each step.

This view should use the structured artifacts introduced by `report_001`.

## Necessary Conditions

- `report.html` shows useful progress before the first model task completes.
- The report shows scenario start, cycle transitions and task lifecycle events.
- The report shows cycle structure directly on the page.
- Each task row exposes context, input and output in expandable sections.
- Task detail is hidden by default but readable when expanded.
- The report shows who or what requested each action.
- The report shows where each request was sent.
- The report shows remaining budget at each relevant step.
- File creation and modification events are visible with requester information.
- Command tasks show command, arguments and working directory.
- Model tasks show goal, budget, retry information and currently generated text when available.
- Results show success or failure with a human-readable reason.
- File changes include a short diff summary such as changed file count and line counts.
- Additional raw detail remains available without overwhelming the default view.
- Retry attempts show the extra message sent to the model.
- The view remains readable when opened from the filesystem.

## Example Shape

```text
Starting `ollama_cli_todo_app_demo`
  details: scenario metadata, run directory, initial budget

cycle_name: previous_task -> [active_task] -> next_task
command: <command args> in <cwd>
  details: execution process, requester, budget
result: success (<reason>)
diff: X files changed, Y deleted, +200 -100
  details: expanded diff and artifacts

cycle_name: previous_task -> [active_task] -> next_task
model: <goal> with <budget>
  details: generated text while streaming
result: failure (wrong format)

retry 1/3 with additional message to model
  details: validation error and retry message

cycle_name: previous_task -> [active_task] -> next_task
model: <goal> with <budget> (retry 1/3)
  details: generated text while streaming
result: success

cycle up/down to new_cycle_name
```

## Constraints

- Do not render raw JSON as the primary user interface.
- Do not hide important state only inside downloadable artifacts.
- Do not require a server for basic report reading.
- Keep large content collapsed by default.
- Keep the report backed by persisted artifacts rather than process memory.
- Build on the artifact structure from `report_001`.

## Subtasks

- Identify all persisted events needed for the chronological report.
- Add missing trace events for scenario start, cycle transitions and task lifecycle.
- Add persisted requester/source and destination fields where missing.
- Add persisted budget snapshots for relevant steps.
- Add file change and short diff summary data to report artifacts.
- Render cycle structure in the report.
- Render task context, input and output as readable expandable sections.
- Render command and model tasks with specialized summaries.
- Render live model streaming progress when available.
- Render retry attempts and retry messages.
- Add tests or fixtures for active, successful, failed and retried runs.
- Verify the report remains readable from `file://`.

## Outcome

Opening `report.html` during or after a run shows a chronological, expandable and human-readable execution view that exposes cycle structure, task context, inputs, outputs, requester/destination links, budget snapshots, file changes and retry history.

## Verification

- Does `report.html` show progress before the first model task finishes?
- Can a reader see cycle transitions, task lifecycle events and requester/destination links?
- Are context, input and output readable from expandable task sections?
- Are budget snapshots, file changes, retry attempts and retry messages visible?
- Does the report remain usable when opened directly from `file://`?

## Implementation Notes

- Depends on `report_001` so the UI can render stable persisted artifacts rather than process-memory state.
- Started with expandable task details in the task table, backed by per-task `status.json`, `context.json`, `input.json` and `output.json` artifacts.
- Live report shell now renders queued/running work from `status.json`, so the task table is useful before the first model task completes.
- Report pages now show cycle structure directly, including queued live cycles and completed cycle task summaries.
- Model sections now surface retry feedback as a readable report block when a successful retry followed a validation failure.
- `write_files` tasks now expose file change events in report details with action, path and byte count.
