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

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/009_e2e_stub_scenarios.md` before this section was appended; prior `Completion Audit` is summarized separately below.

- [x] Line 1: `# Task 009: E2E Stub Scenarios` checked and complete.
- [x] Line 2: blank separator preserved.
- [x] Line 3: `## Goal` checked and complete.
- [x] Line 4: blank separator preserved.
- [x] Line 5: `Create e2e tests that run complete scenarios with stubbed model responses.` checked and complete.
- [x] Line 6: blank separator preserved.
- [x] Line 7: `## Concept` checked and complete.
- [x] Line 8: blank separator preserved.
- [x] Line 9: `Stubbed e2e scenarios are the main safety net. They prove flow correctness without depending on model quality or local Ollama availability.` checked and complete.
- [x] Line 10: blank separator preserved.
- [x] Line 11: `## Necessary Conditions` checked and complete.
- [x] Line 12: blank separator preserved.
- [x] Line 13: `- Successful e2e scenario passes.` checked and complete.
- [x] Line 14: `- Multiple unsuccessful e2e scenarios pass by failing in expected ways.` checked and complete.
- [x] Line 15: `- Budget exhaustion scenario is covered.` checked and complete.
- [x] Line 16: `- Retry exhaustion scenario is covered.` checked and complete.
- [x] Line 17: `- Patch-loop scenario is covered.` checked and complete.
- [x] Line 18: `- All scenarios produce trace directories.` checked and complete.
- [x] Line 19: `- Both scenarios produce HTML reports.` checked and complete.
- [x] Line 20: `- Tests assert final status.` checked and complete.
- [x] Line 21: `- Tests assert key task outcomes.` checked and complete.
- [x] Line 22: blank separator preserved.
- [x] Line 23: `## Constraints` checked and complete.
- [x] Line 24: blank separator preserved.
- [x] Line 25: `- Do not call real models in these tests.` checked and complete.
- [x] Line 26: `- Do not depend on network.` checked and complete.
- [x] Line 27: `- Keep fixtures small.` checked and complete.
- [x] Line 28: blank separator preserved.
- [x] Line 29: `## Phase 2 Decisions` checked and complete.
- [x] Line 30: blank separator preserved.
- [x] Line 31: `- Stub e2e coverage should include success plus bad scenarios for each important runtime element.` checked and complete.
- [x] Line 32: `- At minimum, cover budget exhaustion and model retry exhaustion.` checked and complete.
- [x] Line 33: `- Stub tests must cover the repair loop used when generated tests fail.` checked and complete.
- [x] Line 34: blank separator preserved.
- [x] Line 35: `## Subtasks` checked and complete.
- [x] Line 36: blank separator preserved.
- [x] Line 37: `- Create success scenario fixture.` checked and complete.
- [x] Line 38: `- Create failure scenario fixtures.` checked and complete.
- [x] Line 39: `- Create budget exhaustion fixture.` checked and complete.
- [x] Line 40: `- Create retry exhaustion fixture.` checked and complete.
- [x] Line 41: `- Create patch-loop fixture.` checked and complete.
- [x] Line 42: `- Create stub model responses.` checked and complete.
- [x] Line 43: `- Add e2e test runner.` checked and complete.
- [x] Line 44: `- Assert trace and report artifacts.` checked and complete.
- [x] Line 45: `- Document how to run e2e tests.` checked and complete.
- [x] Line 46: blank separator preserved.
- [x] Line 47: `## Dependencies` checked and complete.
- [x] Line 48: blank separator preserved.
- [x] Line 49: `- Depends on task 008.` checked and complete.
- [x] Line 50: `- Blocks task 010.` checked and complete.
- [x] Line 51: blank separator preserved.
- [x] Line 52: `## Done` checked and complete.
- [x] Line 53: blank separator preserved.
- [x] Line 54: `The project has deterministic e2e tests for both success and failure flows.` checked and complete.
- [x] Line 55: blank separator preserved.
- [x] Line 56: `## Implementation Notes` checked and complete.
- [x] Line 57: blank separator preserved.
- [x] Line 58: `- Stub e2e fixtures live under \`tests/fixtures/scenarios/e2e_*.yaml\` and \`tests/fixtures/scenarios/cycles/e2e_*.yaml\`.` checked and complete.
- [x] Line 59: `- \`tests/test_e2e_stub_scenarios.py\` covers success, command failure, budget exhaustion, retry exhaustion and a bounded repair loop.` checked and complete.
- [x] Line 60: `- Every stub e2e test writes a trace directory and static HTML report under pytest \`tmp_path\`.` checked and complete.
- [x] Line 61: `- Stub e2e tests can be run with \`python -m pytest tests/test_e2e_stub_scenarios.py\`.` checked and complete.
- [x] Line 62: `- Continue with [Task 010: Ollama E2E](010_ollama_e2e.md).` checked and complete.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Phase 2 Decisions, Subtasks, Dependencies, Done and Implementation Notes line is complete.
- ✅ Evidence: `tests/test_e2e_stub_scenarios.py` and `tests/fixtures/scenarios/e2e_*.yaml` cover success, expected failures, budget exhaustion, retry exhaustion and repair-loop traces/reports.
- ✅ No unchecked quest lines remain in this file.
