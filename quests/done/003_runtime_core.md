# Task 003: Runtime Core

## Goal

Implement the deterministic scenario/cycle/task execution loop.

## Concept

The runtime owns control flow. Tasks return enum outcomes, and links decide the next step. Models and commands are called only through executors.

## Necessary Conditions

- Scenario run returns final status.
- Cycle run returns final status.
- Task execution returns a result envelope.
- Links branch by enum outcome.
- Terminal states `success` and `fail` work.
- Parent cycle can receive typed child requests.

## Constraints

- Do not implement real executors here beyond test doubles.
- Do not add complex parallel DAG logic yet.
- Keep runtime decisions explicit and traceable.

## Phase 2 Decisions

- Result envelope is JSON-serializable.
- Cycle starts from explicit `entrypoint`.
- Link terminal states are `success` and `fail`.
- `parent` is a control target, not a terminal state.
- Outcome names use `need_*`.
- MVP execution is sequential.
- Parent-child communication uses typed outcome plus `request` payload; parent link decides the next task or terminal state.

## Subtasks

- Define outcome enum.
- Define task result envelope.
- Implement scenario runner.
- Implement cycle runner.
- Implement link resolution.
- Implement parent request propagation.
- Add unit tests for success, failure and missing link.

## Dependencies

- Depends on task 002.
- Blocks quests 004, 005 and 006.

## Done

Stub tasks can run through a small nested scenario and produce the expected final status.

## Implementation Notes

- Runtime core lives in `src/planfoldr/runtime.py`.
- `Outcome`, `TaskResult`, `CycleResult` and `ScenarioResult` are JSON-friendly runtime primitives.
- `run_scenario` and `run_cycle` execute loaded scenarios sequentially from each cycle `entrypoint`.
- Links support task targets plus terminal `success`, terminal `fail` and control target `parent`.
- Task execution is injected through an executor callable; real command/model/tool executors start in Task 006.
- Runtime tests live in `tests/test_runtime_core.py`.
- Continue with [Task 004: Context, State And Audit](004_context_state_audit.md).

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/003_runtime_core.md` before this section was appended; prior `Completion Audit` is summarized separately below.

- [x] Line 1: `# Task 003: Runtime Core` checked and complete.
- [x] Line 2: blank separator preserved.
- [x] Line 3: `## Goal` checked and complete.
- [x] Line 4: blank separator preserved.
- [x] Line 5: `Implement the deterministic scenario/cycle/task execution loop.` checked and complete.
- [x] Line 6: blank separator preserved.
- [x] Line 7: `## Concept` checked and complete.
- [x] Line 8: blank separator preserved.
- [x] Line 9: `The runtime owns control flow. Tasks return enum outcomes, and links decide the next step. Models and commands are called only through ex...` checked and complete.
- [x] Line 10: blank separator preserved.
- [x] Line 11: `## Necessary Conditions` checked and complete.
- [x] Line 12: blank separator preserved.
- [x] Line 13: `- Scenario run returns final status.` checked and complete.
- [x] Line 14: `- Cycle run returns final status.` checked and complete.
- [x] Line 15: `- Task execution returns a result envelope.` checked and complete.
- [x] Line 16: `- Links branch by enum outcome.` checked and complete.
- [x] Line 17: `- Terminal states \`success\` and \`fail\` work.` checked and complete.
- [x] Line 18: `- Parent cycle can receive typed child requests.` checked and complete.
- [x] Line 19: blank separator preserved.
- [x] Line 20: `## Constraints` checked and complete.
- [x] Line 21: blank separator preserved.
- [x] Line 22: `- Do not implement real executors here beyond test doubles.` checked and complete.
- [x] Line 23: `- Do not add complex parallel DAG logic yet.` checked and complete.
- [x] Line 24: `- Keep runtime decisions explicit and traceable.` checked and complete.
- [x] Line 25: blank separator preserved.
- [x] Line 26: `## Phase 2 Decisions` checked and complete.
- [x] Line 27: blank separator preserved.
- [x] Line 28: `- Result envelope is JSON-serializable.` checked and complete.
- [x] Line 29: `- Cycle starts from explicit \`entrypoint\`.` checked and complete.
- [x] Line 30: `- Link terminal states are \`success\` and \`fail\`.` checked and complete.
- [x] Line 31: `- \`parent\` is a control target, not a terminal state.` checked and complete.
- [x] Line 32: `- Outcome names use \`need_*\`.` checked and complete.
- [x] Line 33: `- MVP execution is sequential.` checked and complete.
- [x] Line 34: `- Parent-child communication uses typed outcome plus \`request\` payload; parent link decides the next task or terminal state.` checked and complete.
- [x] Line 35: blank separator preserved.
- [x] Line 36: `## Subtasks` checked and complete.
- [x] Line 37: blank separator preserved.
- [x] Line 38: `- Define outcome enum.` checked and complete.
- [x] Line 39: `- Define task result envelope.` checked and complete.
- [x] Line 40: `- Implement scenario runner.` checked and complete.
- [x] Line 41: `- Implement cycle runner.` checked and complete.
- [x] Line 42: `- Implement link resolution.` checked and complete.
- [x] Line 43: `- Implement parent request propagation.` checked and complete.
- [x] Line 44: `- Add unit tests for success, failure and missing link.` checked and complete.
- [x] Line 45: blank separator preserved.
- [x] Line 46: `## Dependencies` checked and complete.
- [x] Line 47: blank separator preserved.
- [x] Line 48: `- Depends on task 002.` checked and complete.
- [x] Line 49: `- Blocks quests 004, 005 and 006.` checked and complete.
- [x] Line 50: blank separator preserved.
- [x] Line 51: `## Done` checked and complete.
- [x] Line 52: blank separator preserved.
- [x] Line 53: `Stub tasks can run through a small nested scenario and produce the expected final status.` checked and complete.
- [x] Line 54: blank separator preserved.
- [x] Line 55: `## Implementation Notes` checked and complete.
- [x] Line 56: blank separator preserved.
- [x] Line 57: `- Runtime core lives in \`src/planfoldr/runtime.py\`.` checked and complete.
- [x] Line 58: `- \`Outcome\`, \`TaskResult\`, \`CycleResult\` and \`ScenarioResult\` are JSON-friendly runtime primitives.` checked and complete.
- [x] Line 59: `- \`run_scenario\` and \`run_cycle\` execute loaded scenarios sequentially from each cycle \`entrypoint\`.` checked and complete.
- [x] Line 60: `- Links support task targets plus terminal \`success\`, terminal \`fail\` and control target \`parent\`.` checked and complete.
- [x] Line 61: `- Task execution is injected through an executor callable; real command/model/tool executors start in Task 006.` checked and complete.
- [x] Line 62: `- Runtime tests live in \`tests/test_runtime_core.py\`.` checked and complete.
- [x] Line 63: `- Continue with [Task 004: Context, State And Audit](004_context_state_audit.md).` checked and complete.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Phase 2 Decisions, Subtasks, Dependencies, Done and Implementation Notes line is complete.
- ✅ Evidence: `src/planfoldr/runtime.py` and `tests/test_runtime_core.py` cover statuses, envelopes, links, terminal states and parent propagation.
- ✅ No unchecked quest lines remain in this file.
