# Planfoldr

Planfoldr is a dynamic ticket-graph orchestration runtime. You give it a plain-text goal; it decomposes the work into a live tree of **Tickets**, assigns each ticket to a specialised **Role**, selects the best **Model** by score, meters every resource against a **Budget**, and streams everything to a terminal or a browser in real time.

The current implementation is **Phase 3/4**. The frozen Phase 1/2 code lives in [`v1/`](v1/).

---

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m planfoldr run examples/scenario.yaml
```

The scenario file describes the goal, budget, filesystem accesses, and verification:

```yaml
name: fastapi_health
goal: "Add GET /health endpoint to the FastAPI service"
budget:
  tokens: 50000
accesses:
  - path: ./src
    mode: read_write
verification:
  commands:
    - "pytest tests/test_health.py"
model:
  provider: ollama
  name: gemma4:26b-mlx
```

See [`examples/`](examples/) for more scenarios (calculator, brainfuck interpreter, task queue, file server).

---

## CLI reference

```
python -m planfoldr run <scenario.yaml> [options]

Options:
  --model NAME          Override model name from scenario
  --provider PROVIDER   Override provider (ollama | stub)
  --runs-dir DIR        Output directory (default: runs/)
  --run-id ID           Set a custom run ID
  --max-cycles N        Hard cycle limit (default: 40)
  --visibility MODE     terminal | web | none  (default: terminal)
  --port PORT           Web UI port (default: 8765)
  --hold                Keep web server alive after run finishes
```

Output is a JSON result written to `<runs-dir>/<run-id>/`:

| File | Contents |
|------|----------|
| `audit.jsonl` | Append-only event stream (every transition, tool call, budget event) |
| `report.html` | Self-contained HTML run report |
| `kb.json` | Final knowledge base snapshot |
| `result.json` | Run status, ticket summary, tokens used |

---

## Running tests

```bash
.venv/bin/pytest -q
```

The default suite runs entirely with the stub model — no Ollama required.

To run the optional end-to-end test against a local Ollama instance:

```bash
PLANFOLDR_OLLAMA_E2E=1 PLANFOLDR_MODEL=gemma4:26b-mlx .venv/bin/pytest -q -m ollama
```

---

## Key concepts

| Concept | Description |
|---------|-------------|
| **Scenario** | YAML file — goal text, budget caps, filesystem accesses, verification criteria, model settings |
| **Ticket** | Atomic unit of work. Has a goal, type, status, checks (command + model), and comments |
| **Cycle** | One execution pass over a ticket: Context Exploration → Changes → Command Verification → Model Verification |
| **Role** | A model specialisation — system prompt, toolset, and responsibility scope. Built-in: orchestration, developer, research, verification, security |
| **Queue** | Routes tickets to the roles responsible for them |
| **Budget** | Multi-scope resource accounting (tokens, money, wall-clock, commands, file edits, …) |
| **Score** | Tracks model performance per role and task type; switches models after repeated failures |
| **Knowledge Base** | Versioned, section-based shared context with per-role access control |
| **Audit Log** | Append-only JSONL stream; the single source of truth for the run |
| **Visibility** | Terminal stream or live web UI (WebSocket push + HTML) |

---

## Scenario YAML format

```yaml
name: <string>           # unique run name
goal: <string>           # free-text task description

budget:
  tokens: 50000          # total token budget  (aliases: token_budget)
  money: 1.0             # USD cap             (alias: cost_usd)
  wall_clock: 3600       # seconds cap

accesses:
  - path: ./src          # path relative to working directory
    mode: read_write     # read_only | read_write

verification:
  commands:              # shell commands that must exit 0
    - "pytest tests/"
  criteria:              # free-text human-readable success conditions
    - "All endpoints return 200"

model:
  provider: ollama       # ollama | stub | openai | anthropic
  name: gemma4:26b-mlx
  parameter_count: 26000000000   # optional
  cost_per_token: 0.0            # optional

constraints:             # optional free-text constraints passed to prompts
  - "Do not modify existing API contracts"
```

---

## Project layout

```
src/planfoldr/
├── audit.py            Level 0 — append-only event log
├── toolset.py          Level 0 — tool registry and access control
├── budget.py           Level 1 — multi-scope resource metering
├── score.py            Level 1 — model scoring and selection
├── knowledge_base.py   Level 1 — versioned shared context
├── ticket.py           Level 2 — ticket entity and lifecycle
├── role.py             Level 2 — role specialisations
├── graph.py            Level 3 — dependency graph
├── queue.py            Level 3 — work routing
├── birthgiver.py       Level 4 — dynamic role/queue creation
├── model.py            Level 5 — model abstraction + provider adapters
├── cycle.py            Level 5 — four-phase execution loop
├── visibility/         Level 6 — terminal and web observability
├── scenario.py         Level 7 — YAML scenario loader
├── orchestrator.py     Level 7 — runtime wiring and main loop
└── cli.py                       — CLI entry point
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for a detailed walkthrough of how these layers interact.
