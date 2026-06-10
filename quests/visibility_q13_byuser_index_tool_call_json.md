# Task visibility_q13_byuser_index_tool_call_json: Render tool_call envelopes in index
File name: `visibility_q13_byuser_index_tool_call_json.md`

## Status

Current status: active
Blocked by: visibility_q12_byuser_index_model_json_fallback
Description: Model output that uses `<tool_call>{...}</tool_call>` can fall through the Streaming
Log renderer and appear as raw envelope text or JSON.

## Goal

Teach `index.html` rendering to parse and display `<tool_call>` model responses as first-class
tool/action blocks, not as raw JSON-like text.

## Necessary Conditions

- `<tool_call>` envelopes must render as the same readable action/tool blocks as JSON action
  envelopes.
- Tool name, arguments, summary, and malformed-argument notes must be visible without raw JSON.
- Parser behavior must stay aligned with `planfoldr.model.parse_action`, which already has a
  `<tool_call>` fallback.

## TODO

### RnD

1. Inspect `src/planfoldr/model.py::parse_action` and `_parse_tool_call` to understand accepted
   `<tool_call>` formats.

   Verify: record the accepted envelope shapes and argument field names.

2. Inspect `src/planfoldr/visibility/web.py::_render_action_content` and
   `_model_output_html` to find why `<tool_call>` content is not rendered like an action.

   Verify: create a minimal `<tool_call>` sample that currently reaches the raw model fallback.

### Implementation

3. Add a Streaming Log renderer path for `<tool_call>` envelopes that reuses the readable action
   table rendering.

   Verify: add a visibility test where model content is a `<tool_call>` envelope; assert
   `index.html` shows the action/tool name and arguments but not the raw `<tool_call>` JSON.

4. Handle malformed `<tool_call>` arguments with a readable diagnostic block.

   Verify: add a malformed-envelope test and assert the output labels the issue without dumping
   raw JSON in the default view.

### Verification

5. Run visibility and model parsing tests:
   `.venv/bin/python -m pytest tests/test_visibility.py tests/test_model.py -q`.

   Verify: tests pass and the parser/rendering expectations match.

6. Run a stub scenario that emits a `<tool_call>` response and inspect `visibility/index.html`.

   Verify: the action appears as a readable block, not raw envelope text.

## Final Verification

- Confirm `<tool_call>` rendering matches model parser behavior.
- Run focused tests and full suite.
- Inspect generated `visibility/index.html` directly before moving this quest to `quests/done/`.

## Implementation Notes

- Found while searching `index.html` JSON leaks: `_model_output_html` renders JSON actions, but not
  `<tool_call>` envelopes even though `model.parse_action` accepts them.
