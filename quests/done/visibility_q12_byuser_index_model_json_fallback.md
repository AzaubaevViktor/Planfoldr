# Task visibility_q12_byuser_index_model_json_fallback: Remove raw model JSON fallback from index
File name: `visibility_q12_byuser_index_model_json_fallback.md`

## Status

Current status: completed
Blocked by: visibility_q10b_byuser_report_hardening
Description: `index.html` can still show raw model output when `_model_output_html` cannot parse
the content into an action block.

## Goal

Replace the raw `<pre class="model-content">...</pre>` fallback for model output with a readable
diagnostic block that names what could not be parsed and extracts any available action, summary,
tool name, or text without dumping raw JSON at the user.

## Necessary Conditions

- The Streaming Log default view must never display a raw JSON action object as the model response.
- Malformed or partial JSON must render as a readable "unparsed model action" block with extracted
  fields when possible.
- The full raw content may remain available only in an explicitly labelled diagnostic/details area
  if the interface rules allow it, and it must not be the primary visible output.

## TODO

### RnD

1. Inspect `src/planfoldr/visibility/web.py::_model_output_html`,
   `_render_action_content`, `_action_from_broken_json`, and tests that render Streaming Log
   entries.

   Verify: identify every branch that can currently reach
   `<pre class="model-content">{esc(content)}</pre>` in `index.html`.

2. Create or capture representative model outputs for malformed JSON, unknown action envelopes,
   plain text, and multiple action lines.

   Verify: list which examples should render as action blocks, diagnostic blocks, or plain prose.

### Implementation

3. Replace the raw model-content fallback with a human-readable diagnostic renderer that extracts
   action-like fields and labels malformed content without dumping the whole JSON object.

   Verify: add tests where malformed JSON and unknown action content render without `{`/`"action"`
   raw dumps in the default Streaming Log HTML.

4. Preserve useful debugging access without violating the no-raw-JSON default. If raw content is
   retained, put it behind an explicit diagnostic label and keep the main view readable.

   Verify: inspect rendered `index.html` and confirm the default visible path contains readable
   labels rather than raw JSON.

### Verification

5. Run visibility tests:
   `.venv/bin/python -m pytest tests/test_visibility.py -q`.

   Verify: tests pass and include a malformed model-output case.

6. Run a stub scenario and inspect `visibility/index.html`.

   Verify: no raw action JSON is visible in the default model-output blocks.

## Final Verification

- Re-read this quest and confirm each TODO has evidence.
- Run focused visibility tests and full suite.
- Inspect generated `visibility/index.html` directly before moving this quest to `quests/done/`.

## Implementation Notes

- Found in `src/planfoldr/visibility/web.py::_model_output_html`, fallback branch that currently
  appends `<pre class="model-content">{esc(content)}</pre>`.
- Implemented `_model_content_fallback_html` in `src/planfoldr/visibility/web.py` so the final
  model-output fallback now renders action-like JSON as a labelled `unparsed model action`
  diagnostic block and plain non-action model text as prose.
- Diagnostic extraction now handles parsed unknown envelopes and malformed/partial JSON by pulling
  visible fields such as `action`, `tool_name`, `summary`, `text`, and `arguments` without dumping
  the raw JSON object in the default Streaming Log view.
- Added focused coverage in `tests/test_visibility.py`:
  `test_stream_log_renders_malformed_model_json_as_diagnostic_not_raw_dump`,
  `test_stream_log_renders_unknown_model_json_envelope_as_diagnostic`, and
  `test_stream_log_renders_plain_model_text_as_prose`.
- Verification evidence:
  `.venv/bin/python -m pytest tests/test_visibility.py -q` -> 17 passed.
- Generated and inspected
  `runs/2026-06-10_test_run_visibility_q12/visibility/index.html`; the visible page contains
  `unparsed model action`, extracted `action/summary/text` and `tool_name/arguments` rows, and a
  `model-prose` block for plain text. The raw source content remains only in the embedded
  `__SNAPSHOT__` script data, not in the default visible log.
- Full suite verification:
  `.venv/bin/python -m pytest -q` -> 117 passed, 1 skipped.
