# Planfoldr — Architecture

## Overview

Planfoldr is built around a single central abstraction: the **Cycle**. A cycle is one execution pass over one ticket. Cycles can spawn new tickets; those tickets are queued, picked up by roles, and run as new cycles. The result is a self-expanding ticket graph that terminates when all tickets are done (or a budget is exceeded).

Everything is deterministic and observable: every state transition, tool call, model response, and budget event is written to an append-only audit log, and the live state is streamed to the terminal or a browser.

---

## Dependency levels

The codebase is organised in strict bottom-up layers. A module at level N may only import from levels below N.

```
Level 0   Audit, Toolset
Level 1   Knowledge Base, Budget, Score System
Level 2   Ticket, Role
Level 3   Ticket Graph, Queue
Level 4   Queue Manager, Executor, Birthgiver
Level 5   Model, Cycle
Level 6   Visibility
Level 7   Scenario, Orchestrator
           └── CLI
```

---

## Layer-by-layer description

### Level 0 — Foundation

**`audit.py`** — `AuditLog` is an append-only JSONL file on disk. Every component emits `AuditEvent` records; nothing reads from the log at runtime. The log is the single source of truth for post-run analysis and the visibility layer.

**`toolset.py`** — `ToolRegistry` holds all known tools. Each tool has a name, scope (`BASE` / `DOMAIN` / `META`), description, and a handler function. `Toolset` is a role-scoped view of the registry: it enforces that a role can only invoke tools it was granted. `BASE_TOOLS` (read/write context, create/update ticket, comment, request decision) are available to every executor role. `META_TOOLS` (create_role) are birthgiver-only.

---

### Level 1 — Resource management

**`budget.py`** — `Budget` tracks 13 metrics (tokens, money, wall-clock seconds, commands run, files edited, GPU-RAM-hours, …) across four nested scopes: project → queue → ticket → cycle. `consume()` records usage at all scopes; `is_exceeded()` checks caps. The orchestrator soft-stops a cycle that breaches its budget.

**`score.py`** — `ScoreSystem` maintains per-model scores on three axes: global, per-role, and per-task-type. After each cycle it applies penalties (failure, budget breach) or bonuses (success, fast completion). If the same model fails twice in a row on the same task type, `best_model_for()` switches to the next candidate.

**`knowledge_base.py`** — `KnowledgeBase` is a versioned, section-based shared context. Each `KBSection` has an owner role and an ACL. Roles can read any section they are granted; only the owner can write. The orchestrator initialises sections for each built-in role and passes them to cycles.

---

### Level 2 — Core entities

**`ticket.py`** — `Ticket` is the unit of work. It carries an immutable goal, a type (feature / bug / research / …), a lifecycle `Status`, a list of `Check` records (each check is either a shell command or a model-assessed criterion), and `Comment` threads (supporting @role summoning). `transition()` validates legal state changes; `is_ready()` checks that all blocking tickets are resolved.

Status flow:
```
incoming
  ├─→ blocked   (has unresolved dependencies)
  └─→ ready     (all deps clear)
        └─→ running
              ├─→ done
              ├─→ failed
              └─→ needs_review
                    └─→ done | failed
```

**`role.py`** — `Role` bundles a system prompt, a `Toolset`, and a responsibility description. `QueueManager(Role)` is responsible for triage (accept / decline) of incoming tickets. `Executor(Role)` pulls ready tickets and runs cycles. Both are immutable after construction.

---

### Level 3 — Routing and dependencies

**`graph.py`** — `TicketGraph` is an append-only directed graph of `Link` records. Link types: `spawned_by`, `blocks` / `blocked_by`, `related_to`, `evidence_for`, `escalates`. `is_ready(ticket)` walks the graph to confirm no blocking ticket is still open. Cycles are rejected at insertion time.

**`queue.py`** — `Queue` groups tickets by direction and role. It does not execute anything — it only stages work. `add()` puts a ticket in the incoming bucket; `accept()` moves it to ready; `decline()` sends it back; `reserve()` claims a ready ticket for an executor.

---

### Level 4 — Dynamic role creation

**`birthgiver.py`** — `Birthgiver` is the meta-role that extends the role system at runtime. When the orchestrator receives a `create_role` tool call it delegates to `Birthgiver.handle_create_role()`, which either links the request to an existing role, refuses it, or instantiates a new `Role` + `Queue` pair and registers them in `RoleRegistry` / `QueueRegistry`.

`Human` is a thin wrapper that forwards `request_decision` and `request_context` calls to stdout/stdin, allowing a human operator to answer questions the model asks mid-run.

---

### Level 5 — Execution

**`model.py`** — `ModelAdapter` is the abstract base. Concrete implementations: `OllamaModel` (streaming, token counting), and a `StubModel` used in tests (returns scripted `Action` objects). An `Action` is the parsed output of one model turn: `{action, args, thinking}`. `ModelConfig` carries provider, name, parameter count, cost-per-token, and context limits.

**`cycle.py`** — `Cycle` is the workhorse. One cycle runs four phases in order:

| Phase | What happens |
|-------|-------------|
| **CONTEXT_EXPLORATION** | Model reads the ticket, KB sections, and relevant files to build a working context |
| **CHANGES** | Model drives a JSON-action loop: it emits `Action` objects, each dispatched to a tool handler via `tools_impl.py`. Loop ends when the model emits `done` or the cycle budget is exhausted |
| **COMMAND_VERIFICATION** | Each `Check` with a shell command is executed; exit code is recorded as evidence |
| **MODEL_VERIFICATION** | Model assesses each non-command `Check` criterion against the evidence gathered so far |

`CycleResult` carries: outcome (success/failure/budget_exceeded), spawned tickets, budget consumed, evidence records.

---

### Level 6 — Observability

The visibility layer is entirely read-only at the data level — it consumes audit events but never modifies state.

**`visibility/events.py`** — `VisibilityState` reconstructs the live system state by replaying audit events: active queues, ticket statuses, model selections, cycle progress.

**`visibility/terminal.py`** — `TerminalStream` writes coloured, timestamped lines to stdout as events arrive.

**`visibility/web.py`** — `VisibilityServer` runs an embedded HTTP + WebSocket server. It serves four HTML views (stream log, state, tickets, knowledge base, run analysis) and a JSON API. After the run it writes a self-contained `report.html` to the run directory.

**`visibility/ws.py`** — WebSocket handler that pushes JSON event payloads to all connected browser clients in real time.

**`visibility/analysis.py`** — `build_analysis()` produces a structured post-run summary: success/failure per ticket, failure signatures, suggested harness improvements.

---

### Level 7 — Entry points

**`scenario.py`** — `Scenario` is the immutable task definition loaded from YAML. `load_scenario()` parses budget aliases (`tokens` → `tokens_used`, `money` → `cost_usd`), validates accesses, and returns a `Scenario` object.

**`orchestrator.py`** — `Orchestrator` wires all entities and runs the main loop:

```
for each cycle slot (up to max_cycles):
    1. find the highest-priority ready ticket across all queues
    2. select the best model via ScoreSystem
    3. instantiate and run a Cycle
    4. on cycle completion:
       - record budget usage
       - record score delta
       - emit audit events
       - enqueue spawned tickets
       - resolve dependency graph
    5. stop if no work remains or any hard budget is exceeded
```

Built-in roles and their queues:

| Role | Responsibility |
|------|---------------|
| `orchestration` | Triage and route incoming tickets |
| `developer` | Implement code changes |
| `research` | Information gathering, analysis |
| `verification` | Check correctness and acceptance criteria |
| `security` | Security-related tasks |

**`cli.py`** — `argparse` wrapper around `cmd_run()`. Loads the scenario, starts the visibility server if requested, calls `Orchestrator.run()`, prints the JSON result, and optionally holds the web server open.

---

## Data flow for a single run

```
cli.py
  └─ load_scenario()
  └─ Orchestrator(scenario)
        ├─ AuditLog(run_dir/audit.jsonl)
        ├─ Budget(scenario.budget)
        ├─ ScoreSystem()
        ├─ KnowledgeBase(sections)
        ├─ TicketGraph()
        ├─ RoleRegistry + QueueRegistry
        ├─ VisibilityServer | TerminalStream
        │
        └─ run():
             seed ticket ← scenario.goal
             loop:
               ticket  ← queue.reserve()
               model   ← score.best_model_for(role, ticket.type)
               cycle   ← Cycle(ticket, role, model, budget, graph, kb, tools, audit)
               result  ← cycle.run()
               budget.consume(result.budget_used)
               score.record(model, result.outcome)
               graph.link(result.spawned_tickets)
               queue.add(result.spawned_tickets)
               audit.emit(CYCLE_COMPLETED, ...)
             return RunResult
```

---

## Artifact layout (one run)

```
runs/<run-id>/
├── audit.jsonl     append-only event stream
├── result.json     final status, ticket summary, tokens used
├── kb.json         knowledge base snapshot at run end
└── report.html     self-contained HTML report
```

---

## Testing strategy

Tests are co-located with the module hierarchy and mirror the dependency levels:

- Levels 0–3: pure unit tests with no I/O
- Level 4–5: use `StubModel` to avoid requiring a running Ollama instance
- Level 7: `test_e2e_stub.py` runs a full `Orchestrator` end-to-end with the stub model
- `@pytest.mark.ollama`: optional live Ollama tests, gated by `PLANFOLDR_OLLAMA_E2E=1`
