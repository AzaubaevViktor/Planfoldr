# Task phase4_q08: Scenario + Orchestrator + CLI (level 7)
File name: `phase4_q08_scenario_orchestrator_cli.md`

## Status

Current status: done
Blocked by: phase4_q04..q07
Description: The integration that makes the whole system runnable from a YAML scenario.

## Goal

Load a Scenario, seed base queues via birthgiver, run the top decomposition cycle, drive the
executor loop (triage → select model → run cycle → resolve deps → soft-stop), run final scenario
verification, persist artifacts, and expose a CLI.

## Necessary Conditions

- `load_scenario` parses goal/budget/accesses/verification/model; budget aliases normalized;
  Scenario immutable.
- Orchestrator: per-run dir + isolated workspace under `runs/<id>/`; base queues (orchestration,
  developer, research, verification, security) each with manager+executor; top cycle creates the
  first tickets; executor loop runs ready tickets, re-attempts needs_review, soft-stops on budget;
  `create_ticket` routes by type and escalates unknown types to birthgiver; final verification gate.
- Artifacts persisted: audit.jsonl, graph.json, scores.json, tickets.json, scenario.json, result.json.
- CLI: `python -m planfoldr run examples/scenario.yaml` with `--model/--provider/--visibility`.

## Constraints

- Per-run workspace isolation; scenario paths rendered against the workspace allowlist.

## Outcome

`planfoldr.{scenario,orchestrator,cli}` + minimal `visibility.terminal`; full flow runs offline
with a StubModel.

## Verification

- `.venv/bin/python -m pytest tests/test_e2e_stub.py -q` → **5 passed**; full suite **85 passed, 1 skipped**.
- Concrete evidence:
  - `test_e2e_stub.py::test_full_scenario_completes_and_persists` — scenario→done; both dynamic
    tickets done; alpha.txt+beta.txt written; all artifacts present; tokens metered.
  - `::test_dependency_resolved_via_graph` — developer-2 blocked_by developer-1; runs only after
    developer-1 done (audit seq ordering).
  - `::test_audit_has_every_phase_and_tool_call` — scenario.started/ticket.created/
    cycle.phase_completed(×4 phases)/tool.invoked/model.score_updated/scenario.completed.
  - `::test_budget_soft_stop_stops_the_run` — budget_exceeded + soft stop.
  - `::test_failed_ticket_makes_scenario_fail` — failed ticket + false_verification penalty scored.
- Terminal sink smoke (manual): renders code-agent-style flow (cycle/phase/tool/score/ticket lines).

## Implementation Notes

- Files: `src/planfoldr/{scenario,orchestrator,cli,__main__}.py`, `src/planfoldr/visibility/{__init__,terminal}.py`,
  `examples/{scenario.yaml,calc_local.yaml}`, `tests/test_e2e_stub.py`. Added orchestration/plan/decompose
  phase subsets to `cycle.PHASES_BY_TYPE`.
- `examples/scenario.yaml` preserves the PHASE_4 Quest-6 FastAPI example shape (+model block);
  `examples/calc_local.yaml` is an offline-safe variant for real-model runs.
- Visibility terminal is the minimal Q08 version; the two HTML pages + WebSocket land in Q09.
