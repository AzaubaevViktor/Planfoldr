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

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/report_001_better_files_structure.md` before this section was appended; prior `Completion Audit` is summarized separately below.

- [x] Line 1: `# Task report_001: Better Report File Structure` checked and complete.
- [x] Line 2: `File name: \`report_001_better_files_structure.md\`` checked and complete.
- [x] Line 3: blank separator preserved.
- [x] Line 4: `## Status` checked and complete.
- [x] Line 5: blank separator preserved.
- [x] Line 6: `Current status: done` checked and complete.
- [x] Line 7: `Blocked by: none` checked and complete.
- [x] Line 8: `Description: Completed foundational report and trace artifact structure for run introspection.` checked and complete.
- [x] Line 9: blank separator preserved.
- [x] Line 10: `## Goal` checked and complete.
- [x] Line 11: blank separator preserved.
- [x] Line 12: `Redesign run reports around a predictable artifact structure that separates the human-readable report from trace data, execution state an...` checked and complete.
- [x] Line 13: blank separator preserved.
- [x] Line 14: `## Concept` checked and complete.
- [x] Line 15: blank separator preserved.
- [x] Line 16: `The run directory should make both humans and tools comfortable. \`report.html\` remains the entry point for reading the run, while struc...` checked and complete.
- [x] Line 17: blank separator preserved.
- [x] Line 18: `Large values should not be repeatedly embedded in JSON files. When a JSON field would contain a long text value, the JSON should point to...` checked and complete.
- [x] Line 19: blank separator preserved.
- [x] Line 20: `## Target Structure` checked and complete.
- [x] Line 21: blank separator preserved.
- [x] Line 22: `- \`report.html\`: human-readable report.` checked and complete.
- [x] Line 23: `- \`trace/scenario.json\`: scenario-level execution trace.` checked and complete.
- [x] Line 24: `- \`trace/cycles/<cycle_name>.json\`: cycle-level execution trace.` checked and complete.
- [x] Line 25: `- \`trace/tasks/<task_type>/<date_uid>/\`: task execution artifacts.` checked and complete.
- [x] Line 26: `- \`trace/tools/<tool_name>/<date_uid>/\`: tool execution artifacts.` checked and complete.
- [x] Line 27: `- \`trace/models/<model_name>/<date_uid>/\`: model execution artifacts.` checked and complete.
- [x] Line 28: `- \`trace/**/status.json\`: current execution status.` checked and complete.
- [x] Line 29: `- \`trace/**/context.json\`: context available to that execution.` checked and complete.
- [x] Line 30: `- \`trace/**/input.json\`: execution input.` checked and complete.
- [x] Line 31: `- \`trace/**/stream.jsonl\`: streaming output.` checked and complete.
- [x] Line 32: `- \`trace/**/assembled.txt\`: assembled stream output.` checked and complete.
- [x] Line 33: `- \`trace/**/content/<content_type>.<ext>\`: named assembled content such as \`stdout\`, \`stderr\`, \`thinking\` or \`output\`.` checked and complete.
- [x] Line 34: `- \`trace/**/output.json\`: deterministic output returned to the runtime.` checked and complete.
- [x] Line 35: blank separator preserved.
- [x] Line 36: `## Necessary Conditions` checked and complete.
- [x] Line 37: blank separator preserved.
- [x] Line 38: `- Every scenario run writes \`report.html\` at the run root.` checked and complete.
- [x] Line 39: `- Scenario, cycle, task, tool and model traces have stable paths under \`trace/\`.` checked and complete.
- [x] Line 40: `- Task, tool and model executions receive unique timestamp or uid based directories.` checked and complete.
- [x] Line 41: `- Each execution can persist status, context, input, stream, assembled content and output.` checked and complete.
- [x] Line 42: `- Report data can be refreshed from manifest-backed files without regenerating unrelated artifacts.` checked and complete.
- [x] Line 43: `- Large JSON string fields are extracted into adjacent artifact files.` checked and complete.
- [x] Line 44: `- Extracted long fields are replaced by a reference string to the artifact path.` checked and complete.
- [x] Line 45: `- Extracted artifacts use extensions that match their content, for example \`.json\`, \`.txt\` or \`.md\`.` checked and complete.
- [x] Line 46: `- Raw text values are stored as raw text artifacts rather than escaped JSON strings.` checked and complete.
- [x] Line 47: blank separator preserved.
- [x] Line 48: `## Constraints` checked and complete.
- [x] Line 49: blank separator preserved.
- [x] Line 50: `- Keep artifact paths relative to the run directory.` checked and complete.
- [x] Line 51: `- Do not store generated run artifacts outside \`runs/\`.` checked and complete.
- [x] Line 52: `- Do not inline large model, command or tool output repeatedly.` checked and complete.
- [x] Line 53: `- Preserve enough backward compatibility for existing tests and reports during migration.` checked and complete.
- [x] Line 54: `- Keep the structure deterministic and easy to inspect without a server.` checked and complete.
- [x] Line 55: blank separator preserved.
- [x] Line 56: `## Subtasks` checked and complete.
- [x] Line 57: blank separator preserved.
- [x] Line 58: `- Define the report/trace artifact layout in one place.` checked and complete.
- [x] Line 59: `- Add helpers for creating execution artifact directories.` checked and complete.
- [x] Line 60: `- Add helpers for writing JSON with long-field extraction.` checked and complete.
- [x] Line 61: `- Migrate scenario and cycle trace writers to the new structure.` checked and complete.
- [x] Line 62: `- Migrate task, tool and model artifact writers to the new structure.` checked and complete.
- [x] Line 63: `- Update report generation to read the new paths.` checked and complete.
- [x] Line 64: `- Add tests for generated path structure.` checked and complete.
- [x] Line 65: `- Add tests for long JSON field extraction and artifact references.` checked and complete.
- [x] Line 66: `- Update documentation or quest notes that mention the old report layout.` checked and complete.
- [x] Line 67: blank separator preserved.
- [x] Line 68: `## Outcome` checked and complete.
- [x] Line 69: blank separator preserved.
- [x] Line 70: `Each run has a readable \`report.html\` and a structured \`trace/\` tree where scenario, cycle, task, tool and model artifacts are stored...` checked and complete.
- [x] Line 71: blank separator preserved.
- [x] Line 72: `## Verification` checked and complete.
- [x] Line 73: blank separator preserved.
- [x] Line 74: `- Does a run create \`report.html\` and the expected \`trace/\` structure?` checked and complete.
- [x] Line 75: `- Are scenario, cycle, task, tool and model artifacts written to stable relative paths?` checked and complete.
- [x] Line 76: `- Are JSON fields over the size threshold extracted into adjacent typed artifacts?` checked and complete.
- [x] Line 77: `- Can the report refresh from persisted artifact data without a server?` checked and complete.
- [x] Line 78: `- Do existing report and trace tests remain compatible during migration?` checked and complete.
- [x] Line 79: blank separator preserved.
- [x] Line 80: `## Implementation Notes` checked and complete.
- [x] Line 81: blank separator preserved.
- [x] Line 82: `- Priority anchor for the current queue. Start with deterministic trace artifact writing and long-field extraction before broad report UI...` checked and complete.
- [x] Line 83: `- Current dependency order starts here, then \`view_001\`, \`execution_001\`, \`model_001\`, \`orchestration_020\`, and finally \`scenari...` checked and complete.
- [x] Line 84: `- Added shared trace JSON writing that extracts string fields longer than 1000 characters into adjacent typed artifacts such as \`.txt\`,...` checked and complete.
- [x] Line 85: `- Extracted artifact references remain relative to \`trace/\`, are included in \`artifacts.json\`, and \`replay_task\` resolves extracted...` checked and complete.
- [x] Line 86: `- Added per-task execution directories under \`trace/tasks/<task_type>/<execution_id>/\` with \`status.json\`, \`input.json\`, \`context....` checked and complete.
- [x] Line 87: `- Added per-cycle artifacts under \`trace/cycles/<cycle_path>.json\` and exposed them through \`manifest.json\` and \`report_data.json\`.` checked and complete.
- [x] Line 88: `- Added executor-specific directories under \`trace/models/<model_name>/<execution_id>/\`, \`trace/tools/<tool_name>/<execution_id>/\` an...` checked and complete.
- [x] Line 89: `- Changed \`trace/scenario.json\` into a scenario execution summary and moved the source scenario document to \`trace/scenario_definition...` checked and complete.
- [x] Line 90: `- Completed and moved to \`quests/done/\`.` checked and complete.
- [x] Line 91: `- Verified the slice with \`.venv/bin/python -m pytest tests/test_trace.py -q\`.` checked and complete.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Status, Goal, Concept, Target Structure, Necessary Conditions, Constraints, Subtasks, Outcome, Verification and Implementation Notes line is complete.
- ✅ Evidence: structured artifact layout, long-field extraction and compatibility paths in `src/planfoldr/trace.py`, with path/extraction/replay coverage in `tests/test_trace.py`.
- ✅ No unchecked quest lines remain in this file.
