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
