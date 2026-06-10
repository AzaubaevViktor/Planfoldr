"""Run Analysis (interface.md "Run Analysis").

Turns a run snapshot into a structured, human- and agent-readable summary: did the scenario
succeed, per-ticket outcomes and why, the failure signatures that matter for hardening the harness
(empty goals, denied tools, protocol errors, repeated/looping actions, command failures, budget
soft-stops, false verifications), budget spend, model scores -- and a concrete list of harness
improvements derived from the run. This is the artifact the improving agent reads each loop.
"""

from __future__ import annotations

import html
from collections import Counter
from typing import Any, Dict, List, Tuple

from planfoldr.model import parse_action


def build_analysis(snapshot: Dict[str, Any]) -> Tuple[str, str]:
    sections = _sections(snapshot)
    return _to_markdown(sections), _to_html(snapshot, sections)


def _sections(snap: Dict[str, Any]) -> List[Tuple[str, List[str]]]:
    tickets = snap.get("tickets", {})
    log = snap.get("log", [])
    audits = [e for e in log if e.get("type") == "audit"]
    outputs = [e for e in log if e.get("type") == "model_output"]

    # -- summary --
    sc = snap.get("scenario", {})
    project = snap.get("budgets", {}).get("project", {})
    tokens = project.get("usage", {}).get("tokens_used")
    summary = [
        f"Scenario: {sc.get('name')}",
        f"Goal: {sc.get('goal')}",
        f"Status: {snap.get('status')}",
        f"Cycles run: {snap.get('cycles_run')}",
        f"Tokens used (project): {tokens}",
    ]

    # -- per-ticket outcome --
    ticket_lines = []
    for tid, t in tickets.items():
        ev = t.get("evidence", [])
        fails = sum(1 for e in ev if e.get("status") == "failure")
        passes = sum(1 for e in ev if e.get("status") == "success")
        ticket_lines.append(
            f"{tid} [{t.get('type')}] → {t.get('status')} "
            f"(attempts {t.get('attempt_count')}/{t.get('max_attempts')}, checks ✓{passes}/✗{fails})"
            + ("  ⚠ EMPTY GOAL" if not t.get("goal") and t.get("type") != "orchestration" else "")
        )

    # -- failure signatures --
    signatures: List[str] = []
    empty_goals = [tid for tid, t in tickets.items() if not t.get("goal") and t.get("type") != "orchestration"]
    if empty_goals:
        signatures.append(f"Empty goals on tickets {empty_goals} — create_ticket did not capture a goal.")

    denied = [e for e in audits if e.get("event_type") == "tool.denied"]
    if denied:
        tools = Counter(e.get("payload", {}).get("tool") for e in denied)
        signatures.append(f"Denied tool calls: {dict(tools)} — a role tried tools outside its toolset.")

    protocol_errors = [o for o in outputs if parse_action(o.get("content", "")).error]
    if protocol_errors:
        signatures.append(f"{len(protocol_errors)} model replies did not conform to the action protocol.")

    # repeated identical tool calls within a cycle
    per_cycle: Dict[str, List[str]] = {}
    for e in audits:
        if e.get("event_type") == "tool.invoked":
            sig = f"{e.get('payload', {}).get('tool')}:{e.get('payload', {}).get('args')}"
            per_cycle.setdefault(e.get("cycle_id"), []).append(sig)
    loops = {cid: _max_run(seq) for cid, seq in per_cycle.items() if _max_run(seq) >= 3}
    if loops:
        signatures.append(f"Repeated identical actions (possible loops) in cycles {loops}.")

    cmd_fail = [c for c in snap.get("commands", []) if c.get("exit_code") not in (0, None)]
    if cmd_fail:
        signatures.append(f"{len(cmd_fail)} command(s) failed (non-zero exit): "
                          f"{[c.get('cmd') for c in cmd_fail][:5]}.")

    budget_hits = [e for e in audits if e.get("event_type") == "budget.exceeded"]
    if budget_hits:
        res = Counter(e.get("payload", {}).get("resource") for e in budget_hits)
        signatures.append(f"Budget soft-stops on {dict(res)}.")

    false_ver = [e for e in audits if e.get("event_type") == "model.score_updated"
                 and "false_verification" in e.get("payload", {}).get("reasons", [])]
    if false_ver:
        signatures.append(f"{len(false_ver)} false verification(s): a model claimed pass without passing evidence.")

    # False-negative model verification: ticket failed even though all command checks passed.
    false_neg = [
        tid for tid, t in tickets.items()
        if t.get("status") == "failed"
        and any(e.get("status") == "success" for e in t.get("evidence", []))
        and not any(e.get("status") == "failure" for e in t.get("evidence", []))
        and t.get("attempt_count", 0) >= t.get("max_attempts", 3)
    ]
    if false_neg:
        signatures.append(
            f"False-negative model verification on {false_neg}: all command checks passed but "
            "the model said 'not satisfied' every attempt, exhausting retries."
        )

    if not signatures:
        signatures.append("No failure signatures detected — clean run.")

    # -- budget --
    budget_lines = [f"Project: tokens {project.get('usage', {}).get('tokens_used')} / "
                    f"limit {project.get('limits', {}).get('tokens_used', '∞')}, exceeded={project.get('exceeded')}"]
    for b in snap.get("budgets", {}).get("tickets", []):
        u = b.get("usage", {})
        budget_lines.append(
            f"{b.get('ticket')} ({b.get('title')}): tokens {u.get('tokens_used')}, "
            f"requests {u.get('api_requests')}, files {u.get('file_changes')}, "
            f"commands {u.get('command_runs')}, gpu·ram·h {round(u.get('gpu_ram_hours', 0), 4)}"
        )

    # -- scores --
    score_lines = []
    reason_counts: Counter = Counter()
    for e in audits:
        if e.get("event_type") == "model.score_updated":
            reason_counts.update(e.get("payload", {}).get("reasons", []))
    for mid, s in snap.get("scores", {}).items():
        score_lines.append(f"{mid}: global {round(s.get('global_score', 0), 2)} over {s.get('tickets')} ticket(s); "
                           f"by role {s.get('by_role')}; by task {s.get('by_task_type')}")
    if reason_counts:
        score_lines.append(f"Score reasons across the run: {dict(reason_counts)}")

    # -- improvement suggestions --
    suggestions: List[str] = []
    if empty_goals:
        suggestions.append("Ensure create_ticket always records a concrete goal (accept aliases; reject empty goals).")
    if denied:
        suggestions.append("Only offer the model actions its role's toolset permits (or grant the missing tool).")
    if protocol_errors:
        suggestions.append("Tighten the action-protocol prompt / add a stricter reformat retry.")
    if loops:
        suggestions.append("Strengthen anti-loop handling and give clearer next-step guidance after read-only actions.")
    bash_uses = snap.get("tools", {}).get("bash", 0)
    if bash_uses and bash_uses >= 3:
        suggestions.append(f"Minimize bash ({bash_uses} uses): steer file creation to file_edit; reserve bash for tests.")
    if cmd_fail:
        suggestions.append("Investigate failing verification commands (workspace paths / missing files).")
    if budget_hits:
        suggestions.append("Right-size budgets or reduce model calls per ticket to avoid soft-stops.")
    if false_ver:
        suggestions.append("Harden the model-verification gate so a pass requires real command evidence.")
    if false_neg:
        suggestions.append(
            "Model over-rejected passing work. Strengthen the model_verification prompt to trust "
            "exit=0 command evidence; show stdout explicitly in the proof so the model sees the output."
        )
    if not suggestions:
        suggestions.append("Nothing actionable — keep escalating task difficulty.")

    return [
        ("Summary", summary),
        ("Ticket outcomes", ticket_lines),
        ("What went wrong (failure signatures)", signatures),
        ("Budget", budget_lines),
        ("Model scores", score_lines),
        ("Harness improvement suggestions", suggestions),
    ]


def _max_run(seq: List[str]) -> int:
    best = run = 0
    prev = None
    for x in seq:
        run = run + 1 if x == prev else 1
        prev = x
        best = max(best, run)
    return best


def _to_markdown(sections: List[Tuple[str, List[str]]]) -> str:
    out = ["# Run Analysis", ""]
    for title, lines in sections:
        out.append(f"## {title}")
        out.extend(f"- {line}" for line in lines)
        out.append("")
    return "\n".join(out)


def _to_html(snap: Dict[str, Any], sections: List[Tuple[str, List[str]]]) -> str:
    blocks = ""
    for title, lines in sections:
        items = "".join(f"<li>{html.escape(str(line))}</li>" for line in lines)
        blocks += f"<section><h2>{html.escape(title)}</h2><ul>{items}</ul></section>"
    nav = ('<nav><a href="index.html">Streaming Log</a> · <a href="state.html">State</a> · '
           '<a href="tickets.html">Tickets</a> · <a href="kb.html">Knowledge Base</a> · '
           '<a href="analysis.html">Analysis</a></nav>')
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Run Analysis</title>
<meta http-equiv="refresh" content="2">
<style>body{{background:#0b0e14;color:#cdd6f4;font:13px/1.6 ui-monospace,Menlo,monospace;padding:16px}}
h1{{font-size:18px}} h2{{font-size:14px;color:#89b4fa}} section{{border:1px solid #313244;border-radius:8px;margin:10px 0;padding:8px}}
nav a{{color:#89b4fa;margin-right:6px}} li{{margin:2px 0}}</style></head>
<body>{nav}<h1>Run Analysis — {html.escape(str(snap.get('scenario', {}).get('name')))} ({html.escape(str(snap.get('status')))})</h1>{blocks}</body></html>"""
