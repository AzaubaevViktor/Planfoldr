# Task 019: Final CLI Todo Contract Check

## Goal

Add a final deterministic check for the Ollama CLI todo demo that is not visible to the model and runs once after the scenario cycle has finished.

## Concept

The current Ollama demo lets the generated project define and run its own tests. That proves the model can create internally consistent code, but it does not prove the resulting CLI behaves like the example prompt asked.

Add an outer test-level contract check after `run_and_trace(...)` succeeds. This check should execute the generated CLI as a user would, exercise add/list/done behavior across separate process invocations and fail if the implementation only satisfies its own generated tests.

## Necessary Conditions

- The check runs outside the scenario YAML cycle.
- The check is not described in model-visible prompts as verifier code.
- The check runs only once after the full Planfoldr cycle exits successfully.
- The check executes generated code in a separate state directory.
- The check accepts common Python CLI entry points such as `python -m todo` and `python -m todo.cli`.
- The check verifies `add`, `list` and `done` commands against real subprocess behavior.
- The check confirms todo state survives across separate CLI invocations.
- The check remains part of optional Ollama e2e coverage and does not require Ollama for the default suite.

## Constraints

- Keep the check deterministic and dependency-free.
- Do not expose the exact final checker logic to the model through scenario tasks.
- Do not write generated state into the repository under test.
- Keep the failure message useful enough to diagnose generated CLI shape problems.

## Subtasks

- Rename the previous active quest 019 to quest 020.
- Add a post-run CLI contract assertion to `tests/test_ollama_e2e.py`.
- Add fast unit coverage for the checker using a synthetic generated project.
- Clarify the generation prompt so the requested CLI includes add/list/done commands.
- Run the default test suite.

## Done

The optional Ollama e2e test now performs a hidden final CLI behavior check after the scenario succeeds, and the default suite covers the checker without requiring Ollama.

## Implementation Notes

- Previous quest `019_ticket_tree_context_orchestration.md` is now `quests/orchestration_020_ticket_tree_context_orchestration.md`.
- The hidden final check lives in `tests/test_ollama_e2e.py` as `_assert_generated_cli_behaves_like_todo_prompt`.
- The checker runs each candidate entry point in an isolated state directory with `PYTHONPATH` pointed at the generated repository.
- The contract checks that `add` persists items, `list` shows them from a later process and `done` changes the visible state of the chosen item.
- `examples/prompts/ollama_generate_cli_todo.md` now explicitly asks for add/list/done commands, while the exact final checker remains outside model-visible workflow.

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/019_final_cli_todo_contract_check.md` before this section was appended; prior `Completion Audit` is summarized separately below.

- [x] Line 1: `# Task 019: Final CLI Todo Contract Check` checked and complete.
- [x] Line 2: blank separator preserved.
- [x] Line 3: `## Goal` checked and complete.
- [x] Line 4: blank separator preserved.
- [x] Line 5: `Add a final deterministic check for the Ollama CLI todo demo that is not visible to the model and runs once after the scenario cycle has ...` checked and complete.
- [x] Line 6: blank separator preserved.
- [x] Line 7: `## Concept` checked and complete.
- [x] Line 8: blank separator preserved.
- [x] Line 9: `The current Ollama demo lets the generated project define and run its own tests. That proves the model can create internally consistent c...` checked and complete.
- [x] Line 10: blank separator preserved.
- [x] Line 11: `Add an outer test-level contract check after \`run_and_trace(...)\` succeeds. This check should execute the generated CLI as a user would...` checked and complete.
- [x] Line 12: blank separator preserved.
- [x] Line 13: `## Necessary Conditions` checked and complete.
- [x] Line 14: blank separator preserved.
- [x] Line 15: `- The check runs outside the scenario YAML cycle.` checked and complete.
- [x] Line 16: `- The check is not described in model-visible prompts as verifier code.` checked and complete.
- [x] Line 17: `- The check runs only once after the full Planfoldr cycle exits successfully.` checked and complete.
- [x] Line 18: `- The check executes generated code in a separate state directory.` checked and complete.
- [x] Line 19: `- The check accepts common Python CLI entry points such as \`python -m todo\` and \`python -m todo.cli\`.` checked and complete.
- [x] Line 20: `- The check verifies \`add\`, \`list\` and \`done\` commands against real subprocess behavior.` checked and complete.
- [x] Line 21: `- The check confirms todo state survives across separate CLI invocations.` checked and complete.
- [x] Line 22: `- The check remains part of optional Ollama e2e coverage and does not require Ollama for the default suite.` checked and complete.
- [x] Line 23: blank separator preserved.
- [x] Line 24: `## Constraints` checked and complete.
- [x] Line 25: blank separator preserved.
- [x] Line 26: `- Keep the check deterministic and dependency-free.` checked and complete.
- [x] Line 27: `- Do not expose the exact final checker logic to the model through scenario tasks.` checked and complete.
- [x] Line 28: `- Do not write generated state into the repository under test.` checked and complete.
- [x] Line 29: `- Keep the failure message useful enough to diagnose generated CLI shape problems.` checked and complete.
- [x] Line 30: blank separator preserved.
- [x] Line 31: `## Subtasks` checked and complete.
- [x] Line 32: blank separator preserved.
- [x] Line 33: `- Rename the previous active quest 019 to quest 020.` checked and complete.
- [x] Line 34: `- Add a post-run CLI contract assertion to \`tests/test_ollama_e2e.py\`.` checked and complete.
- [x] Line 35: `- Add fast unit coverage for the checker using a synthetic generated project.` checked and complete.
- [x] Line 36: `- Clarify the generation prompt so the requested CLI includes add/list/done commands.` checked and complete.
- [x] Line 37: `- Run the default test suite.` checked and complete.
- [x] Line 38: blank separator preserved.
- [x] Line 39: `## Done` checked and complete.
- [x] Line 40: blank separator preserved.
- [x] Line 41: `The optional Ollama e2e test now performs a hidden final CLI behavior check after the scenario succeeds, and the default suite covers the...` checked and complete.
- [x] Line 42: blank separator preserved.
- [x] Line 43: `## Implementation Notes` checked and complete.
- [x] Line 44: blank separator preserved.
- [x] Line 45: `- Previous quest \`019_ticket_tree_context_orchestration.md\` is now \`quests/orchestration_020_ticket_tree_context_orchestration.md\`.` checked and complete.
- [x] Line 46: `- The hidden final check lives in \`tests/test_ollama_e2e.py\` as \`_assert_generated_cli_behaves_like_todo_prompt\`.` checked and complete.
- [x] Line 47: `- The checker runs each candidate entry point in an isolated state directory with \`PYTHONPATH\` pointed at the generated repository.` checked and complete.
- [x] Line 48: `- The contract checks that \`add\` persists items, \`list\` shows them from a later process and \`done\` changes the visible state of the...` checked and complete.
- [x] Line 49: `- \`examples/prompts/ollama_generate_cli_todo.md\` now explicitly asks for add/list/done commands, while the exact final checker remains ...` checked and complete.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Subtasks, Done and Implementation Notes line is complete.
- ✅ Evidence: hidden checker and synthetic coverage in `tests/test_ollama_e2e.py`, renamed `orchestration_020` quest and prompt clarification in `examples/prompts/ollama_generate_cli_todo.md`.
- ✅ No unchecked quest lines remain in this file.
