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

- Depends on tasks 003, 004, 006 and 007.
- Blocks task 009.

## Done

Every e2e run leaves a trace JSON and static HTML report that can be inspected without rerunning the scenario.
