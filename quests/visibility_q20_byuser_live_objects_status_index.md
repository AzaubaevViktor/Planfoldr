# Task visibility_q20_byuser_live_objects_status_index: Live objects and action status in index.html
File name: `visibility_q20_byuser_live_objects_status_index.md`

## Status

Current status: active
Blocked by: none
Related: `visibility_q19_byuser_live_model_stream_dom.md`
Description: Make `visibility/index.html` reflect live runtime activity while work is still
running, including newly created objects, current model/tool/check action, and visible streamed
model text.

## Goal

During a run, `index.html` must show what is happening now instead of only catching up after a
cycle or scenario finishes. Newly created tickets/cycles/tools/results should appear while the run
is active, model text should be visible while the model is generating, and the status banner should
use concrete action text such as `модель генерирует`, `идёт проверка`,
`выполняется tool: <name>`, `ожидание следующей фазы`, and
`сценарий завершён: <status>`.

## Necessary Conditions

- `VisibilityState.snapshot()` exposes a structured current activity object with:
  `current_action`, `current_action_label`, `current_model`, `current_tool`, `current_phase`,
  `ticket_id`, and `cycle_id`.
- `index.html` renders current action status in the default view.
- `model_stream_chunk` content is visible in `index.html` before the final `model_output` event.
- `ticket.created`, `cycle.started`, `cycle.phase_started`, `tool.invoked`, `tool_result`, and
  `model_output` are reflected before cycle completion where applicable.
- Static `visibility/index.html` is refreshed during active execution, including throttled
  per-second refreshes while model chunks stream.
- WebSocket events update the live DOM without requiring a full-page reload.
- Static completed reports still work without a server.

## TODO

### RnD

1. Inspect the current visibility event path in `src/planfoldr/orchestrator.py`,
   `src/planfoldr/cycle.py`, `src/planfoldr/visibility/events.py`, and
   `src/planfoldr/visibility/web.py`.

   Verify: record in Implementation Notes where `ticket.created`, `cycle.started`,
   `cycle.phase_started`, `model_stream_chunk`, `model_output`, `tool.invoked`, and
   `tool_result` currently enter visibility, and whether each one reaches `index.html` before
   cycle completion.

2. Inspect the current report write cadence.

   Verify: record every place `_write_report()` is called and identify which live events currently
   do not trigger an updated `visibility/index.html`.

3. Inspect `_render_live_status()` and `_WS_SCRIPT`.

   Verify: record the current status strings and confirm whether `ws.onmessage` updates the DOM or
   is still effectively decorative.

4. Inspect active visibility quests, especially `visibility_q19_byuser_live_model_stream_dom.md`.

   Verify: add an Implementation Notes line explaining what q20 adds beyond q19: live object
   creation, action-specific status, per-second static report freshness, and medium-scenario
   verification.

### Implementation

5. Add a live activity state to `VisibilityState`.

   Verify: focused test ingests phase/model/tool events and asserts snapshot fields expose
   `current_action`, `current_action_label`, `current_model`, `current_tool`, `current_phase`,
   `ticket_id`, and `cycle_id`.

6. Update activity labels for the main runtime actions.

   Verify: tests assert exact visible labels for model generation, command verification, model
   verification, tool execution, waiting between phases, and terminal scenario status.

7. Make newly created objects visible before the creating cycle completes.

   Verify: focused test emits `ticket.created` during a running cycle and asserts
   `render_stream_log_html()` shows the new ticket link and summary in the default `index.html`
   view.

8. Refresh the static visibility report after important live events, not only after phase/cycle
   boundaries.

   Verify: integration test runs a slow stub scenario and asserts `visibility/index.html` is already
   updated when `ticket.created`, `model_stream_chunk`, `model_output`, and `tool.invoked` are
   observed by the external stream sink.

9. Implement live DOM updates for WebSocket events on `index.html`.

   Verify: focused test confirms `_WS_SCRIPT` exposes `__PLANFOLDR_HANDLE_EVENT__` and handles
   `model_stream_chunk`, `ticket.created`, `tool.invoked`, and `cycle.phase_started` through DOM
   update helpers instead of an empty `ws.onmessage`.

10. Preserve static report behavior.

    Verify: render `visibility/index.html` from a completed snapshot with no server and assert the
    page still contains scenario header, streaming log, ticket links, model output, tool calls, and
    final status.

### Verification

11. Check that no other Planfoldr run is active before manual smoke verification.

    Verify: run `pgrep -af "planfoldr run|python -m planfoldr"` and record either “no active run”
    or the exact unrelated process inspected before starting the smoke run.

12. Start a medium scenario with web visibility.

    Verify: use a level around l07-l10, preferably `examples/expr_local_l10.yaml` if an eligible
    local model is available; otherwise use `examples/csv_roundtrip_local_l07.yaml` or a
    deterministic slow-streaming stub scenario. Record the exact command, model/provider, run id,
    port, and run directory.

13. Inspect `index.html` while the scenario is still running.

    Verify: at least three observations one second apart show that `visibility/index.html` updates
    during execution and contains live text from the model currently generating.

14. Confirm action-specific status text during the run.

    Verify: inspect the live page or saved HTML and record concrete visible strings for model
    generation, verification, and tool execution.

15. Confirm new objects appear before run completion.

    Verify: while the scenario is still running, inspect `visibility/index.html` and confirm a newly
    created ticket/cycle/tool entry is visible before `scenario.completed` appears in `audit.jsonl`.

16. Run focused tests.

    Verify: `.venv/bin/python -m pytest tests/test_visibility.py tests/test_cycle_stub.py -q`
    passes.

17. Run the full default suite.

    Verify: `.venv/bin/python -m pytest -q` passes; record pass/skip counts in Implementation
    Notes.

18. Commit the quest and implementation.

    Verify: `git status --short` shows only intended files staged, ignored run artifacts are not
    staged, and the commit message starts with `[AI]`.

## Final Verification

- Re-read this quest and confirm every implementation item has concrete test or manual evidence.
- Confirm q19 remains a live DOM streaming quest and q20 adds live objects, action status, static
  report freshness, and medium-scenario smoke verification.
- Run focused visibility/cycle tests and the full default test suite.
- Inspect a live run's `visibility/index.html` during execution and confirm it contains live model
  text, action status, and a newly created object before scenario completion.
- Move this quest to `quests/done/` only in the same commit that implements and verifies it.

## Implementation Notes

- Created from the user request on 2026-06-10.
- Current event path before implementation:
  - Audit events enter `VisibilityState` through `Orchestrator._sink()` as `{"event": "audit",
    ...}` after `AuditLog.emit()`.
  - `ticket.created`, `cycle.started`, `cycle.phase_started`, and `tool.invoked` are appended to
    the streaming log by `VisibilityState._audit()`.
  - `model_stream_chunk` enters `VisibilityState._live_chunk()` but was only stored on the cycle
    preview and not appended to the persisted log.
  - `model_output` enters `VisibilityState._model_output()` and is appended to the log.
  - `tool_result` enters through `Cycle._emit_tool()` and is appended as a stream event.
- Current report cadence before implementation:
  - `_write_report()` runs at scenario start, after `_checks_already_satisfied()`, after
    `_run_birthgiver()`, after each `Cycle` phase through `report_hook`, after each cycle returns,
    and during final persistence.
  - Live events such as `ticket.created`, `cycle.phase_started`, `model_stream_chunk`,
    `model_output`, `tool.invoked`, and `tool_result` did not each guarantee an immediately updated
    static `visibility/index.html`.
- Current live browser behavior before implementation:
  - `_render_live_status()` used English phase text such as `exploring context`, `making changes`,
    `running verification commands`, and `model verifying`.
  - `_WS_SCRIPT` opened a WebSocket but used `ws.onmessage=()=>{}`, so the browser did not update
    the DOM from live messages.
- q20 is intentionally broader than q19: q19 focuses on streaming model tokens into the DOM, while
  q20 also covers live object creation, action-specific status text, per-second static report
  freshness, and medium-scenario/manual smoke verification.
- Implemented live activity tracking in `VisibilityState`: snapshots now expose `activity` with
  `current_action`, `current_action_label`, `current_model`, `current_tool`, `current_phase`,
  `ticket_id`, and `cycle_id`.
- Implemented action-specific labels used by `index.html`: `модель генерирует`, `идёт проверка`,
  `выполняется tool: <name>`, `ожидание следующей фазы`, and
  `сценарий завершён: <status>`.
- Implemented static live previews in `render_stream_log_html()` from cycle `live` /
  `live_thinking` snapshot fields so streamed model text is visible in `index.html` before final
  `model_output`.
- Implemented a non-empty `_WS_SCRIPT` handler that exposes `window.__PLANFOLDR_HANDLE_EVENT__`,
  parses WebSocket event JSON, updates `#live-status`, appends live model chunks to
  `#live-preview`, and appends visible ticket/tool/model entries to `#log`.
- Implemented live report refreshes from `Orchestrator._sink()` for important audit/model/tool
  events and throttled `model_stream_chunk` refreshes to at most once per second.
- Focused verification run:
  `.venv/bin/python -m pytest tests/test_visibility.py tests/test_cycle_stub.py -q`
  returned `46 passed in 2.47s`.
- Full verification run:
  `.venv/bin/python -m pytest -q`
  returned `136 passed, 1 skipped in 7.22s`.
- Manual pre-smoke process check on 2026-06-10 found an already active Planfoldr execution:
  PID 58377 was running
  `python -m planfoldr run examples/taskmanager_local_l10b.yaml --visibility terminal`
  under shell PID 58375. The manual medium smoke run was not started to avoid overlapping a second
  Planfoldr execution with the active run. The automated focused test
  `test_static_index_report_updates_on_live_events` still ran a deterministic scenario through
  `run_scenario()`, inspected `visibility/index.html` from the external stream sink while the run
  was active, and confirmed live model text, `ticket.created`, `model_output`, and `tool.invoked`
  were visible before the final result.
