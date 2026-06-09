"""Queue (level 3).

Groups tickets by direction of work and routes them to roles. A queue holds tickets in various
statuses and supports parallel processing. It does not execute tickets, does not change their
goals, and does not manage budgets.

PHASE_3 "Очереди" + PHASE_4 §4/§5:
- fields: id, name, description, roles (manager + executors), tickets by status, template,
  extra_prompt, extra_scope.
- QueueManager triage: incoming → in_queue (priority) OR declined (cause); declined is visible
  only to the manager.
- a ticket becomes ready when its blocked_by deps are done (via the Ticket Graph).
- executors take the highest-priority ready ticket; several executors can take independent
  tickets in parallel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from planfoldr.audit import AuditLog, EventType
from planfoldr.graph import TicketGraph
from planfoldr.ticket import Status, Ticket


@dataclass
class Queue:
    id: str
    name: str
    description: str = ""
    graph: Optional[TicketGraph] = None
    audit: Optional[AuditLog] = None
    manager_role: Optional[str] = None
    executor_roles: List[str] = field(default_factory=list)
    template: Dict[str, Any] = field(default_factory=dict)
    extra_prompt: str = ""
    extra_scope: List[str] = field(default_factory=list)
    tickets: Dict[str, Ticket] = field(default_factory=dict)
    _order: List[str] = field(default_factory=list)

    # -- intake ---------------------------------------------------------------
    def add(self, ticket: Ticket) -> None:
        ticket.queue = self.id
        self.tickets[ticket.id] = ticket
        self._order.append(ticket.id)
        if self.graph is not None and ticket.id not in {n["id"] for n in self.graph.to_dict()["nodes"]}:
            self.graph.add_ticket(ticket)

    # -- triage (QueueManager) ------------------------------------------------
    def accept(self, ticket_id: str, *, priority: int = 0, actor: str = "manager") -> None:
        ticket = self.tickets[ticket_id]
        ticket.priority = priority
        ticket.transition(Status.IN_QUEUE, actor=actor, audit=self.audit)
        self._settle_readiness(ticket, actor=actor)

    def decline(self, ticket_id: str, *, cause: str, actor: str = "manager") -> None:
        ticket = self.tickets[ticket_id]
        ticket.transition(Status.DECLINED, actor=actor, audit=self.audit, cause=cause)
        if self.audit is not None:
            self.audit.emit(EventType.TICKET_DECLINED, ticket_id=ticket_id, actor=actor, cause=cause)

    def _settle_readiness(self, ticket: Ticket, *, actor: str) -> None:
        if self.graph is not None and self.graph.is_ready(ticket.id):
            ticket.transition(Status.READY, actor=actor, audit=self.audit)
        else:
            ticket.transition(Status.BLOCKED, actor=actor, audit=self.audit)

    def refresh_ready(self, *, actor: str = "runtime") -> List[str]:
        """Promote blocked tickets whose deps are now done. Returns the ids newly made ready."""
        promoted: List[str] = []
        if self.graph is None:
            return promoted
        for ticket_id in self._order:
            ticket = self.tickets[ticket_id]
            if ticket.status == Status.BLOCKED and self.graph.is_ready(ticket_id):
                ticket.transition(Status.READY, actor=actor, audit=self.audit)
                promoted.append(ticket_id)
        return promoted

    # -- views ----------------------------------------------------------------
    def list_for_executor(self) -> List[Ticket]:
        """Executors never see declined tickets (declined is manager-only)."""
        return [
            self.tickets[i] for i in self._order
            if self.tickets[i].status == Status.READY
        ]

    def list_for_manager(self) -> List[Ticket]:
        return [self.tickets[i] for i in self._order]

    def incoming(self) -> List[Ticket]:
        return [self.tickets[i] for i in self._order if self.tickets[i].status == Status.INCOMING]

    def declined(self) -> List[Ticket]:
        return [self.tickets[i] for i in self._order if self.tickets[i].status == Status.DECLINED]

    # -- dispatch -------------------------------------------------------------
    def get_next(self) -> Optional[Ticket]:
        """Highest-priority ready ticket; ties broken by intake order (FIFO)."""
        ready = self.list_for_executor()
        if not ready:
            return None
        return max(ready, key=lambda t: (t.priority, -self._order.index(t.id)))

    def to_dict(self) -> Dict[str, Any]:
        by_status: Dict[str, List[str]] = {}
        for tid in self._order:
            by_status.setdefault(self.tickets[tid].status, []).append(tid)
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "manager_role": self.manager_role,
            "executor_roles": list(self.executor_roles),
            "template": dict(self.template),
            "extra_prompt": self.extra_prompt,
            "extra_scope": list(self.extra_scope),
            "tickets_by_status": by_status,
        }
