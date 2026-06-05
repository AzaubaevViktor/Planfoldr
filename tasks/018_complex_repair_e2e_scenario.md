# Task 018: Complex Repair E2E Scenario

## Goal

Add a harder e2e scenario that creates a simple app, intentionally verifies a broken test, then repairs it without deleting tests.

## Concept

The current demo proves the happy path and a bounded repair loop, but it does not strongly prove that the system can reason through a failing test while preserving the test suite. Add a scenario with an explicit regression step: generate an app, break or introduce a failing test, confirm the failure, then repair the implementation or test expectation according to the task.

## Necessary Conditions

- Scenario asks the model to build a small but non-trivial app.
- Generated project includes multiple files and tests.
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

## Subtasks

- Design the demo app and regression story.
- Add scenario YAML for generate, break, verify-fail, repair and verify-pass.
- Add a task that checks test files still exist.
- Add a verifier that compares test-file inventory before and after repair.
- Add optional Ollama e2e coverage.
- Document how to run and inspect the scenario.

## Done

The e2e scenario demonstrates a real failing-test repair cycle and fails if the model solves the problem by deleting tests.
