"""Scoped context, state and audit primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, MutableMapping, Optional
from uuid import uuid4

from planfoldr.schema import ContextAccess


SCOPES = ("task", "cycle", "scenario", "decision_log", "audit_log")


class ContextAccessDenied(PermissionError):
    """Raised when a context operation is outside declared access."""


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    timestamp: str
    actor_id: str
    action: str
    scope_path: str
    value_summary: str
    result: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "actor_id": self.actor_id,
            "action": self.action,
            "scope_path": self.scope_path,
            "value_summary": self.value_summary,
            "result": self.result,
        }


@dataclass(frozen=True)
class DecisionEvent:
    decision_id: str
    timestamp: str
    actor_id: str
    subject: str
    decision: str
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "timestamp": self.timestamp,
            "actor_id": self.actor_id,
            "subject": self.subject,
            "decision": self.decision,
            "reason": self.reason,
        }


@dataclass
class ContextStore:
    """Nested context/state snapshots plus immutable audit and decisions."""

    context: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {"task": {}, "cycle": {}, "scenario": {}}
    )
    state: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {"task": {}, "cycle": {}, "scenario": {}}
    )
    audit_events: List[AuditEvent] = field(default_factory=list)
    decisions: List[DecisionEvent] = field(default_factory=list)

    def read(self, path: str, *, actor_id: str, access: Optional[ContextAccess] = None) -> Any:
        self._check("read", path, access)
        value = _get_nested(self._scope_data(path), _parts(path)[1:])
        self._audit(actor_id, "read", path, value, "allowed")
        return value

    def write(
        self,
        path: str,
        value: Any,
        *,
        actor_id: str,
        access: Optional[ContextAccess] = None,
    ) -> None:
        try:
            self._check("write", path, access)
        except ContextAccessDenied:
            self._audit(actor_id, "write", path, value, "denied")
            raise
        _set_nested(self._scope_data(path), _parts(path)[1:], value)
        self._audit(actor_id, "write", path, value, "allowed")

    def delete(self, path: str, *, actor_id: str, access: Optional[ContextAccess] = None) -> None:
        try:
            self._check("delete", path, access)
        except ContextAccessDenied:
            self._audit(actor_id, "delete", path, None, "denied")
            raise
        _delete_nested(self._scope_data(path), _parts(path)[1:])
        self._audit(actor_id, "delete", path, None, "allowed")

    def write_state(self, path: str, value: Any, *, actor_id: str) -> None:
        scope, nested = _scope_and_nested(path)
        if scope not in self.state:
            raise ContextAccessDenied(f"Unknown state scope '{scope}'")
        _set_nested(self.state[scope], nested, value)
        self._audit(actor_id, "write_state", path, value, "allowed")

    def record_decision(
        self,
        *,
        actor_id: str,
        subject: str,
        decision: str,
        reason: Optional[str] = None,
    ) -> DecisionEvent:
        event = DecisionEvent(
            decision_id=f"decision_{uuid4().hex}",
            timestamp=_now(),
            actor_id=actor_id,
            subject=subject,
            decision=decision,
            reason=reason,
        )
        self.decisions.append(event)
        self._audit(actor_id, "decision", f"decision_log.{subject}", event.to_dict(), "allowed")
        return event

    def propagate_facts(
        self,
        facts: Mapping[str, Any],
        *,
        actor_id: str,
        access: Optional[ContextAccess] = None,
    ) -> None:
        for key, value in facts.items():
            self.write(f"cycle.facts.{key}", value, actor_id=actor_id, access=access)

    def _check(self, action: str, path: str, access: Optional[ContextAccess]) -> None:
        scope = _parts(path)[0]
        if scope == "task":
            return
        allowed = _allowed_paths(action, access)
        if any(_path_matches(path, candidate) for candidate in allowed):
            return
        raise ContextAccessDenied(f"{action} denied for '{path}'")

    def _scope_data(self, path: str) -> MutableMapping[str, Any]:
        scope = _parts(path)[0]
        if scope not in self.context:
            raise ContextAccessDenied(f"Unknown context scope '{scope}'")
        return self.context[scope]

    def _audit(self, actor_id: str, action: str, path: str, value: Any, result: str) -> None:
        self.audit_events.append(
            AuditEvent(
                event_id=f"audit_{uuid4().hex}",
                timestamp=_now(),
                actor_id=actor_id,
                action=action,
                scope_path=path,
                value_summary=_summary(value),
                result=result,
            )
        )


def _allowed_paths(action: str, access: Optional[ContextAccess]) -> List[str]:
    if access is None:
        return []
    if action == "read":
        return access.read
    if action == "write":
        return access.write
    if action == "delete":
        return access.delete
    return []


def _path_matches(path: str, allowed: str) -> bool:
    return path == allowed or path.startswith(f"{allowed}.")


def _scope_and_nested(path: str) -> tuple[str, List[str]]:
    parts = _parts(path)
    return parts[0], parts[1:]


def _parts(path: str) -> List[str]:
    parts = [part for part in path.split(".") if part]
    if not parts:
        raise ContextAccessDenied("Context path cannot be empty")
    if parts[0] not in SCOPES:
        raise ContextAccessDenied(f"Unknown scope '{parts[0]}'")
    return parts


def _get_nested(root: Mapping[str, Any], parts: List[str]) -> Any:
    current: Any = root
    for part in parts:
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _set_nested(root: MutableMapping[str, Any], parts: List[str], value: Any) -> None:
    current = root
    for part in parts[:-1]:
        child = current.setdefault(part, {})
        if not isinstance(child, MutableMapping):
            raise ContextAccessDenied(f"Cannot write through non-mapping path '{part}'")
        current = child
    if not parts:
        raise ContextAccessDenied("Cannot replace an entire context scope")
    current[parts[-1]] = value


def _delete_nested(root: MutableMapping[str, Any], parts: List[str]) -> None:
    current = root
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, MutableMapping):
            return
        current = child
    if parts:
        current.pop(parts[-1], None)


def _summary(value: Any) -> str:
    text = repr(value)
    if len(text) > 120:
        return text[:117] + "..."
    return text


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
