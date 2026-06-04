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

## Subtasks

- Select or implement schema validation.
- Add validation to model task execution.
- Add retry loop for invalid model output.
- Implement verifier task helpers.
- Add verifier evidence to result envelope.
- Add unit tests for valid, invalid and retry-exceeded outputs.

## Dependencies

- Depends on tasks 006 and 005.
- Supports task 009.

## Done

A cycle can prove success through verifier tasks, and invalid model output cannot drive transitions unchecked.
