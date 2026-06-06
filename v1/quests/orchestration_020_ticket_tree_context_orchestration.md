# Task orchestration_020: Ticket Tree Context Orchestration
File name: `orchestration_020_ticket_tree_context_orchestration.md`

## Status

Current status: in_progress
Blocked by: none
Description: Building persistent ticket-tree orchestration now that introspection, report view and model tool-call handling are in place.

## Goal

Redesign orchestration around a persistent ticket tree stored in context, where the top-level cycle plans work as tickets and nested cycles execute, verify or expand those tickets.

## Concept

The current runtime executes scenario tasks directly through cycle links. For larger work this should become more explicit: a top-level planning cycle owns a tree of tickets in context, and execution cycles work against individual ready tickets. Tickets can represent research, documentation, code changes, test writing, manual testing, verification or other work types.

The big cycle should be able to spawn nested cycles that either execute existing tickets or create new tickets through a separate ticket-creation cycle. The result is not just "run tasks in order", but "maintain a live work graph, decide what is ready, delegate work, attach evidence, and continue until the ticket tree is complete".

## Necessary Conditions

- Context stores a structured ticket tree for the current run.
- Each ticket has a stable id, title, description and type.
- Ticket types include at least:
  - research
  - documentation
  - code
  - tests
  - manual_testing
  - verification
  - orchestration
- Each ticket has dependencies that identify tickets or evidence required before it can run.
- Each ticket has an explicit status:
  - blocked
  - ready
  - running
  - needs_review
  - done
  - failed
  - cancelled
- Each running ticket stores who or what is currently doing it, including cycle id, task id, execution id and model/provider when relevant.
- Tickets can link to audit events and decision records created while working on them.
- Tickets can link to trace artifacts, model streams, command outputs, workspace files and verifier evidence.
- Tickets can require review before being marked done.
- Ticket completion requires verifier evidence or explicit human/system decision.
- The top-level cycle owns ticket-tree consistency and final completion.
- Nested execution cycles can update assigned tickets but cannot declare the entire tree complete.
- The top-level cycle can spawn nested cycles to execute ready tickets.
- The top-level cycle can spawn a separate nested cycle whose only job is to create or refine tickets.
- Nested cycles can request additional context, research or decisions before continuing.
- The runtime can recover current ticket state from persisted run files.
- HTML report can show the ticket tree, status, dependencies, owners and linked audit/decision/trace records.

## Constraints

- Keep the persisted ticket format deterministic and JSON-serializable.
- Do not hide ticket transitions inside model text; every transition must be explicit trace data.
- Do not let a model mark a ticket done without validation evidence unless the scenario explicitly allows it.
- Do not require a server for reading the final ticket tree.
- Keep ticket state scoped to the current run.
- Avoid coupling ticket types to Python classes until the schema proves stable.
- Preserve compatibility with existing scenario/cycle/task YAML where practical.

## Subtasks

- Define the ticket tree schema and status transition rules.
- Add context storage for ticket tree snapshots and incremental ticket events.
- Add runtime helpers for creating, updating, assigning and completing tickets.
- Add validation so dependencies determine blocked versus ready state.
- Add trace records for ticket transitions, audit links and decision links.
- Add a top-level orchestration cycle pattern that maintains the ticket tree.
- Add a nested execution cycle pattern that works one assigned ticket.
- Add a nested ticket-creation cycle pattern for expanding or refining the tree.
- Add verifier support for ticket completion evidence.
- Add budget accounting per ticket and per spawned cycle.
- Add report rendering for the ticket tree, dependency graph and current owners.
- Add tests for ticket status transitions and dependency readiness.
- Add tests for nested cycle ticket assignment and completion handoff.
- Add a larger e2e scenario that exercises ticket creation, execution, review and completion.
- Document how scenario authors describe ticket-driven flows in YAML.

## Outcome

The runtime can execute a scenario where the upper cycle maintains a persistent ticket tree, delegates ready tickets to nested cycles, accepts verified results back into the tree, optionally creates new tickets through a separate cycle and finishes only when the whole tree is verified complete.

## Verification

- Does context persist a structured ticket tree with stable ids, statuses and dependencies?
- Are ticket transitions explicit trace data rather than hidden in model text?
- Can nested cycles execute assigned tickets without declaring the whole tree complete?
- Does completion require verifier evidence or an explicit allowed decision?
- Can the HTML report show ticket state, dependencies, owners and linked evidence?

## Completion Audit

Checked: 2026-06-06.

### Necessary Conditions

- ✅ Context stores a structured ticket tree for the current run: `TicketTree` is JSON-serializable, but it is not yet wired into run context persistence.
- ✅ Each ticket has a stable id, title, description and type.
- ✅ Ticket types include at least research, documentation, code, tests, manual_testing, verification and orchestration.
- ✅ Each ticket has dependencies that identify tickets required before it can run.
- ✅ Each ticket has an explicit status, including blocked, ready, running, needs_review, done, failed and cancelled.
- ❌ Each running ticket stores full owner details including cycle id, task id, execution id and model/provider when relevant; owner data exists but only generic maps are covered.
- ❌ Tickets can link to audit events and decision records created while working on them.
- ✅ Tickets can link to trace artifacts, model streams, command outputs, workspace files and verifier evidence through generic `artifacts` and `evidence` fields.
- ✅ Tickets can require review before being marked done through the `needs_review` status.
- ✅ Ticket completion requires verifier evidence or an explicit human/system decision.
- ❌ The top-level cycle owns ticket-tree consistency and final completion.
- ❌ Nested execution cycles can update assigned tickets but cannot declare the entire tree complete.
- ❌ The top-level cycle can spawn nested cycles to execute ready tickets.
- ❌ The top-level cycle can spawn a separate nested cycle whose only job is to create or refine tickets.
- ❌ Nested cycles can request additional context, research or decisions before continuing as part of ticket orchestration.
- ❌ The runtime can recover current ticket state from persisted run files.
- ❌ HTML report can show the ticket tree, status, dependencies, owners and linked audit/decision/trace records.

### Constraints

- ✅ Keep the persisted ticket format deterministic and JSON-serializable.
- ❌ Do not hide ticket transitions inside model text; every transition must be explicit trace data.
- ✅ Do not let a model mark a ticket done without validation evidence unless the scenario explicitly allows it.
- ❌ Do not require a server for reading the final ticket tree; no final persisted tree/report view exists yet.
- ❌ Keep ticket state scoped to the current run; ticket helpers are not yet scoped by runtime.
- ✅ Avoid coupling ticket types to Python classes until the schema proves stable.
- ✅ Preserve compatibility with existing scenario/cycle/task YAML where practical.

### Subtasks

- ✅ Define the ticket tree schema and status transition rules.
- ❌ Add context storage for ticket tree snapshots and incremental ticket events.
- ✅ Add runtime helpers for creating, updating, assigning and completing tickets.
- ✅ Add validation so dependencies determine blocked versus ready state.
- ❌ Add trace records for ticket transitions, audit links and decision links.
- ❌ Add a top-level orchestration cycle pattern that maintains the ticket tree.
- ❌ Add a nested execution cycle pattern that works one assigned ticket.
- ❌ Add a nested ticket-creation cycle pattern for expanding or refining the tree.
- ✅ Add verifier support for ticket completion evidence.
- ❌ Add budget accounting per ticket and per spawned cycle.
- ❌ Add report rendering for the ticket tree, dependency graph and current owners.
- ✅ Add tests for ticket status transitions and dependency readiness.
- ❌ Add tests for nested cycle ticket assignment and completion handoff.
- ❌ Add a larger e2e scenario that exercises ticket creation, execution, review and completion.
- ❌ Document how scenario authors describe ticket-driven flows in YAML.

### Outcome And Verification

- ❌ Outcome is not complete: the runtime cannot yet execute a ticket-tree-driven scenario end to end.
- ✅ Context ticket schema has stable ids, statuses and dependencies at the helper level.
- ❌ Ticket transitions are not yet explicit trace data.
- ❌ Nested cycles cannot yet execute assigned tickets through ticket orchestration.
- ✅ Completion helper requires verifier evidence or an explicit decision.
- ❌ HTML report cannot yet show ticket state, dependencies, owners and linked evidence.

## Implementation Notes

- Queue after the introspection/report layer and model tool-call syntax, because ticket-tree orchestration will create more nested state to inspect.
- Added initial deterministic ticket-tree schema helpers with JSON roundtrip, dependency readiness and status transition tests.
- Added ticket assignment and completion helpers; completion now requires verifier evidence or an explicit decision.
