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
