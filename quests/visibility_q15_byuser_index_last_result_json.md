# Task visibility_q15_byuser_index_last_result_json: Render last tool result without JSON
File name: `visibility_q15_byuser_index_last_result_json.md`

## Status

Current status: active
Blocked by: visibility_q14_byuser_index_raw_prompt_json
Description: The model prompt includes `Last tool result: { ... }`, which can surface in
`index.html` as Python/JSON-like raw data through the raw prompt block.

## Goal

Expose last tool result as a structured, readable model input section instead of embedding a raw
dictionary string inside the prompt text shown in the Streaming Log.

## Necessary Conditions

- Last tool result should be available to the model and visible to the user.
- The visible form must be labelled rows: tool/action, status, path/command, stdout/stderr/error,
  and any short hint.
- The raw dict/string form must not appear in default `index.html` output.

## TODO

### RnD

1. Inspect `src/planfoldr/cycle.py::_changes_user` and `_action_loop` to see how `last_result` is
   constructed and embedded into the prompt.

   Verify: list the possible last-result shapes for `file_edit`, `bash`, `create_ticket`,
   rejected bash writes, protocol errors, and tool exceptions.

2. Inspect `src/planfoldr/visibility/web.py::_model_output_html` to decide where structured
   `last_result` should be rendered.

   Verify: identify whether `model_output` events need a new structured field instead of only the
   prompt text.

### Implementation

3. Add structured last-result data to model-output events or parse it safely before rendering.

   Verify: add a focused test where `Last tool result` contains a dict-like result; assert the
   Streaming Log renders labelled fields and does not show the raw dict text.

4. Keep the model prompt semantically equivalent while improving human display.

   Verify: compare the model input before/after at a high level and confirm the model still sees
   the last tool result needed to choose the next action.

### Verification

5. Run cycle and visibility tests:
   `.venv/bin/python -m pytest tests/test_cycle_stub.py tests/test_visibility.py -q`.

   Verify: tests pass and include a last-result rendering check.

6. Run a stub scenario with at least one tool call and inspect `visibility/index.html`.

   Verify: last tool result is readable and no raw `Last tool result: {` text appears by default.

## Final Verification

- Confirm last tool result remains available to model execution.
- Run focused tests and full suite.
- Inspect generated `visibility/index.html` directly before moving this quest to `quests/done/`.

## Implementation Notes

- Found in `src/planfoldr/cycle.py::_changes_user`: `Last tool result: {last_result}` is inserted
  into the prompt as a raw Python/JSON-like string and can appear in `index.html` through raw prompt
  rendering.
