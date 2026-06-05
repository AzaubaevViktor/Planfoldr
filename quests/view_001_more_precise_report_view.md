# Task view_001: More Precise Report View

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

## Done

Opening `report.html` during or after a run shows a chronological, expandable and human-readable execution view that exposes cycle structure, task context, inputs, outputs, requester/destination links, budget snapshots, file changes and retry history.
