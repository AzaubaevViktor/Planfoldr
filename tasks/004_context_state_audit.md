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

## Phase 2 Decisions

- Store context as nested dict snapshots plus immutable audit events.
- Use scope names `task`, `cycle`, `scenario`, `decision_log`, `audit_log`.
- Express context permissions as `context_access.read/write/delete` arrays of dotted paths.
- Audit events include event id, timestamp, actor id, action, scope path, value summary and result.
- Domain facts are not propagated upward implicitly; lower cycles report results to parent cycles through a specified output format.

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
