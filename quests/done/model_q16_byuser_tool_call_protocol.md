# Task model_q16_byuser_tool_call_protocol: Teach models to use tool_call envelopes
File name: `model_q16_byuser_tool_call_protocol.md`

## Status

Current status: done
Blocked by: none
Description: Change the model-facing protocol so models are taught to invoke tools with
`<tool_call>` envelopes instead of only being told to emit bare JSON objects.

## Goal

Make tool use explicit and robust for local models: prompts should demonstrate `<tool_call>` calls,
the parser should accept them consistently, streaming/reporting should display them, and tests
should prove real tool calls execute through that envelope.

## Necessary Conditions

- The primary model-facing tool protocol should show `<tool_call>...</tool_call>` examples.
- `parse_action` must continue accepting legacy JSON during migration, but tests should cover
  `<tool_call>` as the preferred path.
- Tool-call rendering in `index.html` should be human-readable and covered by
  `visibility_q13_byuser_index_tool_call_json`.
- Protocol errors should tell the model to reformat as `<tool_call>`, not only as a bare JSON
  object.

## TODO

### RnD

1. Inspect `src/planfoldr/cycle.py::_PROTOCOL`, `_ACTION_REFERENCE`, `_changes_user`, and
   `_phase_model_verification` to find every prompt that instructs bare JSON action output.

   Verify: list each prompt string and the exact replacement behavior needed.

2. Inspect `src/planfoldr/model.py::parse_action` and tests in `tests/test_model.py`.

   Verify: confirm current `<tool_call>` support and identify missing tests for arguments,
   malformed envelopes, and legacy JSON compatibility.

### Implementation

3. Update model-facing prompts and action references so the preferred tool invocation format is
   `<tool_call>` with one action per response.

   Verify: focused prompt tests or captured stub calls assert the system/user prompt contains
   `<tool_call>` examples and does not describe bare JSON as the preferred tool mechanism.

4. Keep legacy JSON parsing as compatibility, but make reformat hints and protocol errors ask for
   `<tool_call>`.

   Verify: tests cover both a valid `<tool_call>` response and a legacy JSON response.

5. Add an end-to-end stub test where the stub model responds with `<tool_call>` for `file_edit`,
   `bash`, and `finish`, and the cycle executes the tools correctly.

   Verify: the generated file exists, command verification passes, and audit events show the tool
   invocations.

### Verification

6. Run model and cycle tests:
   `.venv/bin/python -m pytest tests/test_model.py tests/test_cycle_stub.py -q`.

   Verify: tests pass and include `<tool_call>` execution coverage.

7. Run the full default suite:
   `.venv/bin/python -m pytest -q`.

   Verify: the full suite passes; record optional skip count.

8. Inspect a generated `model_io.jsonl` or Streaming Log from a stub `<tool_call>` run.

   Verify: tool calls are represented as `<tool_call>` in model output and rendered readably.

## Final Verification

- Confirm models are taught to use `<tool_call>` as the primary protocol.
- Confirm legacy JSON still works during migration.
- Run focused tests and full suite.
- Move this quest to `quests/done/` only after implementation and verification.

## Implementation Notes

- Created from user request: "научить модель в процессе работы ИСПОЛЬЗОВАТЬ ТУЛЫ ЧЕРЕЗ
  `<tool_call>`".
- Parser support exists in `src/planfoldr/model.py`, but prompts still primarily teach bare JSON.
- Implemented on 2026-06-10:
  - `src/planfoldr/cycle.py` now presents `<tool_call>{"name":"...","arguments":...}</tool_call>`
    as the primary model-facing action protocol in `_PROTOCOL`, action references, reformat hints,
    and model-verification instructions. The cycle no longer forces provider `fmt="json"` for
    action calls, so local models can emit the envelope they are taught to use.
  - `src/planfoldr/model.py::parse_action` now prefers `<tool_call>` envelopes when present,
    preserves legacy bare JSON compatibility for migration, parses stringified `arguments`, and
    returns reformat errors that explicitly ask for `<tool_call>`.
  - `src/planfoldr/visibility/web.py` renders `<tool_call>` model outputs as readable action
    blocks in Streaming Log / Models views, including malformed-envelope diagnostics without raw
    fallback dumps.
  - Focused tests added for parser compatibility and malformed envelopes, prompt contents, a
    `file_edit` → `bash` → `finish` cycle driven by `<tool_call>`, static Streaming Log rendering,
    and generated `model_io.jsonl` / `visibility/index.html` from a real stub run.

Verification evidence:
- `.venv/bin/python -m pytest tests/test_model.py tests/test_cycle_stub.py tests/test_visibility.py -q`
  passed with `39 passed, 1 skipped`.
- `.venv/bin/python -m pytest -q` passed with `114 passed, 1 skipped`.
