# Task 007: Verifiers And Output Validation

## Goal

Implement verifier tasks and structured output validation.

## Concept

Required conditions are verifier task chains. Model outputs must match declared schemas before the runtime uses their status for transitions.

## Necessary Conditions

- Validate task output against output schema.
- Retry invalid model output a configured number of times.
- Return `retry_exceeded` when retries are exhausted.
- Implement command verifier.
- Implement schema validation verifier.
- Implement custom script verifier.
- Implement model-based verifier.

## Constraints

- Verifiers are tasks, not hidden hooks.
- Verifier evidence must be captured.
- Custom scripts must go through permission checks.

## Phase 2 Decisions

- `input_schema` and `output_schema` use JSON Schema.
- Every task output must include `status`.
- Verifiers are separate tasks; model verifier tasks are allowed.
- Verifier templates may be added to avoid repeated YAML.
- Verifier evidence contains status, proof and audit log reference.
- Every retry consumes model/tool call budgets.

## Subtasks

- Select or implement schema validation.
- Add validation to model task execution.
- Add retry loop for invalid model output.
- Implement verifier task helpers.
- Add verifier evidence to result envelope.
- Add unit tests for valid, invalid and retry-exceeded outputs.

## Dependencies

- Depends on quests 006 and 005.
- Supports task 009.

## Done

A cycle can prove success through verifier tasks, and invalid model output cannot drive transitions unchecked.

## Implementation Notes

- MVP output validation lives in `src/planfoldr/validation.py`.
- `validate_task_output` checks required `status`, JSON Schema `type`, `required`, `properties`, `items` and `enum`.
- `ExecutorRegistry` validates task outputs before links consume them.
- Model tasks retry invalid output up to `invalid_output_retries`; exhausted retries return `retry_exceeded`.
- Verifier tasks attach `VerifierEvidence` to task results.
- Command, custom script and model verifiers are represented as normal `verify` tasks using command/model executors.
- Tests live in `tests/test_validation.py`.
- Continue with [Task 008: Trace, Task Replay And HTML Report](008_trace_replay_report.md).

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/007_verifiers_and_output_validation.md` before this section was appended; prior `Completion Audit` is summarized separately below.

- [x] Line 1: `# Task 007: Verifiers And Output Validation` checked and complete.
- [x] Line 2: blank separator preserved.
- [x] Line 3: `## Goal` checked and complete.
- [x] Line 4: blank separator preserved.
- [x] Line 5: `Implement verifier tasks and structured output validation.` checked and complete.
- [x] Line 6: blank separator preserved.
- [x] Line 7: `## Concept` checked and complete.
- [x] Line 8: blank separator preserved.
- [x] Line 9: `Required conditions are verifier task chains. Model outputs must match declared schemas before the runtime uses their status for transiti...` checked and complete.
- [x] Line 10: blank separator preserved.
- [x] Line 11: `## Necessary Conditions` checked and complete.
- [x] Line 12: blank separator preserved.
- [x] Line 13: `- Validate task output against output schema.` checked and complete.
- [x] Line 14: `- Retry invalid model output a configured number of times.` checked and complete.
- [x] Line 15: `- Return \`retry_exceeded\` when retries are exhausted.` checked and complete.
- [x] Line 16: `- Implement command verifier.` checked and complete.
- [x] Line 17: `- Implement schema validation verifier.` checked and complete.
- [x] Line 18: `- Implement custom script verifier.` checked and complete.
- [x] Line 19: `- Implement model-based verifier.` checked and complete.
- [x] Line 20: blank separator preserved.
- [x] Line 21: `## Constraints` checked and complete.
- [x] Line 22: blank separator preserved.
- [x] Line 23: `- Verifiers are tasks, not hidden hooks.` checked and complete.
- [x] Line 24: `- Verifier evidence must be captured.` checked and complete.
- [x] Line 25: `- Custom scripts must go through permission checks.` checked and complete.
- [x] Line 26: blank separator preserved.
- [x] Line 27: `## Phase 2 Decisions` checked and complete.
- [x] Line 28: blank separator preserved.
- [x] Line 29: `- \`input_schema\` and \`output_schema\` use JSON Schema.` checked and complete.
- [x] Line 30: `- Every task output must include \`status\`.` checked and complete.
- [x] Line 31: `- Verifiers are separate tasks; model verifier tasks are allowed.` checked and complete.
- [x] Line 32: `- Verifier templates may be added to avoid repeated YAML.` checked and complete.
- [x] Line 33: `- Verifier evidence contains status, proof and audit log reference.` checked and complete.
- [x] Line 34: `- Every retry consumes model/tool call budgets.` checked and complete.
- [x] Line 35: blank separator preserved.
- [x] Line 36: `## Subtasks` checked and complete.
- [x] Line 37: blank separator preserved.
- [x] Line 38: `- Select or implement schema validation.` checked and complete.
- [x] Line 39: `- Add validation to model task execution.` checked and complete.
- [x] Line 40: `- Add retry loop for invalid model output.` checked and complete.
- [x] Line 41: `- Implement verifier task helpers.` checked and complete.
- [x] Line 42: `- Add verifier evidence to result envelope.` checked and complete.
- [x] Line 43: `- Add unit tests for valid, invalid and retry-exceeded outputs.` checked and complete.
- [x] Line 44: blank separator preserved.
- [x] Line 45: `## Dependencies` checked and complete.
- [x] Line 46: blank separator preserved.
- [x] Line 47: `- Depends on quests 006 and 005.` checked and complete.
- [x] Line 48: `- Supports task 009.` checked and complete.
- [x] Line 49: blank separator preserved.
- [x] Line 50: `## Done` checked and complete.
- [x] Line 51: blank separator preserved.
- [x] Line 52: `A cycle can prove success through verifier tasks, and invalid model output cannot drive transitions unchecked.` checked and complete.
- [x] Line 53: blank separator preserved.
- [x] Line 54: `## Implementation Notes` checked and complete.
- [x] Line 55: blank separator preserved.
- [x] Line 56: `- MVP output validation lives in \`src/planfoldr/validation.py\`.` checked and complete.
- [x] Line 57: `- \`validate_task_output\` checks required \`status\`, JSON Schema \`type\`, \`required\`, \`properties\`, \`items\` and \`enum\`.` checked and complete.
- [x] Line 58: `- \`ExecutorRegistry\` validates task outputs before links consume them.` checked and complete.
- [x] Line 59: `- Model tasks retry invalid output up to \`invalid_output_retries\`; exhausted retries return \`retry_exceeded\`.` checked and complete.
- [x] Line 60: `- Verifier tasks attach \`VerifierEvidence\` to task results.` checked and complete.
- [x] Line 61: `- Command, custom script and model verifiers are represented as normal \`verify\` tasks using command/model executors.` checked and complete.
- [x] Line 62: `- Tests live in \`tests/test_validation.py\`.` checked and complete.
- [x] Line 63: `- Continue with [Task 008: Trace, Task Replay And HTML Report](008_trace_replay_report.md).` checked and complete.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Phase 2 Decisions, Subtasks, Dependencies, Done and Implementation Notes line is complete.
- ✅ Evidence: `src/planfoldr/validation.py`, executor validation paths and `tests/test_validation.py` cover schema checks, retries and verifier evidence.
- ✅ No unchecked quest lines remain in this file.
