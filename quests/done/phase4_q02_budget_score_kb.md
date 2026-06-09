# Task phase4_q02: Budget + Score System + Knowledge Base (level 1)
File name: `phase4_q02_budget_score_kb.md`

## Status

Current status: done
Blocked by: phase4_q01
Description: Level-1 primitives that depend only on Audit (+ Toolset).

## Goal

Implement real-time resource budgeting with soft-stop + delegation + `ollama ps` GPU metering,
the three-axis model Score System, and the access-controlled versioned Knowledge Base.

## Necessary Conditions

- Budget: all PHASE_3/§9 metrics (commands cpu/ram/runs; files changes/lines; models
  tokens/money/requests/gpu_ram_hours; general queues/roles/tickets); real-time `consume`;
  soft stop (finish ongoing, block new, emit `budget.exceeded` once); explicit delegation that
  bubbles usage to parent; child cannot raise its own limit without an approved decision;
  gpu_ram_hours from `ollama ps` with per-ticket attribution for a shared model.
- Score: base = f(parameter_count); +/- criteria; three axes (global/role/task_type); switch
  signal after 2-3 same-type fails; runtime `best_model` selection; model never reads own score;
  history persists across provider re-register; `model.score_updated` emitted.
- KB: sections with read/write ACL by role; versioned history; `write` → `kb.written`.

## Constraints

- Budget never hard-kills and never blocks audit. Score System does not pick the model (runtime
  does, via `best_model`). KB does not store cycle local memory.

## Outcome

`planfoldr.budget`, `planfoldr.score`, `planfoldr.knowledge_base` importable and covered.

## Verification

- `.venv/bin/python -m pytest tests/test_budget.py tests/test_score.py tests/test_knowledge_base.py -q` → **16 passed**; full suite **27 passed**.
- Concrete evidence:
  - `test_budget.py::test_soft_stop_emits_once_and_blocks_new_work` — soft stop semantics + single `budget.exceeded`.
  - `test_budget.py::test_delegation_bubbles_usage_to_parent` + `test_child_breach_blocks_child_and_propagates_block_but_not_parent_flag` — delegation + approved-only limit increase.
  - `test_budget.py::test_shared_model_gpu_attribution_is_per_ticket` — two tickets, one model, independent gpu_ram_hours (16.0 vs 8.0).
  - `test_budget.py::test_parse_ollama_ps_processor_split` — `100% GPU` / `100% CPU` / `30%/70% CPU/GPU` parsing.
  - `test_score.py::test_simpler_failed_task_penalized_more_than_harder_one` — difficulty-weighted penalty direction.
  - `test_score.py::test_switch_signal_after_consecutive_failures` + `test_runtime_selects_best_and_avoids_flagged_model`.
  - `test_knowledge_base.py::test_scoped_read_write_by_role` + `test_write_is_versioned_and_audited`.

## Implementation Notes

- Files: `src/planfoldr/{budget,score,knowledge_base}.py`, `tests/test_{budget,score,knowledge_base}.py`.
- gpu metering is per-call (`Budget.charge_model_seconds`) so a shared loaded model is attributed
  to each ticket by its own seconds — solves PHASE_3 "правильно считать если два тикета используют одну модель".
- `ScoreSystem.best_model` is the runtime-only selection seam; the future Model object will not
  expose scores to the model.
