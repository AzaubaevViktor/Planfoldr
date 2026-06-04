# Task 010: Ollama E2E

## Goal

Implement the local-model e2e scenario where Ollama creates a small CLI todo-list project in a separate git repository.

## Concept

This is the MVP demo. It may be slower and less deterministic than stub tests, but the runtime must still control the flow and capture everything needed for inspection.

## Necessary Conditions

- Scenario uses the Ollama adapter.
- Scenario writes into a separate generated repository path.
- Generated project includes code.
- Generated project includes tests.
- Generated project includes multiple files.
- Generated project includes its own `AGENTS.md`.
- Generated project includes its own `ARCHITECTURE.md`.
- Runtime runs the tests.
- If tests fail, runtime runs the repair cycle several times within budget.
- Verifier tasks decide final success/failure.
- Trace and HTML report are produced.
- The scenario can be skipped automatically when Ollama is unavailable.

## Constraints

- Do not require Ollama for normal unit tests.
- Do not write outside allowed filesystem paths.
- Do not let the model decide workflow transitions directly.
- Keep the demo project small, but not trivial.
- Do not add external dependencies to the generated demo project.

## Phase 2 Decisions

- Generated demo project language is Python.
- Generated project should have several files, no external dependencies, plus `AGENTS.md` and `ARCHITECTURE.md`.
- Failed generated tests trigger a bounded repair loop instead of immediate final failure.

## Subtasks

- Create Ollama scenario YAML.
- Create prompt templates.
- Create generated repository setup task.
- Create test execution verifier.
- Create bounded repair cycle.
- Add optional e2e test marker.
- Document local Ollama requirements.
- Document expected report output.

## Dependencies

- Depends on task 009 and task 006.

## Done

A developer with Ollama installed can run the demo scenario and inspect the generated HTML report.
