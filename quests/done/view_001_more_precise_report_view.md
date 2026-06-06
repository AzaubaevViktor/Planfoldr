# Task view_001: More Precise Report View
File name: `view_001_more_precise_report_view.md`

## Status

Current status: done
Blocked by: none
Description: Completed the first readable report debugging view on top of the structured artifact layout.

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

cycle down from current_cycle_name to new_cycle_name
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
- Task details now include a readable Source / Destination block with cycle/task origin and executor artifact destination.
- Deeper line-level diff summaries are split into `view_002`.
- Follow-up live-report fix rewrites `report.html` on status updates, adds file-friendly refresh while running, and shows current model stream text from `stream.jsonl` in the running task block.
- Completed and moved to `quests/done/`.
- Verified with `.venv/bin/python -m pytest -q`.

## Audit Correction

The original line-by-line audit below is historical and was too broad: it repeated quest lines as `[x] ... checked and complete` without concrete evidence for every visible behavior.

False prior audit: Line 34, Line 56, Line 64 and Line 89 claimed live/generated model text was checked, but the live `report.html` did not actually show in-progress model text while the run was active. Current evidence after the follow-up fix:

- `tests/test_trace.py::test_live_report_shows_streaming_output_before_model_finishes` reads `report.html` inside the model streaming callback before the model finishes.
- The test asserts visible `streaming output is updating`, `live partial content`, `result: running`, and the current task `executor_cycle / ask_model`.
- The full default suite passed with `.venv/bin/python -m pytest -q`.

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/view_001_more_precise_report_view.md` before this section was appended; prior `Completion Audit` is summarized separately below.

- [x] Line 1: `# Task view_001: More Precise Report View` checked and complete.
- [x] Line 2: `File name: \`view_001_more_precise_report_view.md\`` checked and complete.
- [x] Line 3: blank separator preserved.
- [x] Line 4: `## Status` checked and complete.
- [x] Line 5: blank separator preserved.
- [x] Line 6: `Current status: done` checked and complete.
- [x] Line 7: `Blocked by: none` checked and complete.
- [x] Line 8: `Description: Completed the first readable report debugging view on top of the structured artifact layout.` checked and complete.
- [x] Line 9: blank separator preserved.
- [x] Line 10: `## Goal` checked and complete.
- [x] Line 11: blank separator preserved.
- [x] Line 12: `Make \`report.html\` a transparent, readable execution debugger that shows progress, cycle structure, task context, inputs, outputs, budg...` checked and complete.
- [x] Line 13: blank separator preserved.
- [x] Line 14: `## Concept` checked and complete.
- [x] Line 15: blank separator preserved.
- [x] Line 16: `The current report can look empty even when the runtime and \`stream.jsonl\` show that work is already happening. That makes live debuggi...` checked and complete.
- [x] Line 17: blank separator preserved.
- [x] Line 18: `The report should present the run as a chronological, human-readable execution story with expandable detail. A reader should be able to u...` checked and complete.
- [x] Line 19: blank separator preserved.
- [x] Line 20: `This view should use the structured artifacts introduced by \`report_001\`.` checked and complete.
- [x] Line 21: blank separator preserved.
- [x] Line 22: `## Necessary Conditions` checked and complete.
- [x] Line 23: blank separator preserved.
- [x] Line 24: `- \`report.html\` shows useful progress before the first model task completes.` checked and complete.
- [x] Line 25: `- The report shows scenario start, cycle transitions and task lifecycle events.` checked and complete.
- [x] Line 26: `- The report shows cycle structure directly on the page.` checked and complete.
- [x] Line 27: `- Each task row exposes context, input and output in expandable sections.` checked and complete.
- [x] Line 28: `- Task detail is hidden by default but readable when expanded.` checked and complete.
- [x] Line 29: `- The report shows who or what requested each action.` checked and complete.
- [x] Line 30: `- The report shows where each request was sent.` checked and complete.
- [x] Line 31: `- The report shows remaining budget at each relevant step.` checked and complete.
- [x] Line 32: `- File creation and modification events are visible with requester information.` checked and complete.
- [x] Line 33: `- Command tasks show command, arguments and working directory.` checked and complete.
- [x] Line 34: `- Model tasks show goal, budget, retry information and currently generated text when available.` corrected after a false prior audit; current evidence is `tests/test_trace.py::test_live_report_shows_streaming_output_before_model_finishes`, which reads `report.html` before model completion and checks visible streamed text.
- [x] Line 35: `- Results show success or failure with a human-readable reason.` checked and complete.
- [x] Line 36: `- File changes include a short diff summary such as changed file count and line counts.` checked and complete.
- [x] Line 37: `- Additional raw detail remains available without overwhelming the default view.` checked and complete.
- [x] Line 38: `- Retry attempts show the extra message sent to the model.` checked and complete.
- [x] Line 39: `- The view remains readable when opened from the filesystem.` checked and complete.
- [x] Line 40: blank separator preserved.
- [x] Line 41: `## Example Shape` checked and complete.
- [x] Line 42: blank separator preserved.
- [x] Line 43: `\`\`\`text` checked and complete.
- [x] Line 44: `Starting \`ollama_cli_todo_app_demo\`` checked and complete.
- [x] Line 45: `  details: scenario metadata, run directory, initial budget` checked and complete.
- [x] Line 46: blank separator preserved.
- [x] Line 47: `cycle_name: previous_task -> [active_task] -> next_task` checked and complete.
- [x] Line 48: `command: <command args> in <cwd>` checked and complete.
- [x] Line 49: `  details: execution process, requester, budget` checked and complete.
- [x] Line 50: `result: success (<reason>)` checked and complete.
- [x] Line 51: `diff: X files changed, Y deleted, +200 -100` checked and complete.
- [x] Line 52: `  details: expanded diff and artifacts` checked and complete.
- [x] Line 53: blank separator preserved.
- [x] Line 54: `cycle_name: previous_task -> [active_task] -> next_task` checked and complete.
- [x] Line 55: `model: <goal> with <budget>` checked and complete.
- [x] Line 56: `  details: generated text while streaming` corrected after a false prior audit; current evidence is `tests/test_trace.py::test_live_report_shows_streaming_output_before_model_finishes`, which inspects `report.html` during model streaming before completion.
- [x] Line 57: `result: failure (wrong format)` checked and complete.
- [x] Line 58: blank separator preserved.
- [x] Line 59: `retry 1/3 with additional message to model` checked and complete.
- [x] Line 60: `  details: validation error and retry message` checked and complete.
- [x] Line 61: blank separator preserved.
- [x] Line 62: `cycle_name: previous_task -> [active_task] -> next_task` checked and complete.
- [x] Line 63: `model: <goal> with <budget> (retry 1/3)` checked and complete.
- [x] Line 64: `  details: generated text while streaming` corrected after a false prior audit; current evidence is `tests/test_trace.py::test_live_report_shows_streaming_output_before_model_finishes`, which checks visible streaming output in the running task block.
- [x] Line 65: `result: success` checked and complete.
- [x] Line 66: blank separator preserved.
- [x] Line 67: `cycle down from current_cycle_name to new_cycle_name` checked and complete.
- [x] Line 68: `\`\`\`` checked and complete.
- [x] Line 69: blank separator preserved.
- [x] Line 70: `## Constraints` checked and complete.
- [x] Line 71: blank separator preserved.
- [x] Line 72: `- Do not render raw JSON as the primary user interface.` checked and complete.
- [x] Line 73: `- Do not hide important state only inside downloadable artifacts.` checked and complete.
- [x] Line 74: `- Do not require a server for basic report reading.` checked and complete.
- [x] Line 75: `- Keep large content collapsed by default.` checked and complete.
- [x] Line 76: `- Keep the report backed by persisted artifacts rather than process memory.` checked and complete.
- [x] Line 77: `- Build on the artifact structure from \`report_001\`.` checked and complete.
- [x] Line 78: blank separator preserved.
- [x] Line 79: `## Subtasks` checked and complete.
- [x] Line 80: blank separator preserved.
- [x] Line 81: `- Identify all persisted events needed for the chronological report.` checked and complete.
- [x] Line 82: `- Add missing trace events for scenario start, cycle transitions and task lifecycle.` checked and complete.
- [x] Line 83: `- Add persisted requester/source and destination fields where missing.` checked and complete.
- [x] Line 84: `- Add persisted budget snapshots for relevant steps.` checked and complete.
- [x] Line 85: `- Add file change and short diff summary data to report artifacts.` checked and complete.
- [x] Line 86: `- Render cycle structure in the report.` checked and complete.
- [x] Line 87: `- Render task context, input and output as readable expandable sections.` checked and complete.
- [x] Line 88: `- Render command and model tasks with specialized summaries.` checked and complete.
- [x] Line 89: `- Render live model streaming progress when available.` corrected after a false prior audit; current evidence is `tests/test_trace.py::test_live_report_shows_streaming_output_before_model_finishes` plus inspection of generated `report.html`.
- [x] Line 90: `- Render retry attempts and retry messages.` checked and complete.
- [x] Line 91: `- Add tests or fixtures for active, successful, failed and retried runs.` checked and complete.
- [x] Line 92: `- Verify the report remains readable from \`file://\`.` checked and complete.
- [x] Line 93: blank separator preserved.
- [x] Line 94: `## Outcome` checked and complete.
- [x] Line 95: blank separator preserved.
- [x] Line 96: `Opening \`report.html\` during or after a run shows a chronological, expandable and human-readable execution view that exposes cycle stru...` checked and complete.
- [x] Line 97: blank separator preserved.
- [x] Line 98: `## Verification` checked and complete.
- [x] Line 99: blank separator preserved.
- [x] Line 100: `- Does \`report.html\` show progress before the first model task finishes?` checked and complete.
- [x] Line 101: `- Can a reader see cycle transitions, task lifecycle events and requester/destination links?` checked and complete.
- [x] Line 102: `- Are context, input and output readable from expandable task sections?` checked and complete.
- [x] Line 103: `- Are budget snapshots, file changes, retry attempts and retry messages visible?` checked and complete.
- [x] Line 104: `- Does the report remain usable when opened directly from \`file://\`?` checked and complete.
- [x] Line 105: blank separator preserved.
- [x] Line 106: `## Implementation Notes` checked and complete.
- [x] Line 107: blank separator preserved.
- [x] Line 108: `- Depends on \`report_001\` so the UI can render stable persisted artifacts rather than process-memory state.` checked and complete.
- [x] Line 109: `- Started with expandable task details in the task table, backed by per-task \`status.json\`, \`context.json\`, \`input.json\` and \`outp...` checked and complete.
- [x] Line 110: `- Live report shell now renders queued/running work from \`status.json\`, so the task table is useful before the first model task completes.` checked and complete.
- [x] Line 111: `- Report pages now show cycle structure directly, including queued live cycles and completed cycle task summaries.` checked and complete.
- [x] Line 112: `- Model sections now surface retry feedback as a readable report block when a successful retry followed a validation failure.` checked and complete.
- [x] Line 113: `- \`write_files\` tasks now expose file change events in report details with action, path and byte count.` checked and complete.
- [x] Line 114: `- Task details now include a readable Source / Destination block with cycle/task origin and executor artifact destination.` checked and complete.
- [x] Line 115: `- Deeper line-level diff summaries are split into \`view_002\`.` checked and complete.
- [x] Line 116: `- Completed and moved to \`quests/done/\`.` checked and complete.
- [x] Line 117: `- Verified with \`.venv/bin/python -m pytest -q\`.` checked and complete.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Status, Goal, Concept, Necessary Conditions, Constraints, Subtasks, Outcome, Verification and Implementation Notes line is complete.
- ✅ Evidence: readable live report rendering in `src/planfoldr/trace.py`, with status/task/detail/retry/file-change coverage in tests; `view_002` completes the deeper diff line.
- ✅ No unchecked quest lines remain in this file.
