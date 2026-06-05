# Task report_002: Trace Execution Bundle Writer
File name: `report_002_trace_execution_bundle_writer.md`

## Status

Current status: ready
Blocked by: none
Description: Follow-up refactor for the trace artifact structure introduced by `report_001`.

## Goal

Consolidate repeated trace bundle writing for task, command, tool and model executions into a shared helper.

## Concept

`report_001` intentionally kept task and executor bundle writing explicit while the artifact shape was still settling. Now that `status.json`, `input.json`, `context.json` and `output.json` appear in several execution directories, the writer can be simplified without changing output behavior.

## Necessary Conditions

- Task, model, tool and command execution directories keep the same public file layout.
- Shared code writes common `status.json`, `input.json`, `context.json` and `output.json` fields.
- Executor-specific additions such as model text artifacts remain supported.
- Existing trace/report tests continue to pass.

## Constraints

- Do not change public trace paths while refactoring.
- Do not remove compatibility files such as `trace/tasks/executions.json`, `trace/inputs/<execution_id>.json` or `trace/models/<execution_id>/stream.jsonl`.
- Keep the helper deterministic and easy to inspect.

## Subtasks

- Identify duplicated bundle-writing fields across task and executor artifact directories.
- Add a small helper for writing common execution bundle files.
- Keep model stream/raw-response copying as executor-specific behavior.
- Update tests only if the refactor exposes clearer assertions.
- Run the full test suite.

## Outcome

Trace bundle writing is easier to maintain, with the same persisted artifact layout and compatibility files as `report_001`.

## Verification

- Do all existing trace/report tests pass?
- Are public trace paths unchanged?
- Are extracted long fields still written and replayable?

## Implementation Notes

Generated as a follow-up after completing `report_001`; lower priority than `view_001`.
