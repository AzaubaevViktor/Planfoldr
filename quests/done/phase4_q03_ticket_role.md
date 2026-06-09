# Task phase4_q03: Ticket + Role (level 2)
File name: `phase4_q03_ticket_role.md`

## Status

Current status: done
Blocked by: phase4_q01, phase4_q02
Description: The first entities with lifecycle/business rules.

## Goal

Implement the full Ticket (all §2.5 fields, status machine, immutable goal, can't-self-complete,
failed-after-N, comments with `@role`, JSON roundtrip) and the Role (self-modify guard, queue
prompt/scope mixing, can_create_ticket_types) with QueueManager/Executor specializations.

## Necessary Conditions

- Ticket: status machine incoming→blocked/ready→running→done/failed/needs_review→done; every
  transition validated + audited; goal immutable; cannot reach `done` without passing mandatory
  checks or an explicit reviewer proof; `declined` requires a cause; attempt counting; comments
  summon `@role`; JSON ser/de; `child_closing_parent` guard.
- Role: every role has BASE_TOOLS; queue prompt mixed in (base preserved); queue scope extends
  base without mutating it; one role serves several queues; cannot modify itself; QueueManager
  and Executor carry their extra fields.

## Constraints

- Ticket holds no execution logic, only data. Role cannot create another role (meta tool gating).

## Outcome

`planfoldr.ticket` and `planfoldr.role` importable and covered.

## Verification

- `.venv/bin/python -m pytest tests/test_ticket.py tests/test_role.py -q` → **18 passed**; full suite **45 passed**.
- Concrete evidence:
  - `test_ticket.py::test_cannot_self_complete_without_passing_mandatory_checks` — PHASE_4 §1 "только через прохождение всех обязательных проверок".
  - `test_ticket.py::test_needs_review_to_done_requires_reviewer_proof` — needs_review→done gate.
  - `test_ticket.py::test_goal_is_immutable`, `::test_declined_requires_cause`, `::test_failed_after_n_attempts`, `::test_comment_can_summon_role`, `::test_json_roundtrip`, `::test_child_cannot_close_parent`.
  - `test_role.py::test_queue_prompt_is_mixed_in_not_overridden` + `::test_queue_scope_extends_without_mutating_base` — PHASE_4 Role↔Queue §3.2 "только расширяет".
  - `test_role.py::test_role_cannot_modify_itself`, `::test_one_role_serves_multiple_queues`.

## Implementation Notes

- Files: `src/planfoldr/{ticket,role}.py`, `tests/test_{ticket,role}.py`.
- `Ticket._goal` is private with a read-only `goal` property; the setter raises to keep the goal
  an immutable contract. `new_ticket` stamps creation metadata + emits `ticket.created`.
- `Role.__setattr__` protects `id`/`_prompt` after construction; `effective_toolset` builds a
  fresh Toolset per queue so a shared role never leaks scope across queues.
- `child_closing_parent(parent, actor, to)` is the guard the cycle/orchestrator will call before
  letting a spawned ticket move its parent to a terminal state.
