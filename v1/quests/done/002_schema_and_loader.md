# Task 002: Schema And Loader

## Goal

Implement loading and validation for YAML scenarios, linked YAML files and external prompt files.

## Concept

The runtime should fail early on invalid scenario structure. Schema objects should mirror [SCHEMA_DRAFT.md](../docs/phase_1/SCHEMA_DRAFT.md) and remain easy to read.

## Necessary Conditions

- Root scenario YAML can be loaded.
- Linked cycle YAML files can be resolved.
- Prompt file references can be resolved.
- Required scenario, cycle and task fields are validated.
- Validation errors name the file, path and missing/invalid field.

## Constraints

- Do not execute tasks in this step.
- Do not build a full DSL.
- Keep schema validation deterministic.

## Phase 2 Decisions

- Use Pydantic for scenario/cycle/task schemas.
- Use PyYAML for YAML parsing.
- Resolve linked YAML and prompt paths relative to the file that declares the link.
- Reject unknown fields; all fields must be explicit.
- Validation errors include file path, YAML path, expected field/type and actual value preview.

## Subtasks

- Define scenario data structures.
- Define cycle data structures.
- Define task data structures.
- Implement YAML loading.
- Implement relative file resolution.
- Implement validation errors.
- Add fixture scenarios.
- Add tests for valid and invalid files.

## Dependencies

- Depends on task 001.
- Blocks task 003.

## Done

Tests prove that valid scenarios load and invalid scenarios fail before runtime execution.

## Implementation Notes

- Pydantic schema objects live in `src/planfoldr/schema.py`.
- YAML loading, linked cycle resolution and prompt file resolution live in `src/planfoldr/loader.py`.
- `load_scenario(path)` returns a `LoadedScenario` with raw scenario data plus resolved cycles and prompt contents.
- Validation failures raise `SchemaLoadError` with file path, YAML path, expected value and actual preview.
- Loader fixtures and valid/invalid tests live under `tests/fixtures/` and `tests/test_schema_loader.py`.
- Continue with [Task 003: Runtime Core](003_runtime_core.md).

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/002_schema_and_loader.md` before this section was appended; prior `Completion Audit` is summarized separately below.

- [x] Line 1: `# Task 002: Schema And Loader` checked and complete.
- [x] Line 2: blank separator preserved.
- [x] Line 3: `## Goal` checked and complete.
- [x] Line 4: blank separator preserved.
- [x] Line 5: `Implement loading and validation for YAML scenarios, linked YAML files and external prompt files.` checked and complete.
- [x] Line 6: blank separator preserved.
- [x] Line 7: `## Concept` checked and complete.
- [x] Line 8: blank separator preserved.
- [x] Line 9: `The runtime should fail early on invalid scenario structure. Schema objects should mirror [SCHEMA_DRAFT.md](../docs/phase_1/SCHEMA_DRAFT....` checked and complete.
- [x] Line 10: blank separator preserved.
- [x] Line 11: `## Necessary Conditions` checked and complete.
- [x] Line 12: blank separator preserved.
- [x] Line 13: `- Root scenario YAML can be loaded.` checked and complete.
- [x] Line 14: `- Linked cycle YAML files can be resolved.` checked and complete.
- [x] Line 15: `- Prompt file references can be resolved.` checked and complete.
- [x] Line 16: `- Required scenario, cycle and task fields are validated.` checked and complete.
- [x] Line 17: `- Validation errors name the file, path and missing/invalid field.` checked and complete.
- [x] Line 18: blank separator preserved.
- [x] Line 19: `## Constraints` checked and complete.
- [x] Line 20: blank separator preserved.
- [x] Line 21: `- Do not execute tasks in this step.` checked and complete.
- [x] Line 22: `- Do not build a full DSL.` checked and complete.
- [x] Line 23: `- Keep schema validation deterministic.` checked and complete.
- [x] Line 24: blank separator preserved.
- [x] Line 25: `## Phase 2 Decisions` checked and complete.
- [x] Line 26: blank separator preserved.
- [x] Line 27: `- Use Pydantic for scenario/cycle/task schemas.` checked and complete.
- [x] Line 28: `- Use PyYAML for YAML parsing.` checked and complete.
- [x] Line 29: `- Resolve linked YAML and prompt paths relative to the file that declares the link.` checked and complete.
- [x] Line 30: `- Reject unknown fields; all fields must be explicit.` checked and complete.
- [x] Line 31: `- Validation errors include file path, YAML path, expected field/type and actual value preview.` checked and complete.
- [x] Line 32: blank separator preserved.
- [x] Line 33: `## Subtasks` checked and complete.
- [x] Line 34: blank separator preserved.
- [x] Line 35: `- Define scenario data structures.` checked and complete.
- [x] Line 36: `- Define cycle data structures.` checked and complete.
- [x] Line 37: `- Define task data structures.` checked and complete.
- [x] Line 38: `- Implement YAML loading.` checked and complete.
- [x] Line 39: `- Implement relative file resolution.` checked and complete.
- [x] Line 40: `- Implement validation errors.` checked and complete.
- [x] Line 41: `- Add fixture scenarios.` checked and complete.
- [x] Line 42: `- Add tests for valid and invalid files.` checked and complete.
- [x] Line 43: blank separator preserved.
- [x] Line 44: `## Dependencies` checked and complete.
- [x] Line 45: blank separator preserved.
- [x] Line 46: `- Depends on task 001.` checked and complete.
- [x] Line 47: `- Blocks task 003.` checked and complete.
- [x] Line 48: blank separator preserved.
- [x] Line 49: `## Done` checked and complete.
- [x] Line 50: blank separator preserved.
- [x] Line 51: `Tests prove that valid scenarios load and invalid scenarios fail before runtime execution.` checked and complete.
- [x] Line 52: blank separator preserved.
- [x] Line 53: `## Implementation Notes` checked and complete.
- [x] Line 54: blank separator preserved.
- [x] Line 55: `- Pydantic schema objects live in \`src/planfoldr/schema.py\`.` checked and complete.
- [x] Line 56: `- YAML loading, linked cycle resolution and prompt file resolution live in \`src/planfoldr/loader.py\`.` checked and complete.
- [x] Line 57: `- \`load_scenario(path)\` returns a \`LoadedScenario\` with raw scenario data plus resolved cycles and prompt contents.` checked and complete.
- [x] Line 58: `- Validation failures raise \`SchemaLoadError\` with file path, YAML path, expected value and actual preview.` checked and complete.
- [x] Line 59: `- Loader fixtures and valid/invalid tests live under \`tests/fixtures/\` and \`tests/test_schema_loader.py\`.` checked and complete.
- [x] Line 60: `- Continue with [Task 003: Runtime Core](003_runtime_core.md).` checked and complete.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Phase 2 Decisions, Subtasks, Dependencies, Done and Implementation Notes line is complete.
- ✅ Evidence: `src/planfoldr/schema.py`, `src/planfoldr/loader.py`, linked fixture scenarios, prompt fixtures and `tests/test_schema_loader.py`.
- ✅ No unchecked quest lines remain in this file.
