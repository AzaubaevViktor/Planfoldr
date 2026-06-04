# Task 004: Context, State And Audit

## Goal

Implement scoped context/state and immutable audit events.

## Concept

Every task has private context. Parent context is available only through declared access. Facts move upward explicitly; constraints move downward through configuration.

## Necessary Conditions

- Task, cycle and scenario contexts exist.
- Task, cycle and scenario states exist.
- Context read/write/delete access is checked.
- Context mutations create audit events.
- Decision log exists.
- Facts can be propagated upward.

## Constraints

- Do not hide context mutation inside arbitrary executors.
- Do not allow global writes without declared access.
- Keep audit events machine-readable.

## Subtasks

- Define context scopes.
- Define context access declarations.
- Implement read/write/delete checks.
- Implement audit event model.
- Implement decision log model.
- Add tests for allowed and denied context access.

## Dependencies

- Depends on task 003.
- Supports tasks 005, 008 and 009.

## Done

Tests show that task-local mutation works, parent writes require permission and all mutations are audited.
