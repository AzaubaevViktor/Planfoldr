# Task phase4_q10b: Visibility and report hardening
File name: `phase4_q10b_visibility_report_hardening.md`

## Status

Current status: active
Blocked by: phase4_q10a
Description: Make observability failures and runtime hardening signals visible in default reports
without allowing report generation to break execution.

## Goal

Keep visibility non-blocking, but stop making visibility failures invisible. Reports must expose
scenario status, failed tickets, false verification, stderr, budget state, and final verification
in the default human-readable view.

## Necessary Conditions

- Visibility/report generation failures do not crash a run.
- Every swallowed visibility/report exception is captured in audit or a run-local side-channel
  artifact.
- Static reports show status consistency signals without requiring the user to dig through embedded
  snapshot data or raw JSON.
- `analysis.md` and the HTML pages are refresh-friendly and continue to use manifest-backed run
  artifacts.

## TODO

### RnD

1. Inspect `src/planfoldr/orchestrator.py` around `_sink`, `_write_report`, `_record_model_io`, and
   `_persist` to find every visibility/report exception that is currently swallowed.

   Verify: list each exception site and the run artifact or audit event that should capture it.

2. Inspect `src/planfoldr/visibility/events.py`, `src/planfoldr/visibility/web.py`,
   `src/planfoldr/visibility/analysis.py`, and `tests/test_visibility.py` to decide where failed
   tickets, false verification, final verification, budget state, and stderr should be visible.

   Verify: name the default HTML page, section, and observable strings for each hardening signal.

3. Inspect the report examples and output rules in `interface.md` so generated reports stay
   chronological and human-readable rather than falling back to raw JSON blobs.

   Verify: record the relevant interface bullets in Implementation Notes and preserve their
   visible-output shape.

### Implementation

4. Add an inspectable path for visibility/report failures. Prefer an audit event plus a
   `visibility_errors.jsonl` artifact under the run directory if the audit path itself is not safe
   for a given exception.

   Verify: inject a failing `VisibilityState.ingest` or failing report writer in a focused test;
   assert the run still completes and the failure is visible in audit or `visibility_errors.jsonl`.

5. Add report-level status consistency sections to the default visible HTML. The report should show
   scenario status, status reason, failed ticket ids, false-verification count, budget exhaustion,
   and final verification result in ordinary visible text.

   Verify: run a stub scenario with a failed ticket and inspect `visibility/index.html` and
   `visibility/state.html` for the failed ticket id, status reason, and final verification result.

6. Ensure command stderr is rendered as stderr text, not hidden inside a raw JSON field or only
   present in collapsed debug data.

   Verify: add or update a visibility test with a failing command that writes stderr; assert the
   generated HTML contains a readable `stderr` label and the stderr content.

7. Extend `analysis.md` to call out false verification, failed spawned tickets, budget exhaustion,
   and final verification mismatch using concise human-readable sections.

   Verify: run a stub scenario that triggers at least one of those signals and inspect
   `analysis.md` for the exact ticket id and signal wording.

### Verification

8. Run the focused visibility tests:
   `.venv/bin/python -m pytest tests/test_visibility.py -q`.

   Verify: all visibility tests pass, including at least one assertion on visible report text
   rather than only embedded snapshot data.

9. Run the focused e2e tests that generate reports:
   `.venv/bin/python -m pytest tests/test_e2e_stub.py -q`.

   Verify: all e2e tests pass and generated report artifacts exist for the inspected run.

10. Run the full default suite:
    `.venv/bin/python -m pytest -q`.

    Verify: the full suite passes; record any optional skip count.

11. Inspect a generated run directory: `analysis.md`, `visibility/index.html`,
    `visibility/state.html`, `visibility/tickets.html`, and any `visibility_errors.jsonl`.

    Verify: status, failed ticket ids, false-verification markers, stderr, budget usage, and final
    verification are human-readable in the intended default artifacts.

## Final Verification

- Re-read this quest and confirm every TODO item has implementation evidence or a concrete defer
  note.
- Re-read report/interface examples and confirm no pretty examples were removed or weakened.
- Run `tests/test_visibility.py`, report-generating e2e tests, and the full suite.
- Inspect the generated report artifacts directly.
- Move this quest to `quests/done/` only in the same commit that implements and verifies the fixes.

## Implementation Notes

- Split from the original aggregate `phase4_q10_runtime_hardening_fixes.md` so reporting can be
  fixed after status/scoring semantics are clear.
- Risk anchors:
  - `src/planfoldr/orchestrator.py::_sink` currently swallows visibility ingest failures.
  - `src/planfoldr/orchestrator.py::_write_report` currently swallows report generation failures.
  - `src/planfoldr/orchestrator.py::_record_model_io` currently swallows write failures.
  - The report must remain non-blocking, but observability failures must themselves be observable.
