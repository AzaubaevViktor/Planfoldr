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
- Supports quests 005, 008 and 009.

## Done

Tests show that task-local mutation works, parent writes require permission and all mutations are audited.

## Implementation Notes

- Context and audit primitives live in `src/planfoldr/context.py`.
- `ContextStore` stores task/cycle/scenario context snapshots and matching state snapshots.
- Task-scope reads/writes are private and allowed by default; cycle/scenario access requires declared `ContextAccess`.
- Mutations, denied mutations, state writes and decisions append immutable `AuditEvent` objects.
- Facts can be propagated upward only through explicit write access such as `cycle.facts`.
- Tests live in `tests/test_context_audit.py`.
- Continue with [Task 005: Budget And Permission Engine](005_budget_permission_engine.md).

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/004_context_state_audit.md` before this section was appended; prior `Completion Audit` is summarized separately below.

- [x] Line 1: `# Task 004: Context, State And Audit` checked and complete.
- [x] Line 2: blank separator preserved.
- [x] Line 3: `## Goal` checked and complete.
- [x] Line 4: blank separator preserved.
- [x] Line 5: `Implement scoped context/state and immutable audit events.` checked and complete.
- [x] Line 6: blank separator preserved.
- [x] Line 7: `## Concept` checked and complete.
- [x] Line 8: blank separator preserved.
- [x] Line 9: `Every task has private context. Parent context is available only through declared access. Facts move upward explicitly; constraints move ...` checked and complete.
- [x] Line 10: blank separator preserved.
- [x] Line 11: `## Necessary Conditions` checked and complete.
- [x] Line 12: blank separator preserved.
- [x] Line 13: `- Task, cycle and scenario contexts exist.` checked and complete.
- [x] Line 14: `- Task, cycle and scenario states exist.` checked and complete.
- [x] Line 15: `- Context read/write/delete access is checked.` checked and complete.
- [x] Line 16: `- Context mutations create audit events.` checked and complete.
- [x] Line 17: `- Decision log exists.` checked and complete.
- [x] Line 18: `- Facts can be propagated upward.` checked and complete.
- [x] Line 19: blank separator preserved.
- [x] Line 20: `## Constraints` checked and complete.
- [x] Line 21: blank separator preserved.
- [x] Line 22: `- Do not hide context mutation inside arbitrary executors.` checked and complete.
- [x] Line 23: `- Do not allow global writes without declared access.` checked and complete.
- [x] Line 24: `- Keep audit events machine-readable.` checked and complete.
- [x] Line 25: blank separator preserved.
- [x] Line 26: `## Phase 2 Decisions` checked and complete.
- [x] Line 27: blank separator preserved.
- [x] Line 28: `- Store context as nested dict snapshots plus immutable audit events.` checked and complete.
- [x] Line 29: `- Use scope names \`task\`, \`cycle\`, \`scenario\`, \`decision_log\`, \`audit_log\`.` checked and complete.
- [x] Line 30: `- Express context permissions as \`context_access.read/write/delete\` arrays of dotted paths.` checked and complete.
- [x] Line 31: `- Audit events include event id, timestamp, actor id, action, scope path, value summary and result.` checked and complete.
- [x] Line 32: `- Domain facts are not propagated upward implicitly; lower cycles report results to parent cycles through a specified output format.` checked and complete.
- [x] Line 33: blank separator preserved.
- [x] Line 34: `## Subtasks` checked and complete.
- [x] Line 35: blank separator preserved.
- [x] Line 36: `- Define context scopes.` checked and complete.
- [x] Line 37: `- Define context access declarations.` checked and complete.
- [x] Line 38: `- Implement read/write/delete checks.` checked and complete.
- [x] Line 39: `- Implement audit event model.` checked and complete.
- [x] Line 40: `- Implement decision log model.` checked and complete.
- [x] Line 41: `- Add tests for allowed and denied context access.` checked and complete.
- [x] Line 42: blank separator preserved.
- [x] Line 43: `## Dependencies` checked and complete.
- [x] Line 44: blank separator preserved.
- [x] Line 45: `- Depends on task 003.` checked and complete.
- [x] Line 46: `- Supports quests 005, 008 and 009.` checked and complete.
- [x] Line 47: blank separator preserved.
- [x] Line 48: `## Done` checked and complete.
- [x] Line 49: blank separator preserved.
- [x] Line 50: `Tests show that task-local mutation works, parent writes require permission and all mutations are audited.` checked and complete.
- [x] Line 51: blank separator preserved.
- [x] Line 52: `## Implementation Notes` checked and complete.
- [x] Line 53: blank separator preserved.
- [x] Line 54: `- Context and audit primitives live in \`src/planfoldr/context.py\`.` checked and complete.
- [x] Line 55: `- \`ContextStore\` stores task/cycle/scenario context snapshots and matching state snapshots.` checked and complete.
- [x] Line 56: `- Task-scope reads/writes are private and allowed by default; cycle/scenario access requires declared \`ContextAccess\`.` checked and complete.
- [x] Line 57: `- Mutations, denied mutations, state writes and decisions append immutable \`AuditEvent\` objects.` checked and complete.
- [x] Line 58: `- Facts can be propagated upward only through explicit write access such as \`cycle.facts\`.` checked and complete.
- [x] Line 59: `- Tests live in \`tests/test_context_audit.py\`.` checked and complete.
- [x] Line 60: `- Continue with [Task 005: Budget And Permission Engine](005_budget_permission_engine.md).` checked and complete.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Phase 2 Decisions, Subtasks, Dependencies, Done and Implementation Notes line is complete.
- ✅ Evidence: `src/planfoldr/context.py` and `tests/test_context_audit.py` cover scoped context/state, access checks, audit events and decisions.
- ✅ No unchecked quest lines remain in this file.
