# Architecture

## Product Shape

Planfoldr is a deterministic runtime for describing, running, testing and inspecting multi-cycle agent flows.

The first user is a solo developer who writes flows for an automated system. The first valuable result is not a general UI builder, but a reliable way to define a flow, run it, test its parts with model stubs, run a larger e2e scenario with a local model, and inspect what happened in a structured report.

The MVP scenario is an e2e test where a local model through Ollama creates a simple project, for example a `cli-todo-list`, inside a separate git repository. The flow must produce code, tests and a test run.

## Core Principle

The model is not the center of control.

The runtime controls:
- scenario lifecycle;
- cycle lifecycle;
- task execution order;
- branch decisions from typed outcomes;
- budgets;
- permissions;
- context access and mutation;
- verification;
- audit and trace output.

Models are executors inside `model` tasks.

## Hierarchy

```text
Scenario
  Cycle
    -> Task -> task -> task -> task -> task ->
    Cycle                             .^  |
      -> Task -> task -> task -> task `   `> task -> 
```

`Scenario` is the whole run. It owns the top-level goal, required conditions, constraints, budgets, inputs, outputs, cycles and context policy.

`Cycle` is a unit of flow control. Cycles can be nested. Parent and child cycles interact only through explicitly described points. A child can send facts and requests upward; a parent can pass constraints, budgets, permissions and decisions downward.

`Task` is the user-facing DSL term for a block of work. A task has a type, task description, input schema, output schema and executor. In runtime, a task execution produces an immutable result.

## Terminology

Use this terminology in implementation:

```text
Intent -> Task -> Execution -> Result
```

- `Intent`: why the work exists.
- `Task`: declarative unit of work in a scenario file.
- `Execution`: one runtime attempt to run a task.
- `Result`: structured output, status, artifacts, budget usage and audit data.

The older `Block` term may appear in notes, but Phase 2 should use `Task` for new files and APIs.

## Scenario Contract

Required scenario fields for MVP:
- `id`
- `goal`
- `required_conditions`
- `constraints`
- `budgets`
- `inputs`
- `outputs`
- `cycles`
- `context_policy`

## Cycle Contract

Required cycle fields for MVP:
- `id`
- `goal`
- `tasks`
- `links`
- `nested_cycles`
- `budgets`
- `constraints`

`links` map enum task outcomes to next tasks, parent requests, child-cycle starts or terminal states.

## Task Contract

Required task fields for MVP:
- `id`
- `type`
- `task`
- `input_schema`
- `output_schema`
- `executor`

Verifier behavior is modeled as separate `verify` tasks, not as a hidden property on every task.

## Outcomes

MVP task and cycle outcomes:
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

Every non-success outcome must include a structured reason and enough evidence for the parent cycle to decide what to do.

## Flow And Branching

MVP branching is based on enum outcomes.

Example:

```text
task.create_code -> success -> task.run_tests
task.create_code -> need_context -> parent.request_context
task.create_code -> failure -> task.inspect_failure
```

Parallel execution is part of the target architecture. For MVP, each cycle may run in its own thread or async task, while links define synchronization points. A parent task may wait for one child result or all child results.

## Context Model

Context has levels:
- task context and state;
- cycle context and state;
- scenario context and state;
- decision log;
- audit log.

Each task and cycle declares read/write/delete access to context sections.

Defaults:
- every task can freely mutate its own private context;
- every task can read allowed parent context;
- writing to parent or scenario context requires explicit permission;
- all context mutations are audit events.

Important rule:

```text
facts go up
constraints go down
```

Some information is automatically written into context. Other information is available by explicit request.

## Constraints And Permissions

There are two categories:
- verifiable constraints checked by verifier tasks;
- capability constraints that define what a scenario, cycle or task is allowed to do.

MVP permission enforcement:
- tool allowlist;
- filesystem allowlist.

Permissions flow from outer cycles to inner cycles. Inner cycles may request additional permissions through a typed `need_permission` outcome.

## Budgets

MVP budgets:
- `max_iterations`
- `max_tool_calls`
- `max_model_calls`
- `max_model_budget`
- `max_cpu_time`
- `max_ram`

A cycle can spend its budget directly or delegate a part of it to nested cycles.

On budget exhaustion, the runtime returns `budget_exceeded` with a report. The parent cycle decides whether to increase budget, stop, retry with another path or fail.

## Executors

MVP executor types:
- `command`
- `model`

Verifier tasks may use:
- command execution;
- schema validation;
- custom script;
- model request with a verification prompt.

Model selection is explicit per model task, with scenario defaults as fallback.

## Prompts

Prompts are versioned templates with:
- `id`
- content hash;
- variables;
- rendered prompt captured in audit;
- prompt id and variable values captured in trace.

## Output Validation

Model outputs must be validated against the task output schema.

On invalid output:
- retry a configured number of times;
- include schema clarification in retry prompt;
- return `retry_exceeded` if retries are exhausted.

## Verification

Required conditions are represented as a chain of verifier tasks.

A cycle is successful when its verifier tasks pass. For MVP, verifier evidence must be captured in the run trace and HTML report.

## Determinism And Replay

For reproducibility, capture:
- full input;
- full output;
- model request and response;
- tool execution result;
- budgets before and after execution;
- config version or hash;
- prompt id, variables and rendered prompt;
- artifacts produced by tasks.

MVP replay scope is task replay. Full scenario replay can be Phase 3.

Run comparison in MVP only needs final status comparison. More detailed run diff is out of Phase 2 unless it becomes necessary for tests.

## Reporting

MVP output includes:
- CLI logs;
- structured machine-readable trace;
- static one-page HTML report.

The HTML report must show the execution structure and allow the user to inspect model behavior step by step. It should support hiding deeper levels of nested cycles.

## Out Of Scope For Phase 2

Do not build in Phase 2 unless required by a task:
- visual scenario builder;
- distributed execution;
- full sandboxing;
- full scenario replay;
- semantic run diff;
- automatic model routing;
- production CI integration;
- complex parallel DAG conflict resolution.
