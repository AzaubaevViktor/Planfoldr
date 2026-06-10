# Task phase4_q10: Runtime hardening fixes after code roast
File name: `phase4_q10_runtime_hardening_fixes.md`

## Status

Current status: active
Blocked by: none
Description: Fix the places where the runtime currently trusts the model, hides observability
failures, or records misleading success.

## Goal

Make Planfoldr's deterministic harness act like a deterministic harness: scenario status,
ticket status, scoring, visibility, and tool execution must agree with concrete evidence instead
of model confidence or swallowed failures.

## Necessary Conditions

- Scenario success cannot hide failed spawned work unless the scenario explicitly declares that
  only the final gate matters and the report visibly names the failed tickets.
- Score updates must reflect command evidence, model verdicts, budget exhaustion, false
  verification, and failed ticket attempts without rewarding a model for claiming success over
  failing command evidence.
- False verification detection must be wired into `ScoreSystem.record` and visible in generated
  analysis/report artifacts.
- Visibility/report generation failures must remain non-blocking, but they must be audited or
  surfaced in a side-channel artifact so observability failures are themselves observable.
- Shell execution must keep compound verification commands working while reducing accidental
  write paths, command ambiguity, and report-hidden stderr.
- Tool permissions must match the "least privilege" claim: base tools and role-specific tools
  should be intentionally granted, documented, and tested.

## TODO

### RnD

1. Re-read the runtime status contract in `PHASE_4_local.md`, `ARCHITECTURE.md`, and
   `interface.md`, then write down which source of truth should decide scenario success when
   spawned tickets fail but final verification passes.

   Verify: inspect the three documents and record the exact section names or bullets that define
   scenario status, ticket status, final verification, and report visibility.

2. Inspect `src/planfoldr/orchestrator.py` around `_executor_loop`, `_final_verification`,
   `_checks_already_satisfied`, and `_persist` to map every path that can return `done`,
   `failed`, `budget_exceeded`, or `error`.

   Verify: create a short implementation note listing each status path and the concrete evidence
   that currently drives it.

3. Inspect `src/planfoldr/cycle.py` around `_phase_model_verification` and `_finalize` to confirm
   how command evidence, model verdict, false verification, attempts, and score recording interact.

   Verify: identify the exact fields written to `local_memory["verdict"]`, the boolean used for
   `passed`, and the arguments passed to `ScoreSystem.record`.

4. Inspect `src/planfoldr/score.py` and `tests/test_score.py` to determine the intended penalty
   for false verification, failed tickets, budget exhaustion, and over-spawning.

   Verify: list the score fields and tests that must change or stay stable.

5. Inspect `src/planfoldr/tools_impl.py`, `src/planfoldr/toolset.py`, `src/planfoldr/role.py`, and
   `tests/test_toolset.py` to separate intentionally universal base tools from role-scoped tools.

   Verify: produce a before/after permission matrix for orchestration, developer, research,
   verification, security, and birthgiver roles.

6. Inspect `src/planfoldr/visibility/web.py`, `src/planfoldr/visibility/events.py`,
   `src/planfoldr/visibility/analysis.py`, and `tests/test_visibility.py` to find where report
   failures, false verification, failed tickets, stderr, and status reasoning should appear.

   Verify: name the default report page and observable strings that should show each hardening
   signal.

### Implementation

7. Replace the current "final gate can override failed spawned tickets" behavior with an explicit
   policy field on `Scenario` or runtime configuration. The default policy should fail the
   scenario when any required spawned ticket failed; an opt-in policy may allow final-gate-only
   success, but must report failed ticket ids in the main status/reason.

   Verify: update the e2e test that currently expects `done` despite a failed spawned ticket so
   the default case expects `failed`, and add a separate opt-in test if final-gate-only behavior is
   still needed.

8. Wire false verification into scoring. When command verification has failed evidence and model
   verification says `passed: true`, pass `false_verification=True` to `ScoreSystem.record` and
   make the ticket/report reason mention the false verification.

   Verify: add a focused test where the model claims success over a failing command; assert the
   cycle does not complete, the score event carries the false-verification penalty, and the
   report/analysis includes a false-verification signal.

9. Stop rewarding command-failed tickets as score passes. Compute score success from the same
   evidence-backed `passed` value used for ticket completion, while still recording separate
   fields for model verdict and command verdict if analysis needs both.

   Verify: add or update a score/cycle test where command checks fail but model verification
   passes; assert the model score decreases or does not increase as a successful verified run.

10. Make observability failures inspectable without blocking execution. Replace bare
    `except Exception: pass` blocks in visibility/report sinks with audit events or a
    `visibility_errors.jsonl` artifact under the run directory.

    Verify: inject a failing report hook or failing `VisibilityState.ingest`, run a stub scenario,
    and confirm the run still completes while the visibility failure is visible in audit or the
    side-channel artifact.

11. Harden command execution without breaking compound acceptance commands. Keep `&&`, `||`, and
    pipes supported for verification commands, but document and test the threat model: allowed
    cwd, minimal env, timeout, captured stdout/stderr, and rejected obvious file writes through
    `bash`.

    Verify: keep `test_run_command_shell_operators_work` passing, add tests for rejected write
    bypass patterns that matter for this project, and confirm stderr is visible in generated
    reports as readable stderr text.

12. Clarify and enforce tool permissions. Decide whether `create_ticket`, `update_ticket`,
    `write_context`, and `request_decision` are universal base tools or phase/role-specific tools;
    then update `BASE_TOOLS`, role construction, docs, and tests to match that decision.

    Verify: `tests/test_toolset.py` should assert the final permission matrix directly, including
    a denial test for at least one role/tool pair that should not be allowed.

13. Make precheck short-circuiting auditable. When `_checks_already_satisfied` marks a ticket done
    without a model cycle, emit a specific audit event or structured note that shows the command,
    exit code, and proof source.

    Verify: update `test_precheck_short_circuits_already_satisfied_ticket` to assert the
    short-circuit evidence appears in audit and in `tickets.json` or the ticket report page.

14. Add report-level status consistency checks. The static report should show scenario status,
    failed tickets, false verifications, budget exhaustion, and final verification result in the
    default visible view, not only in embedded data or collapsed debug details.

    Verify: run a stub scenario that produces at least one failed ticket and inspect
    `visibility/index.html`, `visibility/state.html`, and `analysis.md` for the failed ticket id,
    status reason, and final verification result.

### Verification

15. Run the focused tests for runtime status and scoring:
    `.venv/bin/python -m pytest tests/test_cycle_stub.py tests/test_e2e_stub.py tests/test_score.py -q`.

    Verify: all focused tests pass, and the failing-spawned-ticket scenario asserts the new default
    behavior.

16. Run the focused tests for tool permissions and visibility:
    `.venv/bin/python -m pytest tests/test_toolset.py tests/test_visibility.py -q`.

    Verify: all focused tests pass, and at least one test checks visible report text rather than
    only embedded data.

17. Run the full default suite:
    `.venv/bin/python -m pytest -q`.

    Verify: the full suite passes; if optional Ollama tests are skipped, record the skip count and
    confirm no default test requires a local model.

18. Inspect generated artifacts from at least one stub e2e run under `runs/` or pytest's tmp run
    directory: `result.json`, `tickets.json`, `scores.json`, `analysis.md`, and
    `visibility/index.html`.

    Verify: scenario status, failed ticket ids, false-verification markers, command stderr, and
    budget usage are human-readable in the intended default artifacts.

## Final Verification

- Re-read this quest and confirm every TODO item has either implementation evidence or a concrete
  note explaining why it was intentionally deferred.
- Re-read the examples and acceptance bullets in the relevant quest/docs files; confirm no pretty
  examples were removed or weakened.
- Run the focused test groups for cycle/e2e/score/toolset/visibility.
- Run `.venv/bin/python -m pytest -q`.
- Inspect the generated report artifacts directly and confirm the default view exposes scenario
  status, failed tickets, false verifications, stderr, and final verification result.
- Move this quest to `quests/done/` only in the same commit that implements and verifies the fixes.

## Implementation Notes

- This quest was created from a code audit of the current runtime, not from failing tests alone.
- Current risky anchors:
  - `src/planfoldr/orchestrator.py::_final_verification` can currently return scenario `done`
    even when spawned tickets failed.
  - `tests/test_e2e_stub.py::test_scenario_done_when_gate_passes_despite_failed_spawned_ticket`
    currently locks in that permissive behavior.
  - `src/planfoldr/cycle.py::_phase_model_verification` detects false verification, but
    `_finalize` currently records `false_verification=False` in scoring.
  - `src/planfoldr/cycle.py::_finalize` currently treats model verdict success as the score
    success signal even when command evidence failed.
  - Several visibility/reporting paths intentionally swallow exceptions; keep execution
    non-blocking, but make those failures visible.
