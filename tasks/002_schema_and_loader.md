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
