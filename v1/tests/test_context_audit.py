import pytest

from planfoldr.context import ContextAccessDenied, ContextStore
from planfoldr.schema import ContextAccess


def test_task_local_mutation_is_allowed_and_audited() -> None:
    store = ContextStore()

    store.write("task.scratch.answer", 42, actor_id="task.plan")

    assert store.read("task.scratch.answer", actor_id="task.plan") == 42
    assert [event.action for event in store.audit_events] == ["write", "read"]
    assert store.audit_events[0].result == "allowed"


def test_parent_write_requires_declared_permission() -> None:
    store = ContextStore()

    with pytest.raises(ContextAccessDenied):
        store.write("scenario.facts.answer", 42, actor_id="task.plan")

    assert store.audit_events[-1].result == "denied"

    access = ContextAccess(write=["scenario.facts"])
    store.write("scenario.facts.answer", 42, actor_id="task.plan", access=access)

    assert store.context["scenario"]["facts"]["answer"] == 42
    assert store.audit_events[-1].result == "allowed"


def test_delete_and_read_access_are_checked() -> None:
    store = ContextStore()
    access = ContextAccess(read=["cycle.facts"], write=["cycle.facts"], delete=["cycle.facts"])

    store.write("cycle.facts.answer", "yes", actor_id="task.verify", access=access)
    assert store.read("cycle.facts.answer", actor_id="task.verify", access=access) == "yes"
    store.delete("cycle.facts.answer", actor_id="task.verify", access=access)

    assert store.read("cycle.facts.answer", actor_id="task.verify", access=access) is None


def test_decision_log_and_state_are_machine_readable() -> None:
    store = ContextStore()

    store.write_state("cycle.iteration", 1, actor_id="runtime")
    decision = store.record_decision(
        actor_id="runtime",
        subject="link.plan.success",
        decision="create_files",
        reason="declared link",
    )

    assert store.state["cycle"]["iteration"] == 1
    assert decision.to_dict()["decision"] == "create_files"
    assert store.audit_events[-1].action == "decision"


def test_facts_are_propagated_only_through_declared_write_access() -> None:
    store = ContextStore()

    with pytest.raises(ContextAccessDenied):
        store.propagate_facts({"answer": 42}, actor_id="child")

    store.propagate_facts(
        {"answer": 42},
        actor_id="child",
        access=ContextAccess(write=["cycle.facts"]),
    )

    assert store.context["cycle"]["facts"]["answer"] == 42
