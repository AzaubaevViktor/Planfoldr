# Task 009: E2E Stub Scenarios

## Goal

Create e2e tests that run complete scenarios with stubbed model responses.

## Concept

Stubbed e2e scenarios are the main safety net. They prove flow correctness without depending on model quality or local Ollama availability.

## Necessary Conditions

- Successful e2e scenario passes.
- Multiple unsuccessful e2e scenarios pass by failing in expected ways.
- Budget exhaustion scenario is covered.
- Retry exhaustion scenario is covered.
- Patch-loop scenario is covered.
- All scenarios produce trace directories.
- Both scenarios produce HTML reports.
- Tests assert final status.
- Tests assert key task outcomes.

## Constraints

- Do not call real models in these tests.
- Do not depend on network.
- Keep fixtures small.

## Phase 2 Decisions

- Stub e2e coverage should include success plus bad scenarios for each important runtime element.
- At minimum, cover budget exhaustion and model retry exhaustion.
- Stub tests must cover the repair loop used when generated tests fail.

## Subtasks

- Create success scenario fixture.
- Create failure scenario fixtures.
- Create budget exhaustion fixture.
- Create retry exhaustion fixture.
- Create patch-loop fixture.
- Create stub model responses.
- Add e2e test runner.
- Assert trace and report artifacts.
- Document how to run e2e tests.

## Dependencies

- Depends on task 008.
- Blocks task 010.

## Done

The project has deterministic e2e tests for both success and failure flows.

## Implementation Notes

- Stub e2e fixtures live under `tests/fixtures/scenarios/e2e_*.yaml` and `tests/fixtures/scenarios/cycles/e2e_*.yaml`.
- `tests/test_e2e_stub_scenarios.py` covers success, command failure, budget exhaustion, retry exhaustion and a bounded repair loop.
- Every stub e2e test writes a trace directory and static HTML report under pytest `tmp_path`.
- Stub e2e tests can be run with `python -m pytest tests/test_e2e_stub_scenarios.py`.
- Continue with [Task 010: Ollama E2E](010_ollama_e2e.md).

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Phase 2 Decisions, Subtasks, Dependencies, Done and Implementation Notes line is complete.
- ✅ Evidence: `tests/test_e2e_stub_scenarios.py` and `tests/fixtures/scenarios/e2e_*.yaml` cover success, expected failures, budget exhaustion, retry exhaustion and repair-loop traces/reports.
- ✅ No unchecked quest lines remain in this file.
