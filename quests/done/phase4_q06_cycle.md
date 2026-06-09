# Task phase4_q06: Cycle — 4 phases + nesting (level 5b)
File name: `phase4_q06_cycle.md`

## Status

Current status: done
Blocked by: phase4_q05 (Model), phase4_q03 (Ticket/Role), phase4_q02 (Budget/Score)
Description: The base cycle — the heart of execution.

## Goal

Implement the 4-phase Cycle (context → changes → command verify → model verify) with type-based
phase subsets, a bounded JSON-action tool loop, per-cycle budget/gpu accounting, ephemeral local
memory, child-spawning, and a done/needs_review/failed/budget_exceeded decision + score update.

## Necessary Conditions

- Phases run in strict order; subsets by type (research=context+model; verify=command+model;
  default=all 4); each phase → `cycle.phase_completed`.
- Changes phase = JSON-action loop dispatching file_edit/bash/create_ticket/update_ticket/
  write_context/read_context bounded by budget + iteration cap; `finish` ends it; protocol errors
  trigger a bounded reformat retry.
- Budget accounting in the cycle (not the model): tokens, api_requests, money, gpu seconds; soft
  stop on breach. local_memory ephemeral and per-instance (no leak). spawned tickets carry
  `spawned_by`. Facts flow up via `output`; the child never declares the project done.
- Final decision: command checks + model verdict → done (with proof) / needs_review / failed
  (attempts exhausted); score recorded.

## Constraints

- The cycle only transitions its own ticket. File/command access is confined to the workspace
  allowlist (`tools_impl.safe_path`).

## Outcome

`planfoldr.cycle` + `planfoldr.tools_impl` importable; a StubModel drives a full cycle to done.

## Verification

- `.venv/bin/python -m pytest tests/test_cycle_stub.py -q` → **7 passed**; full suite **72 passed, 1 skipped**.
- Concrete evidence:
  - `test_cycle_stub.py::test_full_code_cycle_runs_four_phases_and_completes` — phases == [context, changes, command_verification, model_verification], file written, command evidence success, ticket done.
  - `::test_research_ticket_runs_context_plus_model_verify_only` + `::test_verify_ticket_runs_command_plus_model_verify_only` — phase subsets.
  - `::test_create_ticket_spawns_child_with_spawned_by` — dynamic ticket creation via tool.
  - `::test_budget_soft_stop_sets_budget_exceeded` — soft stop leaves the ticket un-done.
  - `::test_local_memory_does_not_leak_between_cycles`, `::test_child_cycle_does_not_close_parent`.

## Implementation Notes

- Files: `src/planfoldr/{cycle,tools_impl}.py`, `tests/test_cycle_stub.py`.
- `_one_action` builds the system prompt from `role.effective_prompt(queue)` + the action protocol;
  budget is consumed after each model call; gpu seconds via `Budget.charge_model_seconds` when a
  `ps_provider` is supplied.
- Tool handlers live in `tools_impl.py` and receive a `ToolContext`; `register_default_tools` binds
  them to the registry. `create_ticket` is wrapped so every spawned ticket gets `spawned_by` =
  current ticket and is appended to `spawned_tickets`.
- The model-verification phase flags a false verification when the model claims pass while command
  evidence shows failure (feeds the Score System penalty).
