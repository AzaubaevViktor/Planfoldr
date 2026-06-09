# Task phase4_q09: Visibility — two HTML pages + WebSocket (level 6)
File name: `phase4_q09_visibility.md`

## Status

Current status: done
Blocked by: phase4_q08
Description: First-class observability — streaming log + state view, live over WebSocket.

## Goal

Aggregate the event stream into live slices, serve a Streaming Log page and a State View page,
push updates over a stdlib WebSocket, and also write a server-free static report per run.

## Necessary Conditions

- `VisibilityState` builds all slices: queues / tickets / models / commands / tools / cycles /
  cycle_tree / system / budgets, plus a streaming-log buffer; read-only.
- Streaming Log page: thinking → output → tool calls → results, each execution an expandable
  details/summary block. State View page: every slice section + drill-down.
- WebSocket: real RFC6455 handshake + server→client text frames (stdlib, no dependency); read-only;
  never blocks the run.
- Every run writes `runs/<id>/visibility/{index,state}.html` that open without a server (embedded
  snapshot).

## Constraints

- Visibility never mutates execution state and never blocks it (ingest/broadcast failures swallowed).

## Outcome

`planfoldr.visibility.{events,ws,web,terminal}` importable; live + static modes both work.

## Verification

- `.venv/bin/python -m pytest tests/test_visibility.py -q` → **7 passed**; full suite **92 passed, 1 skipped**.
- Concrete evidence:
  - `test_visibility.py::test_state_slices_populated_from_events` — all 9 slices filled.
  - `::test_state_view_html_has_all_required_slices` — every slice id + details/summary present.
  - `::test_accept_key_matches_rfc6455_vector` — `dGhlIHNhbXBsZSBub25jZQ==` → `s3pPLMBiTxaQ9kYGzzhZRbK+xOo=`.
  - `::test_frame_roundtrip_over_socketpair`, `::test_ws_server_handshakes_and_broadcasts` — real WS.
  - `::test_run_writes_static_visibility_report` — server-free `visibility/{index,state}.html` with embedded snapshot.
- Live web smoke (manual): server serves `/`, `/state`, `/snapshot.json`; snapshot reflects live run (status done).

## Implementation Notes

- Files: `src/planfoldr/visibility/{events,ws,web,__init__}.py`; orchestrator now feeds an internal
  `VisibilityState` for every run and writes the static report in `_persist`.
- The same HTML works live (WS at `window.__WS_PORT__`) and static (embedded `__SNAPSHOT__`/`__LOG__`),
  satisfying "Не требует сервера для чтения".
- WebSocket is a ~150-line stdlib RFC6455 server (handshake + text frames + ping/close) to keep
  "общается по вебсокет" literal with zero new dependencies.
