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


def _norm(embedded: Any) -> Tuple[dict, list]:
    if embedded is None:
        return {}, []
    if isinstance(embedded, tuple):
        snap, log = embedded
        return snap or {}, log or []
    return embedded, embedded.get("log", [])


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _table(rows: List[Dict[str, Any]], columns: Optional[List[str]] = None) -> str:
    if not rows:
        return "<i>none</i>"
    columns = columns or list({k for r in rows for k in r.keys()})
    head = "".join(f"<th>{esc(c)}</th>" for c in columns)
    body = ""
    for r in rows:
        cells = "".join(
            f"<td>{esc(json.dumps(r[c]) if isinstance(r.get(c), (dict, list)) else r.get(c))}</td>"
            for c in columns
        )
        body += f"<tr>{cells}</tr>"
    return f"<table><tr>{head}</tr>{body}</table>"


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
def render_stream_log_html(embedded: Any = None, ws_port: Optional[int] = None) -> str:
    snap, log = _norm(embedded)
    sc = snap.get("scenario", {})
    header = (
        f'<header><h1>{esc(sc.get("name", "Planfoldr run"))}</h1>'
        f'<div class="goal"><b>Goal:</b> {esc(sc.get("goal"))}</div>'
        f'<div class="goal"><b>Status:</b> <span class="status-{esc(snap.get("status"))}">{esc(snap.get("status", "running"))}</span></div>'
        + (f'<div class="goal"><b>Constraints:</b> {esc(", ".join(sc.get("constraints", [])))}</div>' if sc.get("constraints") else "")
        + (f'<div class="goal"><b>Verification:</b> {esc(", ".join(sc.get("verification_commands", [])))}</div>' if sc.get("verification_commands") else "")
        + "</header>"
    )
    entries = "".join(_log_entry_html(e) for e in log)
    body = f'{header}<h2>Streaming Log</h2><div id="log">{entries}</div>'
    return _PAGE.format(title="Planfoldr — Streaming Log", refresh=REFRESH_SECONDS, nav=_NAV, body=body,
                        snapshot=json.dumps(snap, default=str), ws_port=ws_port or 0, script=_WS_SCRIPT)


def _log_entry_html(e: Dict[str, Any]) -> str:
    if e.get("type") == "audit":
        et = e.get("event_type", "")
        p = e.get("payload", {})
        if et == "cycle.started":
            return (f'<details open class="cyc"><summary>▶ cycle {esc(e.get("cycle_id"))[:14]} · '
                    f'ticket {esc(e.get("ticket_id"))} · model {esc(p.get("model"))} · role {esc(p.get("role"))}</summary>'
                    f'<div class="evt">input: ticket={esc(e.get("ticket_id"))} type={esc(p.get("type"))}</div></details>')
        if et == "cycle.phase_completed":
            return f'<div class="evt">● phase: {esc(p.get("phase"))}</div>'
        if et == "tool.invoked":
            return (f'<details class="tool"><summary>🔧 {esc(p.get("tool"))}</summary>'
                    f'<div class="evt">args: {esc(json.dumps(p.get("args")))}\nresult: {esc(json.dumps(p.get("result")))}</div></details>')
        if et == "ticket.status_changed":
            return f'<div class="evt">~ {esc(e.get("ticket_id"))}: {esc(p.get("from"))} → {esc(p.get("to"))}</div>'
        if et == "cycle.completed":
            return f'<div class="evt">■ cycle {esc(p.get("status"))}</div>'
        return ""
    if e.get("type") == "model_stream_chunk":
        cls = "thinking" if e.get("kind") == "thinking" else "content"
        return f'<span class="evt {cls}">{esc(e.get("text"))}</span>'
    return ""


def render_state_view_html(embedded: Any = None, ws_port: Optional[int] = None) -> str:
    snap, _ = _norm(embedded)
    content = {
        "system": _render_system(snap),
        "queues": _table([{"id": q.get("id"), "tickets": q.get("tickets_by_status", {}),
                           "manager": q.get("manager_role"), "executors": q.get("executor_roles")}
                          for q in snap.get("queues", {}).values()]),
        "tickets": _table([{"id": t.get("id"), "type": t.get("type"), "status": t.get("status"),
                            "role": t.get("role"), "attempts": t.get("attempt_count"),
                            "goal": (t.get("goal") or "")[:60]} for t in snap.get("tickets", {}).values()]),
        "models": _render_models(snap),
        "commands": _table(snap.get("commands", []), ["when", "actor", "ticket", "cmd", "exit_code", "status"]),
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
    body = f'<h1>State View</h1><nav class="anchors">{" · ".join(f"<a href=#{s}>{s}</a>" for s in SLICES)}</nav>{sections}'
    return _PAGE.format(title="Planfoldr — State View", refresh=REFRESH_SECONDS, nav=_NAV, body=body,
                        snapshot=json.dumps(snap, default=str), ws_port=ws_port or 0, script="")


def _render_system(snap: Dict[str, Any]) -> str:
    sc = snap.get("scenario", {})
    return (f'<b>Scenario:</b> {esc(sc.get("name"))}<br><b>Goal:</b> {esc(sc.get("goal"))}<br>'
            f'<b>Status:</b> <span class="status-{esc(snap.get("status"))}">{esc(snap.get("status"))}</span><br>'
            f'<b>Constraints:</b> {esc(", ".join(sc.get("constraints", [])))}<br>'
            f'<b>Cycles run:</b> {esc(snap.get("cycles_run"))}')


def _render_models(snap: Dict[str, Any]) -> str:
    rows = []
    for mid, s in (snap.get("scores", {}) or {}).items():
        rows.append({"model": mid, "global_score": round(s.get("global_score", 0), 2),
                     "tickets": s.get("tickets"), "by_role": s.get("by_role"), "by_task_type": s.get("by_task_type")})
    return _table(rows, ["model", "global_score", "tickets", "by_role", "by_task_type"])


def _render_budgets(snap: Dict[str, Any]) -> str:
    budgets = snap.get("budgets", {})
    project = budgets.get("project", {})
    proj_html = (f'<h4>Project</h4><div class="evt">tokens={esc(project.get("usage", {}).get("tokens_used"))} '
                 f'limits={esc(project.get("limits"))} exceeded={esc(project.get("exceeded"))}</div>')
    rows = []
    for b in budgets.get("tickets", []):
        usage = b.get("usage", {})
        rows.append({
            "ticket": b.get("ticket"), "title": b.get("title"), "goal": (b.get("goal") or "")[:50],
            "tokens": usage.get("tokens_used"), "requests": usage.get("api_requests"),
            "files": usage.get("file_changes"), "commands": usage.get("command_runs"),
            "gpu_ram_hours": round(usage.get("gpu_ram_hours", 0), 4), "limit": b.get("limits"),
            "exceeded": b.get("exceeded"),
        })
    return proj_html + "<h4>Per ticket</h4>" + _table(
        rows, ["ticket", "title", "goal", "tokens", "requests", "files", "commands", "gpu_ram_hours", "exceeded"])


def _render_tree(nodes: List[Dict[str, Any]]) -> str:
    if not nodes:
        return "<i>none</i>"
    items = "".join(
        f'<li>cycle {esc(n.get("id"))[:14]} [{esc(n.get("status"))}] ticket={esc(n.get("ticket"))}'
        f'{_render_tree(n.get("children", []))}</li>' for n in nodes
    )
    return f"<ul>{items}</ul>"


def render_tickets_html(embedded: Any = None, ws_port: Optional[int] = None) -> str:
    snap, _ = _norm(embedded)
    tickets = snap.get("tickets", {})
    graph = snap.get("graph", {})
    tree = _ticket_tree(tickets, graph)
    detail = "".join(_ticket_detail_html(t) for t in tickets.values())
    body = (f'<h1>Tickets</h1><section id="ticket-tree"><h2>Structure</h2>{tree}</section>'
            f'<section id="ticket-details"><h2>Every ticket</h2>{detail}</section>')
    return _PAGE.format(title="Planfoldr — Tickets", refresh=REFRESH_SECONDS, nav=_NAV, body=body,
                        snapshot=json.dumps(snap, default=str), ws_port=ws_port or 0, script="")


def _ticket_tree(tickets: Dict[str, Any], graph: Dict[str, Any]) -> str:
    children: Dict[Optional[str], List[str]] = {}
    for tid, t in tickets.items():
        children.setdefault(t.get("spawned_by"), []).append(tid)

    def build(tid: str) -> str:
        t = tickets.get(tid, {})
        kids = "".join(build(c) for c in children.get(tid, []))
        deps = t.get("dependencies", [])
        dep_txt = f' ⟵ blocked_by {esc(deps)}' if deps else ""
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
    evidence = _table([{"check": e.get("check_index"), "status": e.get("status"),
                        "proof": (str(e.get("proof") or ""))[:200]} for e in t.get("evidence", [])],
                      ["check", "status", "proof"])
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
    body = f'<h1>Knowledge Base</h1><section id="kb">{sections}</section>'
    return _PAGE.format(title="Planfoldr — Knowledge Base", refresh=REFRESH_SECONDS, nav=_NAV, body=body,
                        snapshot=json.dumps(snap, default=str), ws_port=ws_port or 0, script="")


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
<meta http-equiv="refresh" content="{refresh}">
<style>
 body{{background:#0b0e14;color:#cdd6f4;font:13px/1.5 ui-monospace,Menlo,monospace;margin:0;padding:16px}}
 h1{{font-size:17px;margin:.2em 0}} h2{{font-size:14px;color:#89b4fa}} h4{{margin:.4em 0;color:#94e2d5}}
 header{{border:1px solid #313244;border-radius:8px;padding:10px;background:#11151f}}
 .goal{{margin:2px 0}} nav a{{color:#89b4fa;margin-right:6px}} nav.anchors a{{color:#a6adc8}}
 section{{border:1px solid #313244;border-radius:8px;margin:10px 0;padding:8px}}
 summary{{cursor:pointer;color:#a6e3a1;font-weight:bold}}
 .thinking{{color:#9399b2}} .content{{color:#cdd6f4}} .tool summary{{color:#f9e2af}}
 .evt{{border-left:2px solid #45475a;padding:2px 8px;margin:2px 0;white-space:pre-wrap}}
 details details,details .evt{{margin-left:12px}} table{{border-collapse:collapse;margin:4px 0;width:100%}}
 td,th{{border:1px solid #313244;padding:2px 6px;text-align:left;vertical-align:top;font-size:12px}}
 th{{color:#fab387}} pre.kbcontent{{background:#11151f;padding:8px;border-radius:6px;white-space:pre-wrap}}
 .status-done{{color:#a6e3a1}} .status-failed{{color:#f38ba8}} .status-running{{color:#f9e2af}}
 .status-needs_review{{color:#fab387}} .status-budget_exceeded{{color:#f38ba8}} .status-blocked{{color:#9399b2}}
</style></head><body>
{nav}
{body}
<script>window.__SNAPSHOT__={snapshot};window.__WS_PORT__={ws_port};{script}</script>
</body></html>
"""

_WS_SCRIPT = r"""
if(window.__WS_PORT__){try{const ws=new WebSocket('ws://'+location.hostname+':'+window.__WS_PORT__);
 ws.onmessage=()=>{};}catch(e){}}
"""
