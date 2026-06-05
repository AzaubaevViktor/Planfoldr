# Task 008: Trace, Task Replay And HTML Report

## Goal

Persist structured run traces, support task replay and render a static HTML report.

## Concept

The trace is the main observability artifact. The HTML report is a human view over the same machine-readable data.

## Necessary Conditions

- Write a trace directory for every run.
- Write a trace manifest for every run.
- Trace contains scenario status.
- Trace contains task executions.
- Trace contains model requests/responses.
- Trace contains command results.
- Trace contains budget snapshots.
- Trace contains prompt metadata.
- Trace contains audit and decision logs.
- Task replay can use captured task input/output without re-executing the model/tool.
- Static one-page HTML report renders from trace manifest and lazily loaded trace parts.
- Report shows nested execution and collapsible deep levels.
- Report can filter execution log by cycle and task.
- Report can inspect what happened in a specific cycle/task/link/tool.

## Constraints

- Full scenario replay is out of scope.
- Semantic run diff is out of scope.
- Report should not require a server.

## Phase 2 Decisions

- Trace uses a structured directory layout under `runs/<scenario_id>/trace/`.
- Trace schema version starts at `0.1`.
- Task replay means restoring task result from saved trace without calling model/tool.
- HTML report first shows cycle/task structure and execution log.
- Static HTML lazily loads data from the trace directory.

## Subtasks

- Define trace writer.
- Define artifact paths.
- Implement task replay mode.
- Implement HTML report renderer.
- Add report fixture tests.
- Add snapshot or smoke tests for generated HTML.

## Dependencies

- Depends on quests 003, 004, 006 and 007.
- Blocks task 009.

## Done

Every e2e run leaves a trace JSON and static HTML report that can be inspected without rerunning the scenario.

## Implementation Notes

- Trace and report support lives in `src/planfoldr/trace.py`.
- `run_and_trace` runs a loaded scenario and writes `runs/<scenario_id>/trace/` plus `report.html`.
- `TraceWriter` writes `manifest.json`, `scenario.json`, cycle/task execution parts, model/command/tool details, audit and decision logs.
- `replay_task(trace_dir, task_id)` restores a captured `TaskResult` without re-executing any adapter.
- The HTML report is static and includes cycle structure, execution log and task filtering.
- Tests live in `tests/test_trace.py`.
- Continue with [Task 009: E2E Stub Scenarios](009_e2e_stub_scenarios.md).

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/008_trace_replay_report.md` before this section was appended; prior `Completion Audit` is summarized separately below.

- [x] Line 1: `# Task 008: Trace, Task Replay And HTML Report` checked and complete.
- [x] Line 2: blank separator preserved.
- [x] Line 3: `## Goal` checked and complete.
- [x] Line 4: blank separator preserved.
- [x] Line 5: `Persist structured run traces, support task replay and render a static HTML report.` checked and complete.
- [x] Line 6: blank separator preserved.
- [x] Line 7: `## Concept` checked and complete.
- [x] Line 8: blank separator preserved.
- [x] Line 9: `The trace is the main observability artifact. The HTML report is a human view over the same machine-readable data.` checked and complete.
- [x] Line 10: blank separator preserved.
- [x] Line 11: `## Necessary Conditions` checked and complete.
- [x] Line 12: blank separator preserved.
- [x] Line 13: `- Write a trace directory for every run.` checked and complete.
- [x] Line 14: `- Write a trace manifest for every run.` checked and complete.
- [x] Line 15: `- Trace contains scenario status.` checked and complete.
- [x] Line 16: `- Trace contains task executions.` checked and complete.
- [x] Line 17: `- Trace contains model requests/responses.` checked and complete.
- [x] Line 18: `- Trace contains command results.` checked and complete.
- [x] Line 19: `- Trace contains budget snapshots.` checked and complete.
- [x] Line 20: `- Trace contains prompt metadata.` checked and complete.
- [x] Line 21: `- Trace contains audit and decision logs.` checked and complete.
- [x] Line 22: `- Task replay can use captured task input/output without re-executing the model/tool.` checked and complete.
- [x] Line 23: `- Static one-page HTML report renders from trace manifest and lazily loaded trace parts.` checked and complete.
- [x] Line 24: `- Report shows nested execution and collapsible deep levels.` checked and complete.
- [x] Line 25: `- Report can filter execution log by cycle and task.` checked and complete.
- [x] Line 26: `- Report can inspect what happened in a specific cycle/task/link/tool.` checked and complete.
- [x] Line 27: blank separator preserved.
- [x] Line 28: `## Constraints` checked and complete.
- [x] Line 29: blank separator preserved.
- [x] Line 30: `- Full scenario replay is out of scope.` checked and complete.
- [x] Line 31: `- Semantic run diff is out of scope.` checked and complete.
- [x] Line 32: `- Report should not require a server.` checked and complete.
- [x] Line 33: blank separator preserved.
- [x] Line 34: `## Phase 2 Decisions` checked and complete.
- [x] Line 35: blank separator preserved.
- [x] Line 36: `- Trace uses a structured directory layout under \`runs/<scenario_id>/trace/\`.` checked and complete.
- [x] Line 37: `- Trace schema version starts at \`0.1\`.` checked and complete.
- [x] Line 38: `- Task replay means restoring task result from saved trace without calling model/tool.` checked and complete.
- [x] Line 39: `- HTML report first shows cycle/task structure and execution log.` checked and complete.
- [x] Line 40: `- Static HTML lazily loads data from the trace directory.` checked and complete.
- [x] Line 41: blank separator preserved.
- [x] Line 42: `## Subtasks` checked and complete.
- [x] Line 43: blank separator preserved.
- [x] Line 44: `- Define trace writer.` checked and complete.
- [x] Line 45: `- Define artifact paths.` checked and complete.
- [x] Line 46: `- Implement task replay mode.` checked and complete.
- [x] Line 47: `- Implement HTML report renderer.` checked and complete.
- [x] Line 48: `- Add report fixture tests.` checked and complete.
- [x] Line 49: `- Add snapshot or smoke tests for generated HTML.` checked and complete.
- [x] Line 50: blank separator preserved.
- [x] Line 51: `## Dependencies` checked and complete.
- [x] Line 52: blank separator preserved.
- [x] Line 53: `- Depends on quests 003, 004, 006 and 007.` checked and complete.
- [x] Line 54: `- Blocks task 009.` checked and complete.
- [x] Line 55: blank separator preserved.
- [x] Line 56: `## Done` checked and complete.
- [x] Line 57: blank separator preserved.
- [x] Line 58: `Every e2e run leaves a trace JSON and static HTML report that can be inspected without rerunning the scenario.` checked and complete.
- [x] Line 59: blank separator preserved.
- [x] Line 60: `## Implementation Notes` checked and complete.
- [x] Line 61: blank separator preserved.
- [x] Line 62: `- Trace and report support lives in \`src/planfoldr/trace.py\`.` checked and complete.
- [x] Line 63: `- \`run_and_trace\` runs a loaded scenario and writes \`runs/<scenario_id>/trace/\` plus \`report.html\`.` checked and complete.
- [x] Line 64: `- \`TraceWriter\` writes \`manifest.json\`, \`scenario.json\`, cycle/task execution parts, model/command/tool details, audit and decision...` checked and complete.
- [x] Line 65: `- \`replay_task(trace_dir, task_id)\` restores a captured \`TaskResult\` without re-executing any adapter.` checked and complete.
- [x] Line 66: `- The HTML report is static and includes cycle structure, execution log and task filtering.` checked and complete.
- [x] Line 67: `- Tests live in \`tests/test_trace.py\`.` checked and complete.
- [x] Line 68: `- Continue with [Task 009: E2E Stub Scenarios](009_e2e_stub_scenarios.md).` checked and complete.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Phase 2 Decisions, Subtasks, Dependencies, Done and Implementation Notes line is complete.
- ✅ Evidence: `src/planfoldr/trace.py` and `tests/test_trace.py` cover trace writing, replay and static report generation.
- ✅ No unchecked quest lines remain in this file.
