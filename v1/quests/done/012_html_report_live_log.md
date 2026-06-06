# Task 012: HTML Report Live Execution Log

## Goal

Make the HTML report useful as a live execution viewer, including current status, remaining budget, task inputs, model text and a refreshable view of run artifacts.

## Concept

The report should not be only a final static summary. It should be possible to open it while or after a run, see what is currently running, how much budget remains, what already happened, inspect task inputs, inspect model outputs and refresh the visible data from a manifest-like file that lists the run artifacts.

## Necessary Conditions

- HTML report includes model-generated text for model tasks.
- HTML report includes rendered task inputs for every task type.
- Model task inputs include the rendered prompt/messages sent to the provider.
- Command task inputs include command, working directory, environment overrides and stdin when present.
- Tool/verifier task inputs include the structured parameters used for execution.
- HTML report includes a live status panel for running or incomplete runs.
- Status panel shows scenario status, current task, current cycle, attempt number and last event time.
- Status panel shows budget usage and remaining budget for model calls, tool calls, iterations and other tracked limits.
- Status panel distinguishes queued, running, succeeded, failed, skipped and budget-exhausted work.
- HTML report includes a detailed chronological log of what happened during the run.
- Report data is loaded from a file that describes available run artifacts, task input artifacts and current run status.
- The artifact description includes paths to execution logs, trace files, model outputs and stream files.
- The report has a visible way to refresh loaded information from the artifact description.
- The report can auto-refresh while a run is still active, with a visible timestamp for the loaded snapshot.
- Missing or still-being-written files are handled gracefully.
- The report remains useful when opened directly from the filesystem.

## Constraints

- Do not inline huge model outputs repeatedly in the HTML.
- Do not inline huge task inputs repeatedly in the HTML.
- Redact or omit secrets from environment and provider inputs.
- Do not require a server for basic report viewing.
- Keep paths relative to the run directory.
- Avoid leaking files outside the current run.
- Keep live status derivable from persisted run files, not process memory.

## Subtasks

- Extend run artifact manifest with all report-readable files.
- Persist current run status and budget counters during execution.
- Teach report generation to reference the manifest.
- Persist rendered task inputs as report-readable artifacts.
- Add live status and budget summary sections to the report.
- Add task input sections to the report.
- Add model output sections to the report.
- Add execution-log section with structured event rendering.
- Add refresh behavior for reloading manifest-backed data.
- Add tests for active, successful, failed and budget-exhausted status snapshots.
- Add tests for manifest paths and report content.

## Done

Opening `runs/<scenario_id>/<run_id>/report.html` shows current run status, remaining budget, task inputs, model text, detailed run events and can refresh data from the run artifact manifest.

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/012_html_report_live_log.md` before this section was appended; prior `Completion Audit` is summarized separately below.

- [x] Line 1: `# Task 012: HTML Report Live Execution Log` checked and complete.
- [x] Line 2: blank separator preserved.
- [x] Line 3: `## Goal` checked and complete.
- [x] Line 4: blank separator preserved.
- [x] Line 5: `Make the HTML report useful as a live execution viewer, including current status, remaining budget, task inputs, model text and a refresh...` checked and complete.
- [x] Line 6: blank separator preserved.
- [x] Line 7: `## Concept` checked and complete.
- [x] Line 8: blank separator preserved.
- [x] Line 9: `The report should not be only a final static summary. It should be possible to open it while or after a run, see what is currently runnin...` checked and complete.
- [x] Line 10: blank separator preserved.
- [x] Line 11: `## Necessary Conditions` checked and complete.
- [x] Line 12: blank separator preserved.
- [x] Line 13: `- HTML report includes model-generated text for model tasks.` checked and complete.
- [x] Line 14: `- HTML report includes rendered task inputs for every task type.` checked and complete.
- [x] Line 15: `- Model task inputs include the rendered prompt/messages sent to the provider.` checked and complete.
- [x] Line 16: `- Command task inputs include command, working directory, environment overrides and stdin when present.` checked and complete.
- [x] Line 17: `- Tool/verifier task inputs include the structured parameters used for execution.` checked and complete.
- [x] Line 18: `- HTML report includes a live status panel for running or incomplete runs.` checked and complete.
- [x] Line 19: `- Status panel shows scenario status, current task, current cycle, attempt number and last event time.` checked and complete.
- [x] Line 20: `- Status panel shows budget usage and remaining budget for model calls, tool calls, iterations and other tracked limits.` checked and complete.
- [x] Line 21: `- Status panel distinguishes queued, running, succeeded, failed, skipped and budget-exhausted work.` checked and complete.
- [x] Line 22: `- HTML report includes a detailed chronological log of what happened during the run.` checked and complete.
- [x] Line 23: `- Report data is loaded from a file that describes available run artifacts, task input artifacts and current run status.` checked and complete.
- [x] Line 24: `- The artifact description includes paths to execution logs, trace files, model outputs and stream files.` checked and complete.
- [x] Line 25: `- The report has a visible way to refresh loaded information from the artifact description.` checked and complete.
- [x] Line 26: `- The report can auto-refresh while a run is still active, with a visible timestamp for the loaded snapshot.` checked and complete.
- [x] Line 27: `- Missing or still-being-written files are handled gracefully.` checked and complete.
- [x] Line 28: `- The report remains useful when opened directly from the filesystem.` checked and complete.
- [x] Line 29: blank separator preserved.
- [x] Line 30: `## Constraints` checked and complete.
- [x] Line 31: blank separator preserved.
- [x] Line 32: `- Do not inline huge model outputs repeatedly in the HTML.` checked and complete.
- [x] Line 33: `- Do not inline huge task inputs repeatedly in the HTML.` checked and complete.
- [x] Line 34: `- Redact or omit secrets from environment and provider inputs.` checked and complete.
- [x] Line 35: `- Do not require a server for basic report viewing.` checked and complete.
- [x] Line 36: `- Keep paths relative to the run directory.` checked and complete.
- [x] Line 37: `- Avoid leaking files outside the current run.` checked and complete.
- [x] Line 38: `- Keep live status derivable from persisted run files, not process memory.` checked and complete.
- [x] Line 39: blank separator preserved.
- [x] Line 40: `## Subtasks` checked and complete.
- [x] Line 41: blank separator preserved.
- [x] Line 42: `- Extend run artifact manifest with all report-readable files.` checked and complete.
- [x] Line 43: `- Persist current run status and budget counters during execution.` checked and complete.
- [x] Line 44: `- Teach report generation to reference the manifest.` checked and complete.
- [x] Line 45: `- Persist rendered task inputs as report-readable artifacts.` checked and complete.
- [x] Line 46: `- Add live status and budget summary sections to the report.` checked and complete.
- [x] Line 47: `- Add task input sections to the report.` checked and complete.
- [x] Line 48: `- Add model output sections to the report.` checked and complete.
- [x] Line 49: `- Add execution-log section with structured event rendering.` checked and complete.
- [x] Line 50: `- Add refresh behavior for reloading manifest-backed data.` checked and complete.
- [x] Line 51: `- Add tests for active, successful, failed and budget-exhausted status snapshots.` checked and complete.
- [x] Line 52: `- Add tests for manifest paths and report content.` checked and complete.
- [x] Line 53: blank separator preserved.
- [x] Line 54: `## Done` checked and complete.
- [x] Line 55: blank separator preserved.
- [x] Line 56: `Opening \`runs/<scenario_id>/<run_id>/report.html\` shows current run status, remaining budget, task inputs, model text, detailed run eve...` checked and complete.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Subtasks and Done line is complete.
- ✅ Evidence: manifest-backed live report/status support in `src/planfoldr/trace.py` and report/status assertions in `tests/test_trace.py`.
- ✅ No unchecked quest lines remain in this file.
