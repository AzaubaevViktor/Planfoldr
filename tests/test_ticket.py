import pytest

from planfoldr.audit import AuditLog, EventType
from planfoldr.ticket import (
    Check,
    Status,
    Ticket,
    TicketTransitionError,
    child_closing_parent,
    new_ticket,
)


def make_ticket(audit=None, **kw):
    return new_ticket(
        "dev-1", title="endpoint", type="code", goal="add GET /health",
        created_by="orchestrator", audit=audit, **kw,
    )


def test_created_event_and_metadata():
    audit = AuditLog()
    t = make_ticket(audit)
    assert audit.events()[0].event_type == EventType.TICKET_CREATED
    assert t.metadata["created_by"] == "orchestrator" and "created_at" in t.metadata


def test_happy_path_transitions_emit_events():
    audit = AuditLog()
    t = make_ticket(audit, checks=[Check(kind="command", spec="pytest")])
    t.transition(Status.READY, actor="manager", audit=audit)
    t.transition(Status.RUNNING, actor="developer", audit=audit)
    t.add_evidence(check_index=0, status="success", proof="pytest exit 0")
    t.transition(Status.DONE, actor="developer", audit=audit)
    changes = [e for e in audit.events() if e.event_type == EventType.TICKET_STATUS_CHANGED]
    assert [e.payload["to"] for e in changes] == [Status.READY, Status.RUNNING, Status.DONE]
    assert t.metadata["change_history"][-1]["to"] == Status.DONE


def test_illegal_transition_raises():
    t = make_ticket()
    with pytest.raises(TicketTransitionError):
        t.transition(Status.DONE, actor="x")  # incoming → done is not allowed


def test_goal_is_immutable():
    t = make_ticket()
    with pytest.raises(TicketTransitionError):
        t.goal = "something else"
    assert t.goal == "add GET /health"


def test_cannot_self_complete_without_passing_mandatory_checks():
    t = make_ticket(checks=[Check(kind="command", spec="pytest", required=True)])
    t.transition(Status.READY, actor="m")
    t.transition(Status.RUNNING, actor="d")
    with pytest.raises(TicketTransitionError):
        t.transition(Status.DONE, actor="d")  # no evidence yet → cannot declare itself done
    t.add_evidence(check_index=0, status="success", proof="ok")
    t.transition(Status.DONE, actor="d")  # now mandatory check passed
    assert t.status == Status.DONE


def test_needs_review_to_done_requires_reviewer_proof():
    t = make_ticket()  # no checks at all
    t.transition(Status.READY, actor="m")
    t.transition(Status.RUNNING, actor="d")
    t.transition(Status.NEEDS_REVIEW, actor="d")
    with pytest.raises(TicketTransitionError):
        t.transition(Status.DONE, actor="reviewer")  # needs an explicit proof
    t.transition(Status.DONE, actor="reviewer", proof="reviewer approved")
    assert t.status == Status.DONE


def test_declined_requires_cause():
    t = make_ticket()
    with pytest.raises(TicketTransitionError):
        t.transition(Status.DECLINED, actor="manager")
    t.transition(Status.DECLINED, actor="manager", cause="out of scope")
    assert t.status == Status.DECLINED and t.decline_cause == "out of scope"


def test_failed_after_n_attempts():
    t = make_ticket(max_attempts=2)
    assert t.record_attempt() == 1 and not t.exhausted_attempts()
    assert t.record_attempt() == 2 and t.exhausted_attempts()


def test_comment_can_summon_role():
    audit = AuditLog()
    t = make_ticket(audit)
    t.add_comment(author="developer", text="need a security pass @security", summon="security", audit=audit)
    assert t.comments[-1].summoned_role == "security"
    assert any(e.event_type == EventType.ROLE_SUMMONED and e.payload["role"] == "security" for e in audit.events())


def test_json_roundtrip():
    t = make_ticket(checks=[Check(kind="model", spec="meets criteria")], dependencies=["dev-0"])
    t.add_comment(author="a", text="hi")
    restored = Ticket.from_dict(t.to_dict())
    assert restored.to_dict() == t.to_dict()
    assert restored.goal == t.goal and restored.dependencies == ["dev-0"]


def test_child_cannot_close_parent():
    parent = make_ticket()
    child = new_ticket("dev-2", title="t", type="tests", goal="g", created_by="developer", spawned_by="dev-1")
    assert child_closing_parent(parent, child, Status.DONE) is True
    assert child_closing_parent(parent, child, Status.RUNNING) is False  # non-terminal is fine
    assert child_closing_parent(parent, parent, Status.DONE) is False    # acting on itself is fine
