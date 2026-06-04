# Getting Started

This is a short practical guide for using the Phase 2 Planfoldr prototype.

## 1. Set Up Locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest
```

The expected regular test result is all tests passing with the optional Ollama e2e test skipped unless explicitly enabled.

## 2. What Planfoldr Runs

A run starts from a root scenario YAML file. The scenario links to one or more cycle YAML files, and model tasks link to prompt files.

Example root scenario:

```text
examples/scenarios/ollama_cli_todo_app.yaml
```

Important fields:

- `inputs` and `outputs`: paths and values the scenario uses.
- `constraints`: allowed tools and filesystem paths.
- `budgets`: max iterations, tool calls, model calls and time.
- `cycles`: linked cycle YAML files.

Inside a cycle, `entrypoint` names the first task. Each task returns a `status`, and `links` decide the next task or terminal state.

## 3. Run Tests First

Run the deterministic suite:

```bash
python -m pytest
```

Run only stub e2e scenarios:

```bash
python -m pytest tests/test_e2e_stub_scenarios.py
```

Stub e2e tests do not call real models. They cover success, command failure, budget exhaustion, retry exhaustion and a repair loop.

## 4. Run A YAML Scenario

Run a scenario by pointing Planfoldr at the root YAML file:

```bash
python -m planfoldr run examples/scenarios/ollama_cli_todo_app.yaml
```

This writes:

```text
runs/<scenario_id>/
  <run_id>/
    logs/
      execution.log
    trace/
      manifest.json
      scenario.json
      tasks/executions.json
      cycles/index.json
    report.html
```

## 5. Inspect A Run

While a run is still executing, start with:

```text
runs/<scenario_id>/<run_id>/logs/execution.log
```

This JSONL file is written immediately at run initialization and then before and after each task.
Streaming model progress is tracked as follow-up work in `tasks/011_streaming_model_progress.md`; until that lands, a long model task may still show only `task_start` until the blocking model request finishes or times out.

Trace files are JSON or JSONL. The main entry point is:

```text
runs/<scenario_id>/<run_id>/trace/manifest.json
```

Captured task results are stored in:

```text
runs/<scenario_id>/<run_id>/trace/tasks/executions.json
```

Open `runs/<scenario_id>/<run_id>/report.html` in a browser for the static report.

## 6. Optional Ollama Demo

The Ollama demo is opt-in:

```bash
ollama serve
ollama pull llama3.1
python -m planfoldr run examples/scenarios/ollama_cli_todo_app.yaml
```

Use another local model:

```bash
python -m planfoldr run examples/scenarios/ollama_cli_todo_app.yaml \
  --ollama-model carstenuhlig/omnicoder-9b:latest \
  --ollama-timeout 180
```

Scenario:

```text
examples/scenarios/ollama_cli_todo_app.yaml
```

The runtime still controls workflow. Ollama only supplies model task output. Generated work stays under `runs/`.

## 7. Common Failure Modes

- `need_permission`: the task asked for a tool or filesystem path outside `constraints`.
- `budget_exceeded`: a configured budget was consumed past its maximum.
- `retry_exceeded`: model output did not match `output_schema` after retries.
- `failure`: a command returned non-zero, an executor failed, or a task output failed validation.

When debugging a live run, start with `logs/execution.log`. After the run finishes, inspect `tasks/executions.json`, then model, command or tool detail files under the trace directory.
