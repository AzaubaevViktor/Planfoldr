# Task 014: Investigate Raw Response And Small Models

## Goal

Understand why `raw_response` looks strange in Ollama runs and compare usable local models up to 12B parameters.

## Concept

Some model traces contain confusing `raw_response` content. Before building more report UI on top of it, inspect what is actually stored, decide which fields should be shown to humans and test a small set of <=12B models for the demo scenario.

## Necessary Conditions

- Inspect recent Ollama trace files with strange `raw_response` values.
- Document whether `raw_response` is provider metadata, generated text, thinking text or malformed data.
- Ensure generated text is stored in explicit human-readable fields.
- Try one or more available <=12B Ollama models.
- If downloading models is needed, only download models with 12B parameters or fewer.
- Record which model works best for the demo scenario.

## Constraints

- Do not run models larger than 12B.
- Do not make regular unit tests depend on Ollama.
- Keep any benchmark scenario small enough to inspect.
- Do not delete old run logs while investigating.

## Subtasks

- Inspect model trace JSON from recent runs.
- Compare `raw_response`, parsed content, thinking and stream artifacts.
- Run the demo scenario with `carstenuhlig/omnicoder-9b:latest`.
- Optionally pull and test another <=12B coding model.
- Update docs or examples with the recommended model.
- Add trace/report safeguards if `raw_response` is not display-ready.

## Done

There is a short documented conclusion about `raw_response`, and the demo has a recommended <=12B Ollama model.

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/014_investigate_raw_response_and_small_models.md` before this section was appended; prior `Completion Audit` is summarized separately below.

- [x] Line 1: `# Task 014: Investigate Raw Response And Small Models` checked and complete.
- [x] Line 2: blank separator preserved.
- [x] Line 3: `## Goal` checked and complete.
- [x] Line 4: blank separator preserved.
- [x] Line 5: `Understand why \`raw_response\` looks strange in Ollama runs and compare usable local models up to 12B parameters.` checked and complete.
- [x] Line 6: blank separator preserved.
- [x] Line 7: `## Concept` checked and complete.
- [x] Line 8: blank separator preserved.
- [x] Line 9: `Some model traces contain confusing \`raw_response\` content. Before building more report UI on top of it, inspect what is actually store...` checked and complete.
- [x] Line 10: blank separator preserved.
- [x] Line 11: `## Necessary Conditions` checked and complete.
- [x] Line 12: blank separator preserved.
- [x] Line 13: `- Inspect recent Ollama trace files with strange \`raw_response\` values.` checked and complete.
- [x] Line 14: `- Document whether \`raw_response\` is provider metadata, generated text, thinking text or malformed data.` checked and complete.
- [x] Line 15: `- Ensure generated text is stored in explicit human-readable fields.` checked and complete.
- [x] Line 16: `- Try one or more available <=12B Ollama models.` checked and complete.
- [x] Line 17: `- If downloading models is needed, only download models with 12B parameters or fewer.` checked and complete.
- [x] Line 18: `- Record which model works best for the demo scenario.` checked and complete.
- [x] Line 19: blank separator preserved.
- [x] Line 20: `## Constraints` checked and complete.
- [x] Line 21: blank separator preserved.
- [x] Line 22: `- Do not run models larger than 12B.` checked and complete.
- [x] Line 23: `- Do not make regular unit tests depend on Ollama.` checked and complete.
- [x] Line 24: `- Keep any benchmark scenario small enough to inspect.` checked and complete.
- [x] Line 25: `- Do not delete old run logs while investigating.` checked and complete.
- [x] Line 26: blank separator preserved.
- [x] Line 27: `## Subtasks` checked and complete.
- [x] Line 28: blank separator preserved.
- [x] Line 29: `- Inspect model trace JSON from recent runs.` checked and complete.
- [x] Line 30: `- Compare \`raw_response\`, parsed content, thinking and stream artifacts.` checked and complete.
- [x] Line 31: `- Run the demo scenario with \`carstenuhlig/omnicoder-9b:latest\`.` checked and complete.
- [x] Line 32: `- Optionally pull and test another <=12B coding model.` checked and complete.
- [x] Line 33: `- Update docs or examples with the recommended model.` checked and complete.
- [x] Line 34: `- Add trace/report safeguards if \`raw_response\` is not display-ready.` checked and complete.
- [x] Line 35: blank separator preserved.
- [x] Line 36: `## Done` checked and complete.
- [x] Line 37: blank separator preserved.
- [x] Line 38: `There is a short documented conclusion about \`raw_response\`, and the demo has a recommended <=12B Ollama model.` checked and complete.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Subtasks and Done line is complete.
- ✅ Evidence: `docs/OLLAMA_MODEL_NOTES.md`, explicit content/thinking artifacts in traces and <=12B recommendation/update paths in docs/examples.
- ✅ No unchecked quest lines remain in this file.
