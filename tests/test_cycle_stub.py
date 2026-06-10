from pathlib import Path

from planfoldr.audit import AuditLog, EventType
from planfoldr.budget import Budget, Metric
from planfoldr.cycle import CHANGES, CONTEXT, COMMAND_VERIFY, MODEL_VERIFY, Cycle
from planfoldr.graph import TicketGraph
from planfoldr.knowledge_base import KnowledgeBase
from planfoldr.model import ModelConfig, StubModel
from planfoldr.role import Executor
from planfoldr.score import ScoreSystem
from planfoldr.ticket import Check, Status, new_ticket
from planfoldr.toolset import ToolRegistry, Toolset
from planfoldr.tools_impl import register_default_tools


def build(
    tmp_path, *, stub, ticket, budget_limits=None, on_create_ticket=None, stream_sink=None,
    role_id="developer", role_prompt="You are a developer.", can_create=None,
):
    audit = AuditLog()
    reg = register_default_tools(ToolRegistry())
    toolset = Toolset(["file_edit", "bash"], registry=reg)
    role = Executor(role_id, prompt=role_prompt, toolset=toolset,
                    can_create_ticket_types=can_create or ["tests", "research"])
    budget = Budget(budget_limits or {Metric.TOKENS: 1_000_000}, audit=audit, ticket_id=ticket.id)
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True, exist_ok=True)
    ticket.status = Status.RUNNING
    cycle = Cycle(
        ticket=ticket, role=role, model_config=ModelConfig("stub", provider="stub"),
        model_adapter=StubModel(stub), budget=budget, audit=audit, toolset=toolset,
        workspace=workspace, graph=TicketGraph(audit=audit), knowledge_base=KnowledgeBase(audit=audit),
        score_system=ScoreSystem(audit=audit),
        on_create_ticket=on_create_ticket, stream_sink=stream_sink, max_iterations=6,
    )
    return cycle, audit, workspace


def code_stub(state=None):
    state = state if state is not None else {"wrote": False}

    def stub(messages):
        text = messages[-1]["content"]
        if "PHASE: context_exploration" in text:
            return {"action": "finish", "args": {}}
        if "PHASE: changes" in text:
            if not state["wrote"]:
                state["wrote"] = True
                return {"action": "file_edit", "args": {"path": "solution.py", "content": "VALUE = 42\n"}}
            return {"action": "finish", "args": {}}
        if "PHASE: model_verification" in text:
            return {"action": "verify", "args": {"passed": True, "reason": "file written, checks pass"}}
        return {"action": "finish", "args": {}}
    return stub


def assert_ticket_command_success(ticket, command):
    matches = [e for e in ticket.evidence if f"$ {command}" in e.get("proof", "")]
    assert matches, f"missing command evidence for {command}\navailable evidence: {ticket.evidence}"
    evidence = matches[-1]
    assert evidence.get("status") == "success", (
        f"command failed for ticket {ticket.id}\ncommand: {command}\n{evidence.get('proof', '')}"
    )
    assert "exit=0" in evidence.get("proof", ""), (
        f"command did not record exit=0 for ticket {ticket.id}\n"
        f"command: {command}\n{evidence.get('proof', '')}"
    )


def test_run_command_never_crashes_on_bad_input(tmp_path):
    from planfoldr.tools_impl import run_command
    # Unbalanced quotes: shell handles this as a syntax error, exits non-zero.
    bad = run_command('python3 -c "print(', cwd=tmp_path, timeout=5)
    assert bad["status"] == "failure"
    missing = run_command("definitely_not_a_real_binary_xyz", cwd=tmp_path, timeout=5)
    assert missing["status"] == "failure"
    empty = run_command("   ", cwd=tmp_path, timeout=5)
    assert empty["status"] == "failure"


def test_run_command_shell_operators_work(tmp_path):
    from planfoldr.tools_impl import run_command
    # && and || must work as shell operators, not be passed as filename arguments.
    ok = run_command("true && true", cwd=tmp_path, timeout=5)
    assert ok["status"] == "success"
    fail = run_command("false || false", cwd=tmp_path, timeout=5)
    assert fail["status"] == "failure"
    # A compound grep check — the original failure pattern from the hardening sweep.
    (tmp_path / "calc.py").write_text("def add(a, b): return a + b\ndef subtract(a, b): return a - b\n")
    compound = run_command("grep -q 'def add(' calc.py && grep -q 'def subtract(' calc.py", cwd=tmp_path, timeout=5)
    assert compound["status"] == "success"


def test_checks_block_appears_in_changes_prompt(tmp_path):
    """Acceptance checks are shown prominently in the changes-phase user prompt."""
    captured = []

    def stub(messages):
        text = messages[-1]["content"]
        if "PHASE: changes" in text:
            captured.append(text)
        return code_stub()(messages)

    ticket = new_ticket("dev-1", title="solution", type="code", goal="write solution.py",
                        created_by="orchestrator",
                        checks=[Check(kind="command", spec="test -f solution.py")])
    cycle, _, _ = build(tmp_path, stub=stub, ticket=ticket)
    cycle.run()
    assert captured, "changes prompt was never captured"
    assert "ACCEPTANCE CHECKS" in captured[0]
    assert "test -f solution.py" in captured[0]
    assert "finish" in captured[0]


def test_tool_call_protocol_appears_in_system_and_changes_prompts(tmp_path):
    captured = {"system": [], "user": []}

    def stub(messages):
        captured["system"].append(messages[0]["content"])
        captured["user"].append(messages[-1]["content"])
        return code_stub()(messages)

    ticket = new_ticket("dev-1", title="solution", type="code", goal="write solution.py",
                        created_by="orchestrator",
                        checks=[Check(kind="command", spec="test -f solution.py")])
    cycle, _, _ = build(tmp_path, stub=stub, ticket=ticket)
    cycle.run()
    system_prompt = "\n".join(captured["system"])
    changes_prompt = "\n".join(u for u in captured["user"] if "PHASE: changes" in u)
    verify_prompt = "\n".join(u for u in captured["user"] if "PHASE: model_verification" in u)

    assert "<tool_call>" in system_prompt
    assert '"summary":"<one short sentence>"' in system_prompt
    assert "Use 'summary' for the short visible explanation" in system_prompt
    assert '"thinking":"<one short sentence>"' not in system_prompt
    assert "Legacy bare JSON actions are accepted only for migration" in system_prompt
    assert "Respond with ONE JSON object" not in system_prompt
    assert '<tool_call>{"name":"file_edit"' in changes_prompt
    assert '<tool_call>{"name":"finish"' in changes_prompt
    assert 'Respond <tool_call>{"name":"verify"' in verify_prompt


def test_tool_call_cycle_executes_file_edit_bash_and_finish(tmp_path):
    steps = {"changes": 0}
    stream_events = []

    def stub(messages):
        text = messages[-1]["content"]
        if "PHASE: context_exploration" in text:
            return '<tool_call>{"name":"finish","arguments":{},"summary":"context ready"}</tool_call>'
        if "PHASE: changes" in text:
            steps["changes"] += 1
            if steps["changes"] == 1:
                return '<tool_call>{"name":"file_edit","arguments":{"path":"solution.py","content":"VALUE = 42\\n"},"summary":"write file"}</tool_call>'
            if steps["changes"] == 2:
                return '<tool_call>{"name":"bash","arguments":{"cmd":"test -f solution.py && grep -q VALUE solution.py"},"summary":"check file"}</tool_call>'
            return '<tool_call>{"name":"finish","arguments":{},"summary":"done"}</tool_call>'
        if "PHASE: model_verification" in text:
            return '<tool_call>{"name":"verify","arguments":{"passed":true,"reason":"tool_call file edit and bash evidence passed"},"summary":"verified"}</tool_call>'
        return '<tool_call>{"name":"finish","arguments":{}}</tool_call>'

    ticket = new_ticket("dev-1", title="solution", type="code", goal="write solution.py with VALUE=42",
                        created_by="orchestrator",
                        checks=[Check(kind="command", spec="test -f solution.py && grep -q VALUE solution.py")])
    cycle, audit, ws = build(tmp_path, stub=stub, ticket=ticket, stream_sink=stream_events.append)
    result = cycle.run()

    assert result.status == Status.DONE
    assert_ticket_command_success(ticket, "test -f solution.py && grep -q VALUE solution.py")
    assert (ws / "solution.py").read_text() == "VALUE = 42\n"
    assert any(e.get("status") == "success" for e in ticket.evidence)
    tool_events = [e.payload for e in audit.events() if e.event_type == EventType.TOOL_INVOKED]
    assert [p["tool"] for p in tool_events if p["tool"] in {"file_edit", "bash"}] == ["file_edit", "bash"]
    model_outputs = [e for e in stream_events if e.get("event") == "model_output"]
    assert any("<tool_call>" in e.get("content", "") and '"name":"file_edit"' in e.get("content", "")
               for e in model_outputs)


def test_full_code_cycle_runs_four_phases_and_completes(tmp_path):
    ticket = new_ticket("dev-1", title="solution", type="code", goal="write solution.py with VALUE=42",
                        created_by="orchestrator", checks=[Check(kind="command", spec="test -f solution.py")])
    cycle, audit, ws = build(tmp_path, stub=code_stub(), ticket=ticket)
    result = cycle.run()
    assert result.status == Status.DONE
    assert_ticket_command_success(ticket, "test -f solution.py")
    assert (ws / "solution.py").read_text() == "VALUE = 42\n"
    phases = [e.payload["phase"] for e in audit.events() if e.event_type == EventType.CYCLE_PHASE_COMPLETED]
    assert phases == [CONTEXT, "changes", COMMAND_VERIFY, MODEL_VERIFY]
    assert any(e.get("status") == "success" for e in ticket.evidence)
    assert ticket.status == Status.DONE


def test_research_ticket_spawns_implementation_before_model_verify(tmp_path):
    created = {}
    captured_verify = []

    def on_create(spec):
        child = new_ticket(spec.get("id", "developer-1"), title=spec.get("title", "implement alpha"),
                           type=spec.get("type", "code"), goal=spec.get("goal", "create alpha.txt"),
                           created_by="research-exec", spawned_by=spec.get("spawned_by"))
        created["child"] = child
        return child.id

    steps = {"changes": 0}

    def stub(messages):
        text = messages[-1]["content"]
        if "PHASE: context_exploration" in text:
            return {"action": "finish", "args": {}}
        if "PHASE: changes" in text:
            assert "RESEARCH COMPLETION RULE" in text
            steps["changes"] += 1
            if steps["changes"] == 1:
                return {"action": "write_context", "args": {"section": "alpha", "content": "spec and test plan"}}
            if steps["changes"] == 2:
                return {"action": "create_ticket", "args": {"id": "developer-1", "type": "code",
                    "title": "implement alpha", "goal": "create alpha.txt from the research findings"}}
            return {"action": "finish", "args": {}}
        if "PHASE: model_verification" in text:
            captured_verify.append(text)
            return {"action": "verify", "args": {"passed": True, "reason": "research spawned code work"}}
        return {"action": "finish", "args": {}}

    ticket = new_ticket("research-1", title="r", type="research", goal="investigate alpha",
                        created_by="orchestrator")
    cycle, audit, _ = build(
        tmp_path, stub=stub, ticket=ticket, on_create_ticket=on_create,
        role_id="research-exec", role_prompt="You are a researcher.",
        can_create=["documentation", "fix", "code", "tests"],
    )
    result = cycle.run()
    phases = [e.payload["phase"] for e in audit.events() if e.event_type == EventType.CYCLE_PHASE_COMPLETED]
    assert phases == [CONTEXT, CHANGES, MODEL_VERIFY]
    assert result.status == Status.DONE
    assert created["child"].spawned_by == "research-1"
    assert "developer-1" in result.spawned_tickets
    assert any("created code ticket developer-1" in e.get("proof", "") for e in ticket.evidence)
    assert any("wrote context section alpha" in e.get("proof", "") for e in ticket.evidence)
    assert "created code ticket developer-1" in captured_verify[-1]


def test_verify_ticket_runs_command_plus_model_verify_only(tmp_path):
    ticket = new_ticket("ver-1", title="v", type="verify", goal="confirm", created_by="orchestrator",
                        checks=[Check(kind="command", spec="true")])
    def stub(messages):
        return {"action": "verify", "args": {"passed": True, "reason": "command passed"}}
    cycle, audit, _ = build(tmp_path, stub=stub, ticket=ticket)
    result = cycle.run()
    phases = [e.payload["phase"] for e in audit.events() if e.event_type == EventType.CYCLE_PHASE_COMPLETED]
    assert phases == [COMMAND_VERIFY, MODEL_VERIFY]
    assert result.status == Status.DONE


def test_create_ticket_spawns_child_with_spawned_by(tmp_path):
    created = {}

    def on_create(spec):
        child = new_ticket(spec.get("id", "dev-2"), title=spec.get("title", "child"),
                           type=spec.get("type", "tests"), goal=spec.get("goal", "g"),
                           created_by="developer", spawned_by=spec.get("spawned_by"))
        created["child"] = child
        return child.id

    def stub(messages):
        text = messages[-1]["content"]
        if "PHASE: context_exploration" in text:
            return {"action": "finish", "args": {}}
        if "PHASE: changes" in text:
            if "child" not in created:
                return {"action": "create_ticket", "args": {"type": "tests", "title": "write tests", "goal": "test it"}}
            return {"action": "finish", "args": {}}
        return {"action": "verify", "args": {"passed": True, "reason": "ok"}}

    ticket = new_ticket("dev-1", title="t", type="code", goal="build + spawn tests", created_by="orchestrator")
    cycle, _, _ = build(tmp_path, stub=stub, ticket=ticket, on_create_ticket=on_create)
    result = cycle.run()
    assert created["child"].spawned_by == "dev-1"   # spawned_by recorded
    assert created["child"].id in result.spawned_tickets


def test_budget_soft_stop_sets_budget_exceeded(tmp_path):
    ticket = new_ticket("dev-1", title="t", type="code", goal="g", created_by="orchestrator")
    # Tiny token limit -> the first model call already crosses it -> soft stop.
    cycle, audit, _ = build(tmp_path, stub=code_stub(), ticket=ticket, budget_limits={Metric.TOKENS: 5})
    result = cycle.run()
    assert result.status == "budget_exceeded"
    assert cycle.budget.exceeded is True
    assert ticket.status == Status.RUNNING  # not declared done under soft stop
    assert any(e.event_type == EventType.BUDGET_EXCEEDED for e in audit.events())


def test_local_memory_does_not_leak_between_cycles(tmp_path):
    t1 = new_ticket("dev-1", title="a", type="code", goal="g", created_by="o",
                    checks=[Check(kind="command", spec="test -f solution.py")])
    t2 = new_ticket("dev-2", title="b", type="code", goal="g", created_by="o",
                    checks=[Check(kind="command", spec="test -f solution.py")])
    c1, _, _ = build(tmp_path / "a", stub=code_stub(), ticket=t1)
    c2, _, _ = build(tmp_path / "b", stub=code_stub(), ticket=t2)
    r1 = c1.run()
    c2.run()
    assert c1.local_memory is not c2.local_memory
    assert c1.execution_id != c2.execution_id
    # local memory is internal -- only facts flow up via output, not the raw working memory
    assert "changes_log" not in r1.output and "context" not in r1.output


def test_child_cycle_does_not_close_parent(tmp_path):
    parent = new_ticket("top-1", title="top", type="orchestration", goal="own the tree", created_by="human")
    child = new_ticket("dev-1", title="leaf", type="code", goal="write solution.py",
                       created_by="orchestrator", spawned_by="top-1",
                       checks=[Check(kind="command", spec="test -f solution.py")])
    cycle, _, _ = build(tmp_path, stub=code_stub(), ticket=child)
    result = cycle.run()
    assert result.status == Status.DONE and child.status == Status.DONE
    assert parent.status == Status.INCOMING  # the child never touched the parent/project


def test_file_edit_patch_modifies_existing_file(tmp_path):
    """file_edit with a unified diff patch edits an existing file; metrics reflect only the changed lines."""
    patch_text = (
        "--- a/target.py\n"
        "+++ b/target.py\n"
        "@@ -1,3 +1,3 @@\n"
        " line1\n"
        "-line2\n"
        "+line2_patched\n"
        " line3\n"
    )
    state = {"patched": False}

    def stub(messages):
        text = messages[-1]["content"]
        if "PHASE: context_exploration" in text:
            return {"action": "finish", "args": {}}
        if "PHASE: changes" in text:
            if not state["patched"]:
                state["patched"] = True
                return {"action": "file_edit", "args": {"path": "target.py", "patch": patch_text}}
            return {"action": "finish", "args": {}}
        if "PHASE: model_verification" in text:
            return {"action": "verify", "args": {"passed": True, "reason": "patch applied"}}
        return {"action": "finish", "args": {}}

    ticket = new_ticket("dev-1", title="patch test", type="code", goal="patch target.py",
                        created_by="orchestrator")
    cycle, audit, workspace = build(tmp_path, stub=stub, ticket=ticket)
    (workspace / "target.py").write_text("line1\nline2\nline3\n")

    result = cycle.run()

    assert result.status == Status.DONE
    assert (workspace / "target.py").read_text() == "line1\nline2_patched\nline3\n"
    tool_events = [
        e for e in audit.events()
        if e.event_type == EventType.TOOL_INVOKED and e.payload.get("tool") == "file_edit"
    ]
    assert tool_events, "file_edit tool event not recorded in audit"
    r = tool_events[0].payload["result"]
    assert r["action"] == "modified"
    assert r["lines_added"] == 1
    assert r["lines_removed"] == 1


def test_patch_mode_documented_in_changes_prompt(tmp_path):
    """The changes-phase prompt mentions both full-content and patch modes for file_edit."""
    captured = []

    def stub(messages):
        text = messages[-1]["content"]
        if "PHASE: changes" in text:
            captured.append(text)
        return code_stub()(messages)

    ticket = new_ticket("dev-1", title="t", type="code", goal="write solution.py",
                        created_by="orchestrator")
    cycle, _, _ = build(tmp_path, stub=stub, ticket=ticket)
    cycle.run()
    assert captured, "changes prompt was never captured"
    prompt = captured[0]
    assert "patch" in prompt, "patch mode not mentioned in changes prompt"
    assert "content" in prompt, "full-content mode not mentioned in changes prompt"
    assert "existing" in prompt.lower(), "prompt should clarify patch is for existing files"
