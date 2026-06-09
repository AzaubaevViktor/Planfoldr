from planfoldr.audit import AuditLog, EventType


def test_emit_assigns_monotonic_seq_and_timestamp():
    log = AuditLog()
    a = log.emit(EventType.TICKET_CREATED, ticket_id="dev-1", actor="orchestrator")
    b = log.emit(EventType.TICKET_STATUS_CHANGED, ticket_id="dev-1", **{"from": "incoming", "to": "ready"})
    assert a.seq == 1 and b.seq == 2
    assert a.event_type == "ticket.created"
    assert b.payload["from"] == "incoming" and b.payload["to"] == "ready"
    assert a.timestamp.endswith("Z")


def test_persists_jsonl_roundtrip(tmp_path):
    path = tmp_path / "run" / "audit.jsonl"
    log = AuditLog(path)
    log.emit(EventType.TICKET_CREATED, ticket_id="dev-1")
    log.emit(EventType.CYCLE_PHASE_COMPLETED, ticket_id="dev-1", cycle_id="c1", phase="changes")
    read_back = AuditLog.read(path)
    assert [e.event_type for e in read_back] == ["ticket.created", "cycle.phase_completed"]
    assert read_back[1].cycle_id == "c1"
    # Append-only: file has exactly one line per event.
    assert len(path.read_text().splitlines()) == 2


def test_replay_filters_by_ticket():
    log = AuditLog()
    log.emit(EventType.TICKET_CREATED, ticket_id="dev-1")
    log.emit(EventType.TICKET_CREATED, ticket_id="dev-2")
    log.emit(EventType.TICKET_STATUS_CHANGED, ticket_id="dev-1", to="done")
    history = log.replay("dev-1")
    assert [e.event_type for e in history] == ["ticket.created", "ticket.status_changed"]
    assert all(e.ticket_id == "dev-1" for e in history)


def test_subscribers_receive_events_and_failures_are_isolated():
    log = AuditLog()
    seen = []
    log.subscribe(lambda e: seen.append(e.event_type))
    log.subscribe(lambda e: (_ for _ in ()).throw(RuntimeError("boom")))  # must not break emit
    log.emit(EventType.MODEL_STREAM, ticket_id="dev-1", kind="thinking", text="hi")
    assert seen == ["model.stream"]


def test_audit_does_not_stop_on_unserializable_payload(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    # object() is not JSON serializable; default=str keeps audit alive (never blocks flow).
    event = log.emit(EventType.BUDGET_EXCEEDED, ticket_id="dev-1", obj=object())
    assert event.seq == 1
    assert AuditLog.read(tmp_path / "audit.jsonl")[0].event_type == "budget.exceeded"
