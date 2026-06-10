# Task runtime_q10a_byuser_status_score: Runtime status and score correctness
File name: `runtime_q10a_byuser_status_score.md`

## Status

Current status: active
Blocked by: none
Description: Make scenario status, ticket status, false verification, and model score agree with
evidence instead of model confidence.

## Goal

Close the correctness hole where a run can look successful while spawned tickets failed or command
evidence contradicted the model's verification verdict.

## Necessary Conditions

- Scenario status has one explicit source of truth when spawned tickets fail and final verification
  passes.
- Default behavior must not silently hide failed required spawned tickets behind a passing final
  gate.
- False verification must affect score and status reasoning when the model claims success over
  failed command evidence.
- Score success must be derived from the same evidence-backed result used to complete the ticket,
  not only from the model's self-verdict.

## TODO

### RnD

1. Re-read the runtime status contract in `PHASE_4_local.md`, `ARCHITECTURE.md`, and
   `interface.md`, then decide what should happen when spawned tickets fail but final verification
   commands pass.

   Verify: record the exact section names or bullets that define scenario status, ticket status,
   final verification, and status visibility in this quest's Implementation Notes.

2. Inspect `src/planfoldr/orchestrator.py` around `_executor_loop`, `_final_verification`,
   `_run_executor_cycle`, and `_checks_already_satisfied` to map every path that can produce
   `done`, `failed`, `budget_exceeded`, or `error`.

   Verify: add a short status-path note naming the function, branch, status, and evidence source
   for each path.

3. Inspect `src/planfoldr/cycle.py` around `_phase_command_verification`,
   `_phase_model_verification`, and `_finalize` to map command evidence, model verdict,
   false-verification detection, attempts, and score recording.

   Verify: record the current `cmd_ok`, `model_ok`, `passed`, `verdict`, and `ScoreSystem.record`
   values that make false success possible.

4. Inspect `src/planfoldr/score.py` and `tests/test_score.py` to identify the intended scoring
   effects for a failed ticket, budget exhaustion, waste, false verification, and over-spawning.

   Verify: list the score fields and test names that must change or remain stable.

### Implementation

5. Replace the current "final gate can override failed spawned tickets" behavior with an explicit
   scenario/runtime policy. The default policy should fail the scenario when any required spawned
   ticket failed. If final-gate-only success is still desired, it must be opt-in and must put
   failed ticket ids in the main status reason.

   Verify: update `tests/test_e2e_stub.py::test_scenario_done_when_gate_passes_despite_failed_spawned_ticket`
   so the default case expects `failed`; add a separate opt-in test only if the final-gate-only
   policy remains supported.

6. Wire false verification into scoring. When command verification has failed evidence and model
   verification says `passed: true`, pass `false_verification=True` to `ScoreSystem.record` and
   include a false-verification note in the cycle output or ticket transition proof/reason.

   Verify: add a focused cycle test where the model claims success over a failing command; assert
   the ticket does not complete, the score event records false verification, and the result reason
   names the false verification.

7. Stop rewarding command-failed tickets as score passes. Compute score success from the same
   evidence-backed `passed` value used for ticket completion. Preserve separate model-verdict and
   command-verdict data only if analysis/reporting needs them.

   Verify: add or update a score/cycle test where command checks fail but model verification
   passes; assert the score does not record a successful verified run.

8. Make status reasoning stable in persisted artifacts. Ensure `result.json`, `tickets.json`, and
   `scores.json` contain enough structured information to explain failed spawned tickets, false
   verification, and score penalties.

   Verify: run a stub scenario that triggers a failed spawned ticket and inspect the three JSON
   artifacts for status, failed ticket id, and score penalty evidence.

### Verification

9. Run the focused status and score tests:
   `.venv/bin/python -m pytest tests/test_cycle_stub.py tests/test_e2e_stub.py tests/test_score.py -q`.

   Verify: all focused tests pass, and the failed-spawned-ticket scenario asserts the new default
   behavior.

10. Run the full default suite:
    `.venv/bin/python -m pytest -q`.

    Verify: the full suite passes; if optional Ollama tests are skipped, record the skip count and
    confirm no default test requires a local model.

11. Inspect generated artifacts from at least one stub e2e run under `runs/` or pytest's temp run
    directory: `result.json`, `tickets.json`, and `scores.json`.

    Verify: scenario status, failed ticket ids, false-verification markers, and score penalties
    are present as inspectable structured data.

## Final Verification

- Re-read this quest and confirm every TODO item has implementation evidence or a concrete defer
  note.
- Re-read the relevant docs/examples and confirm no pretty examples were removed or weakened.
- Run the focused status/score tests and `.venv/bin/python -m pytest -q`.
- Inspect the generated status/score artifacts directly.
- Move this quest to `quests/done/` only in the same commit that implements and verifies the fixes.

## Implementation Notes

- Split from the original aggregate runtime-hardening quest so status/scoring can be fixed
  independently.
- Risk anchors:
  - `src/planfoldr/orchestrator.py::_final_verification` currently can return scenario `done`
    even when spawned tickets failed.
  - `tests/test_e2e_stub.py::test_scenario_done_when_gate_passes_despite_failed_spawned_ticket`
    currently locks in that permissive behavior.
  - `src/planfoldr/cycle.py::_phase_model_verification` detects false verification, but
    `_finalize` currently records `false_verification=False`.
  - `src/planfoldr/cycle.py::_finalize` currently treats model verdict success as the score
    success signal even when command evidence failed.
