# Task scenario_018: Complex Repair E2E Scenario
File name: `scenario_018_complex_repair_e2e_scenario.md`

## Status

Current status: blocked
Blocked by: orchestration_020
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

## Completion Audit

Checked: 2026-06-06.

### Necessary Conditions

- ❌ Scenario asks the model to build a small but non-trivial app.
- ❌ Generated project includes multiple files and tests for this scenario.
- ❌ Scenario is split into at least two cycles.
- ❌ The upper cycle creates a structured plan with multiple checklist items.
- ❌ The upper cycle delegates plan items to the lower cycle for execution.
- ❌ The upper cycle verifies each plan item against actual workspace state before marking it done.
- ❌ The lower cycle executes one or more parts of the plan.
- ❌ The lower cycle can request additional information, inspect context or gather workspace state before acting.
- ❌ The lower cycle returns execution results back to the upper cycle.
- ❌ The scenario keeps iterating until the upper cycle decides the plan is complete.
- ❌ A task intentionally creates or exposes a failing test.
- ❌ A verifier confirms that the test is actually failing before repair.
- ❌ A repair task makes the suite pass again.
- ❌ A guard/verifier ensures tests were not deleted to make the suite pass.
- ❌ Trace and report make the break/repair sequence understandable for this scenario.

### Constraints

- ❌ Use only models up to 12B for real Ollama runs; no real run for this scenario exists yet.
- ✅ Do not require Ollama for regular unit tests.
- ❌ Keep generated app dependency-free or use only the standard library; no generated app exists yet.
- ❌ Keep the scenario bounded by explicit budgets; no scenario YAML exists yet.
- ❌ Preserve all test files unless a task explicitly allows editing them; no inventory guard exists for this scenario yet.
- ❌ Do not let the lower cycle mark the whole plan complete by itself; no lower cycle exists yet.
- ❌ Do not accept plan-item completion without verifier evidence; plan item completion is not implemented yet.

### Subtasks

- ❌ Design the demo app and regression story.
- ❌ Design the upper planning/supervision cycle.
- ❌ Design the lower execution/context-gathering cycle.
- ❌ Define the structured plan format and completion evidence.
- ❌ Add verifier tasks for each plan item.
- ❌ Add scenario YAML for generate, break, verify-fail, repair and verify-pass.
- ❌ Add tasks for context requests and workspace inspection in the lower cycle.
- ❌ Add handoff data between upper and lower cycles.
- ❌ Add a task that checks test files still exist.
- ❌ Add a verifier that compares test-file inventory before and after repair.
- ❌ Add optional Ollama e2e coverage.
- ❌ Document how to run and inspect the scenario.

### Outcome And Verification

- ❌ Outcome is not complete; the scenario remains blocked by `orchestration_020`.
- ❌ The scenario does not yet use at least two cycles with upper supervision and lower execution.
- ❌ No verifier proves an intended test failure before repair.
- ❌ No repair pass proves the suite passes without deleting tests.
- ❌ No upper-cycle verifier-evidence gate exists yet.
- ✅ Optional Ollama coverage remains excluded from the default test suite in the existing project.

## Implementation Notes

- Queue after the foundational introspection, retry, tool-call and ticket-tree work; this scenario should validate those pieces together.
- Partial MVP added before `orchestration_020` is complete: `examples/scenarios/ollama_notes_app.yaml` runs two sequential cycles, `ollama_notes_plan` and `ollama_notes_repair`, so it exercises supervision-plan output plus execution/repair evidence within the current runtime.
- The new notes scenario asks a local model to create a multi-file dependency-free `notes_app` package with CLI, tests, `AGENTS.md` and `ARCHITECTURE.md`, then injects a deterministic mixed-case tag regression test, records test inventory, confirms the regression, repairs, reruns the full suite and verifies the recorded test files still exist.
- Added helper scripts `examples/scripts/inject_notes_regression_test.py` and `examples/scripts/notes_test_inventory.py` for deterministic regression and inventory checks.
- Added default-suite coverage for scenario loading, hidden notes-project contract behavior and a stubbed fail-before-repair loop in `tests/test_ollama_notes_e2e.py`; optional real Ollama coverage is gated by `PLANFOLDR_RUN_OLLAMA_COMPLEX_E2E=1`.
- Verification run: `.venv/bin/python -m pytest tests/test_schema_loader.py::test_loads_complex_notes_ollama_example_scenario tests/test_ollama_notes_e2e.py::test_hidden_notes_contract_accepts_reference_project tests/test_ollama_notes_e2e.py::test_complex_notes_stub_scenario_repairs_mixed_case_regression -q` passed with `3 passed`.
- Verification run: `.venv/bin/python -m pytest -q` passed with `67 passed, 2 skipped`.
- Inspected generated stub report and `trace/report_data.json`; task statuses show `run_regression_tests` failed before `repair_notes_project`, then `verify_repaired` and `verify_test_inventory` succeeded. Full `scenario_018` remains blocked because current runtime still does not execute true nested delegation or upper-cycle evidence gates from `orchestration_020`.
