# Task execution_001: Explain Previous Failure On Retry

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

## Done

When a retry happens, the model receives a concise explanation of what was wrong previously, and the same retry feedback is visible in the run trace.
