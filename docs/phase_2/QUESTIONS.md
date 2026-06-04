# Phase 2 Questions

Implementation questions to answer while building the MVP.

These questions should be answered incrementally by the agent working on each task. Answers should update the relevant task file, schema draft, architecture document or implementation code.

## 1. Project Scaffold

### 1. Which implementation stack should Phase 2 use?

- Answer target: choose one stack and document why.
- Current bias: Python, because the repository already has Python-oriented `.gitignore`, the runtime is CLI/test-heavy, and YAML/schema tooling is straightforward.
- Impacts: task 001.

### 2. What should the package/module name be?

- Answer target: stable import name.
- Current bias: `planfoldr`.
- Impacts: task 001.

### 3. What is the canonical test command?

- Answer target: one command used by agents and CI later.
- Current bias: `python -m pytest`.
- Impacts: task 001.

### 4. What generated directories should never be committed?

- Answer target: exact `.gitignore` entries.
- Current bias: `runs/`, Python caches, test caches.
- Impacts: task 001.

## 2. Schema And Loader

### 5. Should schemas be implemented with dataclasses, Pydantic or plain dictionaries?

- Answer target: one validation approach for scenario/cycle/task.
- Current bias: Pydantic if dependency setup is acceptable; dataclasses plus explicit validators if keeping dependencies minimal.
- Impacts: task 002.

### 6. What YAML parser should be used?

- Answer target: dependency and parser behavior.
- Current bias: PyYAML for MVP.
- Impacts: task 002.

### 7. How are relative paths resolved?

- Answer target: root-relative or file-relative rule.
- Current bias: linked YAML and prompt files resolve relative to the file that declares them.
- Impacts: task 002.

### 8. How strict should unknown fields be?

- Answer target: reject, warn or preserve.
- Current bias: reject unknown fields in core contracts, preserve extension fields only under explicit `metadata` or `x_` keys.
- Impacts: task 002.

### 9. How should schema validation errors be represented?

- Answer target: error object shape.
- Current bias: file path, YAML path, expected field/type, actual value preview.
- Impacts: task 002.

## 3. Runtime Core

### 10. What is the exact result envelope shape?

- Answer target: JSON-serializable structure used by all executors.
- Current bias: align with `docs/phase_1/SCHEMA_DRAFT.md`.
- Impacts: task 003.

### 11. How does a cycle choose its first task?

- Answer target: explicit `entrypoint` or derived from task order.
- Current bias: add explicit `entrypoint` even if Phase 1 did not require it, because it removes ambiguity.
- Impacts: task 003 and schema update.

### 12. How are terminal states represented in links?

- Answer target: exact reserved values.
- Current bias: `success`, `fail`, `parent`.
- Impacts: task 003.

### 13. Should outcome names use `need_*` or `needs_*`?

- Answer target: one naming convention.
- Current bias: keep answered Phase 1 values: `need_context`, `need_decision`, `need_answer`, `need_inner_cycle`, `need_permission`, `need_tool`.
- Impacts: task 003.

### 14. How much parallelism is implemented in MVP?

- Answer target: sequential, async cycles or thread-per-cycle.
- Current bias: implement deterministic sequential execution first; keep cycle runner API async-ready. Add actual concurrency only when a test requires it.
- Impacts: task 003.

### 15. How does parent-child communication work in code?

- Answer target: request/response data model.
- Current bias: child returns typed outcome with `request` payload; parent link maps it to a task or terminal decision.
- Impacts: task 003.

## 4. Context, State And Audit

### 16. What is the context storage shape?

- Answer target: nested dict, typed object or event-derived snapshot.
- Current bias: nested dict snapshots plus immutable audit events in MVP.
- Impacts: task 004.

### 17. What are the exact scope names?

- Answer target: canonical strings.
- Current bias: `task`, `cycle`, `scenario`, `decision_log`, `audit_log`.
- Impacts: task 004.

### 18. How are context permissions expressed in YAML?

- Answer target: `read`, `write`, `delete` schema.
- Current bias: `context_access.read/write/delete` arrays of dotted paths.
- Impacts: task 004 and schema update.

### 19. What is an audit event?

- Answer target: fields for event type, actor, scope, path, before/after or redacted values.
- Current bias: event id, timestamp, actor id, action, scope path, value summary, result.
- Impacts: task 004.

### 20. Which facts are automatically propagated upward?

- Answer target: explicit rule.
- Current bias: none except task result metadata; all domain facts require explicit propagation.
- Impacts: task 004.

## 5. Budgets And Permissions

### 21. How is model budget measured?

- Answer target: tokens, money-like units or abstract counter.
- Current bias: abstract numeric budget in MVP, because local Ollama may not expose cost.
- Impacts: task 005.

### 22. How is RAM budget enforced?

- Answer target: enforce, observe or placeholder.
- Current bias: track as configured budget and report unsupported enforcement for MVP unless process tooling makes it cheap.
- Impacts: task 005.

### 23. How are filesystem allowlists normalized?

- Answer target: realpath behavior and relative path root.
- Current bias: normalize relative to scenario file/root, compare resolved absolute paths.
- Impacts: task 005.

### 24. How is command allowlist matched?

- Answer target: binary only, full command or prefix.
- Current bias: binary/tool name allowlist, with arguments checked separately only when a task specifies stricter constraints.
- Impacts: task 005.

### 25. What happens when a nested cycle asks for more budget or permission?

- Answer target: parent decision protocol.
- Current bias: return `budget_exceeded` or `need_permission` with report; parent link decides next task or fail.
- Impacts: task 005.

## 6. Executors

### 26. How are internal operations represented?

- Answer target: are file writes commands, special executors or runtime helpers?
- Current bias: runtime helper executor for internal file materialization, not arbitrary shell.
- Impacts: task 006.

### 27. What is the command executor safety boundary?

- Answer target: cwd, env, timeout, filesystem access.
- Current bias: explicit cwd, controlled env, timeout from budget, filesystem checks before writes where possible.
- Impacts: task 006.

### 28. What is the model adapter interface?

- Answer target: request/response method signature.
- Current bias: `generate(prompt, schema, model_config, context) -> ModelResponse`.
- Impacts: task 006.

### 29. How does the stub model choose a response?

- Answer target: by task id, prompt id, fixture sequence or all of these.
- Current bias: fixture map by task id plus optional sequence number.
- Impacts: task 006 and 009.

### 30. How does the Ollama adapter handle unavailable local model?

- Answer target: fail, skip or typed outcome.
- Current bias: optional e2e test skips; runtime task returns `need_tool` or `failure` with clear reason.
- Impacts: task 006 and 010.

## 7. Verification And Validation

### 31. What schema dialect should `input_schema` and `output_schema` use?

- Answer target: JSON Schema subset or custom schema.
- Current bias: JSON Schema subset.
- Impacts: task 007.

### 32. Does every task output need a `status` field?

- Answer target: required or executor-derived.
- Current bias: runtime result has outcome status; task domain output may have its own fields but does not need duplicate `status` unless scenario wants it.
- Impacts: task 007 and schema update.

### 33. How are verifier chains represented?

- Answer target: `required_conditions` links to verifier task ids or separate list.
- Current bias: `required_conditions[].verifier_task` references existing verifier tasks.
- Impacts: task 007.

### 34. What evidence must verifier tasks produce?

- Answer target: evidence shape.
- Current bias: check id, status, command/model/script details, observed output, failure reason.
- Impacts: task 007 and 008.

### 35. How are retries counted against budgets?

- Answer target: retry budget semantics.
- Current bias: every retry consumes model/tool call budgets.
- Impacts: task 007.

## 8. Trace, Replay And Report

### 36. Where are trace files written?

- Answer target: path rule.
- Current bias: scenario `outputs.trace_path`, default under `runs/<scenario_id>/trace.json`.
- Impacts: task 008.

### 37. What is the trace schema version?

- Answer target: initial version string.
- Current bias: `0.1`.
- Impacts: task 008.

### 38. What does task replay mean exactly?

- Answer target: replay mode semantics.
- Current bias: rebuild task result from stored trace without calling model/tool; useful for report/debug and downstream deterministic tests.
- Impacts: task 008.

### 39. What should the HTML report show first?

- Answer target: report information architecture.
- Current bias: scenario summary, final status, cycle tree, task list, selected task details, model/tool panels, audit and budget summary.
- Impacts: task 008.

### 40. Should the report embed trace JSON?

- Answer target: separate file or embedded data.
- Current bias: static HTML embeds a compact trace copy or references sibling `trace.json`; choose one during implementation.
- Impacts: task 008.

## 9. E2E Scenarios

### 41. What are the two stub e2e scenarios?

- Answer target: fixture names and expected final statuses.
- Current bias: `cli_todo_success_stub` and `cli_todo_failure_stub`.
- Impacts: task 009.

### 42. What failure should the unsuccessful scenario demonstrate?

- Answer target: one failure mode.
- Current bias: invalid model output followed by retry exhaustion, because it proves validation and retry behavior.
- Impacts: task 009.

### 43. How small should the generated CLI todo project be?

- Answer target: expected file list.
- Current bias: one source file, one test file, minimal package metadata if needed.
- Impacts: task 010.

### 44. Which language should the generated demo project use?

- Answer target: one language for the Ollama demo.
- Current bias: Python, because tests can run with the same toolchain.
- Impacts: task 010.

### 45. What should happen if generated tests fail?

- Answer target: fail immediately or ask model for patch.
- Current bias: for first MVP, fail with rich report; patch loop can be a later scenario.
- Impacts: task 010.

## 10. Documentation And Agent Handoff

### 46. Which task files must be updated after implementation discoveries?

- Answer target: update rule.
- Current bias: update the active task file and any downstream task that relies on changed assumptions.
- Impacts: all tasks.

### 47. How should agents record deviations from Phase 1?

- Answer target: one location.
- Current bias: add a `Decision Updates` section to the relevant task file and update `docs/phase_1/DECISIONS.md` if the change is core.
- Impacts: all tasks.

### 48. What should be committed after each task?

- Answer target: commit boundary.
- Current bias: one task, one or more focused commits, all with `[AI]` prefix.
- Impacts: all tasks.

### 49. What is the minimum evidence before marking a task done?

- Answer target: tests/docs/artifacts per task.
- Current bias: passing relevant tests plus updated docs/examples if the task changed contracts.
- Impacts: all tasks.

### 50. What should Phase 2 not decide yet?

- Answer target: avoid scope creep.
- Current bias: do not decide production UI, distributed execution, full sandboxing, automatic model routing or full scenario replay until MVP proves the runtime.
- Impacts: all tasks.
