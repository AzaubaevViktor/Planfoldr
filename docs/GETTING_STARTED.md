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

## 4. Run A Scenario From Python

Minimal pattern:

```python
from pathlib import Path

from planfoldr.executors import ExecutorRegistry, StubModelAdapter
from planfoldr.guards import BudgetTracker, PermissionEngine
from planfoldr.loader import load_scenario
from planfoldr.trace import run_and_trace

scenario = load_scenario(Path("tests/fixtures/scenarios/e2e_success_scenario.yaml"))

registry = ExecutorRegistry(
    permission_engine=PermissionEngine(scenario.document.constraints, base_dir=Path("tests/fixtures/scenarios")),
    budget_tracker=BudgetTracker(scenario.document.budgets),
    prompts=scenario.cycles[0].prompts,
    model_adapter=StubModelAdapter({"plan:e2e_stub_prompt": {"status": "success"}}),
)

result = run_and_trace(scenario, registry, output_root="runs")
print(result.status)
```

This writes:

```text
runs/<scenario_id>/
  trace/
    manifest.json
    scenario.json
    tasks/executions.json
    cycles/index.json
  report.html
```

## 5. Inspect Trace And Replay A Task

Trace files are JSON or JSONL. The main entry point is:

```text
runs/<scenario_id>/trace/manifest.json
```

Replay a captured task result without running the executor again:

```python
from planfoldr.trace import replay_task

task_result = replay_task("runs/e2e_success_scenario/trace", "plan")
print(task_result.output)
```

Open `runs/<scenario_id>/report.html` in a browser for the static report.

## 6. Optional Ollama Demo

The Ollama demo is opt-in:

```bash
ollama serve
ollama pull llama3.1
PLANFOLDR_RUN_OLLAMA_E2E=1 python -m pytest tests/test_ollama_e2e.py
```

Use another local model:

```bash
PLANFOLDR_RUN_OLLAMA_E2E=1 PLANFOLDR_OLLAMA_MODEL=carstenuhlig/omnicoder-9b:latest PLANFOLDR_OLLAMA_TIMEOUT=180 python -m pytest tests/test_ollama_e2e.py
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

When debugging, start with `tasks/executions.json`, then inspect model, command or tool detail files under the trace directory.
