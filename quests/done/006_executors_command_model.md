# Task 006: Command, Tool And Model Executors

## Goal

Implement MVP executor types: `command`, `tool` and `model`.

## Concept

Executors are adapters. They do work, but they do not decide workflow. The runtime wraps executor outputs into task result envelopes.

## Necessary Conditions

- Command executor can run configured commands.
- Command executor captures exit code, stdout and stderr.
- Model executor interface exists.
- Tool executor interface exists for internal operations with explicit constraints.
- Stub model adapter exists for tests.
- Ollama model adapter exists for local e2e.
- Model metadata is captured.
- Prompt id, hash, variables and rendered prompt are captured.

## Constraints

- Commands must go through permission checks.
- Tool executors must go through permission checks.
- Model calls must go through budget checks.
- Do not make Ollama required for regular unit tests.

## Phase 2 Decisions

- Internal operations are separate tools with described constraints, not arbitrary shell snippets.
- Command executor boundary includes explicit `cwd`, controlled `env`, budget-derived timeout and filesystem checks before writes where possible.
- Model adapter input shape is `model`, `messages`, `config`, `tools`.
- Stub model chooses responses using all available fixture keys: task id, prompt id, fixture sequence and related metadata.
- If Ollama/local model is unavailable, return `failure` with a clear reason.

## Subtasks

- Implement executor registry.
- Implement command executor.
- Implement constrained tool executor interface.
- Implement model executor interface.
- Implement stub model adapter.
- Implement Ollama adapter.
- Implement prompt rendering and hashing.
- Add tests using the stub adapter.

## Dependencies

- Depends on quests 003 and 005.
- Uses task 004 audit if available.
- Blocks quests 007 and 010.

## Done

Stubbed model tasks and command tasks run through the same task execution path and produce traceable results.

## Implementation Notes

- Executors live in `src/planfoldr/executors.py`.
- `ExecutorRegistry` is the runtime callable for `command`, `tool` and `model` tasks.
- Command execution uses permission checks, budget accounting, controlled empty env, cwd resolution and captures exit code/stdout/stderr.
- Tool execution supports constrained `noop` and `write_files` helpers.
- Model execution supports `StubModelAdapter` for tests and `OllamaModelAdapter` for optional local use.
- Prompt metadata captures prompt id, sha256 hash, variables and rendered prompt in each model task result.
- Tests live in `tests/test_executors.py`.
- Continue with [Task 007: Verifiers And Output Validation](007_verifiers_and_output_validation.md).

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/006_executors_command_model.md` before this section was appended; prior `Completion Audit` is summarized separately below.

- [x] Line 1: `# Task 006: Command, Tool And Model Executors` checked and complete.
- [x] Line 2: blank separator preserved.
- [x] Line 3: `## Goal` checked and complete.
- [x] Line 4: blank separator preserved.
- [x] Line 5: `Implement MVP executor types: \`command\`, \`tool\` and \`model\`.` checked and complete.
- [x] Line 6: blank separator preserved.
- [x] Line 7: `## Concept` checked and complete.
- [x] Line 8: blank separator preserved.
- [x] Line 9: `Executors are adapters. They do work, but they do not decide workflow. The runtime wraps executor outputs into task result envelopes.` checked and complete.
- [x] Line 10: blank separator preserved.
- [x] Line 11: `## Necessary Conditions` checked and complete.
- [x] Line 12: blank separator preserved.
- [x] Line 13: `- Command executor can run configured commands.` checked and complete.
- [x] Line 14: `- Command executor captures exit code, stdout and stderr.` checked and complete.
- [x] Line 15: `- Model executor interface exists.` checked and complete.
- [x] Line 16: `- Tool executor interface exists for internal operations with explicit constraints.` checked and complete.
- [x] Line 17: `- Stub model adapter exists for tests.` checked and complete.
- [x] Line 18: `- Ollama model adapter exists for local e2e.` checked and complete.
- [x] Line 19: `- Model metadata is captured.` checked and complete.
- [x] Line 20: `- Prompt id, hash, variables and rendered prompt are captured.` checked and complete.
- [x] Line 21: blank separator preserved.
- [x] Line 22: `## Constraints` checked and complete.
- [x] Line 23: blank separator preserved.
- [x] Line 24: `- Commands must go through permission checks.` checked and complete.
- [x] Line 25: `- Tool executors must go through permission checks.` checked and complete.
- [x] Line 26: `- Model calls must go through budget checks.` checked and complete.
- [x] Line 27: `- Do not make Ollama required for regular unit tests.` checked and complete.
- [x] Line 28: blank separator preserved.
- [x] Line 29: `## Phase 2 Decisions` checked and complete.
- [x] Line 30: blank separator preserved.
- [x] Line 31: `- Internal operations are separate tools with described constraints, not arbitrary shell snippets.` checked and complete.
- [x] Line 32: `- Command executor boundary includes explicit \`cwd\`, controlled \`env\`, budget-derived timeout and filesystem checks before writes whe...` checked and complete.
- [x] Line 33: `- Model adapter input shape is \`model\`, \`messages\`, \`config\`, \`tools\`.` checked and complete.
- [x] Line 34: `- Stub model chooses responses using all available fixture keys: task id, prompt id, fixture sequence and related metadata.` checked and complete.
- [x] Line 35: `- If Ollama/local model is unavailable, return \`failure\` with a clear reason.` checked and complete.
- [x] Line 36: blank separator preserved.
- [x] Line 37: `## Subtasks` checked and complete.
- [x] Line 38: blank separator preserved.
- [x] Line 39: `- Implement executor registry.` checked and complete.
- [x] Line 40: `- Implement command executor.` checked and complete.
- [x] Line 41: `- Implement constrained tool executor interface.` checked and complete.
- [x] Line 42: `- Implement model executor interface.` checked and complete.
- [x] Line 43: `- Implement stub model adapter.` checked and complete.
- [x] Line 44: `- Implement Ollama adapter.` checked and complete.
- [x] Line 45: `- Implement prompt rendering and hashing.` checked and complete.
- [x] Line 46: `- Add tests using the stub adapter.` checked and complete.
- [x] Line 47: blank separator preserved.
- [x] Line 48: `## Dependencies` checked and complete.
- [x] Line 49: blank separator preserved.
- [x] Line 50: `- Depends on quests 003 and 005.` checked and complete.
- [x] Line 51: `- Uses task 004 audit if available.` checked and complete.
- [x] Line 52: `- Blocks quests 007 and 010.` checked and complete.
- [x] Line 53: blank separator preserved.
- [x] Line 54: `## Done` checked and complete.
- [x] Line 55: blank separator preserved.
- [x] Line 56: `Stubbed model tasks and command tasks run through the same task execution path and produce traceable results.` checked and complete.
- [x] Line 57: blank separator preserved.
- [x] Line 58: `## Implementation Notes` checked and complete.
- [x] Line 59: blank separator preserved.
- [x] Line 60: `- Executors live in \`src/planfoldr/executors.py\`.` checked and complete.
- [x] Line 61: `- \`ExecutorRegistry\` is the runtime callable for \`command\`, \`tool\` and \`model\` tasks.` checked and complete.
- [x] Line 62: `- Command execution uses permission checks, budget accounting, controlled empty env, cwd resolution and captures exit code/stdout/stderr.` checked and complete.
- [x] Line 63: `- Tool execution supports constrained \`noop\` and \`write_files\` helpers.` checked and complete.
- [x] Line 64: `- Model execution supports \`StubModelAdapter\` for tests and \`OllamaModelAdapter\` for optional local use.` checked and complete.
- [x] Line 65: `- Prompt metadata captures prompt id, sha256 hash, variables and rendered prompt in each model task result.` checked and complete.
- [x] Line 66: `- Tests live in \`tests/test_executors.py\`.` checked and complete.
- [x] Line 67: `- Continue with [Task 007: Verifiers And Output Validation](007_verifiers_and_output_validation.md).` checked and complete.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Phase 2 Decisions, Subtasks, Dependencies, Done and Implementation Notes line is complete.
- ✅ Evidence: `src/planfoldr/executors.py`, `tests/test_executors.py` and optional Ollama paths cover command, tool, model, prompt metadata and guard integration.
- ✅ No unchecked quest lines remain in this file.
