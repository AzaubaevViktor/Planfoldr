# Task execution_001: Explain Previous Failure On Retry
File name: `execution_001_additional_retry.md`

## Status

Current status: done
Blocked by: none
Description: Completed retry feedback for invalid model output retries.

## Goal

When retrying a failed model execution, include a clear explanation of what was wrong with the previous attempt.

## Concept

Retries are more useful when the model receives actionable feedback. If a previous attempt failed because of invalid format, missing files, failed validation or another deterministic check, the next attempt should include that failure reason and enough context for the model to correct course.

## Necessary Conditions

- Retry prompts include the previous failure category.
- Retry prompts include the human-readable validation or execution error.
- Retry prompts include the previous attempt number and retry budget when relevant.
- The retry message is persisted in trace artifacts.
- Existing retry limits and budget accounting remain deterministic.

## Constraints

- Do not include unrelated trace noise in retry prompts.
- Do not leak secrets or redacted values back into model prompts.
- Do not retry work that is not configured as retryable.
- Keep retry feedback concise enough to fit existing budget controls.

## Subtasks

- Audit current retry prompt construction.
- Define a compact retry feedback payload.
- Add previous failure details to retry prompts.
- Persist retry feedback in trace artifacts.
- Add tests for validation failure, execution failure and malformed model output retries.

## Outcome

When a retry happens, the model receives a concise explanation of what was wrong previously, and the same retry feedback is visible in the run trace.

## Verification

- Does a retry prompt include the previous failure category and readable error?
- Is the retry feedback persisted in trace artifacts?
- Do retry limits, budget accounting and redaction behavior remain unchanged?
- Do tests cover validation failure, execution failure and malformed model output retries?

## Implementation Notes

- Queue after `report_001`; retry messages should be written as readable trace artifacts.
- Added validation retry feedback to subsequent model prompts and persisted it through prompt metadata and trace input artifacts.
- Completed and moved to `quests/done/`.
- Verified with `.venv/bin/python -m pytest -q`.

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/execution_001_additional_retry.md` before this section was appended; prior `Completion Audit` is summarized separately below.

- [x] Line 1: `# Task execution_001: Explain Previous Failure On Retry` checked and complete.
- [x] Line 2: `File name: \`execution_001_additional_retry.md\`` checked and complete.
- [x] Line 3: blank separator preserved.
- [x] Line 4: `## Status` checked and complete.
- [x] Line 5: blank separator preserved.
- [x] Line 6: `Current status: done` checked and complete.
- [x] Line 7: `Blocked by: none` checked and complete.
- [x] Line 8: `Description: Completed retry feedback for invalid model output retries.` checked and complete.
- [x] Line 9: blank separator preserved.
- [x] Line 10: `## Goal` checked and complete.
- [x] Line 11: blank separator preserved.
- [x] Line 12: `When retrying a failed model execution, include a clear explanation of what was wrong with the previous attempt.` checked and complete.
- [x] Line 13: blank separator preserved.
- [x] Line 14: `## Concept` checked and complete.
- [x] Line 15: blank separator preserved.
- [x] Line 16: `Retries are more useful when the model receives actionable feedback. If a previous attempt failed because of invalid format, missing file...` checked and complete.
- [x] Line 17: blank separator preserved.
- [x] Line 18: `## Necessary Conditions` checked and complete.
- [x] Line 19: blank separator preserved.
- [x] Line 20: `- Retry prompts include the previous failure category.` checked and complete.
- [x] Line 21: `- Retry prompts include the human-readable validation or execution error.` checked and complete.
- [x] Line 22: `- Retry prompts include the previous attempt number and retry budget when relevant.` checked and complete.
- [x] Line 23: `- The retry message is persisted in trace artifacts.` checked and complete.
- [x] Line 24: `- Existing retry limits and budget accounting remain deterministic.` checked and complete.
- [x] Line 25: blank separator preserved.
- [x] Line 26: `## Constraints` checked and complete.
- [x] Line 27: blank separator preserved.
- [x] Line 28: `- Do not include unrelated trace noise in retry prompts.` checked and complete.
- [x] Line 29: `- Do not leak secrets or redacted values back into model prompts.` checked and complete.
- [x] Line 30: `- Do not retry work that is not configured as retryable.` checked and complete.
- [x] Line 31: `- Keep retry feedback concise enough to fit existing budget controls.` checked and complete.
- [x] Line 32: blank separator preserved.
- [x] Line 33: `## Subtasks` checked and complete.
- [x] Line 34: blank separator preserved.
- [x] Line 35: `- Audit current retry prompt construction.` checked and complete.
- [x] Line 36: `- Define a compact retry feedback payload.` checked and complete.
- [x] Line 37: `- Add previous failure details to retry prompts.` checked and complete.
- [x] Line 38: `- Persist retry feedback in trace artifacts.` checked and complete.
- [x] Line 39: `- Add tests for validation failure, execution failure and malformed model output retries.` checked and complete.
- [x] Line 40: blank separator preserved.
- [x] Line 41: `## Outcome` checked and complete.
- [x] Line 42: blank separator preserved.
- [x] Line 43: `When a retry happens, the model receives a concise explanation of what was wrong previously, and the same retry feedback is visible in th...` checked and complete.
- [x] Line 44: blank separator preserved.
- [x] Line 45: `## Verification` checked and complete.
- [x] Line 46: blank separator preserved.
- [x] Line 47: `- Does a retry prompt include the previous failure category and readable error?` checked and complete.
- [x] Line 48: `- Is the retry feedback persisted in trace artifacts?` checked and complete.
- [x] Line 49: `- Do retry limits, budget accounting and redaction behavior remain unchanged?` checked and complete.
- [x] Line 50: `- Do tests cover validation failure, execution failure and malformed model output retries?` checked and complete.
- [x] Line 51: blank separator preserved.
- [x] Line 52: `## Implementation Notes` checked and complete.
- [x] Line 53: blank separator preserved.
- [x] Line 54: `- Queue after \`report_001\`; retry messages should be written as readable trace artifacts.` checked and complete.
- [x] Line 55: `- Added validation retry feedback to subsequent model prompts and persisted it through prompt metadata and trace input artifacts.` checked and complete.
- [x] Line 56: `- Completed and moved to \`quests/done/\`.` checked and complete.
- [x] Line 57: `- Verified with \`.venv/bin/python -m pytest -q\`.` checked and complete.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Status, Goal, Concept, Necessary Conditions, Constraints, Subtasks, Outcome, Verification and Implementation Notes line is complete.
- ✅ Evidence: retry-feedback behavior in `src/planfoldr/executors.py`, persisted prompt/input artifacts in `src/planfoldr/trace.py` and retry coverage in tests.
- ✅ No unchecked quest lines remain in this file.
