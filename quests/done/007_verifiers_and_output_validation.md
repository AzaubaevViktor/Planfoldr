# Task 007: Verifiers And Output Validation

## Goal

Implement verifier tasks and structured output validation.

## Concept

Required conditions are verifier task chains. Model outputs must match declared schemas before the runtime uses their status for transitions.

## Necessary Conditions

- Validate task output against output schema.
- Retry invalid model output a configured number of times.
- Return `retry_exceeded` when retries are exhausted.
- Implement command verifier.
- Implement schema validation verifier.
- Implement custom script verifier.
- Implement model-based verifier.

## Constraints

- Verifiers are tasks, not hidden hooks.
- Verifier evidence must be captured.
- Custom scripts must go through permission checks.

## Phase 2 Decisions

- `input_schema` and `output_schema` use JSON Schema.
- Every task output must include `status`.
- Verifiers are separate tasks; model verifier tasks are allowed.
- Verifier templates may be added to avoid repeated YAML.
- Verifier evidence contains status, proof and audit log reference.
- Every retry consumes model/tool call budgets.

## Subtasks

- Select or implement schema validation.
- Add validation to model task execution.
- Add retry loop for invalid model output.
- Implement verifier task helpers.
- Add verifier evidence to result envelope.
- Add unit tests for valid, invalid and retry-exceeded outputs.

## Dependencies

- Depends on quests 006 and 005.
- Supports task 009.

## Done

A cycle can prove success through verifier tasks, and invalid model output cannot drive transitions unchecked.

## Implementation Notes

- MVP output validation lives in `src/planfoldr/validation.py`.
- `validate_task_output` checks required `status`, JSON Schema `type`, `required`, `properties`, `items` and `enum`.
- `ExecutorRegistry` validates task outputs before links consume them.
- Model tasks retry invalid output up to `invalid_output_retries`; exhausted retries return `retry_exceeded`.
- Verifier tasks attach `VerifierEvidence` to task results.
- Command, custom script and model verifiers are represented as normal `verify` tasks using command/model executors.
- Tests live in `tests/test_validation.py`.
- Continue with [Task 008: Trace, Task Replay And HTML Report](008_trace_replay_report.md).

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Phase 2 Decisions, Subtasks, Dependencies, Done and Implementation Notes line is complete.
- ✅ Evidence: `src/planfoldr/validation.py`, executor validation paths and `tests/test_validation.py` cover schema checks, retries and verifier evidence.
- ✅ No unchecked quest lines remain in this file.
