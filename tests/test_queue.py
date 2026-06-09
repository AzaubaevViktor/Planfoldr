from planfoldr.audit import AuditLog
from planfoldr.graph import TicketGraph
from planfoldr.queue import Queue
from planfoldr.ticket import Status, new_ticket


def t(tid, **kw):
    return new_ticket(tid, title=tid, type="code", goal="g", created_by="orchestrator", **kw)


def make_queue():
    audit = AuditLog()
    graph = TicketGraph(audit=audit)
    q = Queue(id="developer", name="developer", graph=graph, audit=audit,
              manager_role="dev-manager", executor_roles=["dev-exec"])
    return q, graph, audit


def test_add_lands_in_incoming():
    q, _, _ = make_queue()
    q.add(t("dev-1"))
    assert [x.id for x in q.incoming()] == ["dev-1"]


def test_accept_no_deps_becomes_ready():
    q, _, _ = make_queue()
    q.add(t("dev-1"))
    q.accept("dev-1", priority=5)
    assert q.tickets["dev-1"].status == Status.READY
    assert [x.id for x in q.list_for_executor()] == ["dev-1"]


def test_accept_with_unmet_deps_becomes_blocked_then_ready():
    q, graph, _ = make_queue()
    dep = t("dev-1")
    dependent = t("dev-2", dependencies=["dev-1"])
    q.add(dep)
    q.add(dependent)
    q.accept("dev-1")
    q.accept("dev-2")
    assert q.tickets["dev-2"].status == Status.BLOCKED  # dep not done yet
    # Finish the dependency, then refresh.
    dep.status = Status.DONE
    promoted = q.refresh_ready()
    assert promoted == ["dev-2"] and q.tickets["dev-2"].status == Status.READY


def test_declined_is_manager_only():
    q, _, _ = make_queue()
    q.add(t("dev-9"))
    q.decline("dev-9", cause="out of scope")
    assert [x.id for x in q.declined()] == ["dev-9"]
    assert "dev-9" not in [x.id for x in q.list_for_executor()]   # invisible to executor
    assert "dev-9" in [x.id for x in q.list_for_manager()]        # visible to manager


def test_get_next_by_priority_then_fifo():
    q, _, _ = make_queue()
    for tid in ["dev-1", "dev-2", "dev-3"]:
        q.add(t(tid))
    q.accept("dev-1", priority=1)
    q.accept("dev-2", priority=9)
    q.accept("dev-3", priority=9)
    # Highest priority wins; tie → earliest intake (dev-2 before dev-3).
    assert q.get_next().id == "dev-2"


def test_parallel_executors_take_independent_tickets():
    q, _, _ = make_queue()
    q.add(t("dev-1"))
    q.add(t("dev-2"))
    q.accept("dev-1", priority=5)
    q.accept("dev-2", priority=3)
    first = q.get_next()
    first.transition(Status.RUNNING, actor="exec-A")  # executor A takes it
    second = q.get_next()
    assert {first.id, second.id} == {"dev-1", "dev-2"} and first.id != second.id
