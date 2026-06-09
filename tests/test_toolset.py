import pytest

from planfoldr.audit import AuditLog
from planfoldr.toolset import BASE_TOOLS, ToolDenied, ToolRegistry, Toolset


def make_registry():
    reg = ToolRegistry()
    reg.register("bash", description="run shell", handler=lambda args, ctx: {"ran": args.get("cmd")})
    reg.register("file_edit", description="write file", handler=lambda args, ctx: {"wrote": args.get("path")})
    return reg


def test_every_role_gets_base_tools():
    reg = make_registry()
    ts = Toolset(["bash"], registry=reg)
    for base in BASE_TOOLS:
        assert ts.can(base)
    assert ts.can("bash")
    assert not ts.can("file_edit")


def test_invoke_runs_handler_and_audits():
    reg = make_registry()
    audit = AuditLog()
    ts = Toolset(["bash"], registry=reg)
    result = ts.invoke("bash", audit=audit, actor="developer", ticket_id="dev-1", args={"cmd": "pytest"})
    assert result == {"ran": "pytest"}
    types = [e.event_type for e in audit.events()]
    assert types == ["tool.invoked"]
    assert audit.events()[0].payload["tool"] == "bash"


def test_denied_tool_emits_trace_event_and_raises():
    reg = make_registry()
    audit = AuditLog()
    ts = Toolset(["bash"], registry=reg)
    with pytest.raises(ToolDenied):
        ts.invoke("file_edit", audit=audit, actor="developer", ticket_id="dev-1", args={"path": "x"})
    ev = audit.events()[0]
    assert ev.event_type == "tool.denied"
    assert ev.payload["tool"] == "file_edit"


def test_create_role_is_meta_only():
    reg = make_registry()
    # A normal (non-meta) toolset cannot hold create_role.
    with pytest.raises(ValueError):
        Toolset(["create_role"], registry=reg)
    # Birthgiver's meta toolset can.
    birthgiver = Toolset(["create_role"], registry=reg, is_meta=True)
    assert birthgiver.can("create_role")


def test_registry_versioned_and_documented():
    reg = ToolRegistry()
    v0 = reg.version
    audit = AuditLog()
    reg.register("bash", handler=lambda a, c: {}, audit=audit)
    assert reg.version == v0 + 1
    assert audit.events()[0].event_type == "toolset.changed"
    names = {entry["name"] for entry in reg.documented()}
    assert BASE_TOOLS <= names and "create_role" in names and "bash" in names


def test_queue_scope_extends_but_base_always_present():
    reg = make_registry()
    ts = Toolset(["bash"], registry=reg)
    ts.extend(["file_edit"])
    assert ts.can("file_edit") and ts.can("bash")
    assert BASE_TOOLS <= ts.names
