# Task 016: Ollama Model Size Policy

## Goal

Prevent demo and test runs from using Ollama models larger than 12B parameters.

## Concept

Large local models can be useful, but current development runs should stay within a predictable GPU budget. The runtime and docs need a clear policy: automated or recommended Ollama runs use models up to and including 12B only.

## Necessary Conditions

- Example commands use a <=12B model.
- Optional Ollama e2e tests default to a <=12B model.
- Docs state the <=12B rule.
- Any model comparison task respects the same limit.
- Local model selection starts from `ollama list`: inspect available models, prefer entries no larger than 12 GB, and try several compatible candidates when comparing behavior.
- Candidate model selection records why each `ollama list` entry was accepted or skipped, including apparent size/parameter hint when available.
- Each eligible installed model can be tried against the same benchmark/demo scenario.
- Comparison results are persisted in a report-readable file so a developer can inspect which model did better later.
- Stored comparison results include model name, apparent size, run id, scenario status, failure reason, budget usage, generated file/test summary and links to trace/report artifacts.
- If a configured model appears larger than 12B, the developer receives a clear warning or failure.

## Constraints

- Do not block non-Ollama unit tests.
- Do not require network access for validation.
- Model-size detection may be conservative when a tag does not expose parameter count.

## Subtasks

- Pick the default <=12B model for local e2e.
- Check `ollama list` for locally installed models no larger than 12 GB, and try different eligible models before settling on recommendations.
- Add a helper or CLI path that lists eligible installed Ollama models from `ollama list`.
- Add a repeatable model comparison runner for eligible <=12B candidates.
- Persist comparison results under a run artifact path such as `runs/<scenario_id>/<run_id>/model_comparison.json` or `trace/model_comparison.json`.
- Render or link the comparison results from the HTML report.
- Update docs and task descriptions.
- Add a guard or helper for obvious model-size violations.
- Add tests for model-name validation where practical.

## Done

Project docs and optional Ollama commands consistently use models with 12B parameters or fewer, and model comparison runs can persist per-model results showing which eligible installed model handled the demo best.

## Implementation Notes

- Default docs now recommend `carstenuhlig/omnicoder-9b:latest`, which is an installed <=12B coding model on the current machine.
- `planfoldr ollama-models` parses `ollama list` and prints accepted/skipped policy decisions with apparent installed size and parameter hints.
- `planfoldr compare-ollama-models <scenario>` runs the same scenario across eligible installed models and writes `model_comparison.json` plus `model_comparison.html`.
- The comparison summary includes model name, apparent size, parameter hint, run id, status, reason, budget snapshot, generated file count, generated test count and links to trace/report artifacts.
- `planfoldr run --ollama-model ...` rejects obvious model names above the <=12B policy before starting the scenario.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Subtasks, Done and Implementation Notes line is complete.
- ✅ Evidence: `src/planfoldr/ollama_policy.py`, CLI commands in `src/planfoldr/cli.py`, `tests/test_ollama_policy.py`, `docs/OLLAMA_MODEL_NOTES.md` and updated Ollama docs.
- ✅ No unchecked quest lines remain in this file.
