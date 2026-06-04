# Planfoldr

Deterministic multi-cycle pipeline builder.

Planfoldr builds agentic flows where the model is not the controller. The deterministic runtime controls scenarios, cycles, tasks, budgets, permissions, context updates, verification and trace reporting. Models are executors inside selected tasks.

## Phase Status

Phase 1 is complete as a product and architecture discovery phase.
Phase 2 is complete as an MVP prototype.

Primary decisions are captured in:
- [ARCHITECTURE.md](ARCHITECTURE.md) — target architecture and MVP boundaries.
- [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) — short practical guide for running and inspecting the prototype.
- [docs/phase_1/PHASE_1_COMPLETE.md](docs/phase_1/PHASE_1_COMPLETE.md) — Phase 1 completion marker and Phase 2 entry point.
- [docs/phase_2/PHASE_2_COMPLETE.md](docs/phase_2/PHASE_2_COMPLETE.md) — Phase 2 completion marker and implementation summary.
- [docs/phase_1/DECISIONS.md](docs/phase_1/DECISIONS.md) — normalized decisions from answered questions.
- [docs/phase_1/MVP_SPEC.md](docs/phase_1/MVP_SPEC.md) — MVP requirements and acceptance criteria.
- [docs/phase_1/SCHEMA_DRAFT.md](docs/phase_1/SCHEMA_DRAFT.md) — initial YAML and trace schema draft.
- [docs/phase_2/QUESTIONS.md](docs/phase_2/QUESTIONS.md) — open implementation questions for Phase 2.
- [docs/phase_2/DECISIONS.md](docs/phase_2/DECISIONS.md) — normalized Phase 2 implementation decisions.
- [tasks](tasks) — implementation tasks for Phase 2.

The cleaned Phase 1 answer record remains in [QUESTIONS_PHASE_1.md](QUESTIONS_PHASE_1.md).

## Phase 2 Implementation

Phase 2 was implemented from [tasks/001_project_scaffold.md](tasks/001_project_scaffold.md) through [tasks/010_ollama_e2e.md](tasks/010_ollama_e2e.md), following [docs/phase_1/IMPLEMENTATION_ORDER.md](docs/phase_1/IMPLEMENTATION_ORDER.md).

## Local Setup

Planfoldr Phase 2 uses Python and the `planfoldr` package under `src/`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest
```

Generated run artifacts belong under `runs/` and are ignored by git.

See [docs/phase_2/PHASE_2_COMPLETE.md](docs/phase_2/PHASE_2_COMPLETE.md) for implementation evidence and known MVP boundaries.
For a quick usage walkthrough, read [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md).

## Stub E2E Tests

Deterministic e2e coverage uses stubbed model responses and does not require network access or Ollama:

```bash
python -m pytest tests/test_e2e_stub_scenarios.py
```

## Optional Ollama Demo

The local-model demo is opt-in and skips automatically unless enabled:

```bash
ollama serve
ollama pull llama3.1
PLANFOLDR_RUN_OLLAMA_E2E=1 python -m pytest tests/test_ollama_e2e.py
```

Use `PLANFOLDR_OLLAMA_MODEL=<model-name>` to run the demo with another local Ollama model. Use `PLANFOLDR_OLLAMA_TIMEOUT=<seconds>` for slower models.

The demo scenario is [examples/scenarios/ollama_cli_todo_app.yaml](examples/scenarios/ollama_cli_todo_app.yaml). It writes generated work under `runs/`, which is ignored by git, and writes each execution log, trace and `report.html` into a timestamped run subdirectory.
