# Planfoldr — Phase 3/4 dynamic orchestration runtime

A deterministic runtime that turns a plain-text **Scenario** into a live, observable
tree of **Tickets**. A ticket *is* a cycle; cycles spawn tickets; roles pull work from
queues; models are chosen by score; budgets meter every resource; everything is audited
and streamed live.

This is the **Phase 3** recompile. The frozen Phase 1/2 implementation lives in [`v1/`](v1/).

The architecture, entities and acceptance criteria live in
[`PHASE_3.md`](PHASE_3.md) (vision) and [`PHASE_4_recompile.md`](PHASE_4_recompile.md)
(entity decomposition + MVP). Requirement → evidence traceability is tracked in
[`PHASE_3_COVERAGE.md`](PHASE_3_COVERAGE.md).

## Quickstart

```bash
/opt/homebrew/bin/python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m planfoldr run examples/scenario.yaml
```

## Tests

```bash
.venv/bin/python -m pytest -q
```

Opt-in local Ollama end-to-end run:

```bash
PLANFOLDR_OLLAMA_E2E=1 PLANFOLDR_MODEL=gemma4:26b-mlx .venv/bin/python -m pytest -q -m ollama
```

## Build order (dependency levels, from PHASE_4_recompile Quest 4)

```
Level 0: Audit, Toolset
Level 1: Knowledge Base, Budget, Score System
Level 2: Ticket, Role
Level 3: Ticket Graph, Queue
Level 4: Queue Manager, Executor, Birthgiver
Level 5: Model, Cycle
Level 6: Visibility
Level 7: Scenario
```
