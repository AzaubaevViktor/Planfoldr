"""Role (level 2).

A role specializes a model: a system prompt, a tool scope and an area of responsibility. A role
is a reusable container of specialization; a queue can mix an extra prompt and extra tool scope
into it. A role cannot modify itself and cannot create another role (only birthgiver can, via the
meta `create_role` tool gated in the Toolset).

PHASE_3 "Ролевая система" + PHASE_4 §3:
- id, prompt (+ queue prompt mixed in), toolset (+ queue scope extended), can_create_ticket_types,
  score_history.
- queue prompt is mixed in (never overrides the base prompt); queue scope extends (never overrides).
- one role can serve several queues; several instances of one role can run in parallel.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from planfoldr.toolset import Toolset


_PROTECTED = {"id", "_prompt"}


class Role:
    def __init__(
        self,
        id: str,
        *,
        prompt: str,
        toolset: Toolset,
        queue_prompts: Optional[Dict[str, str]] = None,
        queue_scopes: Optional[Dict[str, List[str]]] = None,
        can_create_ticket_types: Optional[List[str]] = None,
    ) -> None:
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "_prompt", prompt)
        self.toolset = toolset
        self.queue_prompts = dict(queue_prompts or {})
        self.queue_scopes = dict(queue_scopes or {})
        self.can_create_ticket_types = list(can_create_ticket_types or [])
        self.score_history: List[Dict[str, Any]] = []
        object.__setattr__(self, "_initialized", True)

    # -- a role cannot modify itself -----------------------------------------
    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_initialized", False) and name in _PROTECTED:
            raise AttributeError(f"role '{self.id}' cannot modify its own {name}")
        object.__setattr__(self, name, value)

    @property
    def prompt(self) -> str:
        return self._prompt

    # -- queue mixing ---------------------------------------------------------
    def effective_prompt(self, queue_id: Optional[str] = None) -> str:
        """Base prompt with the queue prompt mixed in (appended, never replacing the base)."""
        if queue_id and queue_id in self.queue_prompts:
            return f"{self._prompt}\n\n{self.queue_prompts[queue_id]}"
        return self._prompt

    def effective_toolset(self, queue_id: Optional[str] = None) -> Toolset:
        """A fresh Toolset = base tools extended by this queue's scope. Never mutates the base,
        so the same role can serve several queues without cross-contamination."""
        names = set(self.toolset.names)
        if queue_id and queue_id in self.queue_scopes:
            names |= set(self.queue_scopes[queue_id])
        return Toolset(
            names,
            registry=self.toolset.registry,
            is_meta=self.toolset.is_meta,
            owner=self.id,
        )

    def can_create(self, ticket_type: str) -> bool:
        return ticket_type in self.can_create_ticket_types

    def record_score(self, entry: Dict[str, Any]) -> None:
        self.score_history.append(entry)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "prompt": self._prompt,
            "kind": type(self).__name__,
            "tools": sorted(self.toolset.names),
            "is_meta": self.toolset.is_meta,
            "queue_prompts": dict(self.queue_prompts),
            "queue_scopes": {k: list(v) for k, v in self.queue_scopes.items()},
            "can_create_ticket_types": list(self.can_create_ticket_types),
        }


class QueueManager(Role):
    """Manages one queue: triages the incoming stream, prioritizes, declines, edits the template.
    Does not execute tickets itself."""

    def __init__(self, id: str, *, prompt: str, toolset: Toolset, queue_id: str,
                 triage_prompt: str = "", **kwargs: Any) -> None:
        super().__init__(id, prompt=prompt, toolset=toolset, **kwargs)
        self.queue_id = queue_id
        self.triage_prompt = triage_prompt


class Executor(Role):
    """Pulls a ticket from its queue and runs the base cycle over it. One ticket at a time."""

    def __init__(self, id: str, *, prompt: str, toolset: Toolset, **kwargs: Any) -> None:
        super().__init__(id, prompt=prompt, toolset=toolset, **kwargs)
        self.current_ticket_id: Optional[str] = None
        self.attempt_count = 0
