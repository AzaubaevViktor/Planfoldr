"""Birthgiver + registries + @human (level 4).

Birthgiver is the meta-role and the single point of extension of the role system. It analyses
missing specializations and -- via the exclusive ``create_role`` tool -- creates new roles, opens
queues and attaches roles to them. When a nonexistent ``@role`` is summoned, the request lands in
birthgiver's incoming as a ticket. Birthgiver may: link an existing role, refuse with a cause, or
create a new queue + manager + executor.

PHASE_3 "Создатель ролей" + PHASE_4 §7. Also defines the ``@human`` responder that services
``request_decision`` / ``request_context``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from planfoldr.audit import AuditLog, EventType
from planfoldr.graph import TicketGraph
from planfoldr.queue import Queue
from planfoldr.role import Executor, QueueManager, Role
from planfoldr.ticket import Ticket, new_ticket
from planfoldr.toolset import ToolRegistry, Toolset
from planfoldr.util import new_id


class RoleRegistry:
    def __init__(self) -> None:
        self.roles: Dict[str, Role] = {}

    def register(self, role: Role) -> None:
        self.roles[role.id] = role

    def has(self, role_id: str) -> bool:
        return role_id in self.roles

    def get(self, role_id: str) -> Role:
        return self.roles[role_id]

    def ids(self) -> List[str]:
        return list(self.roles)


class QueueRegistry:
    def __init__(self) -> None:
        self.queues: Dict[str, Queue] = {}

    def register(self, queue: Queue) -> None:
        self.queues[queue.id] = queue

    def has(self, queue_id: str) -> bool:
        return queue_id in self.queues

    def get(self, queue_id: str) -> Queue:
        return self.queues[queue_id]

    def ids(self) -> List[str]:
        return list(self.queues)


@dataclass
class BirthDecision:
    action: str            # "link" | "refuse" | "create"
    role_name: str
    cause: Optional[str] = None
    queue: Optional[Queue] = None
    roles: Optional[List[Role]] = None


class Birthgiver(Role):
    def __init__(
        self,
        *,
        tool_registry: ToolRegistry,
        role_registry: RoleRegistry,
        queue_registry: QueueRegistry,
        audit: AuditLog,
        graph: Optional[TicketGraph] = None,
        prompt: str = "You are the birthgiver. You create roles and queues only when justified.",
    ) -> None:
        super().__init__(
            "birthgiver",
            prompt=prompt,
            toolset=Toolset(["create_role"], registry=tool_registry, is_meta=True, owner="birthgiver"),
            can_create_ticket_types=["create_role"],
        )
        self.tool_registry = tool_registry
        self.role_registry = role_registry
        self.queue_registry = queue_registry
        self.audit = audit
        self.graph = graph

    # -- summon → incoming ticket --------------------------------------------
    def summon_ticket(self, role_name: str, *, requester: str, reason: str = "") -> Ticket:
        ticket = new_ticket(
            new_id("birth"), title=f"create role @{role_name}", type="create_role",
            goal=f"Decide whether role '{role_name}' is needed and create it if so.",
            created_by=requester, role="birthgiver", queue="orchestration", audit=self.audit,
        )
        self.audit.emit(EventType.ROLE_SUMMONED, ticket_id=ticket.id, actor=requester, role=role_name, reason=reason)
        return ticket

    # -- decision -------------------------------------------------------------
    def link_or_create(
        self,
        role_name: str,
        *,
        needed: bool = True,
        cause: str = "",
        prompt: str = "",
        domain_tools: Optional[List[str]] = None,
        can_create_ticket_types: Optional[List[str]] = None,
        budget_scope: Optional[Dict[str, float]] = None,
    ) -> BirthDecision:
        if self.role_registry.has(role_name) or self.role_registry.has(f"{role_name}-exec"):
            return BirthDecision(action="link", role_name=role_name)
        if not needed:
            self.audit.emit(EventType.ROLE_CREATED, actor="birthgiver", role=role_name,
                            decision="refused", cause=cause or "not needed")
            return BirthDecision(action="refuse", role_name=role_name, cause=cause or "not needed")
        queue, roles = self.create_role(
            role_name, prompt=prompt or f"You are the {role_name}.", domain_tools=domain_tools,
            can_create_ticket_types=can_create_ticket_types, budget_scope=budget_scope,
        )
        return BirthDecision(action="create", role_name=role_name, queue=queue, roles=roles)

    # -- the exclusive create_role capability --------------------------------
    def create_role(
        self,
        role_name: str,
        *,
        prompt: str,
        domain_tools: Optional[List[str]] = None,
        can_create_ticket_types: Optional[List[str]] = None,
        budget_scope: Optional[Dict[str, float]] = None,
        extra_prompt: str = "",
        extra_scope: Optional[List[str]] = None,
    ) -> tuple[Queue, List[Role]]:
        if role_name == "birthgiver":
            raise PermissionError("created roles may not recursively create a birthgiver")
        domain_tools = domain_tools or []
        for tool in domain_tools:
            if not self.tool_registry.has(tool):
                self.tool_registry.register(tool, audit=self.audit)
        queue_id = role_name
        manager = QueueManager(
            f"{role_name}-manager", prompt=f"You manage the {role_name} queue: triage, prioritize, decline.",
            toolset=Toolset([], registry=self.tool_registry), queue_id=queue_id, triage_prompt="prioritize by project goal",
        )
        executor = Executor(
            f"{role_name}-exec", prompt=prompt, toolset=Toolset(domain_tools, registry=self.tool_registry),
            can_create_ticket_types=can_create_ticket_types or [],
        )
        queue = Queue(
            id=queue_id, name=role_name, description=f"work for {role_name}", graph=self.graph, audit=self.audit,
            manager_role=manager.id, executor_roles=[executor.id], extra_prompt=extra_prompt,
            extra_scope=list(extra_scope or []), template={"budget": dict(budget_scope or {})},
        )
        self.role_registry.register(manager)
        self.role_registry.register(executor)
        self.queue_registry.register(queue)
        for role in (manager, executor):
            self.audit.emit(EventType.ROLE_CREATED, actor="birthgiver", role=role.id, kind=type(role).__name__,
                            queue=queue_id, decision="created")
        self.audit.emit(EventType.QUEUE_CREATED, actor="birthgiver", queue=queue_id,
                        roles=[manager.id, executor.id], budget_scope=dict(budget_scope or {}))
        return queue, [manager, executor]


def handle_create_role(args: Dict[str, Any], ctx: Any) -> Dict[str, Any]:
    """create_role tool handler -- only reachable from birthgiver's meta toolset + a ctx.birthgiver."""
    birthgiver: Birthgiver = getattr(ctx, "birthgiver", None)
    if birthgiver is None:
        raise PermissionError("create_role requires a birthgiver context")
    queue, roles = birthgiver.create_role(
        args["name"], prompt=args.get("prompt", f"You are the {args['name']}."),
        domain_tools=args.get("domain_tools"), can_create_ticket_types=args.get("can_create_ticket_types"),
        budget_scope=args.get("budget_scope"),
    )
    return {"queue": queue.id, "roles": [r.id for r in roles]}


class Human:
    """The @human role. Answers request_decision / request_context. `answers` may be a dict keyed
    by substring, a list consumed in order, or a callable; otherwise falls back to `default`."""

    def __init__(self, answers: Any = None, *, default: str = "", audit: Optional[AuditLog] = None,
                 interactive: bool = False) -> None:
        self.answers = answers
        self.default = default
        self.audit = audit
        self.interactive = interactive
        self._i = 0

    def __call__(self, question: str, kind: str = "decision") -> str:
        if self.audit is not None:
            self.audit.emit(EventType.HUMAN_REQUESTED, actor="@human", question=question, kind=kind)
        answer = self._lookup(question)
        if self.audit is not None:
            self.audit.emit(EventType.HUMAN_ANSWERED, actor="@human", question=question, answer=answer)
        return answer

    def _lookup(self, question: str) -> str:
        if callable(self.answers):
            return str(self.answers(question))
        if isinstance(self.answers, dict):
            for key, value in self.answers.items():
                if key.lower() in question.lower():
                    return str(value)
            return self.default
        if isinstance(self.answers, list):
            if self._i < len(self.answers):
                answer = self.answers[self._i]
                self._i += 1
                return str(answer)
            return self.default
        if self.interactive:  # pragma: no cover - real console
            try:
                return input(f"[@human] {question}\n> ")
            except EOFError:
                return self.default
        return self.default
