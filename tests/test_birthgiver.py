import pytest

from planfoldr.audit import AuditLog, EventType
from planfoldr.birthgiver import (
    Birthgiver,
    Human,
    QueueRegistry,
    RoleRegistry,
    handle_create_role,
)
from planfoldr.graph import TicketGraph
from planfoldr.ticket import Status
from planfoldr.toolset import ToolRegistry, Toolset


def make_birthgiver():
    audit = AuditLog()
    reg = ToolRegistry()
    roles = RoleRegistry()
    queues = QueueRegistry()
    bg = Birthgiver(tool_registry=reg, role_registry=roles, queue_registry=queues,
                    audit=audit, graph=TicketGraph(audit=audit))
    return bg, audit, roles, queues, reg


def test_summon_creates_incoming_ticket_for_birthgiver():
    bg, audit, _, _, _ = make_birthgiver()
    ticket = bg.summon_ticket("performance_analyst", requester="developer", reason="slow endpoint")
    assert ticket.type == "create_role" and ticket.role == "birthgiver"
    assert ticket.status == Status.INCOMING
    assert any(e.event_type == EventType.ROLE_SUMMONED and e.payload["role"] == "performance_analyst"
               for e in audit.events())


def test_create_role_opens_queue_with_manager_and_executor():
    bg, audit, roles, queues, _ = make_birthgiver()
    decision = bg.link_or_create(
        "performance_analyst", needed=True, prompt="You analyze performance.",
        domain_tools=["profile"], can_create_ticket_types=["fix"], budget_scope={"tokens_used": 20000},
    )
    assert decision.action == "create"
    assert roles.has("performance_analyst-manager") and roles.has("performance_analyst-exec")
    assert queues.has("performance_analyst")
    created = [e for e in audit.events() if e.event_type == EventType.ROLE_CREATED and e.payload.get("decision") == "created"]
    assert len(created) == 2
    assert any(e.event_type == EventType.QUEUE_CREATED for e in audit.events())
    # executor carries the domain tool + the declared ticket types.
    assert roles.get("performance_analyst-exec").toolset.can("profile")
    assert roles.get("performance_analyst-exec").can_create("fix")


def test_link_existing_role_does_not_create():
    bg, _, roles, queues, _ = make_birthgiver()
    bg.link_or_create("security", needed=True, domain_tools=["scan"])
    before = (set(roles.ids()), set(queues.ids()))
    decision = bg.link_or_create("security", needed=True)
    assert decision.action == "link"
    assert (set(roles.ids()), set(queues.ids())) == before  # nothing new created


def test_refuse_with_cause():
    bg, audit, roles, _, _ = make_birthgiver()
    decision = bg.link_or_create("blockchain_wizard", needed=False, cause="out of project scope")
    assert decision.action == "refuse" and decision.cause == "out of project scope"
    assert not roles.has("blockchain_wizard-exec")
    assert any(e.event_type == EventType.ROLE_CREATED and e.payload.get("decision") == "refused"
               for e in audit.events())


def test_cannot_recursively_create_birthgiver():
    bg, _, _, _, _ = make_birthgiver()
    with pytest.raises(PermissionError):
        bg.create_role("birthgiver", prompt="evil")


def test_create_role_tool_is_meta_and_invokes_birthgiver():
    bg, audit, roles, queues, reg = make_birthgiver()
    reg.bind("create_role", handle_create_role)

    class Ctx:
        birthgiver = bg

    meta_toolset = Toolset(["create_role"], registry=reg, is_meta=True)
    result = meta_toolset.invoke("create_role", audit=audit, actor="birthgiver",
                                 args={"name": "data_engineer", "domain_tools": ["sql"]}, ctx=Ctx())
    assert result["queue"] == "data_engineer"
    assert roles.has("data_engineer-exec") and queues.has("data_engineer")


def test_human_answers_and_audits():
    audit = AuditLog()
    human = Human({"budget": "you may spend up to 50k tokens"}, default="proceed", audit=audit)
    assert "50k" in human("What is the budget for this work?", "decision")
    assert human("Anything else?") == "proceed"
    kinds = [e.event_type for e in audit.events()]
    assert EventType.HUMAN_REQUESTED in kinds and EventType.HUMAN_ANSWERED in kinds


def test_human_list_answers_in_order():
    human = Human(["first", "second"], default="done")
    assert (human("q1"), human("q2"), human("q3")) == ("first", "second", "done")
