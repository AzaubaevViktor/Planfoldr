"""Tool handler implementations + a runtime context for them.

These are the domain/base tools a cycle dispatches during its Changes phase. Each handler takes
``(args, ctx)`` where ``ctx`` is a :class:`ToolContext` carrying the per-cycle handles (workspace,
budget, graph, ticket, knowledge base, orchestrator callbacks). File/command access is confined to
an allowlist rooted at the per-run workspace.
"""

from __future__ import annotations

import difflib
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from planfoldr.audit import AuditLog
from planfoldr.budget import Budget, Metric
from planfoldr.knowledge_base import KnowledgeBase
from planfoldr.toolset import ToolRegistry


class ToolError(Exception):
    pass


class PathNotAllowed(ToolError):
    pass


@dataclass
class ToolContext:
    audit: AuditLog
    budget: Budget
    workspace: Path
    ticket: Any                      # planfoldr.ticket.Ticket
    role: Any = None                 # planfoldr.role.Role
    graph: Any = None
    knowledge_base: Optional[KnowledgeBase] = None
    allowed_paths: List[Path] = field(default_factory=list)
    command_timeout: float = 120.0
    on_create_ticket: Optional[Callable[[Dict[str, Any]], str]] = None
    on_request_decision: Optional[Callable[[str, str], str]] = None

    def roots(self) -> List[Path]:
        return self.allowed_paths or [self.workspace]


def safe_path(ctx: ToolContext, path: str) -> Path:
    """Resolve `path` against the workspace and ensure it stays within an allowed root."""
    candidate = (ctx.workspace / path).resolve() if not os.path.isabs(path) else Path(path).resolve()
    for root in ctx.roots():
        try:
            candidate.relative_to(root.resolve())
            return candidate
        except ValueError:
            continue
    raise PathNotAllowed(f"path '{path}' is outside the allowed workspace")


def _line_changes(before: str, after: str) -> tuple[int, int]:
    matcher = difflib.SequenceMatcher(a=before.splitlines(), b=after.splitlines())
    added = removed = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in {"replace", "delete"}:
            removed += i2 - i1
        if tag in {"replace", "insert"}:
            added += j2 - j1
    return added, removed


def handle_file_edit(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    path = args.get("path")
    if not path:
        raise ToolError("file_edit requires 'path'")
    target = safe_path(ctx, path)
    before = target.read_text(encoding="utf-8") if target.exists() else ""
    if args.get("delete"):
        if target.exists():
            target.unlink()
        added, removed = _line_changes(before, "")
        action = "deleted"
        content = ""
    else:
        content = str(args.get("content", ""))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        added, removed = _line_changes(before, content)
        action = "modified" if before else "created"
    ctx.budget.consume(Metric.FILE_CHANGES, 1)
    ctx.budget.consume(Metric.LINES_ADDED, added)
    ctx.budget.consume(Metric.LINES_REMOVED, removed)
    return {"path": str(target.relative_to(ctx.workspace.resolve())) if str(target).startswith(str(ctx.workspace.resolve())) else str(target),
            "action": action, "lines_added": added, "lines_removed": removed, "bytes": len(content.encode("utf-8"))}


def run_command(cmd: str, *, cwd: Path, timeout: float, budget: Optional[Budget] = None) -> Dict[str, Any]:
    """Run a shell command in `cwd` with a minimal environment. Used by the bash tool and by
    command verification."""
    completed = subprocess.run(
        shlex.split(cmd),
        cwd=str(cwd),
        env={"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")},
        capture_output=True, text=True, timeout=timeout, check=False,
    )
    if budget is not None:
        budget.consume(Metric.COMMAND_RUNS, 1)
    return {
        "exit_code": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
        "status": "success" if completed.returncode == 0 else "failure",
    }


def handle_bash(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    cmd = args.get("cmd") or args.get("command")
    if not cmd:
        raise ToolError("bash requires 'cmd'")
    cwd = safe_path(ctx, args.get("cwd", ".")) if args.get("cwd") else ctx.workspace
    return run_command(cmd, cwd=cwd, timeout=ctx.command_timeout, budget=ctx.budget)


def handle_create_ticket(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    if ctx.role is not None and args.get("type") and not ctx.role.can_create(args["type"]):
        raise ToolError(f"role '{ctx.role.id}' may not create ticket type '{args['type']}'")
    if ctx.on_create_ticket is None:
        raise ToolError("create_ticket is not wired in this context")
    ticket_id = ctx.on_create_ticket(args)
    ctx.budget.consume(Metric.TICKETS_CREATED, 1)
    return {"ticket_id": ticket_id, "type": args.get("type"), "title": args.get("title")}


def handle_update_ticket(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    finding = args.get("finding") or args.get("evidence") or args.get("note", "")
    ctx.ticket.evidence.append({"status": args.get("status", "note"), "proof": finding, "via": "update_ticket"})
    return {"ok": True, "evidence_count": len(ctx.ticket.evidence)}


def handle_write_context(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    if ctx.knowledge_base is None:
        raise ToolError("no knowledge base in this context")
    section = args["section"]
    if section not in ctx.knowledge_base.sections:
        ctx.knowledge_base.create_section(section, write_roles={ctx.role.id if ctx.role else "*"})
    version = ctx.knowledge_base.write(section, str(args.get("content", "")), role=ctx.role.id if ctx.role else "*")
    return {"section": section, "version": version}


def handle_read_context(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    if ctx.knowledge_base is None:
        raise ToolError("no knowledge base in this context")
    content = ctx.knowledge_base.read(args["section"], role=ctx.role.id if ctx.role else "*")
    return {"section": args["section"], "content": content}


def handle_request_decision(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    question = args.get("question", args.get("text", ""))
    kind = args.get("kind", "decision")
    if ctx.on_request_decision is None:
        return {"answer": None, "available": False}
    answer = ctx.on_request_decision(question, kind)
    return {"answer": answer, "available": True}


DEFAULT_HANDLERS = {
    "file_edit": ("domain", handle_file_edit),
    "bash": ("domain", handle_bash),
    "create_ticket": ("base", handle_create_ticket),
    "update_ticket": ("base", handle_update_ticket),
    "write_context": ("base", handle_write_context),
    "read_context": ("base", handle_read_context),
    "request_decision": ("base", handle_request_decision),
    "request_context": ("base", handle_request_decision),
}


def register_default_tools(registry: ToolRegistry) -> ToolRegistry:
    for name, (scope, handler) in DEFAULT_HANDLERS.items():
        registry.bind(name, handler)
        if name not in {"create_ticket", "update_ticket", "read_context", "write_context",
                        "request_context", "request_decision"}:
            registry.register(name, scope=scope, handler=handler)
    return registry
