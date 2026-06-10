"""Visibility web layer (level 6): four server-rendered HTML pages + a JSON API + WebSocket.

Pages (all link to each other, all auto-refresh so they update live during a run, and all work as
static files with no server -- "Не требует сервера для чтения"):
- `/`            Streaming Log: goal/description header, then thinking → output → tool calls →
                 results, each execution an expandable details/summary block.
- `/state`       State View: queues / tickets / models / commands / tools / cycles / cycle tree /
                 system / budgets, human-readable.
- `/tickets`     Ticket tree + every ticket in full: goal, status history, comments, evidence, deps.
- `/kb`          Knowledge Base: every section the models wrote, with version history.

Pages are rendered server-side from a snapshot dict (built by the orchestrator from live objects),
so the data is present in the HTML itself -- robust and inspectable.
"""

from __future__ import annotations

import html
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from planfoldr.visibility.events import SLICES, VisibilityState
from planfoldr.visibility.ws import WebSocketServer

REFRESH_SECONDS = 2
TERMINAL_STATUSES = {"done", "failed", "budget_exceeded", "error"}


def _refresh_meta(snap: Any) -> str:
    """Auto-refresh tag only while the run is live. Once the run reaches a terminal state the page
    is static and can never change, so a periodic reload would do nothing but re-render every
    <details> at its default state and collapse whatever the reader had expanded."""
    status = snap.get("status") if isinstance(snap, dict) else None
    if status in TERMINAL_STATUSES:
        return ""
    return f'<meta http-equiv="refresh" content="{REFRESH_SECONDS}" id="refresh-meta">'


def _norm(embedded: Any) -> Tuple[dict, list]:
    if embedded is None:
        return {}, []
    if isinstance(embedded, tuple):
        snap, log = embedded
        return snap or {}, log or []
    return embedded, embedded.get("log", [])


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


# --------------------------------------------------------------------------- #
# Value formatting helpers — no raw JSON dumps anywhere
# --------------------------------------------------------------------------- #
def _fmt_value(v: Any) -> str:
    """Render any value human-readably: dict → labelled pairs, list → items, else plain str."""
    if v is None:
        return "<i>—</i>"
    if isinstance(v, dict):
        if not v:
            return "<i>—</i>"
        return "<br>".join(f"<b>{esc(k)}</b>: {esc(str(vv))}" for k, vv in v.items())
    if isinstance(v, list):
        if not v:
            return "<i>—</i>"
        return ", ".join(esc(str(i)) for i in v)
    return esc(str(v))


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds // 60)}m {int(seconds % 60)}s"


def _fmt_tokens(n: Any) -> str:
    if n is None:
        return "—"
    n = int(n)
    return f"{n:,}"


def _table(rows: List[Dict[str, Any]], columns: Optional[List[str]] = None) -> str:
    if not rows:
        return "<i>none</i>"
    columns = columns or list({k for r in rows for k in r.keys()})
    head = "".join(f"<th>{esc(c)}</th>" for c in columns)
    body = ""
    for r in rows:
        cells = "".join(f"<td>{_fmt_value(r.get(c))}</td>" for c in columns)
        body += f"<tr>{cells}</tr>"
    return f"<table><tr>{head}</tr>{body}</table>"


# --------------------------------------------------------------------------- #
# Tool-call rendering helpers (no JSON dumps)
# --------------------------------------------------------------------------- #
_PHASE_ICONS: Dict[str, str] = {
    "context_exploration": "📋",
    "changes": "✏️",
    "command_verification": "🧪",
    "model_verification": "⚖️",
}


def _rc_badge(rc: Any) -> str:
    ok = rc == 0 or str(rc) == "0"
    cls = "rc-ok" if ok else "rc-err"
    return f'<span class="{cls}">exit {esc(rc)}</span>'


def _tool_html(payload: Dict[str, Any]) -> str:
    """Render a tool.invoked event as a human-readable block, no raw JSON."""
    tool = payload.get("tool", "?")
    args = payload.get("args") or {}
    result = payload.get("result") or {}

    if tool == "bash":
        cmd = args.get("cmd", "")
        rc = result.get("exit_code", "?")
        stdout = (result.get("stdout") or "").strip()
        stderr = (result.get("stderr") or "").strip()
        cmd_short = (cmd[:90] + "…") if len(cmd) > 90 else cmd
        summary = f'🔧 bash {_rc_badge(rc)} <code class="cmd-inline">{esc(cmd_short)}</code>'
        body = f'<pre class="cmd-full">{esc(cmd)}</pre>'
        if stdout:
            body += f'<div class="out-label">stdout</div><pre class="pre-out">{esc(stdout)}</pre>'
        if stderr:
            body += f'<div class="out-label err-label">stderr</div><pre class="pre-err">{esc(stderr)}</pre>'
        return f'<details class="tool"><summary>{summary}</summary>{body}</details>'

    if tool == "file_edit":
        path = args.get("path") or result.get("path") or "?"
        action = result.get("action", "?")
        added = result.get("lines_added", 0)
        removed = result.get("lines_removed", 0)
        err = result.get("error")
        if err:
            return f'<div class="tool-line err-line">🔧 file_edit <b>{esc(path)}</b> → <span class="rc-err">{esc(err)}</span></div>'
        content = args.get("content", "")
        diff = f'<span class="diff-add">+{added}</span> <span class="diff-del">−{removed}</span>'
        summary = f'🔧 file_edit <b>{esc(path)}</b> → {esc(action)} {diff}'
        body = f'<pre class="pre-file">{esc(content)}</pre>' if content else ""
        return f'<details class="tool"><summary>{summary}</summary>{body}</details>'

    if tool == "command_verification":
        cmd = args.get("cmd") or args.get("spec") or "?"
        rc = result.get("exit_code", "?")
        status = result.get("status", "?")
        stdout = (result.get("stdout") or "").strip()
        stderr = (result.get("stderr") or "").strip()
        cmd_short = (cmd[:100] + "…") if len(cmd) > 100 else cmd
        summary = f'🧪 {_rc_badge(rc)} <code class="cmd-inline">{esc(cmd_short)}</code>'
        body = ""
        if cmd != cmd_short:
            body += f'<pre class="cmd-full">{esc(cmd)}</pre>'
        if stdout:
            body += f'<div class="out-label">stdout</div><pre class="pre-out">{esc(stdout)}</pre>'
        if stderr:
            body += f'<div class="out-label err-label">stderr</div><pre class="pre-err">{esc(stderr)}</pre>'
        if body:
            return f'<details class="tool"><summary>{summary}</summary>{body}</details>'
        return f'<div class="tool-line">{summary}</div>'

    if tool == "create_ticket":
        err = result.get("error")
        if err:
            return f'<div class="tool-line err-line">🎫 create_ticket → <span class="rc-err">{esc(err)}</span></div>'
        tid = result.get("ticket_id") or result.get("id") or "?"
        ttype = args.get("type") or "?"
        goal = (args.get("goal") or "")[:150]
        summary = f'🎫 create_ticket → <b>{esc(tid)}</b> [{esc(ttype)}]'
        body = f'<div class="evt">{esc(goal)}</div>' if goal else ""
        return f'<details class="tool"><summary>{summary}</summary>{body}</details>'

    if tool in ("write_context", "read_context"):
        section = args.get("section") or result.get("section") or "?"
        version = result.get("version")
        icon = "📝" if tool == "write_context" else "📖"
        v_txt = f" v{version}" if version is not None else ""
        return f'<div class="tool-line">{icon} {esc(tool)} · <b>{esc(section)}</b>{v_txt}</div>'

    if tool == "update_ticket":
        tid = args.get("ticket_id") or "?"
        return f'<div class="tool-line">📋 update_ticket · <b>{esc(tid)}</b></div>'

    if tool == "comment":
        text = (args.get("text") or "")[:120]
        return f'<div class="tool-line">💬 comment: {esc(text)}</div>'

    if tool == "finish":
        return f'<div class="tool-line">✓ finish</div>'

    # Generic fallback: labelled fields, no json.dumps
    parts = []
    for k, v in args.items():
        parts.append(f'<b>{esc(k)}:</b> {esc(str(v)[:200])}')
    for k, v in result.items():
        parts.append(f'<b>→ {esc(k)}:</b> {esc(str(v)[:200])}')
    body = "<br>".join(parts)
    summary = f'🔧 {esc(tool)}'
    return f'<details class="tool"><summary>{summary}</summary><div class="evt">{body}</div></details>'


def _model_output_html(e: Dict[str, Any]) -> str:
    """Render a model_output log entry: phase header + thinking + content + verdict."""
    model = e.get("model", "?")
    tokens = e.get("tokens", 0)
    thinking = (e.get("thinking") or "").strip()
    content = (e.get("content") or "").strip()
    phase = e.get("phase", "")

    phase_icon = _PHASE_ICONS.get(phase, "●")
    summary = (f'{phase_icon} <span class="phase-name">{esc(phase)}</span> · '
               f'<span class="model-badge">{esc(model)}</span> · '
               f'<span class="tok-count">{_fmt_tokens(tokens)} tok</span>')

    body = ""
    if thinking:
        body += f'<div class="thinking">💭 {esc(thinking)}</div>'
    if content:
        body += f'<pre class="model-content">{esc(content)}</pre>'

    # For model_verification: parse and display the verdict prominently
    if phase == "model_verification" and content:
        try:
            obj = json.loads(content)
            if obj.get("action") == "verify":
                passed = bool(obj.get("args", {}).get("passed", False))
                reason = obj.get("args", {}).get("reason", "")
                v_cls = "verdict-pass" if passed else "verdict-fail"
                v_icon = "✅" if passed else "❌"
                v_word = "PASSED" if passed else "FAILED"
                body += f'<div class="{v_cls}">{v_icon} <b>{v_word}</b>: {esc(reason)}</div>'
        except Exception:
            pass

    return f'<details class="model-call" open><summary>{summary}</summary>{body}</details>'


# --------------------------------------------------------------------------- #
# Streaming log renderer
# --------------------------------------------------------------------------- #
def _log_entry_html(e: Dict[str, Any]) -> str:
    """Render a single log entry. model_output events carry full model responses."""
    # Full model response (assembled from stream; never truncated)
    if e.get("type") == "model_output":
        return _model_output_html(e)

    if e.get("type") == "audit":
        et = e.get("event_type", "")
        p = e.get("payload", {})

        if et == "cycle.started":
            model = p.get("model", "?")
            role = p.get("role", "?")
            ttype = p.get("type", "?")
            tid = e.get("ticket_id", "?")
            summary = (f'▶ <span class="cyc-id">{esc(e.get("cycle_id", "")[:14])}</span> · '
                       f'ticket <b>{esc(tid)}</b> [{esc(ttype)}] · '
                       f'<span class="model-badge">{esc(model)}</span> · '
                       f'<span class="role-badge">{esc(role)}</span>')
            return f'<details open class="cyc"><summary>{summary}</summary>'

        if et == "cycle.completed":
            status = p.get("status", "?")
            b = p.get("budget", {})
            tokens = int(b.get("tokens_used", 0))
            files = int(b.get("file_changes", 0))
            cmds = int(b.get("command_runs", 0))
            spawned = p.get("spawned", [])
            sp_txt = f' · spawned: {esc(", ".join(spawned))}' if spawned else ""
            return (f'<div class="cycle-footer status-{esc(status)}">■ {esc(status)} · '
                    f'{_fmt_tokens(tokens)} tokens · {files} file changes · {cmds} cmd runs{sp_txt}</div>'
                    f'</details>')

        if et == "cycle.phase_completed":
            # Phase separators are rendered inline by model_output; nothing extra needed here
            return ""

        if et == "tool.invoked":
            return _tool_html(p)

        if et == "ticket.status_changed":
            status = p.get("to", "")
            return (f'<div class="evt small">~ {esc(e.get("ticket_id"))} '
                    f'{esc(p.get("from"))} → <span class="status-{esc(status)}">{esc(status)}</span></div>')

        if et == "ticket.created":
            tid = e.get("ticket_id", "?")
            ttype = p.get("type", "?")
            goal = (p.get("goal") or "")[:100]
            return f'<div class="evt small">+ ticket <b>{esc(tid)}</b> [{esc(ttype)}] {esc(goal)}</div>'

        if et == "model.score_updated":
            model = p.get("model", "?")
            delta = p.get("delta", 0)
            gs = round(p.get("global_score", 0), 3)
            reasons = ", ".join(p.get("reasons", []))
            d_cls = "score-pos" if delta >= 0 else "score-neg"
            return (f'<div class="evt small">· score '
                    f'<b>{esc(model)}</b> <span class="{d_cls}">{delta:+.1f}</span> '
                    f'→ {gs} ({esc(reasons)})</div>')

        if et == "model.selected":
            model = p.get("model", "?")
            ranking = p.get("ranking", {})
            ranked = sorted(ranking.items(), key=lambda x: x[1], reverse=True)
            rank_txt = " · ".join(f"{esc(m)}: {round(s, 2)}" for m, s in ranked)
            return (f'<div class="evt small">▷ selected <b>{esc(model)}</b> '
                    f'for {esc(p.get("role"))} · [{rank_txt}]</div>')

        # Skip low-value infrastructure events
        if et in ("queue.created", "budget.delegated", "kb.written",
                  "graph.link_added", "scenario.started", "budget.exceeded"):
            return ""

        if et == "scenario.completed":
            status = p.get("status", "?")
            reason = p.get("reason", "")
            cls = "verdict-pass" if status == "done" else "verdict-fail"
            return f'<div class="{cls}"><b>SCENARIO {esc(status.upper())}</b>: {esc(reason)}</div>'

        return ""

    # Live streaming chunks — only present during WS live view, not in static HTML
    if e.get("type") == "model_stream_chunk":
        cls = "thinking" if e.get("kind") == "thinking" else "content"
        return f'<span class="evt {cls}">{esc(e.get("text"))}</span>'

    return ""


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
def render_stream_log_html(embedded: Any = None, ws_port: Optional[int] = None) -> str:
    snap, log = _norm(embedded)
    sc = snap.get("scenario", {})
    status = snap.get("status", "running")
    header = (
        f'<header><h1>{esc(sc.get("name", "Planfoldr run"))}</h1>'
        f'<div class="goal"><b>Goal:</b> {esc(sc.get("goal"))}</div>'
        f'<div class="goal"><b>Status:</b> <span class="status-{esc(status)}">{esc(status)}</span></div>'
        + (f'<div class="goal"><b>Constraints:</b> {esc(", ".join(sc.get("constraints", [])))}</div>' if sc.get("constraints") else "")
        + (f'<div class="goal"><b>Verification:</b> {esc(", ".join(sc.get("verification_commands", [])))}</div>' if sc.get("verification_commands") else "")
        + "</header>"
    )
    entries = "".join(_log_entry_html(e) for e in log)
    body = f'{header}<h2>Streaming Log <button id="rf-btn" class="rf-btn" onclick="toggleRefresh()">⏸ pause refresh</button></h2><div id="log">{entries}</div>'
    return _PAGE.format(title="Planfoldr — Streaming Log", refresh_meta=_refresh_meta(snap), nav=_NAV, body=body,
                        snapshot=json.dumps(snap, default=str), ws_port=ws_port or 0, preserve=_PRESERVE_SCRIPT, script=_WS_SCRIPT)


def render_state_view_html(embedded: Any = None, ws_port: Optional[int] = None) -> str:
    snap, _ = _norm(embedded)
    content = {
        "system": _render_system(snap),
        "queues": _table([{"id": q.get("id"), "tickets": _fmt_value(q.get("tickets_by_status", {})),
                           "manager": q.get("manager_role"), "executors": _fmt_value(q.get("executor_roles"))}
                          for q in snap.get("queues", {}).values()]),
        "tickets": _table([{"id": t.get("id"), "type": t.get("type"), "status": t.get("status"),
                            "role": t.get("role"), "attempts": t.get("attempt_count"),
                            "goal": (t.get("goal") or "")[:60]} for t in snap.get("tickets", {}).values()]),
        "models": _render_models(snap),
        "commands": _render_commands(snap),
        "tools": _table([{"tool": k, "count": v} for k, v in (snap.get("tools", {}) or {}).items()]),
        "cycles": _table([{"id": c.get("id"), "ticket": c.get("ticket"), "model": c.get("model"),
                          "role": c.get("role"), "phase": c.get("phase"), "status": c.get("status")}
                         for c in snap.get("cycles", {}).values()]),
        "cycle_tree": _render_tree(snap.get("cycle_tree", [])),
        "budgets": _render_budgets(snap),
    }
    sections = "\n".join(
        f'<section id="{s}"><details open><summary>{s.replace("_", " ").title()}</summary>'
        f'<div class="slice">{content.get(s, "")}</div></details></section>'
        for s in SLICES
    )
    body = (f'<h1>State View <button id="rf-btn" class="rf-btn" onclick="toggleRefresh()">⏸ pause refresh</button></h1>'
            f'<nav class="anchors">{" · ".join(f"<a href=#{s}>{s}</a>" for s in SLICES)}</nav>{sections}')
    return _PAGE.format(title="Planfoldr — State View", refresh_meta=_refresh_meta(snap), nav=_NAV, body=body,
                        snapshot=json.dumps(snap, default=str), ws_port=ws_port or 0, preserve=_PRESERVE_SCRIPT, script="")


def _render_system(snap: Dict[str, Any]) -> str:
    sc = snap.get("scenario", {})
    return (f'<b>Scenario:</b> {esc(sc.get("name"))}<br><b>Goal:</b> {esc(sc.get("goal"))}<br>'
            f'<b>Status:</b> <span class="status-{esc(snap.get("status"))}">{esc(snap.get("status"))}</span><br>'
            f'<b>Constraints:</b> {esc(", ".join(sc.get("constraints", [])))}<br>'
            f'<b>Cycles run:</b> {esc(snap.get("cycles_run"))}')


def _render_models(snap: Dict[str, Any]) -> str:
    scores = snap.get("scores") or {}
    if not scores:
        return "<i>No model activity yet.</i>"
    rows = []
    for mid, s in scores.items():
        by_role = s.get("by_role") or {}
        by_type = s.get("by_task_type") or {}
        fails = s.get("consecutive_fails") or {}
        rows.append({
            "model": mid,
            "base": round(s.get("base", 0), 2),
            "global score": round(s.get("global_score", 0), 3),
            "tickets": s.get("tickets") or 0,
            "by role": "<br>".join(f"{esc(r)}: {round(v,2)}" for r, v in sorted(by_role.items())),
            "by task type": "<br>".join(f"{esc(t)}: {round(v,2)}" for t, v in sorted(by_type.items())),
            "consec. fails": "<br>".join(f"{esc(t)}: {n}" for t, n in fails.items()) or "—",
        })
    rows.sort(key=lambda r: r["global score"], reverse=True)
    head = "".join(f"<th>{esc(c)}</th>" for c in ["model", "base", "global score", "tickets", "by role", "by task type", "consec. fails"])
    body_rows = ""
    for r in rows:
        gs = r["global score"]
        gs_cls = "score-pos" if gs >= 0 else "score-neg"
        cells = (f'<td>{esc(r["model"])}</td>'
                 f'<td>{esc(r["base"])}</td>'
                 f'<td class="{gs_cls}">{esc(r["global score"])}</td>'
                 f'<td>{esc(r["tickets"])}</td>'
                 f'<td>{r["by role"]}</td>'
                 f'<td>{r["by task type"]}</td>'
                 f'<td>{r["consec. fails"]}</td>')
        body_rows += f"<tr>{cells}</tr>"
    return f"<table><tr>{head}</tr>{body_rows}</table>"


def _render_commands(snap: Dict[str, Any]) -> str:
    cmds = snap.get("commands", [])
    if not cmds:
        return "<i>none</i>"
    rows = []
    for c in cmds:
        cmd_raw = c.get("cmd")
        cmd_str = json.dumps(cmd_raw) if isinstance(cmd_raw, dict) else str(cmd_raw or "")
        rc = c.get("exit_code")
        rc_html = _rc_badge(rc) if rc is not None else "<i>—</i>"
        rows.append(f'<tr><td>{esc(str(c.get("when", ""))[:19])}</td>'
                    f'<td>{esc(c.get("actor"))}</td>'
                    f'<td>{esc(c.get("ticket"))}</td>'
                    f'<td><code>{esc(cmd_str[:120])}</code></td>'
                    f'<td>{rc_html}</td>'
                    f'<td>{esc(c.get("status"))}</td></tr>')
    head = "".join(f"<th>{esc(h)}</th>" for h in ["when", "actor", "ticket", "cmd", "exit", "status"])
    return f'<table><tr>{head}</tr>{"".join(rows)}</table>'


def _render_budgets(snap: Dict[str, Any]) -> str:
    budgets = snap.get("budgets", {})
    project = budgets.get("project", {})
    usage = project.get("usage", {})
    limits = project.get("limits", {})
    tok_used = _fmt_tokens(usage.get("tokens_used"))
    tok_lim = _fmt_tokens(limits.get("tokens_used")) if limits else "—"
    exceeded = project.get("exceeded")
    exc_html = f' <span class="rc-err">EXCEEDED: {esc(", ".join(exceeded))}</span>' if exceeded else ""
    proj_html = (f'<h4>Project</h4><div class="evt">'
                 f'tokens: {tok_used} / {tok_lim}'
                 f' · requests: {esc(usage.get("api_requests"))} · files: {esc(usage.get("file_changes"))}'
                 f' · commands: {esc(usage.get("command_runs"))} · gpu·ram·h: {round(usage.get("gpu_ram_hours", 0), 4)}'
                 f'{exc_html}</div>')
    rows = []
    for b in budgets.get("tickets", []):
        u = b.get("usage", {})
        lim = b.get("limits") or {}
        tok_u = _fmt_tokens(u.get("tokens_used"))
        tok_l = _fmt_tokens(lim.get("tokens_used")) if lim else "—"
        rows.append({
            "ticket": b.get("ticket"),
            "title": (b.get("title") or "")[:30],
            "goal": (b.get("goal") or "")[:50],
            "tokens": f"{tok_u} / {tok_l}",
            "requests": u.get("api_requests"),
            "files": u.get("file_changes"),
            "cmds": u.get("command_runs"),
            "gpu·ram·h": round(u.get("gpu_ram_hours", 0), 4),
            "exceeded": "yes" if b.get("exceeded") else "—",
        })
    return proj_html + _table(rows, ["ticket", "title", "goal", "tokens", "requests", "files", "cmds", "gpu·ram·h", "exceeded"])


def _render_tree(nodes: List[Dict[str, Any]]) -> str:
    if not nodes:
        return "<i>none</i>"
    items = "".join(
        f'<li>cycle {esc(n.get("id", "")[:14])} '
        f'[<span class="status-{esc(n.get("status"))}">{esc(n.get("status"))}</span>] '
        f'ticket={esc(n.get("ticket"))}'
        f'{_render_tree(n.get("children", []))}</li>' for n in nodes
    )
    return f"<ul>{items}</ul>"


def render_tickets_html(embedded: Any = None, ws_port: Optional[int] = None) -> str:
    snap, _ = _norm(embedded)
    tickets = snap.get("tickets", {})
    graph = snap.get("graph", {})
    tree = _ticket_tree(tickets, graph)
    detail = "".join(_ticket_detail_html(t) for t in tickets.values())
    body = (f'<h1>Tickets <button id="rf-btn" class="rf-btn" onclick="toggleRefresh()">⏸ pause refresh</button></h1>'
            f'<section id="ticket-tree"><h2>Structure</h2>{tree}</section>'
            f'<section id="ticket-details"><h2>Every ticket</h2>{detail}</section>')
    return _PAGE.format(title="Planfoldr — Tickets", refresh_meta=_refresh_meta(snap), nav=_NAV, body=body,
                        snapshot=json.dumps(snap, default=str), ws_port=ws_port or 0, preserve=_PRESERVE_SCRIPT, script="")


def _ticket_tree(tickets: Dict[str, Any], graph: Dict[str, Any]) -> str:
    children: Dict[Optional[str], List[str]] = {}
    for tid, t in tickets.items():
        children.setdefault(t.get("spawned_by"), []).append(tid)

    def build(tid: str) -> str:
        t = tickets.get(tid, {})
        kids = "".join(build(c) for c in children.get(tid, []))
        deps = t.get("dependencies", [])
        dep_txt = f' ⟵ blocked_by {esc(str(deps))}' if deps else ""
        return (f'<li><a href="#t_{esc(tid)}">{esc(tid)}</a> [{esc(t.get("type"))}] '
                f'<span class="status-{esc(t.get("status"))}">{esc(t.get("status"))}</span>{dep_txt}'
                f'{f"<ul>{kids}</ul>" if kids else ""}</li>')

    roots = children.get(None, []) + [tid for tid, t in tickets.items() if t.get("spawned_by") and t["spawned_by"] not in tickets]
    return f'<ul>{"".join(build(r) for r in dict.fromkeys(roots))}</ul>'


def _ticket_detail_html(t: Dict[str, Any]) -> str:
    history = t.get("metadata", {}).get("change_history", [])
    hist_rows = _table(history, ["from", "to", "actor", "at", "proof", "cause"])
    comments = t.get("comments", [])
    comm_rows = _table([{"author": c.get("author"), "when": c.get("timestamp"),
                         "summons": c.get("summoned_role"), "text": c.get("text")} for c in comments],
                       ["when", "author", "summons", "text"])
    evidence_rows = []
    for e in t.get("evidence", []):
        status = e.get("status", "?")
        proof = str(e.get("proof") or "")
        s_cls = "verdict-pass" if status == "success" else ("verdict-fail" if status == "failure" else "")
        evidence_rows.append(
            f'<tr><td>{esc(e.get("check_index"))}</td>'
            f'<td class="{s_cls}">{esc(status)}</td>'
            f'<td><pre class="pre-out">{esc(proof)}</pre></td></tr>'
        )
    evidence = (f'<table><tr><th>check</th><th>status</th><th>proof</th></tr>{"".join(evidence_rows)}</table>'
                if evidence_rows else "<i>none</i>")
    checks = _table([{"kind": c.get("kind"), "spec": c.get("spec"), "required": c.get("required")}
                     for c in t.get("checks", [])], ["kind", "spec", "required"])
    return (
        f'<details id="t_{esc(t.get("id"))}" class="ticket"><summary>{esc(t.get("id"))} '
        f'[{esc(t.get("type"))}] <span class="status-{esc(t.get("status"))}">{esc(t.get("status"))}</span> — {esc(t.get("title"))}</summary>'
        f'<div class="evt"><b>Goal:</b> {esc(t.get("goal"))}</div>'
        f'<div class="evt"><b>Role:</b> {esc(t.get("role"))} · <b>Queue:</b> {esc(t.get("queue"))} · '
        f'<b>Attempts:</b> {esc(t.get("attempt_count"))}/{esc(t.get("max_attempts"))} · '
        f'<b>spawned_by:</b> {esc(t.get("spawned_by"))} · <b>deps:</b> {esc(t.get("dependencies"))}</div>'
        f'<h4>Checks</h4>{checks}<h4>Evidence</h4>{evidence}'
        f'<h4>Comments</h4>{comm_rows}<h4>Status history</h4>{hist_rows}</details>'
    )


def render_kb_html(embedded: Any = None, ws_port: Optional[int] = None) -> str:
    snap, _ = _norm(embedded)
    kb = snap.get("kb", {})
    if not kb:
        sections = "<i>The knowledge base is empty.</i>"
    else:
        sections = ""
        for name, sec in kb.items():
            versions = _table([{"version": v.get("version"), "when": v.get("timestamp"), "role": v.get("role")}
                               for v in sec.get("versions", [])], ["version", "when", "role"])
            sections += (
                f'<details class="kb" open><summary>{esc(name)} '
                f'(read: {esc(sec.get("read_roles"))}, write: {esc(sec.get("write_roles"))})</summary>'
                f'<pre class="kbcontent">{esc(sec.get("content"))}</pre>'
                f'<h4>Versions</h4>{versions}</details>'
            )
    body = (f'<h1>Knowledge Base <button id="rf-btn" class="rf-btn" onclick="toggleRefresh()">⏸ pause refresh</button></h1>'
            f'<section id="kb">{sections}</section>')
    return _PAGE.format(title="Planfoldr — Knowledge Base", refresh_meta=_refresh_meta(snap), nav=_NAV, body=body,
                        snapshot=json.dumps(snap, default=str), ws_port=ws_port or 0, preserve=_PRESERVE_SCRIPT, script="")


PAGES = {
    "index.html": render_stream_log_html,
    "state.html": render_state_view_html,
    "tickets.html": render_tickets_html,
    "kb.html": render_kb_html,
}


def write_report(target: Path | str, snapshot: Dict[str, Any]) -> Path:
    vis = Path(target) / "visibility"
    vis.mkdir(parents=True, exist_ok=True)
    (vis / "snapshot.json").write_text(json.dumps(snapshot, default=str, indent=2), encoding="utf-8")
    for filename, render in PAGES.items():
        (vis / filename).write_text(render(snapshot), encoding="utf-8")
    return vis


# --------------------------------------------------------------------------- #
# Live server
# --------------------------------------------------------------------------- #
class VisibilityServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.http_port = port
        self.ws_port = 0
        self.state = VisibilityState()
        self.ws = WebSocketServer(host, 0)
        self._httpd: Optional[ThreadingHTTPServer] = None
        self.run_dir: Optional[Path] = None

    def start(self) -> "VisibilityServer":
        self.ws_port = self.ws.start()
        server = self
        route = {"/": "index.html", "/state": "state.html", "/tickets": "tickets.html", "/kb": "kb.html"}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, body: str, ctype: str = "text/html") -> None:
                payload = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", f"{ctype}; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):  # noqa: N802
                path = self.path.split("?")[0]
                vis = server.run_dir / "visibility" if server.run_dir else None
                if path == "/snapshot.json":
                    f = (vis / "snapshot.json") if vis else None
                    self._send(f.read_text() if f and f.exists() else json.dumps(server.state.snapshot()), "application/json")
                    return
                page = route.get(path, "index.html")
                f = (vis / page) if vis else None
                if f and f.exists():
                    self._send(f.read_text())
                elif page == "state.html":
                    self._send(render_state_view_html(ws_port=server.ws_port))
                else:
                    self._send(render_stream_log_html(ws_port=server.ws_port))

        self._httpd = ThreadingHTTPServer((self.host, self.http_port), Handler)
        self.http_port = self._httpd.server_address[1]
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self

    def sink(self, event: Dict[str, Any]) -> None:
        self.state.ingest(event)
        try:
            self.ws.broadcast(json.dumps(event, default=str))
        except Exception:  # noqa: BLE001
            pass

    def attach_run(self, run_dir: Path | str) -> None:
        self.run_dir = Path(run_dir)

    def stop(self) -> None:
        self.ws.stop()
        if self._httpd is not None:
            self._httpd.shutdown()


_NAV = ('<nav class="top"><a href="/">Streaming Log</a> · <a href="/state">State</a> · '
        '<a href="/tickets">Tickets</a> · <a href="/kb">Knowledge Base</a> · '
        '<a href="index.html">log</a> · <a href="state.html">state</a> · '
        '<a href="tickets.html">tickets</a> · <a href="kb.html">kb</a></nav>')

_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
{refresh_meta}
<style>
 body{{background:#0b0e14;color:#cdd6f4;font:13px/1.5 ui-monospace,Menlo,monospace;margin:0;padding:16px}}
 h1{{font-size:17px;margin:.2em 0}} h2{{font-size:14px;color:#89b4fa}} h4{{margin:.4em 0;color:#94e2d5}}
 header{{border:1px solid #313244;border-radius:8px;padding:10px;background:#11151f}}
 .goal{{margin:2px 0}} nav a{{color:#89b4fa;margin-right:6px}} nav.anchors a{{color:#a6adc8}}
 section{{border:1px solid #313244;border-radius:8px;margin:10px 0;padding:8px}}
 summary{{cursor:pointer;color:#a6e3a1;font-weight:bold}}
 .evt{{border-left:2px solid #45475a;padding:2px 8px;margin:2px 0;white-space:pre-wrap}}
 .evt.small{{border-left-color:#2d2f40;color:#9399b2;font-size:11px}}
 details details,details .evt{{margin-left:12px}} table{{border-collapse:collapse;margin:4px 0;width:100%}}
 td,th{{border:1px solid #313244;padding:2px 6px;text-align:left;vertical-align:top;font-size:12px}}
 th{{color:#fab387}} pre.kbcontent{{background:#11151f;padding:8px;border-radius:6px;white-space:pre-wrap}}
 /* status badges */
 .status-done{{color:#a6e3a1}} .status-failed{{color:#f38ba8}} .status-running{{color:#f9e2af}}
 .status-needs_review{{color:#fab387}} .status-budget_exceeded{{color:#f38ba8}} .status-blocked{{color:#9399b2}}
 /* exit code badges */
 .rc-ok{{background:#1e3a2a;color:#a6e3a1;padding:0 4px;border-radius:3px;font-size:11px}}
 .rc-err{{background:#3a1e1e;color:#f38ba8;padding:0 4px;border-radius:3px;font-size:11px}}
 /* verdicts */
 .verdict-pass{{background:#1a3a25;border-left:3px solid #a6e3a1;padding:4px 8px;margin:4px 0}}
 .verdict-fail{{background:#3a1a1a;border-left:3px solid #f38ba8;padding:4px 8px;margin:4px 0}}
 /* model / role badges */
 .model-badge{{color:#89b4fa;background:#1a2a3a;padding:0 4px;border-radius:3px}}
 .role-badge{{color:#cba6f7;background:#2a1a3a;padding:0 4px;border-radius:3px}}
 .phase-name{{color:#f9e2af}} .tok-count{{color:#9399b2;font-size:11px}}
 .cyc-id{{color:#a6adc8;font-size:11px}}
 /* tool calls */
 .tool summary{{color:#f9e2af}} .model-call summary{{color:#89b4fa}}
 .tool-line{{border-left:2px solid #45475a;padding:2px 8px;margin:2px 0;color:#cdd6f4}}
 .err-line{{border-left-color:#f38ba8;color:#f38ba8}}
 /* terminal output */
 .pre-out,.pre-err,.pre-file,.cmd-full,.model-content{{background:#0d1117;border-radius:4px;padding:6px 8px;margin:2px 0 4px;white-space:pre-wrap;word-break:break-all;font-size:12px}}
 .pre-err{{color:#f38ba8}} .cmd-full{{color:#94e2d5}}
 .cmd-inline{{color:#94e2d5;font-size:12px}} .model-content{{color:#cdd6f4}}
 .out-label{{font-size:11px;color:#9399b2;margin-top:4px}}
 .err-label{{color:#f38ba8}}
 /* diff stats */
 .diff-add{{color:#a6e3a1}} .diff-del{{color:#f38ba8}}
 /* score colors */
 .score-pos{{color:#a6e3a1}} .score-neg{{color:#f38ba8}}
 /* thinking */
 .thinking{{color:#9399b2;border-left:2px solid #313244;padding:2px 8px;margin:2px 0;white-space:pre-wrap}}
 /* cycle footer */
 .cycle-footer{{border-left:2px solid #45475a;padding:2px 8px;margin:4px 0;font-size:11px;color:#a6adc8}}
 /* refresh toggle */
 .rf-btn{{background:#1a2a3a;border:1px solid #313244;color:#89b4fa;padding:2px 8px;border-radius:4px;cursor:pointer;font:12px ui-monospace,monospace;margin-left:8px;vertical-align:middle}}
 .rf-btn:hover{{background:#2a3a4a}}
</style></head><body>
{nav}
{body}
<script>window.__SNAPSHOT__={snapshot};window.__WS_PORT__={ws_port};
{preserve}
{script}
function toggleRefresh(){{
  var m=document.getElementById('refresh-meta');
  var b=document.getElementById('rf-btn');
  if(!m){{b.textContent='⏸ pause refresh';return;}}
  if(m.parentNode){{m.parentNode.removeChild(m);b.textContent='▶ resume refresh';}}
  else{{var nm=document.createElement('meta');nm.httpEquiv='refresh';nm.content=m.content;nm.id='refresh-meta';document.head.appendChild(nm);b.textContent='⏸ pause refresh';}}
}}
</script>
</body></html>
"""

_PRESERVE_SCRIPT = r"""
(function(){
  var OK='pf_open', SK='pf_scroll';
  function key(d){
    if(d.id) return d.id;
    var parts=[], el=d;
    while(el && el.tagName==='DETAILS'){
      var s=el.querySelector(':scope>summary'), i=0, p=el.previousElementSibling;
      while(p){ if(p.tagName==='DETAILS') i++; p=p.previousElementSibling; }
      parts.unshift((s?s.textContent.trim().slice(0,48):'')+'#'+i);
      el=el.parentElement?el.parentElement.closest('details'):null;
    }
    return parts.join('>');
  }
  function load(){ try{return JSON.parse(sessionStorage.getItem(OK)||'{}');}catch(e){return {};} }
  function save(m){ try{sessionStorage.setItem(OK,JSON.stringify(m));}catch(e){} }
  var state=load();
  document.querySelectorAll('details').forEach(function(d){
    var k=key(d);
    if(Object.prototype.hasOwnProperty.call(state,k)) d.open=state[k];
    d.addEventListener('toggle',function(){ var m=load(); m[k]=d.open; save(m); });
  });
  try{ var y=sessionStorage.getItem(SK); if(y!==null) window.scrollTo(0,parseFloat(y)); }catch(e){}
  addEventListener('scroll',function(){ try{sessionStorage.setItem(SK,String(scrollY));}catch(e){} },{passive:true});
})();
"""

_WS_SCRIPT = r"""
if(window.__WS_PORT__){try{const ws=new WebSocket('ws://'+location.hostname+':'+window.__WS_PORT__);
 ws.onmessage=()=>{};}catch(e){}}
"""
