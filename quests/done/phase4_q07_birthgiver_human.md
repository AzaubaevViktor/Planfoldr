# Task phase4_q07: Birthgiver + dynamic roles + @human (level 4)
File name: `phase4_q07_birthgiver_human.md`

## Status

Current status: done
Blocked by: phase4_q03 (Role), phase4_q04 (Queue/Graph)
Description: Dynamic extension of the role system + the human escalation seam.

## Goal

Implement RoleRegistry/QueueRegistry, the Birthgiver meta-role (exclusive `create_role`, summon →
incoming, link/refuse/create decision), and the `@human` responder for request_decision/context.

## Necessary Conditions

- Summon of a nonexistent `@role` → an `incoming` `create_role` ticket for birthgiver + `role.summoned`.
- `link_or_create`: existing role → link (no creation); not needed → refuse with cause; needed →
  create queue + manager + executor + toolset + budget scope → `role.created` ×2 + `queue.created`.
- Created roles cannot recursively create a birthgiver.
- `create_role` is meta-only and reachable through a birthgiver context.
- `@human` answers request_decision/context (dict/list/callable/interactive) and audits
  `human.requested` / `human.answered`.

## Constraints

- Birthgiver does not run normal dev tickets, does not manage priorities, does not score.

## Outcome

`planfoldr.birthgiver` importable and covered.

## Verification

- `.venv/bin/python -m pytest tests/test_birthgiver.py -q` → **8 passed**; full suite **80 passed, 1 skipped**.
- Concrete evidence:
  - `test_birthgiver.py::test_summon_creates_incoming_ticket_for_birthgiver`.
  - `::test_create_role_opens_queue_with_manager_and_executor` — role.created ×2 + queue.created + executor carries domain tool + ticket types.
  - `::test_link_existing_role_does_not_create`, `::test_refuse_with_cause`, `::test_cannot_recursively_create_birthgiver`.
  - `::test_create_role_tool_is_meta_and_invokes_birthgiver` — meta-gated tool path.
  - `::test_human_answers_and_audits`, `::test_human_list_answers_in_order`.

## Implementation Notes

- Files: `src/planfoldr/birthgiver.py`, `tests/test_birthgiver.py`.
- `create_role` builds `{name}-manager` (QueueManager) + `{name}-exec` (Executor) + a `Queue`, then
  registers all three and emits the trace events; budget scope is stored on the queue template.
- The orchestrator (Q08) wires `@human` as the cycle's `on_request_decision` and routes comment
  summons of unknown roles to `Birthgiver.summon_ticket`.
