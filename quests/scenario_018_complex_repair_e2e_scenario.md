# Task scenario_018: Complex Repair E2E Scenario
File name: `scenario_018_complex_repair_e2e_scenario.md`

## Status

Current status: blocked
Blocked by: report_001, view_001, execution_001, model_001, orchestration_020
Description: The harder e2e scenario should come after the debugging, retry, tool-call and orchestration foundations it is meant to exercise.

## Goal

Add a harder e2e scenario that creates a simple app, intentionally verifies a broken test, then repairs it without deleting tests.

## Concept

The current demo proves the happy path and a bounded repair loop, but it does not strongly prove that the system can reason through a failing test while preserving the test suite. Add a scenario with an explicit regression step: generate an app, break or introduce a failing test, confirm the failure, then repair the implementation or test expectation according to the task.

The scenario should also exercise nested orchestration. A top-level supervision cycle creates and maintains a plan, delegates plan items to a lower execution cycle, then verifies that every plan item is done. The lower execution cycle performs individual plan steps and may request extra information or context before continuing. The whole scenario continues until the top-level plan is complete or a budget/guard stops it.

## Necessary Conditions

- Scenario asks the model to build a small but non-trivial app.
- Generated project includes multiple files and tests.
- Scenario is split into at least two cycles.
- The upper cycle creates a structured plan with multiple checklist items.
- The upper cycle delegates plan items to the lower cycle for execution.
- The upper cycle verifies each plan item against actual workspace state before marking it done.
- The lower cycle executes one or more parts of the plan.
- The lower cycle can request additional information, inspect context or gather workspace state before acting.
- The lower cycle returns execution results back to the upper cycle.
- The scenario keeps iterating until the upper cycle decides the plan is complete.
- A task intentionally creates or exposes a failing test.
- A verifier confirms that the test is actually failing before repair.
- A repair task makes the suite pass again.
- A guard/verifier ensures tests were not deleted to make the suite pass.
- Trace and report make the break/repair sequence understandable.

## Constraints

- Use only models up to 12B for real Ollama runs.
- Do not require Ollama for regular unit tests.
- Keep generated app dependency-free or use only the standard library.
- Keep the scenario bounded by explicit budgets.
- Preserve all test files unless a task explicitly allows editing them.
- Do not let the lower cycle mark the whole plan complete by itself.
- Do not accept plan-item completion without verifier evidence.

## Subtasks

- Design the demo app and regression story.
- Design the upper planning/supervision cycle.
- Design the lower execution/context-gathering cycle.
- Define the structured plan format and completion evidence.
- Add verifier tasks for each plan item.
- Add scenario YAML for generate, break, verify-fail, repair and verify-pass.
- Add tasks for context requests and workspace inspection in the lower cycle.
- Add handoff data between upper and lower cycles.
- Add a task that checks test files still exist.
- Add a verifier that compares test-file inventory before and after repair.
- Add optional Ollama e2e coverage.
- Document how to run and inspect the scenario.

## Outcome

The e2e scenario demonstrates nested planning/execution cycles, completes only after the upper plan verifies every item, demonstrates a real failing-test repair cycle and fails if the model solves the problem by deleting tests.

## Verification

- Does the scenario use at least two cycles with upper supervision and lower execution?
- Does a verifier prove the intended test failure before repair?
- Does repair make the suite pass again without deleting tests?
- Does the upper cycle require verifier evidence before marking plan items done?
- Is Ollama coverage optional and excluded from the default test suite?

## Implementation Notes

- Queue after the foundational introspection, retry, tool-call and ticket-tree work; this scenario should validate those pieces together.
