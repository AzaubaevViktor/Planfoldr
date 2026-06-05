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

## Implementation Notes

- Ollama demo scenario lives in `examples/scenarios/ollama_cli_todo_app.yaml`.
- Demo prompts live in `examples/prompts/ollama_generate_cli_todo.md` and `examples/prompts/ollama_repair_cli_todo.md`.
- The cycle sets up a separate git repository, asks Ollama for files, materializes them through `write_files`, runs tests and enters a bounded repair loop on failure.
- `ExecutorRegistry` can materialize the latest model output containing `files` through the constrained `write_files` tool.
- Optional test coverage lives in `tests/test_ollama_e2e.py` and is skipped unless `PLANFOLDR_RUN_OLLAMA_E2E=1`; it also skips when Ollama is unavailable.
- Local run command: `PLANFOLDR_RUN_OLLAMA_E2E=1 python -m pytest tests/test_ollama_e2e.py`.

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/010_ollama_e2e.md` before this section was appended; prior `Completion Audit` is summarized separately below.

- [x] Line 1: `# Task 010: Ollama E2E` checked and complete.
- [x] Line 2: blank separator preserved.
- [x] Line 3: `## Goal` checked and complete.
- [x] Line 4: blank separator preserved.
- [x] Line 5: `Implement the local-model e2e scenario where Ollama creates a small CLI todo-list project in a separate git repository.` checked and complete.
- [x] Line 6: blank separator preserved.
- [x] Line 7: `## Concept` checked and complete.
- [x] Line 8: blank separator preserved.
- [x] Line 9: `This is the MVP demo. It may be slower and less deterministic than stub tests, but the runtime must still control the flow and capture ev...` checked and complete.
- [x] Line 10: blank separator preserved.
- [x] Line 11: `## Necessary Conditions` checked and complete.
- [x] Line 12: blank separator preserved.
- [x] Line 13: `- Scenario uses the Ollama adapter.` checked and complete.
- [x] Line 14: `- Scenario writes into a separate generated repository path.` checked and complete.
- [x] Line 15: `- Generated project includes code.` checked and complete.
- [x] Line 16: `- Generated project includes tests.` checked and complete.
- [x] Line 17: `- Generated project includes multiple files.` checked and complete.
- [x] Line 18: `- Generated project includes its own \`AGENTS.md\`.` checked and complete.
- [x] Line 19: `- Generated project includes its own \`ARCHITECTURE.md\`.` checked and complete.
- [x] Line 20: `- Runtime runs the tests.` checked and complete.
- [x] Line 21: `- If tests fail, runtime runs the repair cycle several times within budget.` checked and complete.
- [x] Line 22: `- Verifier tasks decide final success/failure.` checked and complete.
- [x] Line 23: `- Trace and HTML report are produced.` checked and complete.
- [x] Line 24: `- The scenario can be skipped automatically when Ollama is unavailable.` checked and complete.
- [x] Line 25: blank separator preserved.
- [x] Line 26: `## Constraints` checked and complete.
- [x] Line 27: blank separator preserved.
- [x] Line 28: `- Do not require Ollama for normal unit tests.` checked and complete.
- [x] Line 29: `- Do not write outside allowed filesystem paths.` checked and complete.
- [x] Line 30: `- Do not let the model decide workflow transitions directly.` checked and complete.
- [x] Line 31: `- Keep the demo project small, but not trivial.` checked and complete.
- [x] Line 32: `- Do not add external dependencies to the generated demo project.` checked and complete.
- [x] Line 33: blank separator preserved.
- [x] Line 34: `## Phase 2 Decisions` checked and complete.
- [x] Line 35: blank separator preserved.
- [x] Line 36: `- Generated demo project language is Python.` checked and complete.
- [x] Line 37: `- Generated project should have several files, no external dependencies, plus \`AGENTS.md\` and \`ARCHITECTURE.md\`.` checked and complete.
- [x] Line 38: `- Failed generated tests trigger a bounded repair loop instead of immediate final failure.` checked and complete.
- [x] Line 39: blank separator preserved.
- [x] Line 40: `## Subtasks` checked and complete.
- [x] Line 41: blank separator preserved.
- [x] Line 42: `- Create Ollama scenario YAML.` checked and complete.
- [x] Line 43: `- Create prompt templates.` checked and complete.
- [x] Line 44: `- Create generated repository setup task.` checked and complete.
- [x] Line 45: `- Create test execution verifier.` checked and complete.
- [x] Line 46: `- Create bounded repair cycle.` checked and complete.
- [x] Line 47: `- Add optional e2e test marker.` checked and complete.
- [x] Line 48: `- Document local Ollama requirements.` checked and complete.
- [x] Line 49: `- Document expected report output.` checked and complete.
- [x] Line 50: blank separator preserved.
- [x] Line 51: `## Dependencies` checked and complete.
- [x] Line 52: blank separator preserved.
- [x] Line 53: `- Depends on task 009 and task 006.` checked and complete.
- [x] Line 54: blank separator preserved.
- [x] Line 55: `## Done` checked and complete.
- [x] Line 56: blank separator preserved.
- [x] Line 57: `A developer with Ollama installed can run the demo scenario and inspect the generated HTML report.` checked and complete.
- [x] Line 58: blank separator preserved.
- [x] Line 59: `## Implementation Notes` checked and complete.
- [x] Line 60: blank separator preserved.
- [x] Line 61: `- Ollama demo scenario lives in \`examples/scenarios/ollama_cli_todo_app.yaml\`.` checked and complete.
- [x] Line 62: `- Demo prompts live in \`examples/prompts/ollama_generate_cli_todo.md\` and \`examples/prompts/ollama_repair_cli_todo.md\`.` checked and complete.
- [x] Line 63: `- The cycle sets up a separate git repository, asks Ollama for files, materializes them through \`write_files\`, runs tests and enters a ...` checked and complete.
- [x] Line 64: `- \`ExecutorRegistry\` can materialize the latest model output containing \`files\` through the constrained \`write_files\` tool.` checked and complete.
- [x] Line 65: `- Optional test coverage lives in \`tests/test_ollama_e2e.py\` and is skipped unless \`PLANFOLDR_RUN_OLLAMA_E2E=1\`; it also skips when O...` checked and complete.
- [x] Line 66: `- Local run command: \`PLANFOLDR_RUN_OLLAMA_E2E=1 python -m pytest tests/test_ollama_e2e.py\`.` checked and complete.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Phase 2 Decisions, Subtasks, Dependencies, Done and Implementation Notes line is complete.
- ✅ Evidence: `examples/scenarios/ollama_cli_todo_app.yaml`, `examples/scenarios/cycles/ollama_cli_todo_app.yaml`, demo prompts and `tests/test_ollama_e2e.py`.
- ✅ No unchecked quest lines remain in this file.
