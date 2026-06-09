# Task phase4_q04: Ticket Graph + Queue (level 3)
File name: `phase4_q04_graph_queue.md`

## Status

Current status: done
Blocked by: phase4_q03
Description: First coordinating structures over tickets.

## Goal

Implement the append-only Ticket Graph (6 link types, auto spawned_by, is_ready, acyclic
blocked_by, immutable history, JSON) and the Queue (triage, graph-driven readiness, priority
dispatch, manager-only declined, parallel executors).

## Necessary Conditions

- Graph: all 6 link types; auto `spawned_by` + `blocked_by`-from-dependencies on add; inverse
  blocks/blocked_by maintained; `is_ready` follows dependency completion; blocked_by stays
  acyclic (`GraphCycleError`); links append-only (no remove); `to_dict`/`replay`.
- Queue: add→incoming; accept→in_queue→ready/blocked; decline→declined+cause; declined invisible
  to executors but visible to manager; `get_next` by priority then FIFO; `refresh_ready` promotes
  blocked→ready when deps finish; parallel executors take independent tickets.

## Constraints

- Graph reflects state only; it does not drive execution. Queue does not execute tickets or change
  their goals.

## Outcome

`planfoldr.graph` and `planfoldr.queue` importable and covered.

## Verification

- `.venv/bin/python -m pytest tests/test_graph.py tests/test_queue.py -q` → **12 passed**; full suite **57 passed**.
- Concrete evidence:
  - `test_graph.py::test_blocked_by_cycle_is_rejected` — deadlock prevention (PHASE_4 §11.4).
  - `test_graph.py::test_is_ready_tracks_dependency_completion`, `::test_auto_spawned_by_and_blocked_by_on_add`, `::test_history_is_append_only_and_serializes`.
  - `test_queue.py::test_declined_is_manager_only` — PHASE_4 §5.4 "Declined тикеты видны только управляющему".
  - `test_queue.py::test_accept_with_unmet_deps_becomes_blocked_then_ready` — graph→queue ready signal.
  - `test_queue.py::test_get_next_by_priority_then_fifo`, `::test_parallel_executors_take_independent_tickets`.

## Implementation Notes

- Files: `src/planfoldr/{graph,queue}.py`, `tests/test_{graph,queue}.py`.
- Graph keeps Ticket references so `is_ready` reads live status; blocked_by automatically records
  the inverse `blocks` link so both directions are queryable. Acyclic guard does a DFS over
  blocked_by before inserting.
- Queue depends on the shared TicketGraph for readiness; `refresh_ready` is the seam the
  orchestrator calls when a dependency completes.
