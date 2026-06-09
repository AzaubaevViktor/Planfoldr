# Task phase4_q01: Scaffold + Audit + Toolset (level 0)
File name: `phase4_q01_audit_toolset.md`

## Status

Current status: done
Blocked by: none
Description: Root `planfoldr` package scaffold plus the two level-0 entities (Audit, Toolset) from PHASE_4_recompile Quest 4.

## Goal

Stand up the new canonical package at repo root and implement the append-only Audit log and the versioned Toolset registry with least-privilege enforcement.

## Necessary Conditions

- `pyproject.toml`, `requirements.txt`, `src/planfoldr/`, `tests/` exist; `pip install -e .` works.
- Audit: `emit(event_type, **payload)` appends a JSON line to `audit.jsonl`; canonical event-type constants; ticket-level replay; live subscribers; never blocks the flow (unserializable payload + subscriber errors tolerated).
- Toolset: base/domain/meta scopes; every role gets BASE_TOOLS; `create_role` meta-only; unauthorized invoke → `tool.denied` trace event + refusal; registry versioned + documented.

## Constraints

- Audit only records; it does not mutate state or run business logic.
- Toolset must refuse meta `create_role` for non-birthgiver toolsets at construction time.

## Outcome

`planfoldr.audit` and `planfoldr.toolset` are importable, installed, and covered by focused tests.

## Verification

- `.venv/bin/python -m pytest tests/test_audit.py tests/test_toolset.py -q` → **11 passed**.
- Concrete evidence:
  - `test_audit.py::test_persists_jsonl_roundtrip` — append-only JSONL, one line/event, roundtrip via `AuditLog.read`.
  - `test_audit.py::test_replay_filters_by_ticket` — replay at ticket level (PHASE_3 "Replay на уровне тикета").
  - `test_audit.py::test_audit_does_not_stop_on_unserializable_payload` — never blocks on bad payload (PHASE_4 §12 "Не блокировать ... при превышении бюджета").
  - `test_toolset.py::test_create_role_is_meta_only` — `create_role` reserved to birthgiver meta toolset.
  - `test_toolset.py::test_denied_tool_emits_trace_event_and_raises` — PHASE_4 §15 "Вызов неразрешённого инструмента → trace event + отказ".
  - `test_toolset.py::test_registry_versioned_and_documented` — PHASE_4 §15 "Toolset документирован и версионирован".

## Implementation Notes

- Files: `src/planfoldr/{__init__,util,audit,toolset}.py`, `tests/test_{audit,toolset}.py`, root `pyproject.toml`, `requirements.txt`, `README.md`.
- Audit carries optional `actor/ticket_id/cycle_id` first-class fields so replay and Visibility slices can filter without parsing payloads.
- Tool handlers are bound at runtime (`ToolRegistry.bind`) by later layers (cycle/orchestrator); Q01 registers dummy handlers in tests only.
