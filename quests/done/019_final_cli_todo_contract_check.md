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

- Previous quest `019_ticket_tree_context_orchestration.md` is now `quests/020_ticket_tree_context_orchestration.md`.
- The hidden final check lives in `tests/test_ollama_e2e.py` as `_assert_generated_cli_behaves_like_todo_prompt`.
- The checker runs each candidate entry point in an isolated state directory with `PYTHONPATH` pointed at the generated repository.
- The contract checks that `add` persists items, `list` shows them from a later process and `done` changes the visible state of the chosen item.
- `examples/prompts/ollama_generate_cli_todo.md` now explicitly asks for add/list/done commands, while the exact final checker remains outside model-visible workflow.
