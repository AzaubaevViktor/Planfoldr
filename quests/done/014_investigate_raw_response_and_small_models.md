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
