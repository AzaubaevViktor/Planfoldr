# Task 009: E2E Stub Scenarios

## Goal

Create e2e tests that run complete scenarios with stubbed model responses.

## Concept

Stubbed e2e scenarios are the main safety net. They prove flow correctness without depending on model quality or local Ollama availability.

## Necessary Conditions

- Successful e2e scenario passes.
- Unsuccessful e2e scenario passes by failing in the expected way.
- Both scenarios produce trace files.
- Both scenarios produce HTML reports.
- Tests assert final status.
- Tests assert key task outcomes.

## Constraints

- Do not call real models in these tests.
- Do not depend on network.
- Keep fixtures small.

## Subtasks

- Create success scenario fixture.
- Create failure scenario fixture.
- Create stub model responses.
- Add e2e test runner.
- Assert trace and report artifacts.
- Document how to run e2e tests.

## Dependencies

- Depends on task 008.
- Blocks task 010.

## Done

The project has deterministic e2e tests for both success and failure flows.
