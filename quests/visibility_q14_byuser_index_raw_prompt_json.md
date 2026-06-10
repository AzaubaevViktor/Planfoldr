# Task visibility_q14_byuser_index_raw_prompt_json: Remove raw JSON prompt blocks from index
File name: `visibility_q14_byuser_index_raw_prompt_json.md`

## Status

Current status: active
Blocked by: visibility_q10b_byuser_report_hardening
Description: `index.html` includes a collapsed raw prompt block whose system/user text contains
JSON protocol examples, action envelopes, and sometimes JSON-like last-result data.

## Goal

Keep prompt inspection useful without showing raw JSON protocol dumps as the human-facing shape in
the Streaming Log.

## Necessary Conditions

- The default model-call view should show `source`, `context`, and `input` as structured,
  human-readable sections.
- Raw system/user prompt text must not be the primary way to understand a model call.
- JSON action examples inside prompts must be rendered as command/action reference rows or hidden
  behind a clearly labelled diagnostic/debug details block.

## TODO

### RnD

1. Inspect `src/planfoldr/visibility/web.py::_model_output_html` raw prompt rendering and
   `src/planfoldr/cycle.py::_changes_user` prompt construction.

   Verify: list the prompt sections that currently put JSON examples into `index.html`: protocol,
   action reference, acceptance checks, context, and last tool result.

2. Inspect `interface.md` for user-facing output requirements around `source`, `context`, `input`,
   thinking, output, and tool calls.

   Verify: record the expected visible structure in Implementation Notes.

### Implementation

3. Replace the raw prompt default view with structured prompt metadata: source/model/phase,
   context table, acceptance checks, available actions, and last tool result summary.

   Verify: add a visibility test that renders a model call and asserts these sections appear
   without raw JSON action examples in the default visible body.

4. Keep a diagnostic raw prompt details block only if needed for replay, clearly labelled as debug,
   collapsed by default, and not used as the primary user-facing view.

   Verify: inspect `index.html` and confirm a normal reader can understand the model call without
   expanding raw prompt details.

### Verification

5. Run visibility tests:
   `.venv/bin/python -m pytest tests/test_visibility.py -q`.

   Verify: tests pass and include an assertion against raw prompt JSON in the default view.

6. Run a stub scenario and inspect `visibility/index.html`.

   Verify: prompt information is readable as sections, not as raw JSON examples.

## Final Verification

- Re-read `interface.md` and confirm the Streaming Log shape matches the examples.
- Run focused tests and full suite.
- Inspect generated `visibility/index.html` directly before moving this quest to `quests/done/`.

## Implementation Notes

- Found in `src/planfoldr/visibility/web.py::_model_output_html`: the raw prompt block writes full
  system/user prompts into `<pre class="pre-input">`, including JSON action references from
  `src/planfoldr/cycle.py::_ACTION_REFERENCE`.
