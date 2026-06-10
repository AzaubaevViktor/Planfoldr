# Task visibility_q19_byuser_live_model_stream_dom: Stream model output into the page without reload
File name: `visibility_q19_byuser_live_model_stream_dom.md`

## Status

Current status: active
Blocked by: visibility_q18_byuser_internal_thinking_summary
Description: The live Visibility page currently opens a WebSocket but its browser handler ignores
messages, so model generation becomes visible only after auto-refresh or final rendered output.

## Goal

Make live Visibility actually live: while a model is generating, content and thinking chunks should
append into the visible Streaming Log through WebSocket events without waiting for a page reload.
The page refresh may remain as a fallback, but it must not be the primary mechanism for seeing
generation progress.

## Necessary Conditions

- `ws.onmessage` must parse incoming Visibility events and update the current page DOM.
- `model_stream_chunk` content chunks must appear immediately in the active cycle/phase live output
  block.
- `model_stream_chunk` thinking chunks must appear immediately in a distinct thinking block once
  `visibility_q18_byuser_internal_thinking_summary` has separated thinking from action summary.
- `model_output` must replace or reconcile the live preview with the final readable model-output
  block so the page does not show duplicate or contradictory output.
- Tool results and audit events that already arrive over the same stream should update visible
  status/tool sections or trigger a targeted refresh of the affected block, not a blind whole-page
  reload for every token.
- Auto-refresh can remain for static-file and reconnect fallback, but a live WebSocket connection
  must disable or defer timer-based full-page reloads during active generation.

## TODO

### RnD

1. Inspect the current live browser path in `src/planfoldr/visibility/web.py`, especially
   `VisibilityServer.sink`, `_WS_SCRIPT`, `_render_live_status`, `render_stream_log_html`, and the
   page refresh script.

   Verify: record the exact current behavior in Implementation Notes: WebSocket broadcasts events,
   browser `ws.onmessage` is a no-op, auto-refresh is responsible for visible updates, and
   `model_stream_chunk` entries are not persisted into the static log.

2. Inspect `src/planfoldr/visibility/events.py::VisibilityState.ingest` and `_live_chunk` to map
   how `model_stream_chunk` events are stored today.

   Verify: list the fields available to the browser for a chunk: `cycle_id`, `ticket_id`, `phase`,
   `kind`, and `text`; confirm whether thinking chunks are currently ignored by `_live_chunk`.

3. Inspect `src/planfoldr/cycle.py::_one_action` and model adapters in `src/planfoldr/model.py` to
   confirm which events are emitted during streaming and which event marks final assembled output.

   Verify: write down the event order for one model call: zero or more `model_stream_chunk`
   events, then one `model_output`, then tool execution/result events when applicable.

4. Inspect `tests/test_visibility.py` and existing WebSocket tests to decide whether the live DOM
   behavior can be tested with the existing stdlib server tests or needs a small browser/JS
   harness.

   Verify: name the exact test file and test strategy before implementation, including how the
   test proves no full-page reload is required for the first visible chunk.

### Implementation

5. Add stable DOM anchors to live cycle/model-call areas in `render_stream_log_html` and
   `_model_output_html`.

   Verify: render a minimal Streaming Log snapshot and assert the HTML contains deterministic
   element ids or data attributes for cycle id, phase, live content, live thinking, and final model
   output.

6. Replace the no-op `ws.onmessage` handler in `_WS_SCRIPT` with a small event dispatcher that
   parses WebSocket messages and routes them by event type.

   Verify: a JS unit-style test or HTML fixture dispatches a `model_stream_chunk` event to the
   handler and the expected live output element receives appended text.

7. Implement live content chunk rendering for `model_stream_chunk` events with `kind=content`.

   Verify: simulate two chunks for the same cycle/phase and assert the browser-visible block shows
   the concatenated text in order, without raw event data and without replacing earlier chunks from
   the same model call.

8. Implement live thinking chunk rendering for `model_stream_chunk` events with `kind=thinking`,
   using the labels and summary/thinking separation introduced by
   `visibility_q18_byuser_internal_thinking_summary`.

   Verify: simulate thinking and content chunks for the same model call and assert thinking appears
   in the thinking area while content appears in the output area; neither area is mislabeled as the
   final action summary.

9. Handle `model_output` events by finalizing the live preview.

   Verify: simulate chunked output followed by `model_output`; assert the final readable model
   block is present, the live preview is either removed or clearly marked final, and no duplicate
   content appears in the default view.

10. Handle reconnect and fallback behavior without fighting the live stream.

    Verify: with an open WebSocket, assert timer-based refresh is paused or deferred during active
    streaming; when WebSocket fails or closes, assert the existing refresh fallback still updates
    the page.

11. Keep the static report behavior unchanged.

    Verify: run a stub scenario, open the generated `visibility/index.html` as a static artifact,
    and confirm it still renders from embedded snapshot/log data without requiring a server or
    WebSocket.

### Verification

12. Add focused tests for the live WebSocket DOM behavior.

    Verify: tests prove that content appears after a streamed chunk before any final `model_output`
    event and before any full-page reload path can be involved.

13. Run visibility tests:
    `.venv/bin/python -m pytest tests/test_visibility.py -q`.

    Verify: tests pass and include live chunk DOM coverage for content, thinking, and finalization.

14. Run model/cycle focused tests if event shapes or streaming callbacks changed:
    `.venv/bin/python -m pytest tests/test_model.py tests/test_cycle_stub.py tests/test_visibility.py -q`.

    Verify: tests pass and existing `model_output`, tool-call rendering, and visibility report
    behavior are unchanged except for the new live DOM path.

15. Run the full default suite:
    `.venv/bin/python -m pytest -q`.

    Verify: full suite passes; record the pass/skip count in Implementation Notes.

16. Perform a live manual or automated smoke run with web visibility enabled.

    Verify: start a stub or Ollama run that emits multiple streamed chunks, open the live Streaming
    Log page, and confirm text appears incrementally without manually refreshing the page.

## Final Verification

- Confirm WebSocket is no longer decorative: `ws.onmessage` updates the page for streamed model
  chunks.
- Confirm content chunks, thinking chunks, final model output, tool results, and reconnect fallback
  each have observable behavior.
- Confirm static `visibility/index.html` still works without a server.
- Run focused visibility tests, relevant model/cycle tests, and the full suite.
- Inspect the live page and generated static report before moving this quest to `quests/done/`.

## Implementation Notes

- Created from user request after observing that live Visibility currently opens a WebSocket but
  `ws.onmessage` ignores messages while page refresh does the visible updating.
- Current code points to inspect first:
  - `src/planfoldr/visibility/web.py::_WS_SCRIPT`
  - `src/planfoldr/visibility/web.py::VisibilityServer.sink`
  - `src/planfoldr/visibility/events.py::_live_chunk`
  - `src/planfoldr/cycle.py::_one_action`
