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
import re as _re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from planfoldr.visibility.events import SLICES, VisibilityState
from planfoldr.visibility.ws import WebSocketServer

REFRESH_SECONDS = 2
TERMINAL_STATUSES = {"done", "failed", "budget_exceeded", "error"}


def _refresh_meta(snap: Any) -> str:
    """Returns "1" if the run is live (auto-refresh should be active), "0" otherwise.

    Used as window.__LIVE__ in the page script; the actual reload is driven by a JS setTimeout so
    that the pause button can cancel it reliably (removing a <meta http-equiv=refresh> after the
    browser has already started the timer does not cancel it in all browsers).
    """
    status = snap.get("status") if isinstance(snap, dict) else None
    return "0" if status in TERMINAL_STATUSES else "1"


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
        title = (args.get("title") or "").strip()
        goal_lines = (args.get("goal") or "").strip().splitlines()
        goal_preview = "\n".join(goal_lines[:3])
        if len(goal_lines) > 3:
            goal_preview += f"\n… (+{len(goal_lines) - 3} lines)"
        checks = args.get("checks") or []
        deps = args.get("dependencies") or []
        tid_link = f'<a href="tickets.html#t_{esc(tid)}">{esc(tid)}</a>'
        summary = f'🎫 create_ticket → {tid_link} [{esc(ttype)}] <b>{esc(title)}</b>'
        body = f'<pre class="evt">{esc(goal_preview)}</pre>' if goal_preview else ""
        if checks:
            chk_rows = "".join(
                f'<tr><td>{esc(c.get("kind","?"))}</td><td><code>{esc(c.get("spec","?"))}</code></td></tr>'
                for c in checks
            )
            body += f'<div class="evt small">{len(checks)} check{"s" if len(checks) != 1 else ""}<table>{chk_rows}</table></div>'
        if deps:
            body += f'<div class="evt small">depends on: {esc(", ".join(str(d) for d in deps))}</div>'
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


def _strip_think_tags(s: str) -> str:
    """Remove <think>...</think> blocks and stray </think> tags emitted by some models."""
    s = _re.sub(r"<think>.*?</think>", "", s, flags=_re.DOTALL)
    return s.replace("</think>", "").replace("<think>", "").strip()


def _try_parse_json(s: str) -> Optional[dict]:
    """Parse JSON, stripping think-tags and repairing truncated objects."""
    s = _strip_think_tags(s)
    try:
        return json.loads(s)
    except Exception:
        pass
    for closing in ("}", "}}", "}}}"):
        try:
            return json.loads(s + closing)
        except Exception:
            pass
    return None


def _tool_call_body(s: str) -> Optional[str]:
    s = _strip_think_tags(s)
    match = _re.search(r"<tool_call>\s*(.*?)\s*</tool_call>", s, flags=_re.DOTALL)
    if match is None:
        return None
    return match.group(1).strip()


def _try_parse_action_obj(content: str) -> Optional[dict]:
    body = _tool_call_body(content)
    if body is not None:
        return _try_parse_json(body)
    return _try_parse_json(content)


def _action_from_broken_json(s: str) -> Optional[Tuple[str, str]]:
    """Regex fallback when JSON is malformed (e.g. unescaped quotes in args).

    Extracts at least the action name and thinking so the block is not a raw dump.
    """
    s = _strip_think_tags(s)
    action_m = _re.search(r'"action"\s*:\s*"([^"]+)"', s)
    if not action_m:
        return None
    action = action_m.group(1)
    thinking_m = _re.search(r'"thinking"\s*:\s*"((?:[^"\\]|\\.)*)"', s)
    thinking = thinking_m.group(1) if thinking_m else ""
    note = '<span class="thinking" style="font-size:10px"> [args truncated — malformed JSON]</span>'
    return thinking, f'<div class="tool-line">⚡ <b>{esc(action)}</b>{note}</div>'


def _action_from_broken_tool_call(s: str) -> Optional[Tuple[str, str]]:
    body = _tool_call_body(s)
    if body is None:
        return None
    name_m = _re.search(r'"(?:name|action|tool)"\s*:\s*"([^"]+)"', body)
    if not name_m:
        return "", '<div class="tool-line err-line">⚡ malformed <b>tool_call</b> <span class="thinking" style="font-size:10px">[missing action name]</span></div>'
    thinking_m = _re.search(r'"thinking"\s*:\s*"((?:[^"\\]|\\.)*)"', body)
    thinking = thinking_m.group(1) if thinking_m else ""
    note = '<span class="thinking" style="font-size:10px"> [arguments truncated — malformed tool_call]</span>'
    return thinking, f'<div class="tool-line">⚡ <b>{esc(name_m.group(1))}</b>{note}</div>'


def _render_action_content(content: str) -> Optional[Tuple[str, str]]:
    """Parse an action-protocol response and return (json_thinking, action_html).

    Returns None if content is not a valid action-protocol response.
    """
    obj = _try_parse_action_obj(content)
    if obj is None:
        return None
    function = obj.get("function") if isinstance(obj.get("function"), dict) else {}
    action = obj.get("action") or obj.get("tool") or obj.get("name") or function.get("name")
    if not action:
        return None

    json_thinking = (obj.get("thinking") or "").strip()
    action_html = f'<div class="tool-line">⚡ <b>{esc(action)}</b></div>'
    args = obj.get("args")
    if args is None:
        args = obj.get("arguments", obj.get("parameters", function.get("arguments", {})))
    if isinstance(args, str):
        args = _try_parse_json(args) or {"value": args}
    if not isinstance(args, dict):
        args = {"value": args}
    if args:
        rows = ""
        for k, v in args.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                val_html = _table(v)
            elif isinstance(v, list):
                val_html = (", ".join(esc(str(i)) for i in v)) if v else "<i>—</i>"
            elif isinstance(v, dict) and v:
                val_html = _table([{"key": kk, "value": str(vv)} for kk, vv in v.items()])
            elif isinstance(v, str) and len(v) > 120:
                val_html = f'<pre class="model-content">{esc(v)}</pre>'
            elif v is None or v == [] or v == {}:
                val_html = "<i>—</i>"
            else:
                val_html = esc(str(v))
            rows += f'<tr><th>{esc(k)}</th><td>{val_html}</td></tr>'
        action_html += f'<table>{rows}</table>'
    return json_thinking, action_html


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

    allowed_actions = e.get("allowed_actions") or []
    context_data = e.get("context_data") or {}
    inp = e.get("input") or {}
    inp_system = (inp.get("system") or "").strip()
    inp_user = (inp.get("user") or "").strip()
    body = ""
    # Tools available — always visible as badges
    if allowed_actions:
        badges = " ".join(f'<span class="action-badge">{esc(a)}</span>' for a in allowed_actions)
        body += f'<div class="model-ctx-row">🔧 <span class="ctx-label">tools:</span> {badges}</div>'
    # Context/information available — table, open by default
    if context_data:
        ctx_rows = ""
        for k, v in context_data.items():
            if v is None or v == [] or v == {}:
                continue
            if isinstance(v, list):
                val_html = esc(", ".join(str(i) for i in v)) if v else "<i>—</i>"
            elif isinstance(v, dict):
                val_html = "<br>".join(f"<b>{esc(kk)}</b>: {esc(str(vv))}" for kk, vv in v.items()) or "<i>—</i>"
            else:
                val_html = f'<pre class="pre-input">{esc(str(v))}</pre>' if len(str(v)) > 80 else esc(str(v))
            ctx_rows += f'<tr><th class="ctx-key">{esc(k)}</th><td>{val_html}</td></tr>'
        if ctx_rows:
            body += f'<details class="model-input" open><summary>📋 context</summary><table>{ctx_rows}</table></details>'
    # Raw prompts — collapsed by default, available for deep inspection
    if inp_system or inp_user:
        inp_body = ""
        if inp_system:
            inp_body += f'<div class="out-label">system</div><pre class="pre-input">{esc(inp_system)}</pre>'
        if inp_user:
            inp_body += f'<div class="out-label">user</div><pre class="pre-input">{esc(inp_user)}</pre>'
        body += f'<details class="model-input"><summary>📄 raw prompt</summary>{inp_body}</details>'
    if thinking:
        body += f'<div class="thinking">💭 {esc(thinking)}</div>'
    if content:
        parsed = _render_action_content(content)
        if parsed is not None:
            json_thinking, action_html = parsed
            if json_thinking and not thinking:
                body += f'<div class="thinking">💭 {esc(json_thinking)}</div>'
            body += action_html
        else:
            # Model emitted multiple JSON actions on separate lines
            blocks = [_render_action_content(ln.strip()) for ln in content.splitlines() if ln.strip()]
            blocks = [b for b in blocks if b is not None]
            if blocks:
                for i, (jt, ah) in enumerate(blocks):
                    if jt and (i > 0 or not thinking):
                        body += f'<div class="thinking">💭 {esc(jt)}</div>'
                    body += ah
            else:
                fallback = _action_from_broken_json(content)
                if fallback is None:
                    fallback = _action_from_broken_tool_call(content)
                if fallback is not None:
                    jt, ah = fallback
                    if jt and not thinking:
                        body += f'<div class="thinking">💭 {esc(jt)}</div>'
                    body += ah
                else:
                    body += f'<pre class="model-content">{esc(content)}</pre>'

    # For model_verification: parse and display the verdict prominently
    if phase == "model_verification" and content:
        obj = _try_parse_action_obj(content)
        action = obj.get("action") or obj.get("name") if obj else None
        args = obj.get("args") if obj else {}
        if obj and args is None:
            args = obj.get("arguments", {})
        if obj and action == "verify":
            passed = bool((args or {}).get("passed", False))
            reason = (args or {}).get("reason", "")
            v_cls = "verdict-pass" if passed else "verdict-fail"
            v_icon = "✅" if passed else "❌"
            v_word = "PASSED" if passed else "FAILED"
            body += f'<div class="{v_cls}">{v_icon} <b>{v_word}</b>: {esc(reason)}</div>'

    return f'<details class="model-call" open><summary>{summary}</summary>{body}</details>'


# --------------------------------------------------------------------------- #
# Streaming log renderer
# --------------------------------------------------------------------------- #
def _log_entry_html(e: Dict[str, Any], cycle_starts: Optional[Dict[str, str]] = None) -> str:
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
            cyc_id = e.get("cycle_id", "")
            tid_link = f'<a href="tickets.html#t_{esc(tid)}">{esc(tid)}</a>'
            summary = (f'▶ <span class="cyc-id">{esc(cyc_id[:14])}</span> · '
                       f'ticket {tid_link} [{esc(ttype)}] · '
                       f'<span class="model-badge">{esc(model)}</span> · '
                       f'<span class="role-badge">{esc(role)}</span>')
            return f'<details id="exec_{esc(cyc_id)}" open class="cyc"><summary>{summary}</summary>'

        if et == "cycle.completed":
            status = p.get("status", "?")
            b = p.get("budget", {})
            tokens = int(b.get("tokens_used", 0))
            files = int(b.get("file_changes", 0))
            cmds = int(b.get("command_runs", 0))
            gpu_h = float(b.get("gpu_ram_hours", 0.0))
            money = float(b.get("money_spent", 0.0))
            spawned = p.get("spawned", [])
            sp_txt = f' · spawned: {esc(", ".join(spawned))}' if spawned else ""
            cid = e.get("cycle_id", "")
            ts_end = e.get("timestamp", "")
            ts_start = (cycle_starts or {}).get(cid, "")
            dur_txt = ""
            if ts_start and ts_end:
                try:
                    from datetime import datetime as _dt
                    t0 = _dt.fromisoformat(ts_start.replace("Z", "+00:00"))
                    t1 = _dt.fromisoformat(ts_end.replace("Z", "+00:00"))
                    dur_txt = f' · ⏱ {_fmt_duration((t1 - t0).total_seconds())}'
                except Exception:
                    pass
            date_txt = f' · {esc(ts_end[:16].replace("T", " "))}' if ts_end else ""
            money_txt = f' · ${money:.4f}' if money else ""
            gpu_txt = f' · {gpu_h:.4f} gpu·ram·h' if gpu_h else ""
            return (f'<div class="cycle-footer status-{esc(status)}">■ {esc(status)}{date_txt}{dur_txt} · '
                    f'{_fmt_tokens(tokens)} tok{money_txt} · {files} files · {cmds} cmds{gpu_txt}{sp_txt}</div>'
                    f'</details>')

        if et == "cycle.phase_completed":
            # Phase separators are rendered inline by model_output; nothing extra needed here
            return ""

        if et == "tool.invoked":
            return _tool_html(p)

        if et == "ticket.status_changed":
            status = p.get("to", "")
            actor = e.get("actor") or p.get("actor", "?")
            ts = (e.get("timestamp") or "")[:19]
            proof = (p.get("proof") or "").strip()
            cause = (p.get("cause") or "").strip()
            why = proof or cause or ""
            why_html = f' — {esc(why[:120])}' if why else ""
            tid_str = e.get("ticket_id", "")
            tid_link = f'<a href="tickets.html#t_{esc(tid_str)}">{esc(tid_str)}</a>'
            return (f'<div class="evt small">~ {tid_link} '
                    f'{esc(p.get("from"))} → <span class="status-{esc(status)}">{esc(status)}</span>'
                    f' · by <b>{esc(actor)}</b> at {esc(ts)}{why_html}</div>')

        if et == "ticket.created":
            tid = e.get("ticket_id", "?")
            ttype = p.get("type", "?")
            goal = (p.get("goal") or "")[:100]
            tid_link = f'<a href="tickets.html#t_{esc(tid)}">{esc(tid)}</a>'
            return f'<div class="evt small">+ ticket {tid_link} [{esc(ttype)}] {esc(goal)}</div>'

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
# Live status panel
# --------------------------------------------------------------------------- #
def _render_live_status(snap: Dict[str, Any]) -> str:
    """Sticky banner showing currently running cycles; empty string when the run is terminal."""
    overall = snap.get("status", "running")
    if overall in TERMINAL_STATUSES:
        return ""
    cycles = snap.get("cycles") or {}
    running = [c for c in cycles.values() if c.get("status") == "running"]
    if not running:
        # Nothing explicitly running — show generic "initialising" hint
        return '<div class="live-status">⟳ <b>Initialising…</b></div>'
    _PHASE_VERBS = {
        "context_exploration": "exploring context",
        "changes": "making changes",
        "command_verification": "running verification commands",
        "model_verification": "model verifying",
    }
    parts = []
    for c in running:
        tid = c.get("ticket", "?")
        model = c.get("model", "?")
        role = c.get("role", "?")
        current_phase = c.get("current_phase")
        last_phase = c.get("phase")
        if current_phase:
            phase_txt = f'⟳ <b>{esc(_PHASE_VERBS.get(current_phase, current_phase))}</b>'
        elif last_phase:
            phase_txt = f'✓ {esc(last_phase)} → waiting for next phase'
        else:
            phase_txt = "⟳ starting…"
        tid_link = f'<a href="tickets.html#t_{esc(tid)}">{esc(tid)}</a>'
        parts.append(
            f'ticket {tid_link} · '
            f'<span class="model-badge">{esc(model)}</span> · '
            f'<span class="role-badge">{esc(role)}</span> · '
            f'{phase_txt}'
        )
    return '<div class="live-status">' + " &nbsp;|&nbsp; ".join(parts) + "</div>"


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
    cycle_starts = {
        e.get("cycle_id"): e.get("timestamp", "")
        for e in log
        if e.get("type") == "audit" and e.get("event_type") == "cycle.started" and e.get("cycle_id")
    }
    entries = "".join(_log_entry_html(e, cycle_starts) for e in log)
    live = _render_live_status(snap)
    body = f'{header}{live}<h2>Streaming Log <button id="rf-btn" class="rf-btn" onclick="toggleRefresh()">⏸ pause refresh</button></h2><div id="log">{entries}</div>'
    return _PAGE.format(title="Planfoldr — Streaming Log", refresh_meta=_refresh_meta(snap), nav=_NAV, body=body,
                        snapshot=json.dumps(snap, default=str), ws_port=ws_port or 0, preserve=_PRESERVE_SCRIPT, script=_WS_SCRIPT,
                        refresh_ms=REFRESH_SECONDS * 1000)


def render_state_view_html(embedded: Any = None, ws_port: Optional[int] = None) -> str:
    snap, _ = _norm(embedded)
    content = {
        "system": _render_system(snap),
        "queues": _table([{"id": q.get("id"), "tickets": q.get("tickets_by_status", {}),
                           "manager": q.get("manager_role"), "executors": q.get("executor_roles")}
                          for q in snap.get("queues", {}).values()]),
        "tickets": _render_tickets_table(snap.get("tickets", {})),
        "models": _render_models(snap),
        "commands": _render_commands(snap),
        "tools": _table([{"tool": k, "count": v} for k, v in (snap.get("tools", {}) or {}).items()]),
        "cycles": _render_cycles_table(snap.get("cycles", {})),
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
                        snapshot=json.dumps(snap, default=str), ws_port=ws_port or 0, preserve=_PRESERVE_SCRIPT, script="",
                        refresh_ms=REFRESH_SECONDS * 1000)


def _render_tickets_table(tickets: Dict[str, Any]) -> str:
    if not tickets:
        return "<i>none</i>"
    head = ("<tr><th>id</th><th>type</th><th>status</th><th>role</th>"
            "<th>attempts</th><th>goal</th></tr>")
    rows = ""
    for t in tickets.values():
        tid = t.get("id", "")
        status = t.get("status", "")
        rows += (f'<tr>'
                 f'<td><a href="tickets.html#t_{esc(tid)}">{esc(tid)}</a></td>'
                 f'<td>{esc(t.get("type"))}</td>'
                 f'<td class="status-{esc(status)}">{esc(status)}</td>'
                 f'<td>{esc(t.get("role"))}</td>'
                 f'<td>{esc(t.get("attempt_count"))}</td>'
                 f'<td>{esc((t.get("goal") or "")[:60])}</td>'
                 f'</tr>')
    return f"<table>{head}{rows}</table>"


def _render_cycles_table(cycles: Dict[str, Any]) -> str:
    if not cycles:
        return "<i>none</i>"
    head = ("<tr><th>id</th><th>ticket</th><th>model</th>"
            "<th>role</th><th>phase</th><th>status</th></tr>")
    rows = ""
    for c in cycles.values():
        cid = c.get("id", "")
        tid = c.get("ticket", "")
        rows += (f'<tr>'
                 f'<td><a href="index.html#exec_{esc(cid)}">{esc(cid[:16])}</a></td>'
                 f'<td><a href="tickets.html#t_{esc(tid)}">{esc(tid)}</a></td>'
                 f'<td>{esc(c.get("model"))}</td>'
                 f'<td>{esc(c.get("role"))}</td>'
                 f'<td>{esc(c.get("phase"))}</td>'
                 f'<td>{esc(c.get("status"))}</td>'
                 f'</tr>')
    return f"<table>{head}{rows}</table>"


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
        tid = c.get("ticket") or ""
        ticket_html = f'<a href="tickets.html#t_{esc(tid)}">{esc(tid)}</a>' if tid else "<i>—</i>"
        rows.append(f'<tr><td>{esc(str(c.get("when", ""))[:19])}</td>'
                    f'<td>{esc(c.get("actor"))}</td>'
                    f'<td>{ticket_html}</td>'
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
    if not budgets.get("tickets"):
        return proj_html
    cols = ["ticket", "title", "goal", "tokens", "requests", "files", "cmds", "gpu·ram·h", "exceeded"]
    head = "".join(f"<th>{esc(c)}</th>" for c in cols)
    body_rows = ""
    for b in budgets.get("tickets", []):
        u = b.get("usage", {})
        lim = b.get("limits") or {}
        tok_u = _fmt_tokens(u.get("tokens_used"))
        tok_l = _fmt_tokens(lim.get("tokens_used")) if lim else "—"
        tid = b.get("ticket") or ""
        ticket_html = f'<a href="tickets.html#t_{esc(tid)}">{esc(tid)}</a>' if tid else "<i>—</i>"
        body_rows += (f'<tr><td>{ticket_html}</td>'
                      f'<td>{esc((b.get("title") or "")[:30])}</td>'
                      f'<td>{esc((b.get("goal") or "")[:50])}</td>'
                      f'<td>{esc(f"{tok_u} / {tok_l}")}</td>'
                      f'<td>{esc(u.get("api_requests"))}</td>'
                      f'<td>{esc(u.get("file_changes"))}</td>'
                      f'<td>{esc(u.get("command_runs"))}</td>'
                      f'<td>{esc(round(u.get("gpu_ram_hours", 0), 4))}</td>'
                      f'<td>{"yes" if b.get("exceeded") else "—"}</td></tr>')
    return proj_html + f"<table><tr>{head}</tr>{body_rows}</table>"


def _render_tree(nodes: List[Dict[str, Any]]) -> str:
    if not nodes:
        return "<i>none</i>"
    items = ""
    for n in nodes:
        cid = n.get("id", "")
        tid = n.get("ticket", "")
        cyc_link = f'<a href="index.html#exec_{esc(cid)}">{esc(cid[:14])}</a>'
        ticket_link = f'<a href="tickets.html#t_{esc(tid)}">{esc(tid)}</a>' if tid else "<i>—</i>"
        items += (f'<li>cycle {cyc_link} '
                  f'[<span class="status-{esc(n.get("status"))}">{esc(n.get("status"))}</span>] '
                  f'ticket={ticket_link}'
                  f'{_render_tree(n.get("children", []))}</li>')
    return f"<ul>{items}</ul>"


def render_tickets_html(embedded: Any = None, ws_port: Optional[int] = None) -> str:
    snap, _ = _norm(embedded)
    tickets = snap.get("tickets", {})
    graph = snap.get("graph", {})
    cycles = snap.get("cycles", {})
    tree = _ticket_tree(tickets, graph)
    detail = "".join(_ticket_detail_html(t, cycles) for t in tickets.values())
    body = (f'<h1>Tickets <button id="rf-btn" class="rf-btn" onclick="toggleRefresh()">⏸ pause refresh</button></h1>'
            f'<section id="ticket-tree"><h2>Structure</h2>{tree}</section>'
            f'<section id="ticket-details"><h2>Every ticket</h2>{detail}</section>')
    return _PAGE.format(title="Planfoldr — Tickets", refresh_meta=_refresh_meta(snap), nav=_NAV, body=body,
                        snapshot=json.dumps(snap, default=str), ws_port=ws_port or 0, preserve=_PRESERVE_SCRIPT, script="",
                        refresh_ms=REFRESH_SECONDS * 1000)


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


def _ticket_detail_html(t: Dict[str, Any], cycles: Optional[Dict[str, Any]] = None) -> str:
    tid_val = t.get("id", "")
    model_usage: Dict[str, Dict[str, int]] = {}
    for cyc in (cycles or {}).values():
        if cyc.get("ticket") == tid_val:
            m = cyc.get("model", "?")
            r = cyc.get("role", "?")
            model_usage.setdefault(m, {}).setdefault(r, 0)
            model_usage[m][r] += 1
    if model_usage:
        parts = [
            f'<span class="model-badge">{esc(m)}</span> ({esc(", ".join(f"{r}×{n}" for r, n in sorted(rs.items())))})'
            for m, rs in sorted(model_usage.items())
        ]
        model_html = " · ".join(parts)
    else:
        model_html = "<i>—</i>"
    history = t.get("metadata", {}).get("change_history", [])
    hist_rows = _render_status_history(history)
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
    spawned_by = t.get("spawned_by")
    spawned_html = (f'<a href="#t_{esc(spawned_by)}">{esc(spawned_by)}</a>'
                    if spawned_by else "<i>—</i>")
    deps = t.get("dependencies") or []
    deps_html = (", ".join(f'<a href="#t_{esc(d)}">{esc(d)}</a>' for d in deps)
                 if deps else "<i>—</i>")
    return (
        f'<details id="t_{esc(t.get("id"))}" class="ticket"><summary>{esc(t.get("id"))} '
        f'[{esc(t.get("type"))}] <span class="status-{esc(t.get("status"))}">{esc(t.get("status"))}</span> — {esc(t.get("title"))}</summary>'
        f'<div class="evt"><b>Goal:</b> {esc(t.get("goal"))}</div>'
        f'<div class="evt"><b>Role:</b> {esc(t.get("role"))} · <b>Model(s):</b> {model_html} · <b>Queue:</b> {esc(t.get("queue"))} · '
        f'<b>Attempts:</b> {esc(t.get("attempt_count"))}/{esc(t.get("max_attempts"))} · '
        f'<b>spawned_by:</b> {spawned_html} · <b>deps:</b> {deps_html}</div>'
        f'<h4>Checks</h4>{checks}<h4>Evidence</h4>{evidence}'
        f'<h4>Comments</h4>{comm_rows}<h4>Status history</h4>{hist_rows}</details>'
    )


def _render_status_history(history: List[Dict[str, Any]]) -> str:
    if not history:
        return "<i>none</i>"
    head = ("<tr><th>when</th><th>who</th><th>model</th><th>from</th><th>to</th><th>why (proof / cause)</th></tr>")
    rows = ""
    for h in history:
        to = h.get("to", "")
        proof = (h.get("proof") or "").strip()
        cause = (h.get("cause") or "").strip()
        why = proof or cause or ""
        model = h.get("model") or ""
        model_cell = f'<span class="model-badge">{esc(model)}</span>' if model else "<i>—</i>"
        rows += (f'<tr>'
                 f'<td>{esc(str(h.get("at", ""))[:19])}</td>'
                 f'<td><b>{esc(h.get("actor"))}</b></td>'
                 f'<td>{model_cell}</td>'
                 f'<td>{esc(h.get("from"))}</td>'
                 f'<td class="status-{esc(to)}">{esc(to)}</td>'
                 f'<td>{esc(why)}</td>'
                 f'</tr>')
    return f"<table>{head}{rows}</table>"


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
                        snapshot=json.dumps(snap, default=str), ws_port=ws_port or 0, preserve=_PRESERVE_SCRIPT, script="",
                        refresh_ms=REFRESH_SECONDS * 1000)


def _render_cycle_trace(cycle_log: List[Dict[str, Any]]) -> str:
    """Render the model outputs and tool calls for one cycle (for models.html)."""
    parts = []
    for e in cycle_log:
        t = e.get("type")
        et = e.get("event_type", "")
        if t == "model_output":
            parts.append(_model_output_html(e))
        elif t == "audit" and et == "tool.invoked":
            parts.append(_tool_html(e.get("payload") or {}))
    return "".join(parts) or "<i>no outputs recorded</i>"


def render_models_html(embedded: Any = None, ws_port: Optional[int] = None) -> str:
    snap, log = _norm(embedded)
    scores = snap.get("scores") or {}
    cycles = snap.get("cycles") or {}
    tickets = snap.get("tickets") or {}
    sc = snap.get("scenario") or {}

    # Index log entries by cycle_id
    log_by_cycle: Dict[str, List[Dict[str, Any]]] = {}
    for entry in log:
        cid = entry.get("cycle_id")
        if cid:
            log_by_cycle.setdefault(cid, []).append(entry)

    # Files generated per model (from file_edit tool events)
    files_by_model: Dict[str, List[str]] = {}
    for entry in log:
        if entry.get("type") == "audit" and entry.get("event_type") == "tool.invoked":
            p = entry.get("payload") or {}
            if p.get("tool") == "file_edit":
                cid = entry.get("cycle_id", "")
                m = (cycles.get(cid) or {}).get("model", "?")
                path = (p.get("args") or {}).get("path") or (p.get("result") or {}).get("path")
                if path and path not in files_by_model.get(m, []):
                    files_by_model.setdefault(m, []).append(path)

    all_models = sorted({*scores.keys(), *(c.get("model", "") for c in cycles.values() if c.get("model"))})

    sc_name = sc.get("name", "")
    goal_text = sc.get("goal", "")

    body = (f'<h1>Models <button id="rf-btn" class="rf-btn" onclick="toggleRefresh()">⏸ pause refresh</button></h1>'
            f'<section id="scores-summary"><details open><summary>Score Summary</summary>'
            f'{_render_models(snap)}</details></section>')

    for mid in all_models:
        score = scores.get(mid) or {}
        gs = round(score.get("global_score", 0), 3)
        gs_cls = "score-pos" if gs >= 0 else "score-neg"
        tickets_count = score.get("tickets") or 0

        # Tickets this model touched
        model_tids = sorted({cyc.get("ticket") for cyc in cycles.values()
                              if cyc.get("model") == mid and cyc.get("ticket")})
        ticket_parts = []
        for tid in model_tids:
            t = tickets.get(tid) or {}
            st = t.get("status", "?")
            tlink = f'<a href="tickets.html#t_{esc(tid)}">{esc(tid)}</a>'
            ticket_parts.append(f'{tlink} <span class="status-{esc(st)}">{esc(st)}</span>')
        tickets_html = ("<div class='evt small'>Tickets: " + " · ".join(ticket_parts) + "</div>"
                        if ticket_parts else "")

        # Environment: scenario name + goal + generated files
        goal_short = goal_text[:120] + ("…" if len(goal_text) > 120 else "")
        env_html = ""
        if sc_name:
            env_html = (f'<div class="evt small">Scenario: <b>{esc(sc_name)}</b>'
                        + (f' — {esc(goal_short)}' if goal_short else "") + "</div>")
        gen_files = files_by_model.get(mid, [])
        if gen_files:
            env_html += ("<div class='evt small'>Generated: "
                         + " ".join(f"<code>{esc(f)}</code>" for f in gen_files) + "</div>")

        # Cycles with full trace under collapsibles (кат)
        model_cycles = sorted([(cid, cyc) for cid, cyc in cycles.items() if cyc.get("model") == mid],
                               key=lambda x: x[0])
        cycles_html = ""
        for cid, cyc in model_cycles:
            tid = cyc.get("ticket", "")
            role = cyc.get("role", "?")
            cyc_status = cyc.get("status", "?")
            tid_link = f'<a href="tickets.html#t_{esc(tid)}">{esc(tid)}</a>' if tid else "<i>—</i>"
            cyc_link = f'<a href="index.html#exec_{esc(cid)}">{esc(cid[:14])}</a>'
            trace = _render_cycle_trace(log_by_cycle.get(cid, []))
            sum_txt = (f'▶ {cyc_link} · ticket {tid_link} · '
                       f'<span class="role-badge">{esc(role)}</span> · '
                       f'<span class="status-{esc(cyc_status)}">{esc(cyc_status)}</span>')
            cycles_html += (f'<details class="cyc"><summary>{sum_txt}</summary>'
                            f'<div style="margin-left:12px">{trace}</div></details>')
        if not cycles_html:
            cycles_html = "<i>no cycles recorded</i>"

        mid_slug = esc(mid.replace(":", "-").replace("/", "-").replace(".", "-"))
        body += (
            f'<section id="model-{mid_slug}">'
            f'<details open><summary>'
            f'<span class="model-badge">{esc(mid)}</span> · '
            f'score: <span class="{gs_cls}">{gs:+.3f}</span> · '
            f'tickets: {esc(tickets_count)}'
            f'</summary>'
            f'{env_html}{tickets_html}'
            f'<h3>Cycles &amp; Outputs</h3>'
            f'{cycles_html}'
            f'</details></section>'
        )

    if not all_models:
        body += "<i>No model activity yet.</i>"

    return _PAGE.format(title="Planfoldr — Models", refresh_meta=_refresh_meta(snap), nav=_NAV, body=body,
                        snapshot=json.dumps(snap, default=str), ws_port=ws_port or 0,
                        preserve=_PRESERVE_SCRIPT, script="", refresh_ms=REFRESH_SECONDS * 1000)


PAGES = {
    "index.html": render_stream_log_html,
    "state.html": render_state_view_html,
    "tickets.html": render_tickets_html,
    "kb.html": render_kb_html,
    "models.html": render_models_html,
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
        route = {
            "/": "index.html", "/state": "state.html", "/tickets": "tickets.html",
            "/kb": "kb.html", "/models": "models.html",
            "/index.html": "index.html", "/state.html": "state.html",
            "/tickets.html": "tickets.html", "/kb.html": "kb.html", "/models.html": "models.html",
        }

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
                elif page == "models.html":
                    self._send(render_models_html(ws_port=server.ws_port))
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


_NAV = ('<nav class="top"><a href="index.html">Streaming Log</a> · <a href="state.html">State</a> · '
        '<a href="tickets.html">Tickets</a> · <a href="kb.html">Knowledge Base</a> · '
        '<a href="models.html">Models</a></nav>')

_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
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
 /* prompt input & context */
 .model-input summary{{color:#6c7086;font-size:11px}} .model-input{{margin:2px 0 4px}}
 .pre-input{{background:#0d1117;border-radius:4px;padding:6px 8px;margin:2px 0 4px;white-space:pre-wrap;word-break:break-all;font-size:11px;color:#6c7086}}
 .model-ctx-row{{padding:2px 0;margin:2px 0;font-size:11px;color:#a6adc8}}
 .ctx-label{{color:#6c7086}} .ctx-key{{color:#6c7086;font-size:11px;white-space:nowrap;width:1%}}
 .action-badge{{background:#2a1e0a;color:#fab387;border:1px solid #3a2a0a;padding:0 4px;border-radius:3px;font-size:11px;margin-right:2px}}
 /* cycle footer */
 .cycle-footer{{border-left:2px solid #45475a;padding:2px 8px;margin:4px 0;font-size:11px;color:#a6adc8}}
 /* refresh toggle */
 .rf-btn{{background:#1a2a3a;border:1px solid #313244;color:#89b4fa;padding:2px 8px;border-radius:4px;cursor:pointer;font:12px ui-monospace,monospace;margin-left:8px;vertical-align:middle}}
 .rf-btn:hover{{background:#2a3a4a}}
 /* live status banner */
 .live-status{{border:1px solid #45475a;border-radius:6px;padding:6px 10px;margin:8px 0;background:#11151f;color:#f9e2af;font-size:12px}}
</style></head><body>
{nav}
{body}
<script>window.__SNAPSHOT__={snapshot};window.__WS_PORT__={ws_port};window.__LIVE__={refresh_meta};
{preserve}
{script}
var __rfTimer=null;
function _startRefresh(){{if(window.__LIVE__&&!__rfTimer)__rfTimer=setTimeout(function(){{location.reload();}},{refresh_ms});}}
function _stopRefresh(){{if(__rfTimer){{clearTimeout(__rfTimer);__rfTimer=null;}}}}
function toggleRefresh(){{
  var b=document.getElementById('rf-btn');
  if(__rfTimer){{
    _stopRefresh();
    b.textContent='▶ resume refresh';
    try{{sessionStorage.setItem('pf_rf_paused','1');}}catch(e){{}}
  }}else{{
    _startRefresh();
    b.textContent='⏸ pause refresh';
    try{{sessionStorage.removeItem('pf_rf_paused');}}catch(e){{}}
  }}
}}
(function(){{
  var paused=false;try{{paused=sessionStorage.getItem('pf_rf_paused')==='1';}}catch(e){{}}
  var b=document.getElementById('rf-btn');
  if(paused){{if(b)b.textContent='▶ resume refresh';}}
  else{{_startRefresh();}}
}})();
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
