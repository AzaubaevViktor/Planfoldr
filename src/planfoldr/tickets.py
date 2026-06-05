"""Deterministic ticket-tree helpers for orchestration state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional


TICKET_TYPES = {
    "research",
    "documentation",
    "code",
    "tests",
    "manual_testing",
    "verification",
    "orchestration",
}

TICKET_STATUSES = {
    "blocked",
    "ready",
    "running",
    "needs_review",
    "done",
    "failed",
    "cancelled",
}


@dataclass(frozen=True)
class Ticket:
    id: str
    title: str
    description: str
    type: str
    dependencies: List[str] = field(default_factory=list)
    status: str = "blocked"
    owner: Optional[Dict[str, Any]] = None
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "type": self.type,
            "dependencies": list(self.dependencies),
            "status": self.status,
            "owner": self.owner,
            "evidence": list(self.evidence),
            "artifacts": list(self.artifacts),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Ticket":
        return cls(
            id=str(value["id"]),
            title=str(value["title"]),
            description=str(value.get("description", "")),
            type=str(value["type"]),
            dependencies=[str(item) for item in value.get("dependencies", [])],
            status=str(value.get("status", "blocked")),
            owner=dict(value["owner"]) if isinstance(value.get("owner"), Mapping) else None,
            evidence=[dict(item) for item in value.get("evidence", [])],
            artifacts=[dict(item) for item in value.get("artifacts", [])],
        )


@dataclass(frozen=True)
class TicketTree:
    tickets: Dict[str, Ticket] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"tickets": [ticket.to_dict() for ticket in self.tickets.values()]}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TicketTree":
        tickets = [Ticket.from_dict(item) for item in value.get("tickets", [])]
        return cls(tickets={ticket.id: ticket for ticket in tickets})


def create_ticket(
    *,
    ticket_id: str,
    title: str,
    description: str,
    ticket_type: str,
    dependencies: Optional[Iterable[str]] = None,
) -> Ticket:
    _validate_ticket_type(ticket_type)
    deps = [str(item) for item in dependencies or []]
    return Ticket(
        id=ticket_id,
        title=title,
        description=description,
        type=ticket_type,
        dependencies=deps,
        status="blocked" if deps else "ready",
    )


def add_ticket(tree: TicketTree, ticket: Ticket) -> TicketTree:
    if ticket.id in tree.tickets:
        raise ValueError(f"Ticket '{ticket.id}' already exists")
    _validate_ticket(ticket)
    tickets = dict(tree.tickets)
    tickets[ticket.id] = _with_dependency_status(ticket, tickets)
    return TicketTree(tickets=tickets)


def set_ticket_status(
    tree: TicketTree,
    ticket_id: str,
    status: str,
    *,
    evidence: Optional[Iterable[Mapping[str, Any]]] = None,
    owner: Optional[Mapping[str, Any]] = None,
) -> TicketTree:
    _validate_status(status)
    ticket = _require_ticket(tree, ticket_id)
    updated = Ticket(
        id=ticket.id,
        title=ticket.title,
        description=ticket.description,
        type=ticket.type,
        dependencies=list(ticket.dependencies),
        status=status,
        owner=dict(owner) if owner is not None else ticket.owner,
        evidence=[dict(item) for item in evidence] if evidence is not None else list(ticket.evidence),
        artifacts=list(ticket.artifacts),
    )
    tickets = dict(tree.tickets)
    tickets[ticket_id] = updated
    return refresh_readiness(TicketTree(tickets=tickets))


def refresh_readiness(tree: TicketTree) -> TicketTree:
    tickets = dict(tree.tickets)
    for ticket_id, ticket in list(tickets.items()):
        tickets[ticket_id] = _with_dependency_status(ticket, tickets)
    return TicketTree(tickets=tickets)


def ready_ticket_ids(tree: TicketTree) -> List[str]:
    return [ticket.id for ticket in tree.tickets.values() if ticket.status == "ready"]


def _with_dependency_status(ticket: Ticket, tickets: Mapping[str, Ticket]) -> Ticket:
    if ticket.status in {"running", "needs_review", "done", "failed", "cancelled"}:
        return ticket
    status = "ready" if _dependencies_done(ticket, tickets) else "blocked"
    if status == ticket.status:
        return ticket
    return Ticket(
        id=ticket.id,
        title=ticket.title,
        description=ticket.description,
        type=ticket.type,
        dependencies=list(ticket.dependencies),
        status=status,
        owner=ticket.owner,
        evidence=list(ticket.evidence),
        artifacts=list(ticket.artifacts),
    )


def _dependencies_done(ticket: Ticket, tickets: Mapping[str, Ticket]) -> bool:
    for dependency in ticket.dependencies:
        if tickets.get(dependency, Ticket("", "", "", "research")).status != "done":
            return False
    return True


def _require_ticket(tree: TicketTree, ticket_id: str) -> Ticket:
    try:
        return tree.tickets[ticket_id]
    except KeyError as exc:
        raise KeyError(f"Ticket '{ticket_id}' does not exist") from exc


def _validate_ticket(ticket: Ticket) -> None:
    _validate_ticket_type(ticket.type)
    _validate_status(ticket.status)


def _validate_ticket_type(ticket_type: str) -> None:
    if ticket_type not in TICKET_TYPES:
        raise ValueError(f"Unknown ticket type '{ticket_type}'")


def _validate_status(status: str) -> None:
    if status not in TICKET_STATUSES:
        raise ValueError(f"Unknown ticket status '{status}'")
