"""Ticket Graph (level 3).

Stores the real dependency/spawn structure between tickets as an append-only set of typed links.
It is the single source of truth for "who spawned what, who blocks whom, who is evidence for
whom". It only reflects state -- it never drives execution.

PHASE_3 "Граф тикетов" + PHASE_4 §11. Link types:
- spawned_by   — who/when created this ticket
- blocks       — this ticket blocks another
- blocked_by   — this ticket is blocked by another (from dependencies)
- related_to   — soft informational link
- evidence_for — this ticket provides proof for another
- escalates    — this ticket escalates a problem from another

Rules: spawned_by is added automatically on create; `is_ready` is True when all blocked_by deps
are done; blocked_by/blocks must stay acyclic (deadlock prevention); links are append-only and
never deleted (history is immutable); every link is a `graph.link_added` trace event.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from planfoldr.audit import AuditLog, EventType
from planfoldr.ticket import Status, Ticket
from planfoldr.util import now_iso


SPAWNED_BY = "spawned_by"
BLOCKS = "blocks"
BLOCKED_BY = "blocked_by"
RELATED_TO = "related_to"
EVIDENCE_FOR = "evidence_for"
ESCALATES = "escalates"

LINK_TYPES = {SPAWNED_BY, BLOCKS, BLOCKED_BY, RELATED_TO, EVIDENCE_FOR, ESCALATES}


class GraphCycleError(Exception):
    pass


@dataclass
class Link:
    src: str
    type: str
    dst: str
    actor: Optional[str] = None
    reason: Optional[str] = None
    timestamp: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "src": self.src, "type": self.type, "dst": self.dst,
            "actor": self.actor, "reason": self.reason, "timestamp": self.timestamp,
        }


class TicketGraph:
    def __init__(self, audit: Optional[AuditLog] = None) -> None:
        self.audit = audit
        self._tickets: Dict[str, Ticket] = {}
        self._links: List[Link] = []  # append-only

    # -- nodes ----------------------------------------------------------------
    def add_ticket(
        self,
        ticket: Ticket,
        *,
        spawned_by: Optional[str] = None,
        actor: Optional[str] = None,
    ) -> None:
        self._tickets[ticket.id] = ticket
        parent = spawned_by or ticket.spawned_by
        if parent:
            ticket.spawned_by = parent
            self.add_link(ticket.id, SPAWNED_BY, parent, actor=actor or "runtime", reason="created")
        for dep in ticket.dependencies:
            self.add_link(ticket.id, BLOCKED_BY, dep, actor=actor or "runtime", reason="dependency")

    def status_of(self, ticket_id: str) -> Optional[str]:
        t = self._tickets.get(ticket_id)
        return t.status if t else None

    # -- links (append-only) --------------------------------------------------
    def add_link(
        self,
        src: str,
        link_type: str,
        dst: str,
        *,
        actor: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Link:
        if link_type not in LINK_TYPES:
            raise ValueError(f"unknown link type '{link_type}'")
        if link_type in (BLOCKED_BY, BLOCKS):
            self._guard_acyclic(src, link_type, dst)
        link = Link(src=src, type=link_type, dst=dst, actor=actor, reason=reason)
        self._links.append(link)
        # Maintain the inverse for blocks/blocked_by so both directions are queryable.
        if link_type == BLOCKED_BY:
            self._links.append(Link(src=dst, type=BLOCKS, dst=src, actor=actor, reason=reason, timestamp=link.timestamp))
        elif link_type == BLOCKS:
            self._links.append(Link(src=dst, type=BLOCKED_BY, dst=src, actor=actor, reason=reason, timestamp=link.timestamp))
        if self.audit is not None:
            self.audit.emit(
                EventType.GRAPH_LINK_ADDED, ticket_id=src, actor=actor,
                link_type=link_type, dst=dst, reason=reason,
            )
        return link

    def _guard_acyclic(self, src: str, link_type: str, dst: str) -> None:
        # Normalize to a blocked_by edge src→dst (src is blocked by dst).
        a, b = (src, dst) if link_type == BLOCKED_BY else (dst, src)
        if a == b:
            raise GraphCycleError(f"ticket '{a}' cannot block itself")
        # Adding a (blocked_by) b creates a cycle iff a is already (transitively) blocking b,
        # i.e. b is reachable from a via blocked_by.
        if self._reaches_via_blocked_by(b, a):
            raise GraphCycleError(f"blocked_by {a}→{b} would create a dependency cycle")

    def _reaches_via_blocked_by(self, start: str, target: str) -> bool:
        seen: set[str] = set()
        stack = [start]
        while stack:
            node = stack.pop()
            if node == target:
                return True
            if node in seen:
                continue
            seen.add(node)
            stack.extend(self.blocked_by(node))
        return False

    # -- queries --------------------------------------------------------------
    def links_of_type(self, link_type: str) -> List[Link]:
        return [l for l in self._links if l.type == link_type]

    def blocked_by(self, ticket_id: str) -> List[str]:
        return [l.dst for l in self._links if l.type == BLOCKED_BY and l.src == ticket_id]

    def blocks(self, ticket_id: str) -> List[str]:
        return [l.dst for l in self._links if l.type == BLOCKS and l.src == ticket_id]

    def dependents_of(self, ticket_id: str) -> List[str]:
        """Tickets that are blocked_by `ticket_id` (i.e. become unblocked when it finishes)."""
        return [l.src for l in self._links if l.type == BLOCKED_BY and l.dst == ticket_id]

    def related(self, ticket_id: str, link_type: str) -> List[str]:
        return [l.dst for l in self._links if l.type == link_type and l.src == ticket_id]

    def is_ready(self, ticket_id: str) -> bool:
        deps = self.blocked_by(ticket_id)
        return all(self.status_of(dep) == Status.DONE for dep in deps)

    def replay(self, ticket_id: str) -> List[Link]:
        return [l for l in self._links if l.src == ticket_id or l.dst == ticket_id]

    # -- serialization / visualization ---------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [
                {
                    "id": t.id, "type": t.type, "title": t.title, "status": t.status,
                    "spawned_by": t.spawned_by, "role": t.role, "queue": t.queue,
                }
                for t in self._tickets.values()
            ],
            "links": [l.to_dict() for l in self._links],
        }

    def report_data(self) -> Dict[str, Any]:
        return self.to_dict()
