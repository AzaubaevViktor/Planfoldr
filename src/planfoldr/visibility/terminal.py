"""Terminal streaming -- code-agent-style live output (Q08 minimal; enriched in Q09).

Renders the event stream as it happens: phases, model thinking/output, and tool calls with their
results. The orchestrator feeds this sink both audit events ({"event": "audit", ...}) and raw
cycle stream events (model chunks / tool results).
"""

from __future__ import annotations

import sys
from typing import Any, Dict, Optional, TextIO


_PHASE_ICON = {
    "context_exploration": "🧭", "changes": "✏️", "command_verification": "🧪",
    "model_verification": "⚖️",
}


class TerminalStream:
    def __init__(self, out: Optional[TextIO] = None, *, stream_thinking: bool = True) -> None:
        self.out = out or sys.stdout
        self.stream_thinking = stream_thinking
        self._last_kind: Optional[str] = None

    def sink(self, event: Dict[str, Any]) -> None:
        kind = event.get("event")
        if kind == "audit":
            self._audit(event)
        elif kind == "model_stream_chunk":
            self._chunk(event)
        elif kind == "tool_result":
            self._tool(event)

    # -- handlers -------------------------------------------------------------
    def _audit(self, e: Dict[str, Any]) -> None:
        et = e.get("event_type", "")
        p = e.get("payload", {})
        if et == "cycle.started":
            self._line(f"\n┌─ cycle {e.get('cycle_id','')[:14]}  ticket={e.get('ticket_id')}  model={p.get('model')}  role={p.get('role')}")
        elif et == "cycle.phase_completed":
            self._line(f"│  {_PHASE_ICON.get(p.get('phase'),'•')} phase: {p.get('phase')}")
        elif et == "cycle.completed":
            self._line(f"└─ cycle done → {p.get('status')}  spawned={p.get('spawned')}")
        elif et == "ticket.created":
            self._line(f"  + ticket {e.get('ticket_id')} [{p.get('type')}] {p.get('title')}")
        elif et == "ticket.status_changed":
            self._line(f"  ~ {e.get('ticket_id')}: {p.get('from')} → {p.get('to')}")
        elif et == "ticket.declined":
            self._line(f"  ✗ {e.get('ticket_id')} declined: {p.get('cause')}")
        elif et == "role.created":
            self._line(f"  ★ role {p.get('role')} ({p.get('decision')})")
        elif et == "budget.exceeded":
            self._line(f"  ! budget exceeded: {p.get('resource')} used={p.get('used')} limit={p.get('limit')}")
        elif et == "model.score_updated":
            self._line(f"  · score[{p.get('model')}] {p.get('delta'):+} ({','.join(p.get('reasons', []))})")
        elif et == "scenario.completed":
            self._line(f"\n══ scenario {p.get('status')} ══ {p.get('reason') or ''}")

    def _chunk(self, e: Dict[str, Any]) -> None:
        kind = e.get("kind")
        text = e.get("text", "")
        if kind == "thinking" and not self.stream_thinking:
            return
        if self._last_kind != kind:
            self.out.write(f"\n│  {'💭' if kind == 'thinking' else '📤'} ")
            self._last_kind = kind
        self.out.write(text)
        self.out.flush()

    def _tool(self, e: Dict[str, Any]) -> None:
        call = e.get("call", {})
        result = e.get("result", {})
        ec = result.get("exit_code")
        summary = result.get("path") or result.get("ticket_id") or (f"exit={ec}" if ec is not None else None)
        self._line(f"\n│  🔧 [{call.get('action')}] → {summary if summary is not None else _short(result)}")
        self._last_kind = None

    # -- util -----------------------------------------------------------------
    def _line(self, text: str) -> None:
        self.out.write(text + "\n")
        self.out.flush()
        self._last_kind = None


def _short(value: Any, limit: int = 120) -> str:
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "…"
