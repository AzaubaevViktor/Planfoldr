import pytest

from planfoldr.toolset import BASE_TOOLS, ToolRegistry, Toolset
from planfoldr.role import Executor, QueueManager, Role


def make_role(**kw):
    reg = ToolRegistry()
    reg.register("file_edit", handler=lambda a, c: {})
    reg.register("bash", handler=lambda a, c: {})
    reg.register("security_scan", handler=lambda a, c: {})
    ts = Toolset(["file_edit", "bash"], registry=reg)
    return Role("developer", prompt="You are a developer.", toolset=ts, **kw), reg


def test_role_has_base_tools_and_declared_domain_tools():
    role, _ = make_role()
    assert BASE_TOOLS <= role.toolset.names
    assert role.toolset.can("file_edit") and role.toolset.can("bash")


def test_queue_prompt_is_mixed_in_not_overridden():
    role, _ = make_role(queue_prompts={"developer-q": "Follow the developer queue rules."})
    base = role.effective_prompt()
    mixed = role.effective_prompt("developer-q")
    assert base == "You are a developer."
    assert mixed.startswith("You are a developer.")  # base preserved
    assert "developer queue rules" in mixed            # queue prompt appended


def test_queue_scope_extends_without_mutating_base():
    role, _ = make_role(queue_scopes={"security-q": ["security_scan"]})
    base_ts = role.effective_toolset()
    sec_ts = role.effective_toolset("security-q")
    assert not base_ts.can("security_scan")            # base unchanged
    assert sec_ts.can("security_scan")                 # queue scope added
    assert sec_ts.can("file_edit") and BASE_TOOLS <= sec_ts.names
    # The role's own toolset object was not mutated.
    assert not role.toolset.can("security_scan")


def test_one_role_serves_multiple_queues():
    role, _ = make_role(
        queue_prompts={"q1": "Q1 rules", "q2": "Q2 rules"},
        queue_scopes={"q1": ["security_scan"]},
    )
    assert "Q1 rules" in role.effective_prompt("q1")
    assert "Q2 rules" in role.effective_prompt("q2")
    assert role.effective_toolset("q1").can("security_scan")
    assert not role.effective_toolset("q2").can("security_scan")


def test_can_create_ticket_types():
    role, _ = make_role(can_create_ticket_types=["security-review", "research"])
    assert role.can_create("security-review")
    assert not role.can_create("release")


def test_role_cannot_modify_itself():
    role, _ = make_role()
    with pytest.raises(AttributeError):
        role.prompt = "I am now an admin"
    with pytest.raises(AttributeError):
        role.id = "root"


def test_specializations_carry_their_fields():
    reg = ToolRegistry()
    ts = Toolset([], registry=reg)
    qm = QueueManager("dev-manager", prompt="triage", toolset=ts, queue_id="developer", triage_prompt="prioritize")
    ex = Executor("dev-exec", prompt="dig", toolset=ts)
    assert qm.queue_id == "developer" and qm.triage_prompt == "prioritize"
    assert ex.current_ticket_id is None and ex.attempt_count == 0
