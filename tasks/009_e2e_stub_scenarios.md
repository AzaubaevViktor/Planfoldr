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
