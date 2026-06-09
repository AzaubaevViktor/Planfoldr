from planfoldr.audit import AuditLog, EventType
from planfoldr.budget import Budget, Metric, parse_ollama_ps


def test_realtime_update_increments_on_each_consume():
    b = Budget({Metric.TOKENS: 1000})
    assert b.consume(Metric.TOKENS, 100) is True
    assert b.usage[Metric.TOKENS] == 100
    b.consume(Metric.TOKENS, 50)
    assert b.usage[Metric.TOKENS] == 150  # updated continuously, not at the end


def test_soft_stop_emits_once_and_blocks_new_work():
    audit = AuditLog()
    b = Budget({Metric.TOKENS: 200}, audit=audit, ticket_id="dev-1")
    assert b.consume(Metric.TOKENS, 150) is True
    assert b.can_start_new() is True
    # Crossing the limit returns False but still records usage (ongoing op finishes).
    assert b.consume(Metric.TOKENS, 100) is False
    assert b.usage[Metric.TOKENS] == 250
    assert b.blocked is True and b.can_start_new() is False
    exceeded = [e for e in audit.events() if e.event_type == EventType.BUDGET_EXCEEDED]
    assert len(exceeded) == 1  # emitted once, not per subsequent consume
    b.consume(Metric.TOKENS, 10)
    assert len([e for e in audit.events() if e.event_type == EventType.BUDGET_EXCEEDED]) == 1
    assert exceeded[0].payload["resource"] == Metric.TOKENS
    assert exceeded[0].payload["limit"] == 200


def test_delegation_bubbles_usage_to_parent():
    audit = AuditLog()
    project = Budget({Metric.TOKENS: 10000}, scope="project", audit=audit)
    child = project.delegate({Metric.TOKENS: 500}, scope="ticket", ticket_id="dev-1")
    assert any(e.event_type == EventType.BUDGET_DELEGATED for e in audit.events())
    child.consume(Metric.TOKENS, 300)
    assert child.usage[Metric.TOKENS] == 300
    assert project.usage[Metric.TOKENS] == 300  # bubbled up to the project total


def test_child_breach_blocks_child_and_propagates_block_but_not_parent_flag():
    project = Budget({Metric.TOKENS: 10000}, scope="project")
    child = project.delegate({Metric.TOKENS: 400}, scope="ticket", ticket_id="dev-1")
    assert child.consume(Metric.TOKENS, 500) is False
    assert child.blocked is True
    assert project.exceeded is False  # project still has room
    # Child cannot raise its own limit without an approved decision.
    assert child.request_increase(Metric.TOKENS, 1000, approved=False) is False
    assert child.blocked is True
    assert child.request_increase(Metric.TOKENS, 1000, approved=True) is True
    assert child.blocked is False


def test_shared_model_gpu_attribution_is_per_ticket():
    ps = (
        "NAME            ID      SIZE   PROCESSOR   CONTEXT  UNTIL\n"
        "gemma4:26b-mlx  abc123  16 GB  100% GPU    8192     4 minutes from now\n"
    )
    a = Budget(scope="ticket", ticket_id="dev-1")
    c = Budget(scope="ticket", ticket_id="dev-2")
    # Two tickets share one loaded model; each is charged only for its own seconds.
    a_hours = a.charge_model_seconds("gemma4:26b-mlx", 3600, ps_text=ps)
    c_hours = c.charge_model_seconds("gemma4:26b-mlx", 1800, ps_text=ps)
    assert round(a_hours, 3) == 16.0       # 16 GB * 1.0 GPU * 1.0 h
    assert round(c_hours, 3) == 8.0        # 16 GB * 1.0 GPU * 0.5 h
    assert round(a.usage[Metric.GPU_RAM_HOURS], 3) == 16.0
    assert round(c.usage[Metric.GPU_RAM_HOURS], 3) == 8.0


def test_parse_ollama_ps_processor_split():
    text = (
        "NAME      ID    SIZE     PROCESSOR        CONTEXT  UNTIL\n"
        "fullgpu   a     8.1 GB   100% GPU         4096     x\n"
        "fullcpu   b     512 MB   100% CPU         2048     x\n"
        "split     c     16 GB    30%/70% CPU/GPU  8192     x\n"
    )
    parsed = parse_ollama_ps(text)
    assert round(parsed["fullgpu"]["size_gb"], 2) == 8.1
    assert parsed["fullgpu"]["gpu_fraction"] == 1.0
    assert parsed["fullcpu"]["gpu_fraction"] == 0.0
    assert round(parsed["fullcpu"]["size_gb"], 4) == round(512 / 1024.0, 4)
    assert parsed["split"]["gpu_fraction"] == 0.70
