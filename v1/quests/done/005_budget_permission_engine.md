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

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/005_budget_permission_engine.md` before this section was appended; prior `Completion Audit` is summarized separately below.

- [x] Line 1: `# Task 005: Budget And Permission Engine` checked and complete.
- [x] Line 2: blank separator preserved.
- [x] Line 3: `## Goal` checked and complete.
- [x] Line 4: blank separator preserved.
- [x] Line 5: `Track budgets and enforce basic permissions.` checked and complete.
- [x] Line 6: blank separator preserved.
- [x] Line 7: `## Concept` checked and complete.
- [x] Line 8: blank separator preserved.
- [x] Line 9: `Budgets and permissions are inherited from parent cycles and can be delegated to nested cycles. A denied action returns a typed outcome r...` checked and complete.
- [x] Line 10: blank separator preserved.
- [x] Line 11: `## Necessary Conditions` checked and complete.
- [x] Line 12: blank separator preserved.
- [x] Line 13: `- Track \`max_iterations\`.` checked and complete.
- [x] Line 14: `- Track \`max_tool_calls\`.` checked and complete.
- [x] Line 15: `- Track \`max_model_calls\`.` checked and complete.
- [x] Line 16: `- Track \`max_model_budget\`.` checked and complete.
- [x] Line 17: `- Track \`max_cpu_time\`.` checked and complete.
- [x] Line 18: `- Track \`max_ram\`.` checked and complete.
- [x] Line 19: `- Enforce tool allowlist.` checked and complete.
- [x] Line 20: `- Enforce filesystem allowlist.` checked and complete.
- [x] Line 21: `- Return \`budget_exceeded\` with a report.` checked and complete.
- [x] Line 22: `- Return \`need_permission\` for denied permissions.` checked and complete.
- [x] Line 23: blank separator preserved.
- [x] Line 24: `## Constraints` checked and complete.
- [x] Line 25: blank separator preserved.
- [x] Line 26: `- Full sandboxing is out of scope.` checked and complete.
- [x] Line 27: `- Permission checks should be centralized.` checked and complete.
- [x] Line 28: `- Budget accounting should be deterministic where possible.` checked and complete.
- [x] Line 29: `- RAM budget enforcement is out of scope for MVP; report it as unsupported/placeholder if configured.` checked and complete.
- [x] Line 30: blank separator preserved.
- [x] Line 31: `## Subtasks` checked and complete.
- [x] Line 32: blank separator preserved.
- [x] Line 33: `- Define budget model.` checked and complete.
- [x] Line 34: `- Define budget report.` checked and complete.
- [x] Line 35: `- Implement budget debit/check APIs.` checked and complete.
- [x] Line 36: `- Define permission model.` checked and complete.
- [x] Line 37: `- Implement tool allowlist checks.` checked and complete.
- [x] Line 38: `- Implement filesystem allowlist checks.` checked and complete.
- [x] Line 39: `- Add tests for budget exhaustion and denied access.` checked and complete.
- [x] Line 40: blank separator preserved.
- [x] Line 41: `## Phase 2 Decisions` checked and complete.
- [x] Line 42: blank separator preserved.
- [x] Line 43: `- Model budget may use request count, token count or provider-returned cost.` checked and complete.
- [x] Line 44: `- Filesystem allowlists use resolved paths; leave room for future jail-mount behavior.` checked and complete.
- [x] Line 45: `- Command permissions use allowlist and blacklist regex rules.` checked and complete.
- [x] Line 46: `- Nested budget/permission requests return to parent; parent link decides next task or failure.` checked and complete.
- [x] Line 47: blank separator preserved.
- [x] Line 48: `## Dependencies` checked and complete.
- [x] Line 49: blank separator preserved.
- [x] Line 50: `- Depends on task 003.` checked and complete.
- [x] Line 51: `- Uses context/audit from task 004 when available.` checked and complete.
- [x] Line 52: `- Blocks task 006.` checked and complete.
- [x] Line 53: blank separator preserved.
- [x] Line 54: `## Done` checked and complete.
- [x] Line 55: blank separator preserved.
- [x] Line 56: `Executors cannot run disallowed tools or write outside allowed filesystem paths through the runtime APIs.` checked and complete.
- [x] Line 57: blank separator preserved.
- [x] Line 58: `## Implementation Notes` checked and complete.
- [x] Line 59: blank separator preserved.
- [x] Line 60: `- Budget and permission checks live in \`src/planfoldr/guards.py\`.` checked and complete.
- [x] Line 61: `- \`BudgetTracker\` tracks iterations, tool calls, model calls, model budget and CPU time; RAM is reported as unsupported when configured.` checked and complete.
- [x] Line 62: `- \`PermissionEngine\` enforces tool allow/deny regex rules and resolved filesystem read/write allowlists.` checked and complete.
- [x] Line 63: `- Guard failures can be converted into runtime task results with \`budget_exceeded_result\` and \`need_permission_result\`.` checked and complete.
- [x] Line 64: `- Tests live in \`tests/test_guards.py\`.` checked and complete.
- [x] Line 65: `- Continue with [Task 006: Command, Tool And Model Executors](006_executors_command_model.md).` checked and complete.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Phase 2 Decisions, Subtasks, Dependencies, Done and Implementation Notes line is complete.
- ✅ Evidence: `src/planfoldr/guards.py` and `tests/test_guards.py` cover tracked budgets, permission allowlists and typed guard failures.
- ✅ No unchecked quest lines remain in this file.
