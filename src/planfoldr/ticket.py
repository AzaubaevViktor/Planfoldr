"""Ticket (level 2).

A ticket describes one run of the base cycle: a goal, the mandatory checks that prove the goal
is met, the evidence collected, the accesses/tools/budget granted, dependencies and history. It
is the first entity with a lifecycle and business rules, but it contains *no* execution logic --
only description and data.

PHASE_3 "Тикет как единица исполнения" + PHASE_4 §1:
- id `<role>-<num>`; status incoming → blocked/ready → running → done/failed/needs_review;
  needs_review → done.
- goal is immutable after creation.
- a ticket cannot declare itself done -- only by passing all mandatory checks (or a reviewer).
- a child ticket cannot close its parent.
- failed after N attempts → status failed (+ a difficulty-weighted model penalty applied by runtime).
- comments can summon a role via `@role`.
- fully JSON serializable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from planfoldr.audit import AuditLog, EventType
from planfoldr.util import now_iso


class Status:
    INCOMING = "incoming"
    IN_QUEUE = "in_queue"
    BLOCKED = "blocked"
    READY = "ready"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"
    DECLINED = "declined"
    CANCELLED = "cancelled"


TERMINAL = {Status.DONE, Status.FAILED, Status.CANCELLED}

VALID_TRANSITIONS: Dict[str, set] = {
    Status.INCOMING: {Status.IN_QUEUE, Status.DECLINED, Status.BLOCKED, Status.READY},
    Status.IN_QUEUE: {Status.BLOCKED, Status.READY, Status.DECLINED},
    Status.BLOCKED: {Status.READY, Status.CANCELLED},
    Status.READY: {Status.RUNNING, Status.BLOCKED},
    Status.RUNNING: {Status.DONE, Status.FAILED, Status.NEEDS_REVIEW, Status.BLOCKED},
    Status.NEEDS_REVIEW: {Status.DONE, Status.FAILED, Status.RUNNING},
    Status.DECLINED: {Status.INCOMING},
    Status.DONE: set(),
    Status.FAILED: set(),
    Status.CANCELLED: set(),
}


class TicketTransitionError(Exception):
    pass


@dataclass
class Check:
    kind: str  # "command" | "model"
    spec: str  # the command line, or the model-verification criterion
    required: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "spec": self.spec, "required": self.required}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Check":
        spec = d["spec"]
        if isinstance(spec, str) and spec.startswith("$ "):
            spec = spec[2:]
        return cls(kind=d["kind"], spec=spec, required=bool(d.get("required", True)))


@dataclass
class Comment:
    author: str
    text: str
    timestamp: str = field(default_factory=now_iso)
    summoned_role: Optional[str] = None  # the `@role` called by this comment

    def to_dict(self) -> Dict[str, Any]:
        return {
            "author": self.author,
            "text": self.text,
            "timestamp": self.timestamp,
            "summoned_role": self.summoned_role,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Comment":
        return cls(
            author=d["author"], text=d["text"],
            timestamp=d.get("timestamp", now_iso()), summoned_role=d.get("summoned_role"),
        )


@dataclass
class Ticket:
    id: str
    title: str
    type: str
    _goal: str
    status: str = Status.INCOMING
    checks: List[Check] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    accesses: List[Dict[str, Any]] = field(default_factory=list)
    budget: Dict[str, float] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    role: Optional[str] = None
    queue: Optional[str] = None
    priority: int = 0
    decline_cause: Optional[str] = None
    spawned_by: Optional[str] = None
    attempt_count: int = 0
    max_attempts: int = 3
    difficulty: float = 0.5
    comments: List[Comment] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # -- goal is immutable after creation ------------------------------------
    @property
    def goal(self) -> str:
        return self._goal

    @goal.setter
    def goal(self, value: str) -> None:  # pragma: no cover - guard
        raise TicketTransitionError("ticket goal is immutable after creation")

    # -- checks / evidence ----------------------------------------------------
    def add_evidence(self, *, check_index: Optional[int], status: str, proof: str) -> None:
        self.evidence.append({
            "check_index": check_index,
            "status": status,
            "proof": proof,
            "timestamp": now_iso(),
        })

    def required_checks(self) -> List[int]:
        return [i for i, c in enumerate(self.checks) if c.required]

    def checks_passed(self) -> bool:
        """Every required check has at least one passing evidence entry.

        With no mandatory checks there is nothing mechanical to pass, so completion must come
        through an explicit reviewer/model proof instead -- hence False here."""
        required = self.required_checks()
        if not required:
            return False
        passed_idx = {e["check_index"] for e in self.evidence if e.get("status") == "success"}
        return all(i in passed_idx for i in required)

    # -- lifecycle ------------------------------------------------------------
    def transition(
        self,
        to: str,
        *,
        actor: str,
        audit: Optional[AuditLog] = None,
        proof: Optional[str] = None,
        cause: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        allowed = VALID_TRANSITIONS.get(self.status, set())
        if to not in allowed:
            raise TicketTransitionError(f"{self.id}: illegal transition {self.status} → {to}")
        if to == Status.DONE and not (self.checks_passed() or proof):
            # Cannot self-complete: needs all mandatory checks passed, or an explicit reviewer proof.
            raise TicketTransitionError(
                f"{self.id}: cannot move to done without passing mandatory checks or a reviewer proof"
            )
        if to == Status.DECLINED and not cause:
            raise TicketTransitionError(f"{self.id}: declined requires a cause")
        frm = self.status
        self.status = to
        if to == Status.DECLINED:
            self.decline_cause = cause
        self.metadata.setdefault("change_history", []).append({
            "from": frm, "to": to, "actor": actor, "model": model, "at": now_iso(), "proof": proof, "cause": cause,
        })
        if audit is not None:
            audit.emit(
                EventType.TICKET_STATUS_CHANGED,
                ticket_id=self.id, actor=actor,
                **{"from": frm, "to": to, "proof": proof, "cause": cause},
            )

    def record_attempt(self) -> int:
        self.attempt_count += 1
        return self.attempt_count

    def exhausted_attempts(self) -> bool:
        return self.attempt_count >= self.max_attempts

    # -- comments / summons ---------------------------------------------------
    def add_comment(
        self,
        *,
        author: str,
        text: str,
        summon: Optional[str] = None,
        audit: Optional[AuditLog] = None,
    ) -> Comment:
        comment = Comment(author=author, text=text, summoned_role=summon)
        self.comments.append(comment)
        if audit is not None:
            audit.emit(
                EventType.TICKET_COMMENT_ADDED,
                ticket_id=self.id, actor=author, summoned_role=summon, text=text,
            )
            if summon:
                audit.emit(EventType.ROLE_SUMMONED, ticket_id=self.id, actor=author, role=summon)
        return comment

    # -- serialization --------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "goal": self._goal,
            "status": self.status,
            "checks": [c.to_dict() for c in self.checks],
            "evidence": list(self.evidence),
            "accesses": list(self.accesses),
            "budget": dict(self.budget),
            "dependencies": list(self.dependencies),
            "tools": list(self.tools),
            "role": self.role,
            "queue": self.queue,
            "priority": self.priority,
            "decline_cause": self.decline_cause,
            "spawned_by": self.spawned_by,
            "attempt_count": self.attempt_count,
            "max_attempts": self.max_attempts,
            "difficulty": self.difficulty,
            "comments": [c.to_dict() for c in self.comments],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Ticket":
        return cls(
            id=d["id"], title=d["title"], type=d["type"], _goal=d["goal"],
            status=d.get("status", Status.INCOMING),
            checks=[Check.from_dict(c) for c in d.get("checks", [])],
            evidence=list(d.get("evidence", [])),
            accesses=list(d.get("accesses", [])),
            budget=dict(d.get("budget", {})),
            dependencies=list(d.get("dependencies", [])),
            tools=list(d.get("tools", [])),
            role=d.get("role"), queue=d.get("queue"), priority=int(d.get("priority", 0)),
            decline_cause=d.get("decline_cause"), spawned_by=d.get("spawned_by"),
            attempt_count=int(d.get("attempt_count", 0)), max_attempts=int(d.get("max_attempts", 3)),
            difficulty=float(d.get("difficulty", 0.5)),
            comments=[Comment.from_dict(c) for c in d.get("comments", [])],
            metadata=dict(d.get("metadata", {})),
        )


def new_ticket(
    ticket_id: str,
    *,
    title: str,
    type: str,
    goal: str,
    created_by: str,
    audit: Optional[AuditLog] = None,
    reason: Optional[str] = None,
    **kwargs: Any,
) -> Ticket:
    """Factory that stamps creation metadata and emits ticket.created (with actor, reason,
    spawned_by -- PHASE_3 'Динамическое создание тикетов')."""
    ticket = Ticket(id=ticket_id, title=title, type=type, _goal=goal, **kwargs)
    ticket.metadata.setdefault("created_by", created_by)
    ticket.metadata.setdefault("created_at", now_iso())
    ticket.metadata.setdefault("change_history", [])
    if reason:
        ticket.metadata["reason"] = reason
    if audit is not None:
        audit.emit(
            EventType.TICKET_CREATED,
            ticket_id=ticket_id, actor=created_by,
            type=type, title=title, goal=goal, spawned_by=ticket.spawned_by, reason=reason,
        )
    return ticket


def child_closing_parent(parent: Ticket, actor: Ticket, to_status: str) -> bool:
    """True if `actor` (spawned by `parent`) is trying to move `parent` to a terminal state.
    A child cycle may update its own ticket but cannot close the parent (PHASE_3 cycle nesting)."""
    return to_status in TERMINAL and actor.spawned_by == parent.id and actor.id != parent.id
