import pytest

from planfoldr.audit import AuditLog, EventType
from planfoldr.graph import (
    BLOCKED_BY,
    BLOCKS,
    ESCALATES,
    EVIDENCE_FOR,
    RELATED_TO,
    SPAWNED_BY,
    GraphCycleError,
    TicketGraph,
)
from planfoldr.ticket import Status, new_ticket


def t(tid, **kw):
    return new_ticket(tid, title=tid, type="code", goal="g", created_by="orchestrator", **kw)


def test_auto_spawned_by_and_blocked_by_on_add():
    audit = AuditLog()
    g = TicketGraph(audit=audit)
    g.add_ticket(t("dev-1"))
    g.add_ticket(t("dev-2", spawned_by="dev-1", dependencies=["dev-1"]))
    assert g.related("dev-2", SPAWNED_BY) == ["dev-1"]
    assert g.blocked_by("dev-2") == ["dev-1"]
    assert g.blocks("dev-1") == ["dev-2"]  # inverse maintained
    assert any(e.event_type == EventType.GRAPH_LINK_ADDED for e in audit.events())


def test_all_six_link_types_present():
    g = TicketGraph()
    for tid in ["a", "b"]:
        g.add_ticket(t(tid))
    g.add_link("a", RELATED_TO, "b")
    g.add_link("a", EVIDENCE_FOR, "b")
    g.add_link("a", ESCALATES, "b")
    g.add_link("a", BLOCKED_BY, "b")
    types = {l.type for l in g._links}
    assert {SPAWNED_BY, BLOCKS, BLOCKED_BY, RELATED_TO, EVIDENCE_FOR, ESCALATES} >= {
        BLOCKS, BLOCKED_BY, RELATED_TO, EVIDENCE_FOR, ESCALATES
    }
    assert g.related("a", EVIDENCE_FOR) == ["b"]


def test_is_ready_tracks_dependency_completion():
    g = TicketGraph()
    dep = t("dev-1")
    dependent = t("dev-2", dependencies=["dev-1"])
    g.add_ticket(dep)
    g.add_ticket(dependent)
    assert g.is_ready("dev-2") is False
    dep.status = Status.DONE
    assert g.is_ready("dev-2") is True
    assert g.is_ready("dev-1") is True  # no deps


def test_blocked_by_cycle_is_rejected():
    g = TicketGraph()
    for tid in ["a", "b", "c"]:
        g.add_ticket(t(tid))
    g.add_link("b", BLOCKED_BY, "a")
    g.add_link("c", BLOCKED_BY, "b")
    with pytest.raises(GraphCycleError):
        g.add_link("a", BLOCKED_BY, "c")  # a→c→b→a cycle
    with pytest.raises(GraphCycleError):
        g.add_link("a", BLOCKED_BY, "a")  # self block


def test_dependents_and_replay():
    g = TicketGraph()
    g.add_ticket(t("dev-1"))
    g.add_ticket(t("dev-2", dependencies=["dev-1"]))
    assert g.dependents_of("dev-1") == ["dev-2"]
    hist = g.replay("dev-2")
    assert any(l.type == BLOCKED_BY for l in hist)


def test_history_is_append_only_and_serializes():
    g = TicketGraph()
    g.add_ticket(t("dev-1"))
    g.add_ticket(t("dev-2", dependencies=["dev-1"]))
    assert not hasattr(g, "remove_link")  # never delete links
    data = g.to_dict()
    assert {n["id"] for n in data["nodes"]} == {"dev-1", "dev-2"}
    assert any(l["type"] == BLOCKED_BY for l in data["links"])
