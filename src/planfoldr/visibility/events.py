"""Visibility state aggregation (level 6).

Consumes the orchestrator's event stream (audit events + raw cycle stream events) and maintains a
live, read-only snapshot organized into the slices PHASE_3 requires for the State View:
queues / tickets / models / commands / tools / cycles / cycle tree / system / budgets -- plus a
streaming log buffer for the Streaming Log page. It never mutates execution state.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

SLICES = ["queues", "tickets", "models", "commands", "tools", "cycles", "cycle_tree", "system", "budgets"]

_MAX_LOG = 5000


class VisibilityState:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.tickets: Dict[str, Dict[str, Any]] = {}
        self.queues: Dict[str, Dict[str, Any]] = {}
        self.models: Dict[str, Dict[str, Any]] = {}
        self.commands: List[Dict[str, Any]] = []
        self.tools: Dict[str, int] = {}
        self.cycles: Dict[str, Dict[str, Any]] = {}
        self.budgets: Dict[str, Any] = {}
        self.system: Dict[str, Any] = {"scenario": None, "status": "running", "cycles": 0}
        self.log: List[Dict[str, Any]] = []

    # -- ingest ---------------------------------------------------------------
    def ingest(self, event: Dict[str, Any]) -> None:
        with self._lock:
            kind = event.get("event")
            if kind == "audit":
                self._audit(event)
            elif kind == "model_output":
                self._model_output(event)
            elif kind == "model_stream_chunk":
                self._live_chunk(event)  # live preview only -- not stored in the persisted log
            elif kind == "tool_result":
                self._append_log({"type": kind, **event})

    def _model_output(self, e: Dict[str, Any]) -> None:
        cid = e.get("cycle_id")
        entry = {"phase": e.get("phase"), "model": e.get("model"), "thinking": e.get("thinking", ""),
                 "content": e.get("content", ""), "tokens": e.get("tokens")}
        cyc = self.cycles.get(cid)
        if cyc is not None:
            cyc.setdefault("outputs", []).append(entry)
        # Full output goes to the persisted log (one entry per model call -- start is never dropped).
        self._append_log({"type": "model_output", "cycle_id": cid, "ticket_id": e.get("ticket_id"), **entry})

    def _audit(self, e: Dict[str, Any]) -> None:
        et = e.get("event_type", "")
        p = e.get("payload", {})
        tid = e.get("ticket_id")
        cid = e.get("cycle_id")
        if et == "scenario.started":
            self.system.update({"scenario": p.get("scenario"), "goal": p.get("goal"), "status": "running"})
        elif et == "scenario.completed":
            self.system.update({"status": p.get("status"), "reason": p.get("reason")})
        elif et == "ticket.created":
            self.tickets[tid] = {"id": tid, "type": p.get("type"), "title": p.get("title"),
                                 "status": "incoming", "spawned_by": p.get("spawned_by"), "evidence": 0}
        elif et == "ticket.status_changed" and tid in self.tickets:
            self.tickets[tid]["status"] = p.get("to")
            self._reindex_queue(tid)
        elif et == "ticket.assigned" and tid in self.tickets:
            self.tickets[tid].update({"role": p.get("role"), "model": p.get("model")})
        elif et == "queue.created":
            self.queues[p.get("queue")] = {"id": p.get("queue"), "roles": p.get("roles", []), "tickets": {}}
        elif et == "cycle.started":
            self.cycles[cid] = {"id": cid, "ticket": tid, "model": p.get("model"), "role": p.get("role"),
                                "parent": p.get("parent_cycle_id"), "phase": None, "status": "running",
                                "stream": ""}
        elif et == "cycle.phase_completed" and cid in self.cycles:
            self.cycles[cid]["phase"] = p.get("phase")
            if isinstance(p.get("budget"), dict):
                self.budgets[cid] = p["budget"]
        elif et == "cycle.completed" and cid in self.cycles:
            self.cycles[cid].update({"status": p.get("status"), "spawned": p.get("spawned", [])})
            self.system["cycles"] = self.system.get("cycles", 0) + 1
            if isinstance(p.get("budget"), dict):
                self.budgets[cid] = p["budget"]
        elif et == "model.selected":
            m = self.models.setdefault(p.get("model"), {"id": p.get("model"), "selected": 0, "tokens": 0})
            m["selected"] += 1
        elif et == "model.score_updated":
            m = self.models.setdefault(p.get("model"), {"id": p.get("model"), "selected": 0, "tokens": 0})
            m.update({"global_score": p.get("global_score"), "last_delta": p.get("delta")})
        elif et == "model.stream":
            m = self.models.setdefault(p.get("model"), {"id": p.get("model"), "selected": 0, "tokens": 0})
            m["tokens"] = m.get("tokens", 0) + (p.get("tokens") or 0)
        elif et == "tool.invoked":
            name = p.get("tool")
            self.tools[name] = self.tools.get(name, 0) + 1
            if name in ("bash", "command_verification") or p.get("scope") == "command_verification":
                args = p.get("args") or {}
                result = p.get("result") or {}
                self.commands.append({
                    "ticket": tid,
                    "actor": e.get("actor"),
                    "when": e.get("timestamp"),
                    "cmd": args.get("cmd") or args.get("command") or args,
                    "exit_code": result.get("exit_code"),
                    "status": result.get("status"),
                })
        elif et == "budget.exceeded":
            self.budgets["exceeded"] = {"resource": p.get("resource"), "limit": p.get("limit"), "used": p.get("used")}
        # Everything also lands in the streaming log.
        self._append_log({"type": "audit", "event_type": et, "ticket_id": tid, "cycle_id": cid, "payload": p,
                          "seq": e.get("seq"), "timestamp": e.get("timestamp")})

    def _reindex_queue(self, tid: str) -> None:
        ticket = self.tickets.get(tid, {})
        # queue membership is tracked lazily from ticket.queue if present in later snapshots.

    def _append_log(self, entry: Dict[str, Any]) -> None:
        self.log.append(entry)
        if len(self.log) > _MAX_LOG:
            del self.log[: len(self.log) - _MAX_LOG]

    def _live_chunk(self, event: Dict[str, Any]) -> None:
        # Live token preview for the currently running cycle (drill-down); the canonical full output
        # is captured per call via model_output, so nothing is lost even if this preview is bounded.
        if event.get("kind") != "content":
            return
        cid = event.get("cycle_id")
        cyc = self.cycles.get(cid)
        if cyc is not None:
            cyc["live"] = (cyc.get("live", "") + event.get("text", ""))[-4000:]

    # -- snapshot -------------------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            tickets_by_queue: Dict[str, Dict[str, List[str]]] = {}
            for t in self.tickets.values():
                q = t.get("queue") or "_"
                tickets_by_queue.setdefault(q, {}).setdefault(t.get("status", "?"), []).append(t["id"])
            cycle_tree = self._cycle_tree()
            return {
                "queues": self.queues,
                "tickets": self.tickets,
                "tickets_by_queue": tickets_by_queue,
                "models": self.models,
                "commands": self.commands[-100:],
                "tools": self.tools,
                "cycles": self.cycles,
                "cycle_tree": cycle_tree,
                "system": self.system,
                "budgets": self.budgets,
            }

    def _cycle_tree(self) -> List[Dict[str, Any]]:
        children: Dict[Optional[str], List[str]] = {}
        for cid, c in self.cycles.items():
            children.setdefault(c.get("parent"), []).append(cid)

        def build(cid: str) -> Dict[str, Any]:
            node = dict(self.cycles[cid])
            node["children"] = [build(x) for x in children.get(cid, [])]
            return node

        return [build(cid) for cid in children.get(None, [])]

    def recent_log(self, limit: int = 500) -> List[Dict[str, Any]]:
        with self._lock:
            return self.log[-limit:]
