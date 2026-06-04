# Schema Draft

This is a draft for Phase 2 implementation. It is allowed to evolve, but changes must update examples and task docs.

## Scenario YAML

```yaml
id: cli_todo_app_demo
goal: Create a simple CLI todo-list project with tests.

inputs:
  workspace_root: ./runs/cli_todo_app_demo/workspace
  repository_path: ./runs/cli_todo_app_demo/workspace/project

outputs:
  report_path: ./runs/cli_todo_app_demo/report.html
  trace_path: ./runs/cli_todo_app_demo/trace.json

required_conditions:
  - id: project_tests_pass
    verifier_task: verify_tests

constraints:
  tools:
    allow:
      - git
      - python
      - pytest
      - ollama
      - write_files
  filesystem:
    allow_write:
      - ./runs/cli_todo_app_demo
    allow_read:
      - ./examples
      - ./runs/cli_todo_app_demo

budgets:
  max_iterations: 8
  max_tool_calls: 30
  max_model_calls: 12
  max_model_budget: 1.00
  max_cpu_time: 300
  max_ram: 1073741824

context_policy:
  default_task_parent_read: true
  default_task_parent_write: false

defaults:
  model:
    provider: ollama
    name: llama3.1
  retry:
    invalid_output: 2

cycles:
  - file: ./cycles/build_cli_todo_app.yaml
```

## Cycle YAML

```yaml
id: build_cli_todo_app
goal: Build the todo CLI project and verify tests.
entrypoint: plan_project

budgets:
  max_iterations: 6
  max_tool_calls: 25
  max_model_calls: 10

constraints:
  tools:
    allow:
      - git
      - python
      - pytest
      - ollama
      - write_files

context_access:
  read:
    - scenario.inputs
    - scenario.constraints
  write:
    - cycle.facts
    - cycle.decisions

tasks:
  - id: plan_project
    type: model
    task: Produce a JSON implementation plan for a small CLI todo-list app.
    executor:
      kind: model
      model:
        provider: ollama
        name: llama3.1
      prompt:
        id: plan_cli_todo_app
        file: ../../prompts/plan_cli_todo_app.md
    input_schema:
      type: object
    output_schema:
      type: object
      required:
        - status
        - files
      properties:
        status:
          enum:
            - success
            - failure
        files:
          type: array

  - id: create_files
    type: tool
    task: Materialize files produced by the model.
    executor:
      kind: tool
      tool: write_files
      constraints:
        filesystem:
          allow_write:
            - "{{ inputs.repository_path }}"
    input_schema:
      type: object
    output_schema:
      type: object
      required:
        - status
      properties:
        status:
          enum:
            - success
            - failure

  - id: verify_tests
    type: verify
    task: Run project tests.
    executor:
      kind: command
      command: pytest
      cwd: "{{ inputs.repository_path }}"
    input_schema:
      type: object
    output_schema:
      type: object
      required:
        - status
      properties:
        status:
          enum:
            - success
            - failure

links:
  plan_project:
    success: create_files
    failure: fail
    retry_exceeded: fail
  create_files:
    success: verify_tests
    failure: fail
    need_permission: parent
  verify_tests:
    success: success
    failure: fail
    budget_exceeded: parent

nested_cycles: []
```

## Task Result Envelope

```json
{
  "task_id": "plan_project",
  "execution_id": "exec_001",
  "status": "success",
  "reason": null,
  "input": {},
  "output": {},
  "artifacts": [],
  "budget_before": {},
  "budget_after": {},
  "audit_events": [],
  "started_at": "2026-01-01T00:00:00Z",
  "finished_at": "2026-01-01T00:00:01Z"
}
```

## Trace File

MVP trace is stored as a directory, not only as one flat file.

```text
runs/<scenario_id>/
  trace/
    manifest.json
    scenario.json
    cycles/
    tasks/
    tools/
    models/
    audit.jsonl
    decisions.jsonl
  report.html
```

`manifest.json` points to the structured trace parts and is the default entry point for report rendering.

```json
{
  "schema_version": "0.1",
  "scenario_id": "cli_todo_app_demo",
  "status": "success",
  "inputs": {},
  "outputs": {},
  "cycles": [],
  "task_executions": [],
  "context_events": [],
  "decision_log": [],
  "audit_log": [],
  "artifacts": []
}
```

## Prompt Metadata

```json
{
  "prompt_id": "plan_cli_todo_app",
  "hash": "sha256:...",
  "variables": {},
  "rendered_prompt": "..."
}
```
