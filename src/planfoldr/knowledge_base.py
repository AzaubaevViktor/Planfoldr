"""Knowledge Base (level 1).

Persistent, shared context available to multiple cycles within a project -- as opposed to a
cycle's local memory, which is ephemeral. Split into sections with per-role access control and
full version history. Writes happen through the ``write_context`` tool and are audited; changes
are visible to Visibility.

PHASE_4 §14:
- "Разделяется на секции с access control по ролям"; "Версионируется".
- "Роль/цикл читает только разрешённые секции"; "Запись в разрешённую секцию логируется".
- "Не хранить локальную память циклов".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from planfoldr.audit import AuditLog, EventType
from planfoldr.util import now_iso

WILDCARD = "*"


class KBAccessDenied(Exception):
    def __init__(self, section: str, role: str, mode: str) -> None:
        super().__init__(f"role '{role}' cannot {mode} kb section '{section}'")
        self.section = section
        self.role = role
        self.mode = mode


@dataclass
class KBVersion:
    version: int
    timestamp: str
    role: str
    content: str


@dataclass
class KBSection:
    name: str
    content: str = ""
    read_roles: Set[str] = field(default_factory=lambda: {WILDCARD})
    write_roles: Set[str] = field(default_factory=set)
    versions: List[KBVersion] = field(default_factory=list)

    def can_read(self, role: str) -> bool:
        return WILDCARD in self.read_roles or role in self.read_roles

    def can_write(self, role: str) -> bool:
        return WILDCARD in self.write_roles or role in self.write_roles


class KnowledgeBase:
    def __init__(self, audit: Optional[AuditLog] = None) -> None:
        self.audit = audit
        self.sections: Dict[str, KBSection] = {}

    def create_section(
        self,
        name: str,
        *,
        read_roles: Optional[Set[str]] = None,
        write_roles: Optional[Set[str]] = None,
        content: str = "",
    ) -> KBSection:
        section = KBSection(
            name=name,
            content=content,
            read_roles=set(read_roles) if read_roles is not None else {WILDCARD},
            write_roles=set(write_roles) if write_roles is not None else set(),
        )
        self.sections[name] = section
        return section

    def read(self, name: str, *, role: str) -> str:
        section = self._require(name)
        if not section.can_read(role):
            raise KBAccessDenied(name, role, "read")
        return section.content

    def write(self, name: str, content: str, *, role: str) -> int:
        section = self._require(name)
        if not section.can_write(role):
            raise KBAccessDenied(name, role, "write")
        version = len(section.versions) + 1
        section.versions.append(KBVersion(version=version, timestamp=now_iso(), role=role, content=content))
        section.content = content
        if self.audit is not None:
            self.audit.emit(
                EventType.KB_WRITTEN,
                actor=role,
                section=name,
                version=version,
                chars=len(content),
            )
        return version

    def history(self, name: str) -> List[KBVersion]:
        return list(self._require(name).versions)

    def _require(self, name: str) -> KBSection:
        if name not in self.sections:
            raise KeyError(f"kb section '{name}' does not exist")
        return self.sections[name]

    def to_dict(self) -> Dict[str, object]:
        return {
            name: {
                "content": s.content,
                "read_roles": sorted(s.read_roles),
                "write_roles": sorted(s.write_roles),
                "versions": [
                    {"version": v.version, "timestamp": v.timestamp, "role": v.role}
                    for v in s.versions
                ],
            }
            for name, s in self.sections.items()
        }
