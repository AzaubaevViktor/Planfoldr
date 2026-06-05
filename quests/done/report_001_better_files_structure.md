# Task report_001: Better Report File Structure
File name: `report_001_better_files_structure.md`

## Status

Current status: done
Blocked by: none
Description: Completed foundational report and trace artifact structure for run introspection.

## Goal

Redesign run reports around a predictable artifact structure that separates the human-readable report from trace data, execution state and large content files.

## Concept

The run directory should make both humans and tools comfortable. `report.html` remains the entry point for reading the run, while structured trace files live under `trace/` in stable locations.

Large values should not be repeatedly embedded in JSON files. When a JSON field would contain a long text value, the JSON should point to a sibling artifact file with the appropriate extension and content type. This keeps status and metadata fast to read while preserving full raw output for debugging.

## Target Structure

- `report.html`: human-readable report.
- `trace/scenario.json`: scenario-level execution trace.
- `trace/cycles/<cycle_name>.json`: cycle-level execution trace.
- `trace/tasks/<task_type>/<date_uid>/`: task execution artifacts.
- `trace/tools/<tool_name>/<date_uid>/`: tool execution artifacts.
- `trace/models/<model_name>/<date_uid>/`: model execution artifacts.
- `trace/**/status.json`: current execution status.
- `trace/**/context.json`: context available to that execution.
- `trace/**/input.json`: execution input.
- `trace/**/stream.jsonl`: streaming output.
- `trace/**/assembled.txt`: assembled stream output.
- `trace/**/content/<content_type>.<ext>`: named assembled content such as `stdout`, `stderr`, `thinking` or `output`.
- `trace/**/output.json`: deterministic output returned to the runtime.

## Necessary Conditions

- Every scenario run writes `report.html` at the run root.
- Scenario, cycle, task, tool and model traces have stable paths under `trace/`.
- Task, tool and model executions receive unique timestamp or uid based directories.
- Each execution can persist status, context, input, stream, assembled content and output.
- Report data can be refreshed from manifest-backed files without regenerating unrelated artifacts.
- Large JSON string fields are extracted into adjacent artifact files.
- Extracted long fields are replaced by a reference string to the artifact path.
- Extracted artifacts use extensions that match their content, for example `.json`, `.txt` or `.md`.
- Raw text values are stored as raw text artifacts rather than escaped JSON strings.

## Constraints

- Keep artifact paths relative to the run directory.
- Do not store generated run artifacts outside `runs/`.
- Do not inline large model, command or tool output repeatedly.
- Preserve enough backward compatibility for existing tests and reports during migration.
- Keep the structure deterministic and easy to inspect without a server.

## Subtasks

- Define the report/trace artifact layout in one place.
- Add helpers for creating execution artifact directories.
- Add helpers for writing JSON with long-field extraction.
- Migrate scenario and cycle trace writers to the new structure.
- Migrate task, tool and model artifact writers to the new structure.
- Update report generation to read the new paths.
- Add tests for generated path structure.
- Add tests for long JSON field extraction and artifact references.
- Update documentation or quest notes that mention the old report layout.

## Outcome

Each run has a readable `report.html` and a structured `trace/` tree where scenario, cycle, task, tool and model artifacts are stored consistently, with large JSON fields extracted into adjacent content files.

## Verification

- Does a run create `report.html` and the expected `trace/` structure?
- Are scenario, cycle, task, tool and model artifacts written to stable relative paths?
- Are JSON fields over the size threshold extracted into adjacent typed artifacts?
- Can the report refresh from persisted artifact data without a server?
- Do existing report and trace tests remain compatible during migration?

## Implementation Notes

- Priority anchor for the current queue. Start with deterministic trace artifact writing and long-field extraction before broad report UI changes.
- Current dependency order starts here, then `view_001`, `execution_001`, `model_001`, `orchestration_020`, and finally `scenario_018`.
- Added shared trace JSON writing that extracts string fields longer than 1000 characters into adjacent typed artifacts such as `.txt`, `.md` or `.json`.
- Extracted artifact references remain relative to `trace/`, are included in `artifacts.json`, and `replay_task` resolves extracted references back to text.
- Added per-task execution directories under `trace/tasks/<task_type>/<execution_id>/` with `status.json`, `input.json`, `context.json` and `output.json`, while preserving compatibility files such as `trace/tasks/executions.json` and `trace/inputs/<execution_id>.json`.
- Added per-cycle artifacts under `trace/cycles/<cycle_path>.json` and exposed them through `manifest.json` and `report_data.json`.
- Added executor-specific directories under `trace/models/<model_name>/<execution_id>/`, `trace/tools/<tool_name>/<execution_id>/` and `trace/commands/<command>/<execution_id>/`, preserving old compatibility files and old model stream paths.
- Changed `trace/scenario.json` into a scenario execution summary and moved the source scenario document to `trace/scenario_definition.json`; both are available during live runs.
- Completed and moved to `quests/done/`.
- Verified the slice with `.venv/bin/python -m pytest tests/test_trace.py -q`.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Status, Goal, Concept, Target Structure, Necessary Conditions, Constraints, Subtasks, Outcome, Verification and Implementation Notes line is complete.
- ✅ Evidence: structured artifact layout, long-field extraction and compatibility paths in `src/planfoldr/trace.py`, with path/extraction/replay coverage in `tests/test_trace.py`.
- ✅ No unchecked quest lines remain in this file.
