# MVP Specification

## Goal

Build a minimal deterministic runtime that can run YAML-described nested agent flows, execute command and model tasks, validate structured outputs, enforce basic budgets and permissions, produce trace artifacts and render a static HTML report.

## Primary Demo

Run an e2e scenario where a local Ollama model creates a simple CLI todo-list project in a separate git repository.

Expected demo output:
- generated project files;
- generated tests;
- test command result;
- structured run trace;
- static HTML report.

## Functional Requirements

### Scenario Loading

- Load a root YAML scenario file.
- Resolve linked YAML files.
- Resolve external prompt files.
- Validate required scenario, cycle and task fields.
- Fail before execution if required fields are missing.

### Runtime

- Run a scenario.
- Run nested cycles.
- Run tasks.
- Branch by enum outcome.
- Allow a parent cycle to receive child-cycle requests.
- Return final scenario status.

### Executors

- Run `command` tasks.
- Run `model` tasks through an adapter.
- Provide a stub model adapter for tests.
- Provide an Ollama model adapter for local e2e.

### Validation

- Validate task output against `output_schema`.
- Retry invalid model output according to task retry settings.
- Return `retry_exceeded` after retries are exhausted.

### Verification

- Support verifier tasks for:
  - command result;
  - schema validation;
  - custom script;
  - model-based verification.

### Context

- Maintain task, cycle and scenario context/state.
- Enforce declared context read/write/delete permissions.
- Capture context mutations in audit log.
- Support explicit fact propagation upward.

### Budgets

- Track:
  - iterations;
  - tool calls;
  - model calls;
  - model budget;
  - CPU time;
  - RAM.
- Return `budget_exceeded` with a report when a budget is exhausted.
- Support budget delegation to nested cycles.

### Permissions

- Enforce tool allowlist.
- Enforce filesystem allowlist.
- Support `need_permission` outcome for denied access.

### Trace

- Capture full input and output for every task.
- Capture model request/response.
- Capture tool result.
- Capture budgets before and after execution.
- Capture prompt id, hash, variables and rendered prompt.
- Capture artifacts.

### Reporting

- Produce CLI logs.
- Produce structured trace file.
- Produce static one-page HTML report.
- HTML report shows nested execution structure.
- HTML report allows deep levels to be collapsed.
- HTML report allows step-by-step model request/response inspection.

## Non-Functional Requirements

- Prefer boring, explicit data structures over clever abstractions.
- Keep runtime deterministic where tools and models are not involved.
- Treat model calls as captured external effects.
- Keep schema names stable and readable.
- Make logs and errors useful for weaker follow-up agents.

## Acceptance Criteria

- A stubbed successful e2e scenario passes.
- A stubbed unsuccessful e2e scenario passes and produces useful failure trace.
- The Ollama e2e scenario is implemented and ready to run locally.
- The runtime produces a trace artifact for every run.
- The HTML report renders from the trace artifact.
- Agent-facing task docs in `tasks/` stay in sync with implementation boundaries.

## Explicit Non-Goals

- No production web app.
- No visual scenario builder.
- No distributed runtime.
- No full sandbox implementation.
- No automatic model routing.
- No full scenario replay.
- No semantic run diff.
