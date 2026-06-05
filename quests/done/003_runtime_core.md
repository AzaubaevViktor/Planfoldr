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

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Phase 2 Decisions, Subtasks, Dependencies, Done and Implementation Notes line is complete.
- ✅ Evidence: `src/planfoldr/runtime.py` and `tests/test_runtime_core.py` cover statuses, envelopes, links, terminal states and parent propagation.
- ✅ No unchecked quest lines remain in this file.
