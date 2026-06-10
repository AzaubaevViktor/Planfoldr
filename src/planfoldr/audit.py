"""Audit (level 0).

Append-only trace log. Every significant event in the system is recorded here as an
immutable JSON line. Audit has no dependency on any other entity; everything depends on
it. It only records -- it never participates in business logic, never mutates anything,
and never blocks the main flow (writes are best-effort and a write failure is swallowed
so a full disk cannot stop the run or, critically, stop further auditing).

PHASE_3 / PHASE_4 references:
- Event types: ticket.created / status_changed / assigned, cycle.phase_completed,
  role.created, budget.exceeded, model.score_updated (and more).
- "Каждое событие атомарно записывается"; "Полный аудит сериализуется в JSON";
  "Возможен replay на уровне тикета"; "Не останавливается при budget_exceeded".
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from planfoldr.util import now_iso


class EventType:
    """Canonical event-type constants (PHASE_3 "Аудит" + PHASE_4 §12.5)."""

    TICKET_CREATED = "ticket.created"
    TICKET_STATUS_CHANGED = "ticket.status_changed"
    TICKET_ASSIGNED = "ticket.assigned"
    TICKET_DECLINED = "ticket.declined"
    TICKET_COMMENT_ADDED = "comment.added"

    CYCLE_STARTED = "cycle.started"
    CYCLE_PHASE_STARTED = "cycle.phase_started"
    CYCLE_PHASE_COMPLETED = "cycle.phase_completed"
    CYCLE_COMPLETED = "cycle.completed"

    ROLE_CREATED = "role.created"
    ROLE_SUMMONED = "role.summoned"

    QUEUE_CREATED = "queue.created"

    BUDGET_CONSUMED = "budget.consumed"
    BUDGET_EXCEEDED = "budget.exceeded"
    BUDGET_DELEGATED = "budget.delegated"

    MODEL_SELECTED = "model.selected"
    MODEL_SCORE_UPDATED = "model.score_updated"

    TOOL_INVOKED = "tool.invoked"
    TOOL_DENIED = "tool.denied"
    TOOLSET_CHANGED = "toolset.changed"

    KB_WRITTEN = "kb.written"
    GRAPH_LINK_ADDED = "graph.link_added"

    SCENARIO_STARTED = "scenario.started"
    SCENARIO_COMPLETED = "scenario.completed"

    HUMAN_REQUESTED = "human.requested"
    HUMAN_ANSWERED = "human.answered"
    MODEL_STREAM = "model.stream"


@dataclass(frozen=True)
class AuditEvent:
    seq: int
    timestamp: str
    event_type: str
    actor: Optional[str] = None
    ticket_id: Optional[str] = None
    cycle_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seq": self.seq,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "actor": self.actor,
            "ticket_id": self.ticket_id,
            "cycle_id": self.cycle_id,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEvent":
        return cls(
            seq=int(data["seq"]),
            timestamp=str(data["timestamp"]),
            event_type=str(data["event_type"]),
            actor=data.get("actor"),
            ticket_id=data.get("ticket_id"),
            cycle_id=data.get("cycle_id"),
            payload=dict(data.get("payload", {})),
        )


Subscriber = Callable[[AuditEvent], None]


class AuditLog:
    """Append-only event log with an in-memory mirror and live subscribers.

    Pass ``path`` to persist to ``audit.jsonl``; omit it for an in-memory log (tests).
    Subscribers receive each event as it is emitted -- this is the backbone of live
    Visibility streaming. Subscriber exceptions are isolated so observation can never
    break execution (Visibility is read-only and must not affect the run).
    """

    def __init__(self, path: Optional[Path | str] = None) -> None:
        self.path: Optional[Path] = Path(path) if path is not None else None
        self._events: List[AuditEvent] = []
        self._subscribers: List[Subscriber] = []
        self._seq = 0
        self._lock = threading.RLock()
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Truncate to start a fresh, deterministic log for this run.
            self.path.write_text("", encoding="utf-8")

    # -- emission -------------------------------------------------------------
    def emit(
        self,
        event_type: str,
        *,
        actor: Optional[str] = None,
        ticket_id: Optional[str] = None,
        cycle_id: Optional[str] = None,
        **payload: Any,
    ) -> AuditEvent:
        with self._lock:
            self._seq += 1
            event = AuditEvent(
                seq=self._seq,
                timestamp=now_iso(),
                event_type=event_type,
                actor=actor,
                ticket_id=ticket_id,
                cycle_id=cycle_id,
                payload=payload,
            )
            self._events.append(event)
            self._append_line(event)
        # Notify outside the lock; isolate subscriber failures.
        for subscriber in list(self._subscribers):
            try:
                subscriber(event)
            except Exception:  # noqa: BLE001 -- observation must never break execution
                pass
        return event

    def _append_line(self, event: AuditEvent) -> None:
        if self.path is None:
            return
        try:
            line = json.dumps(event.to_dict(), ensure_ascii=False, default=str)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            # Audit must not be the thing that crashes a run; keep the mirror only.
            pass

    # -- subscriptions --------------------------------------------------------
    def subscribe(self, subscriber: Subscriber) -> Callable[[], None]:
        self._subscribers.append(subscriber)

        def unsubscribe() -> None:
            if subscriber in self._subscribers:
                self._subscribers.remove(subscriber)

        return unsubscribe

    # -- reads ----------------------------------------------------------------
    def events(self) -> List[AuditEvent]:
        with self._lock:
            return list(self._events)

    def replay(self, ticket_id: str) -> List[AuditEvent]:
        """Reconstruct one ticket's history (PHASE_3 'Replay работает на уровне тикета')."""
        with self._lock:
            return [event for event in self._events if event.ticket_id == ticket_id]

    def to_list(self) -> List[Dict[str, Any]]:
        return [event.to_dict() for event in self.events()]

    @classmethod
    def read(cls, path: Path | str) -> List[AuditEvent]:
        events: List[AuditEvent] = []
        for raw in Path(path).read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if raw:
                events.append(AuditEvent.from_dict(json.loads(raw)))
        return events
