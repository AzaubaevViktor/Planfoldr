# Phase 1 Decisions

This document normalizes the answered questionnaire into implementation decisions.

## Product

- First user: solo developer writing flows for an automated system.
- First value: testable flow parts with stubbed real-model responses and a larger e2e run with a local model.
- Main output: static HTML report with visible execution structure, step-by-step model inspection and collapsible deep levels.
- MVP scenario: local Ollama model creates a small `cli-todo-list` project in a separate git repository, including code, tests and a test run.

## Entities

- `Scenario`: whole run.
- `Cycle`: nested flow unit with tasks and nested cycles.
- `Task`: user-facing replacement for `Block`.
- Runtime terminology: `Intent -> Task -> Execution -> Result`.

## Required Fields

Scenario:
- `id`
- `goal`
- `required_conditions`
- `constraints`
- `budgets`
- `inputs`
- `outputs`
- `cycles`
- `context_policy`

Cycle:
- `id`
- `goal`
- `tasks`
- `links`
- `nested_cycles`
- `budgets`
- `constraints`

Task:
- `id`
- `type`
- `task`
- `input_schema`
- `output_schema`
- `executor`

Verifier is a separate task type, not a field on every task.

## Flow

- Transitions branch by enum status.
- Nested cycles communicate at explicitly described points.
- Parent cycles decide how to react to failures and budget exhaustion.
- Parallelism is desired: cycles can run separately, and parent blocks may wait for one or all child results.

## Outcomes

- `success`
- `failure`
- `budget_exceeded`
- `need_context`
- `need_decision`
- `need_answer`
- `need_inner_cycle`
- `need_permission`
- `need_tool`
- `retry_exceeded`

## Context

- Context exists at task, cycle and scenario levels.
- State exists at task, cycle and scenario levels.
- There is a decision log.
- There is an audit log.
- Access to context is explicit.
- By default, a task can mutate its own context and read allowed parent context.
- Facts go up, constraints go down.

## Verification

- Required conditions are verifier task chains.
- Initial verifier capabilities: command, schema validation, custom script, model verification request.
- A cycle succeeds when its verifier tasks pass.

## Budgets

- `max_iterations`
- `max_tool_calls`
- `max_model_calls`
- `max_model_budget`
- `max_cpu_time`
- `max_ram`

Budgets can be delegated from a cycle to nested cycles.

## Permissions

- MVP must enforce tool allowlist.
- MVP must enforce filesystem allowlist.
- Permissions flow from outer cycles to inner cycles.
- Inner cycles may request additional rights.

## Models And Prompts

- MVP executor types are `command` and `model`.
- Model is explicit per model task, with defaults available.
- Invalid model output triggers configured retries with schema clarification.
- Prompts are templates with variables, ids and content hashes.
- Audit includes prompt id, variables and rendered prompt.

## Determinism

Capture all task inputs, outputs, model responses and tool results.

MVP replay target is task replay.

MVP run comparison target is final status comparison.

## Interface

- Scenario format: YAML.
- YAML may link to other YAML files and external files.
- First interface: CLI runner, logs and static one-page HTML report.
- No visual flow UI in MVP.

## Phase 2 Definition Of Done

- E2e tests with stubs pass for successful and unsuccessful scenarios.
- E2e scenario with a local Ollama model is ready to pass.
- Static HTML report is produced.
- Runtime proves the main principle: model is not the controller.
