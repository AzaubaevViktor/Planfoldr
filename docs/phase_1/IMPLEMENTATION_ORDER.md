# Implementation Order

Phase 2 should be implemented in small vertical slices. Do not start with a large abstraction pass.

## Task Dependency Graph

```text
001_project_scaffold
  -> 002_schema_and_loader
    -> 003_runtime_core
      -> 004_context_state_audit
      -> 005_budget_permission_engine
      -> 006_executors_command_model
        -> 007_verifiers_and_output_validation
          -> 008_trace_replay_report
            -> 009_e2e_stub_scenarios
              -> 010_ollama_e2e
```

## Suggested Order

1. [001_project_scaffold](../../tasks/001_project_scaffold.md)
2. [002_schema_and_loader](../../tasks/002_schema_and_loader.md)
3. [003_runtime_core](../../tasks/003_runtime_core.md)
4. [004_context_state_audit](../../tasks/004_context_state_audit.md)
5. [005_budget_permission_engine](../../tasks/005_budget_permission_engine.md)
6. [006_executors_command_model](../../tasks/006_executors_command_model.md)
7. [007_verifiers_and_output_validation](../../tasks/007_verifiers_and_output_validation.md)
8. [008_trace_replay_report](../../tasks/008_trace_replay_report.md)
9. [009_e2e_stub_scenarios](../../tasks/009_e2e_stub_scenarios.md)
10. [010_ollama_e2e](../../tasks/010_ollama_e2e.md)

## Agent Rule

Each task file is intended to be executable by a weaker agent. The agent should:
- read only the linked architecture/spec files first;
- implement only the task scope;
- update examples/tests touched by the task;
- commit changes with `[AI]` prefix.
