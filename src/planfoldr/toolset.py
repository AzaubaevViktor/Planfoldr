"""Toolset (level 0).

Defines the set of tools available to a role inside a cycle, split into base tools
(every role has them), domain tools (role-specific) and meta tools (``create_role`` --
birthgiver only). The toolset enforces least privilege: a role cannot invoke a tool
outside its allow-list, and an attempt is recorded as a trace event and refused.

PHASE_3 "Базовые инструменты роли (toolset)" + PHASE_4 §15:
- base: read_context, write_context, create_ticket, update_ticket, request_context,
  request_decision
- domain: bash, file_edit, ... (declared per role)
- meta: create_role (birthgiver only)
- "Вызов неразрешённого инструмента → trace event + отказ"
- "Toolset документирован и версионирован"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Set

from planfoldr.audit import AuditLog, EventType


# Tool scopes.
BASE = "base"
DOMAIN = "domain"
META = "meta"

BASE_TOOLS: Set[str] = {
    "read_context",
    "write_context",
    "create_ticket",
    "update_ticket",
    "request_context",
    "request_decision",
}
META_TOOLS: Set[str] = {"create_role"}


class ToolDenied(Exception):
    """Raised when a role invokes a tool outside its toolset."""

    def __init__(self, tool: str, reason: str) -> None:
        super().__init__(f"tool '{tool}' denied: {reason}")
        self.tool = tool
        self.reason = reason


# A handler receives the call arguments and a runtime context object, returns a result
# dict. Context is opaque here -- bound by the cycle/orchestrator at runtime.
ToolHandler = Callable[[Dict[str, Any], Any], Dict[str, Any]]


@dataclass
class ToolSpec:
    name: str
    scope: str
    description: str
    handler: Optional[ToolHandler] = None


class ToolRegistry:
    """Global, versioned catalogue of known tools and their handlers."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}
        self.version = 0
        self._seed_base_tools()

    def _seed_base_tools(self) -> None:
        for name in sorted(BASE_TOOLS):
            self._tools[name] = ToolSpec(name=name, scope=BASE, description=f"base tool {name}")
        for name in sorted(META_TOOLS):
            self._tools[name] = ToolSpec(name=name, scope=META, description=f"meta tool {name}")

    def register(
        self,
        name: str,
        *,
        scope: str = DOMAIN,
        description: str = "",
        handler: Optional[ToolHandler] = None,
        audit: Optional[AuditLog] = None,
    ) -> ToolSpec:
        spec = ToolSpec(name=name, scope=scope, description=description or f"{scope} tool {name}", handler=handler)
        self._tools[name] = spec
        self.version += 1
        if audit is not None:
            audit.emit(EventType.TOOLSET_CHANGED, change="register", tool=name, scope=scope, version=self.version)
        return spec

    def bind(self, name: str, handler: ToolHandler) -> None:
        """Attach/replace a handler for an already-declared tool name."""
        if name not in self._tools:
            self.register(name, handler=handler)
            return
        self._tools[name].handler = handler

    def get(self, name: str) -> ToolSpec:
        return self._tools[name]

    def has(self, name: str) -> bool:
        return name in self._tools

    def scope_of(self, name: str) -> str:
        return self._tools[name].scope if name in self._tools else DOMAIN

    def documented(self) -> List[Dict[str, Any]]:
        return [
            {"name": s.name, "scope": s.scope, "description": s.description}
            for s in sorted(self._tools.values(), key=lambda t: (t.scope, t.name))
        ]


class Toolset:
    """A role's allow-list over a :class:`ToolRegistry`.

    ``is_meta`` must be True for a toolset to legitimately contain ``create_role``;
    constructing a non-meta toolset that references a meta tool raises immediately.
    """

    def __init__(
        self,
        allowed: Iterable[str],
        *,
        registry: ToolRegistry,
        is_meta: bool = False,
        owner: Optional[str] = None,
    ) -> None:
        self.registry = registry
        self.is_meta = is_meta
        self.owner = owner
        self._allowed: Set[str] = set(BASE_TOOLS)  # every role gets the base tools
        for name in allowed:
            self._add(name)

    def _add(self, name: str) -> None:
        scope = self.registry.scope_of(name)
        if scope == META and not self.is_meta:
            raise ValueError(
                f"tool '{name}' is meta (create_role) and only birthgiver may hold it"
            )
        self._allowed.add(name)

    def extend(self, extra: Iterable[str]) -> "Toolset":
        """Queue scope extension -- never overrides base, only adds (PHASE_4 Role↔Queue)."""
        for name in extra:
            self._add(name)
        return self

    @property
    def names(self) -> Set[str]:
        return set(self._allowed)

    def can(self, name: str) -> bool:
        return name in self._allowed

    def invoke(
        self,
        name: str,
        *,
        audit: AuditLog,
        actor: str,
        ticket_id: Optional[str] = None,
        cycle_id: Optional[str] = None,
        args: Optional[Mapping[str, Any]] = None,
        ctx: Any = None,
    ) -> Dict[str, Any]:
        args = dict(args or {})
        if not self.can(name):
            audit.emit(
                EventType.TOOL_DENIED,
                actor=actor,
                ticket_id=ticket_id,
                cycle_id=cycle_id,
                tool=name,
                reason="not in toolset",
                allowed=sorted(self._allowed),
            )
            raise ToolDenied(name, "not in toolset")
        if not self.registry.has(name) or self.registry.get(name).handler is None:
            audit.emit(
                EventType.TOOL_DENIED,
                actor=actor,
                ticket_id=ticket_id,
                cycle_id=cycle_id,
                tool=name,
                reason="no handler bound",
            )
            raise ToolDenied(name, "no handler bound")
        handler = self.registry.get(name).handler
        result = handler(args, ctx)  # type: ignore[misc]
        audit.emit(
            EventType.TOOL_INVOKED,
            actor=actor,
            ticket_id=ticket_id,
            cycle_id=cycle_id,
            tool=name,
            scope=self.registry.scope_of(name),
            args=_summarize(args),
            result=_summarize(result),
        )
        return result


def _summarize(value: Any, *, limit: int = 600) -> Any:
    """Keep audit/visibility payloads readable: truncate long strings, recurse shallowly."""
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + f"... (+{len(value) - limit} chars)"
    if isinstance(value, Mapping):
        return {k: _summarize(v, limit=limit) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_summarize(v, limit=limit) for v in value][:50]
    return value
