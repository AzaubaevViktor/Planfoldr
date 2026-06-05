# Task 005: Budget And Permission Engine

## Goal

Track budgets and enforce basic permissions.

## Concept

Budgets and permissions are inherited from parent cycles and can be delegated to nested cycles. A denied action returns a typed outcome rather than escaping the runtime model.

## Necessary Conditions

- Track `max_iterations`.
- Track `max_tool_calls`.
- Track `max_model_calls`.
- Track `max_model_budget`.
- Track `max_cpu_time`.
- Track `max_ram`.
- Enforce tool allowlist.
- Enforce filesystem allowlist.
- Return `budget_exceeded` with a report.
- Return `need_permission` for denied permissions.

## Constraints

- Full sandboxing is out of scope.
- Permission checks should be centralized.
- Budget accounting should be deterministic where possible.
- RAM budget enforcement is out of scope for MVP; report it as unsupported/placeholder if configured.

## Subtasks

- Define budget model.
- Define budget report.
- Implement budget debit/check APIs.
- Define permission model.
- Implement tool allowlist checks.
- Implement filesystem allowlist checks.
- Add tests for budget exhaustion and denied access.

## Phase 2 Decisions

- Model budget may use request count, token count or provider-returned cost.
- Filesystem allowlists use resolved paths; leave room for future jail-mount behavior.
- Command permissions use allowlist and blacklist regex rules.
- Nested budget/permission requests return to parent; parent link decides next task or failure.

## Dependencies

- Depends on task 003.
- Uses context/audit from task 004 when available.
- Blocks task 006.

## Done

Executors cannot run disallowed tools or write outside allowed filesystem paths through the runtime APIs.

## Implementation Notes

- Budget and permission checks live in `src/planfoldr/guards.py`.
- `BudgetTracker` tracks iterations, tool calls, model calls, model budget and CPU time; RAM is reported as unsupported when configured.
- `PermissionEngine` enforces tool allow/deny regex rules and resolved filesystem read/write allowlists.
- Guard failures can be converted into runtime task results with `budget_exceeded_result` and `need_permission_result`.
- Tests live in `tests/test_guards.py`.
- Continue with [Task 006: Command, Tool And Model Executors](006_executors_command_model.md).
