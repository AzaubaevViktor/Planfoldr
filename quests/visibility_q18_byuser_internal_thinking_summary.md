# Task visibility_q18_byuser_internal_thinking_summary: Show internal thinking and rename JSON thinking
File name: `visibility_q18_byuser_internal_thinking_summary.md`

## Status

Current status: active
Blocked by: model_q16_byuser_tool_call_protocol
Description: The UI should show the model's real streaming/internal thinking during work, while
the short `thinking` field inside final action JSON should become a summary field.

## Goal

Separate two concepts that are currently blurred: provider/internal thinking from the model stream
and the short action-envelope explanation. Display internal thinking live when available, and
rename the final action JSON field from `thinking` to `summary`.

## Necessary Conditions

- Streaming provider thinking must be shown during generation in the Streaming Log or terminal
  visibility path.
- The final action envelope should use `summary` for the short visible explanation instead of
  pretending that field is internal reasoning.
- Backward compatibility may accept legacy `thinking` in parsed actions during migration, but the
  prompt should teach `summary`.
- Reports must label internal thinking and summary distinctly.

## TODO

### RnD

1. Inspect `src/planfoldr/model.py::OllamaModel.generate`, `ModelResponse.thinking`,
   `src/planfoldr/cycle.py::_one_action`, and `src/planfoldr/visibility/web.py::_model_output_html`
   to map how provider thinking and final JSON thinking currently flow.

   Verify: write a data-flow note: provider chunk thinking, assembled `response.thinking`,
   final action `thinking`, model_output event fields, and report rendering.

2. Inspect terminal/live visibility code in `src/planfoldr/visibility/terminal.py` and
   `src/planfoldr/visibility/ws.py` to confirm whether thinking chunks are visible during
   generation.

   Verify: record where live thinking appears today and what observable text should change.

### Implementation

3. Update the model action protocol to prefer `summary` instead of final JSON `thinking`.

   Verify: captured prompts show `summary` in action examples and do not ask for final JSON
   `thinking` as the preferred field.

4. Update `parse_action` to read `summary` as the action summary while accepting legacy `thinking`
   for compatibility.

   Verify: tests cover actions with `summary`, legacy `thinking`, and both fields.

5. Update Streaming Log rendering to show provider/internal thinking separately from action
   summary.

   Verify: render a model_output event with both provider thinking and action summary; assert the
   HTML contains distinct labels and no duplicate/confusing "thinking" label for summary.

6. Ensure live streaming shows thinking chunks during generation, not only after final output.

   Verify: add or update terminal/visibility tests, or a stub progress test, that checks a
   `model_stream_chunk` with kind `thinking` is rendered live.

### Verification

7. Run model, cycle, and visibility tests:
   `.venv/bin/python -m pytest tests/test_model.py tests/test_cycle_stub.py tests/test_visibility.py -q`.

   Verify: tests pass and include summary/thinking separation coverage.

8. Run the full default suite:
   `.venv/bin/python -m pytest -q`.

   Verify: the full suite passes; record optional skip count.

9. Inspect generated `visibility/index.html` and live/terminal output from a stub or Ollama run
   where thinking is present.

   Verify: internal thinking is labelled as thinking; final action explanation is labelled as
   summary.

## Final Verification

- Confirm provider/internal thinking and action summary are separate in prompts, parser, events,
  terminal output, and HTML.
- Run focused tests and full suite.
- Inspect generated visibility artifacts directly before moving this quest to `quests/done/`.

## Implementation Notes

- Created from user request: "при работе модели мне нужно чтобы показывалось её внутреннее
  размышление, thinking из финального json-а можно заменить на summary".
