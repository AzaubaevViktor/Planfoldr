# Visibility Interface — design contract

The Visibility interface is a first-class part of the system, not a debug afterthought. It has
**two audiences** and must serve both:

1. **A human** opens it and understands, without reading code: what happened, why it happened,
   what went wrong, where, and what the result was.
2. **The harness-improving agent** (me) reads a **structured analysis** next to it and understands
   what went wrong and what to change so the harness does better next time.

## Hard rules

- **No raw JSON dumps.** Forget dumping raw JSON at the human. Everything is rendered
  human-readable: labelled fields, tables, prose, readable numbers and durations.
- **No empty or meaningless rows.** If a value is unknown, say so in words — never show a blank
  line or a bare `exec_9f3a…` with no context.
- **Budgets are readable.** Not `{"exec_…": {...}}`. Show, per ticket (by title/goal) and for the
  whole project: tokens used / limit, model requests, files changed, commands run, GPU·RAM·hours,
  money — with units, and a clear "exceeded?" flag and why.
- **Scores are explained.** For every model: its score overall, per role, per task type, and the
  **reasons** each delta was applied (verified, budget saved, false verification, …) — in words.
- **Every object is fully inspectable.** Each ticket, cycle, role, queue, model, command and KB
  section has a page/panel showing *all* its information **and all relations it took part in during
  the run**. For a ticket: goal, status history, comments (with who/when/@summons), evidence,
  checks, dependencies, spawned children, owning cycle, model used. Nothing hidden.
- **Navigable.** It is a real navigable site. Many pages is fine. Cross-links everywhere
  (ticket ⇄ cycle ⇄ model ⇄ queue ⇄ commands ⇄ KB). The streaming log never loses its beginning.
- **Live.** The pages exist and update **during** execution, not only at the end.

## Pages

- **Streaming Log** (`index.html`) — header with scenario goal/description/status at the top, then
  the chronological run: each execution (cycle) is an expandable block showing its input/context/
  tools, the model's thinking → output, every tool call and its result. Nothing truncated.
- **State View** (`state.html`) — the live cross-section: system summary, queues, tickets, models
  & scores (explained), commands (who/when/cmd/exit), tools, cycles, cycle tree, budgets
  (human-readable). Each row links to the object's full page.
- **Tickets** (`tickets.html`) — the ticket tree (spawn + dependency structure) and every ticket in
  full (comments, status history, evidence, relations).
- **Knowledge Base** (`kb.html`) — every section the models wrote, its content and version history.
- **Run Analysis** (`analysis.md` / `analysis.html`) — the structured, machine-and-human readable
  post-run summary: did the scenario succeed; per-ticket outcome and why; where models failed
  (false verifications, repeated actions, budget stops, denied tools); token/§budget spend; and a
  concrete **"what to improve in the harness"** list derived from the run. This is the artifact the
  improving agent reads each iteration of the hardening loop.

## Why (analysis output)

The hardening loop is: run several tasks on local models → **read the Run Analysis** → form concrete
harness improvements → implement → escalate difficulty → repeat. So the analysis must surface the
failure signatures that matter: empty goals, model offered tools it can't use, action-protocol
errors, repeated/looping actions, command failures, budget soft-stops, false verifications, and
under-/over-spend — each tied to the ticket/cycle/model it happened in.
