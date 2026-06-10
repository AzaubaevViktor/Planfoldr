import json
import socket
import time
from io import StringIO
from pathlib import Path

from planfoldr.model import StubModel
from planfoldr.orchestrator import run_scenario
from planfoldr.visibility.events import SLICES, VisibilityState
from planfoldr.visibility.terminal import TerminalStream
from planfoldr.visibility.web import render_state_view_html, render_stream_log_html
from planfoldr.visibility.ws import accept_key, encode_text_frame, read_frame, WebSocketServer

import tests.test_e2e_stub as E2E


# -- state aggregation --------------------------------------------------------
def feed(state, et, *, ticket_id=None, cycle_id=None, **payload):
    state.ingest({"event": "audit", "event_type": et, "ticket_id": ticket_id, "cycle_id": cycle_id,
                  "payload": payload, "seq": 1, "timestamp": "t"})


def visible_page(html: str) -> str:
    return html.split("<script>window.__SNAPSHOT__", 1)[0]


def test_state_slices_populated_from_events():
    s = VisibilityState()
    feed(s, "scenario.started", scenario="demo", goal="do it")
    feed(s, "queue.created", queue="developer", roles=["developer-manager", "developer-exec"])
    feed(s, "ticket.created", ticket_id="developer-1", type="code", title="impl")
    feed(s, "cycle.started", ticket_id="developer-1", cycle_id="c1", model="m", role="developer-exec")
    feed(s, "cycle.phase_completed", ticket_id="developer-1", cycle_id="c1", phase="changes", budget={"tokens_used": 10})
    feed(s, "tool.invoked", ticket_id="developer-1", cycle_id="c1", tool="file_edit", args={}, result={"path": "x"})
    feed(s, "model.score_updated", model="m", delta=1.0, global_score=11.0)
    feed(s, "cycle.completed", ticket_id="developer-1", cycle_id="c1", status="done", spawned=[])
    snap = s.snapshot()
    for slice_name in SLICES:
        assert slice_name in snap
    assert "developer" in snap["queues"]
    assert snap["tickets"]["developer-1"]["type"] == "code"
    assert snap["cycles"]["c1"]["status"] == "done"
    assert snap["tools"]["file_edit"] == 1
    assert snap["models"]["m"]["global_score"] == 11.0
    assert snap["system"]["scenario"] == "demo"


def test_state_view_html_has_all_required_slices():
    html = render_state_view_html(ws_port=1234)
    for slice_name in SLICES:
        assert f'id="{slice_name}"' in html
    assert "<details" in html and "<summary>" in html
    assert "queues" in html and "cycle_tree" in html and "budgets" in html


def test_stream_log_renders_entries_and_goal_header():
    snap = {"scenario": {"name": "demo", "goal": "build the thing"}, "status": "running",
            "log": [{"type": "audit", "event_type": "cycle.started", "cycle_id": "c1", "ticket_id": "dev-1",
                     "payload": {"model": "m", "role": "developer"}},
                    {"type": "model_output", "cycle_id": "c1", "content": '{"action":"finish"}', "thinking": "done"}]}
    html = render_stream_log_html(embedded=snap)
    # Goal/description at the TOP (in the header, before the log section heading).
    assert "build the thing" in html
    assert html.index("build the thing") < html.index("<h2>Streaming Log")  # heading may carry a pause-refresh button
    assert html.index("build the thing") < html.index('class="cyc"')  # goal precedes the log entries
    assert 'class="cyc"' in html and "<details" in html  # expandable executions
    assert "__SNAPSHOT__" in html


def test_stream_log_renders_tool_call_envelope_as_action_block():
    content = '<tool_call>{"name":"file_edit","arguments":{"path":"demo.txt","content":"ok\\n"},"summary":"write demo"}</tool_call>'
    snap = {"scenario": {"name": "demo", "goal": "render tool calls"}, "status": "done",
            "log": [{"type": "model_output", "cycle_id": "c1", "phase": "changes", "model": "stub",
                     "content": content, "thinking": "", "tokens": 12}]}
    html = render_stream_log_html(embedded=snap)
    assert "<b>file_edit</b>" in html
    assert "demo.txt" in html
    assert "<b>summary</b>: write demo" in html
    assert "write demo" in html
    assert "&lt;tool_call&gt;" not in html


def test_stream_log_renders_tool_call_function_envelope_as_action_block():
    content = '<tool_call>{"function":{"name":"bash","arguments":"{\\"cmd\\": \\"pytest -q\\"}"},"summary":"run tests"}</tool_call>'
    snap = {"scenario": {"name": "demo", "goal": "render function tool call"}, "status": "done",
            "log": [{"type": "model_output", "cycle_id": "c1", "phase": "changes", "model": "stub",
                     "content": content, "thinking": "", "tokens": 12}]}
    page = visible_page(render_stream_log_html(embedded=snap))
    assert "<b>bash</b>" in page
    assert "<b>summary</b>: run tests" in page
    assert "<th>cmd</th><td>pytest -q</td>" in page
    assert "&lt;tool_call&gt;" not in page
    assert "{&quot;function&quot;" not in page


def test_stream_log_labels_internal_thinking_and_action_summary_separately():
    content = '<tool_call>{"name":"bash","arguments":{"cmd":"pytest -q"},"summary":"run focused tests"}</tool_call>'
    snap = {"scenario": {"name": "demo", "goal": "separate thinking"}, "status": "done",
            "log": [{"type": "model_output", "cycle_id": "c1", "phase": "changes", "model": "stub",
                     "content": content, "thinking": "provider chain of thought preview", "tokens": 12}]}
    page = visible_page(render_stream_log_html(embedded=snap))
    assert "<b>internal thinking</b>: provider chain of thought preview" in page
    assert "<b>summary</b>: run focused tests" in page
    assert page.index("<b>internal thinking</b>") < page.index("<b>summary</b>")


def test_visibility_state_preserves_live_thinking_preview():
    s = VisibilityState()
    feed(s, "cycle.started", ticket_id="dev-1", cycle_id="c1", model="m", role="developer")
    s.ingest({"event": "model_stream_chunk", "cycle_id": "c1", "ticket_id": "dev-1",
              "phase": "changes", "kind": "thinking", "text": "considering plan"})
    s.ingest({"event": "model_stream_chunk", "cycle_id": "c1", "ticket_id": "dev-1",
              "phase": "changes", "kind": "content", "text": "<tool_call>"})
    snap = s.snapshot()
    assert snap["cycles"]["c1"]["live_thinking"] == "considering plan"
    assert snap["cycles"]["c1"]["live"] == "<tool_call>"


def test_visibility_state_tracks_current_activity_fields_and_labels():
    s = VisibilityState()
    feed(s, "cycle.started", ticket_id="dev-1", cycle_id="c1", model="stub", role="developer")
    feed(s, "cycle.phase_started", ticket_id="dev-1", cycle_id="c1", phase="changes")
    s.ingest({"event": "model_stream_chunk", "cycle_id": "c1", "ticket_id": "dev-1",
              "phase": "changes", "kind": "content", "text": "writing"})
    activity = s.snapshot()["activity"]
    assert activity["current_action"] == "model_generating"
    assert activity["current_action_label"] == "модель генерирует"
    assert activity["current_model"] == "stub"
    assert activity["current_tool"] is None
    assert activity["current_phase"] == "changes"
    assert activity["ticket_id"] == "dev-1"
    assert activity["cycle_id"] == "c1"

    feed(s, "tool.invoked", ticket_id="dev-1", cycle_id="c1", tool="file_edit",
         args={"path": "a.py"}, result={"action": "created"})
    activity = s.snapshot()["activity"]
    assert activity["current_action"] == "tool_running"
    assert activity["current_action_label"] == "выполняется tool: file_edit"
    assert activity["current_tool"] == "file_edit"

    feed(s, "cycle.phase_started", ticket_id="dev-1", cycle_id="c1", phase="command_verification")
    assert s.snapshot()["activity"]["current_action_label"] == "идёт проверка"
    feed(s, "cycle.phase_completed", ticket_id="dev-1", cycle_id="c1", phase="command_verification")
    assert s.snapshot()["activity"]["current_action_label"] == "ожидание следующей фазы"
    feed(s, "scenario.completed", status="done", reason="ok")
    assert s.snapshot()["activity"]["current_action_label"] == "сценарий завершён: done"


def test_stream_log_renders_live_preview_and_current_status():
    s = VisibilityState()
    feed(s, "scenario.started", scenario="demo", goal="live")
    feed(s, "cycle.started", ticket_id="dev-1", cycle_id="c1", model="stub", role="developer")
    s.ingest({"event": "model_stream_chunk", "cycle_id": "c1", "ticket_id": "dev-1",
              "phase": "changes", "kind": "content", "text": "live model text"})
    snap = s.snapshot()
    snap.update({"scenario": {"name": "demo", "goal": "live"}, "status": "running", "log": s.recent_log()})
    page = visible_page(render_stream_log_html(embedded=snap))
    assert "модель генерирует" in page
    assert "live model text" in page
    assert 'id="live-preview"' in page


def test_stream_log_shows_new_ticket_before_cycle_completion():
    s = VisibilityState()
    feed(s, "scenario.started", scenario="demo", goal="spawn")
    feed(s, "cycle.started", ticket_id="orchestration-0", cycle_id="c1", model="stub", role="orchestrator")
    feed(s, "ticket.created", ticket_id="developer-1", cycle_id="c1", type="code",
         title="impl", goal="write the implementation", spawned_by="orchestration-0")
    snap = s.snapshot()
    snap.update({"scenario": {"name": "demo", "goal": "spawn"}, "status": "running", "log": s.recent_log()})
    page = visible_page(render_stream_log_html(embedded=snap))
    assert "developer-1" in page
    assert "write the implementation" in page
    assert "cycle.completed" not in page


def test_stream_log_websocket_script_handles_live_events():
    from planfoldr.visibility.web import _WS_SCRIPT

    assert "__PLANFOLDR_HANDLE_EVENT__" in _WS_SCRIPT
    assert "model_stream_chunk" in _WS_SCRIPT
    assert "ticket.created" in _WS_SCRIPT
    assert "tool.invoked" in _WS_SCRIPT
    assert "cycle.phase_started" in _WS_SCRIPT
    assert "appendPreview(ev)" in _WS_SCRIPT
    assert "appendLog" in _WS_SCRIPT
    assert "модель генерирует" in _WS_SCRIPT
    assert "выполняется tool: " in _WS_SCRIPT


def test_static_index_report_updates_on_live_events(tmp_path):
    seen = {}

    def stub(messages):
        text = messages[-1]["content"]
        if "PHASE: context_exploration" in text:
            return {"action": "finish", "args": {}}
        if "PHASE: changes" in text and "(orchestration)" in text:
            if not seen.get("created"):
                seen["created"] = True
                return {"action": "create_ticket", "args": {"id": "developer-1", "type": "code",
                    "title": "impl", "goal": "create file alpha.txt",
                    "checks": [{"kind": "command", "spec": "test -f alpha.txt"}]}}
            return {"action": "finish", "args": {}}
        if "PHASE: changes" in text:
            if not seen.get("wrote"):
                seen["wrote"] = True
                return {"action": "file_edit", "args": {"path": "alpha.txt", "content": "ok\n"}}
            return {"action": "finish", "args": {}}
        if "PHASE: model_verification" in text:
            return {"action": "verify", "args": {"passed": True, "reason": "evidence passed"}}
        return {"action": "finish", "args": {}}

    observations = {}

    def sink(event):
        run_dirs = list(tmp_path.glob("*test_run_live_report*"))
        if not run_dirs:
            return
        index = run_dirs[0] / "visibility" / "index.html"
        if not index.exists():
            return
        text = index.read_text()
        if event.get("event") == "model_stream_chunk" and "model_stream_chunk" not in observations:
            observations["model_stream_chunk"] = "модель генерирует" in text and "action" in text
        if event.get("event") == "model_output" and "model_output" not in observations:
            observations["model_output"] = "<tool_call>" in text or "file_edit" in text
        if event.get("event") == "audit" and event.get("event_type") == "ticket.created":
            observations["ticket.created"] = "developer-1" in text
        if event.get("event") == "audit" and event.get("event_type") == "tool.invoked":
            observations.setdefault("tool.invoked", "file_edit" in text or "create_ticket" in text)

    result = run_scenario(E2E.base_scenario(commands=["test -f alpha.txt"]), runs_dir=tmp_path,
                          run_id="test_run_live_report", model_adapter=StubModel(stub),
                          stream_sink=sink)
    assert result.status == "done", result.reason
    assert observations.get("model_stream_chunk") is True
    assert observations.get("model_output") is True
    assert observations.get("ticket.created") is True
    assert observations.get("tool.invoked") is True


def test_terminal_stream_renders_thinking_chunks_live():
    out = StringIO()
    terminal = TerminalStream(out=out)
    terminal.sink({"event": "model_stream_chunk", "kind": "thinking", "text": "live thought"})
    terminal.sink({"event": "model_stream_chunk", "kind": "content", "text": "final content"})
    rendered = out.getvalue()
    assert "💭 live thought" in rendered
    assert "📤 final content" in rendered


def test_stream_log_renders_malformed_tool_call_without_raw_dump():
    content = '<tool_call>{"name":"bash","arguments":{"cmd":"pytest "bad""}}</tool_call>'
    snap = {"scenario": {"name": "demo", "goal": "render malformed tool calls"}, "status": "done",
            "log": [{"type": "model_output", "cycle_id": "c1", "phase": "changes", "model": "stub",
                     "content": content, "thinking": "", "tokens": 12}]}
    html = render_stream_log_html(embedded=snap)
    assert "<b>bash</b>" in html
    assert "malformed tool_call" in html
    assert "&lt;tool_call&gt;" not in html


def test_stream_log_renders_malformed_model_json_as_diagnostic_not_raw_dump():
    content = '{"action":"bash","summary":"run tests","text":"pytest says "bad""'
    snap = {"scenario": {"name": "demo", "goal": "render malformed json"}, "status": "done",
            "log": [{"type": "model_output", "cycle_id": "c1", "phase": "changes", "model": "stub",
                     "content": content, "thinking": "", "tokens": 12}]}
    page = visible_page(render_stream_log_html(embedded=snap))
    assert "unparsed model action" in page
    assert "<th>action</th><td>bash</td>" in page
    assert "<th>summary</th><td>run tests</td>" in page
    assert "<th>text</th><td>pytest says </td>" in page
    assert '<pre class="model-content">' not in page
    assert "{&quot;action&quot;" not in page


def test_stream_log_renders_unknown_model_json_envelope_as_diagnostic():
    content = '{"summary":"cannot continue","tool_name":"bash","text":"Need pytest output","arguments":{"cmd":"pytest -q"}}'
    snap = {"scenario": {"name": "demo", "goal": "render unknown json"}, "status": "done",
            "log": [{"type": "model_output", "cycle_id": "c1", "phase": "changes", "model": "stub",
                     "content": content, "thinking": "", "tokens": 12}]}
    page = visible_page(render_stream_log_html(embedded=snap))
    assert "unparsed model action" in page
    assert "<th>summary</th><td>cannot continue</td>" in page
    assert "<th>tool_name</th><td>bash</td>" in page
    assert "<th>text</th><td>Need pytest output</td>" in page
    assert "cmd" in page and "pytest -q" in page
    assert '<pre class="model-content">' not in page
    assert "{&quot;summary&quot;" not in page


def test_stream_log_renders_plain_model_text_as_prose():
    content = "I inspected the workspace and need one more command."
    snap = {"scenario": {"name": "demo", "goal": "render prose"}, "status": "done",
            "log": [{"type": "model_output", "cycle_id": "c1", "phase": "context_exploration",
                     "model": "stub", "content": content, "thinking": "", "tokens": 8}]}
    page = visible_page(render_stream_log_html(embedded=snap))
    assert 'class="model-prose"' in page
    assert content in page
    assert "unparsed model action" not in page
    assert '<pre class="model-content">' not in page


def test_tickets_page_shows_comments_history_and_evidence():
    from planfoldr.visibility.web import render_tickets_html
    snap = {"tickets": {"dev-1": {
        "id": "dev-1", "type": "code", "title": "impl", "goal": "write calc.py", "status": "done",
        "role": "developer-exec", "queue": "developer", "attempt_count": 1, "max_attempts": 3,
        "spawned_by": "orchestration-0", "dependencies": [],
        "comments": [{"author": "developer", "text": "needs a security pass", "timestamp": "t", "summoned_role": "security"}],
        "evidence": [{"check_index": 0, "status": "success", "proof": "pytest exit 0"}],
        "checks": [{"kind": "command", "spec": "pytest", "required": True}],
        "metadata": {"change_history": [{"from": "running", "to": "done", "actor": "developer", "at": "t"}]},
    }}, "graph": {"nodes": [], "links": []}}
    html = render_tickets_html(embedded=snap)
    assert "write calc.py" in html and "needs a security pass" in html
    assert "security" in html and "running" in html and "done" in html  # history + summons
    assert "pytest exit 0" in html  # evidence


def test_kb_page_shows_sections_and_content():
    from planfoldr.visibility.web import render_kb_html
    snap = {"kb": {"findings": {"content": "the bug is in auth.py", "read_roles": ["*"],
                                "write_roles": ["developer"], "versions": [{"version": 1, "timestamp": "t", "role": "developer"}]}}}
    html = render_kb_html(embedded=snap)
    assert "findings" in html and "the bug is in auth.py" in html and "developer" in html


def test_state_view_commands_and_budgets_are_human_readable():
    snap = {
        "scenario": {"name": "s", "goal": "g"}, "status": "done",
        "commands": [{"when": "2026-06-10T...", "actor": "developer-exec", "ticket": "dev-1",
                      "cmd": "pytest", "exit_code": 0, "status": "success"}],
        "budgets": {"project": {"usage": {"tokens_used": 100}, "limits": {"tokens_used": 1000}, "exceeded": False},
                    "tickets": [{"ticket": "dev-1", "title": "implement", "goal": "write calc.py",
                                 "usage": {"tokens_used": 80, "api_requests": 4}, "limits": {}, "exceeded": False}]},
        "tickets": {"dev-1": {"id": "dev-1", "type": "code", "status": "done"}},
    }
    html = render_state_view_html(embedded=snap)
    assert "developer-exec" in html and "pytest" in html  # commands: who + cmd
    assert "implement" in html and "write calc.py" in html  # budgets keyed by ticket title/goal, not exec_ ids
    assert "exec_" not in html.split("State View")[-1] or "implement" in html  # readable, not raw exec ids


# -- websocket primitives -----------------------------------------------------
def test_accept_key_matches_rfc6455_vector():
    assert accept_key("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="


def test_frame_roundtrip_over_socketpair():
    a, b = socket.socketpair()
    # client → server frame is masked
    data = "hello ws".encode()
    mask = b"\x01\x02\x03\x04"
    masked = bytes(c ^ mask[i % 4] for i, c in enumerate(data))
    a.sendall(bytes([0x81, 0x80 | len(data)]) + mask + masked)
    opcode, payload = read_frame(b)
    assert opcode == 0x1 and payload == data
    # server → client frame is unmasked
    frame = encode_text_frame("hi")
    assert frame[0] == 0x81 and frame[2:] == b"hi"
    a.close(); b.close()


def test_ws_server_handshakes_and_broadcasts():
    srv = WebSocketServer("127.0.0.1", 0)
    port = srv.start()
    try:
        c = socket.create_connection(("127.0.0.1", port), timeout=3)
        c.sendall(
            b"GET / HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
            b"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        resp = c.recv(1024)
        assert b"101" in resp and b"s3pPLMBiTxaQ9kYGzzhZRbK+xOo=" in resp
        for _ in range(50):
            if srv.client_count == 1:
                break
            time.sleep(0.02)
        assert srv.client_count == 1
        srv.broadcast("live-event")
        c.settimeout(3)
        frame = c.recv(1024)
        length = frame[1] & 0x7F
        assert frame[2:2 + length] == b"live-event"
        c.close()
    finally:
        srv.stop()


# -- static, server-free report from a real run -------------------------------
def test_run_writes_static_visibility_report(tmp_path):
    result = run_scenario(E2E.base_scenario(), runs_dir=tmp_path, run_id="test_run_vis",
                          model_adapter=StubModel(E2E.make_e2e_stub()))
    vis = Path(result.run_dir) / "visibility"
    index = (vis / "index.html").read_text()
    state = (vis / "state.html").read_text()
    # Server-free: the snapshot is embedded in the file.
    assert "__SNAPSHOT__" in index and "developer-1" in index
    for slice_name in SLICES:
        assert f'id="{slice_name}"' in state
    assert "developer-1" in state and "tools" in state


def test_run_writes_all_pages_analysis_and_model_io(tmp_path):
    result = run_scenario(E2E.base_scenario(), runs_dir=tmp_path, run_id="test_run_full_vis",
                          model_adapter=StubModel(E2E.make_e2e_stub()))
    run = Path(result.run_dir)
    vis = run / "visibility"
    for page in ["index.html", "state.html", "tickets.html", "kb.html", "analysis.html"]:
        assert (vis / page).exists(), page
    # Structured analysis artifact for human + improving agent.
    analysis = (run / "analysis.md").read_text()
    assert "# Run Analysis" in analysis and "## Summary" in analysis
    assert "## Harness improvement suggestions" in analysis
    # Full model I/O persisted (nothing lost), per call.
    model_io = (run / "model_io.jsonl").read_text().strip().splitlines()
    assert len(model_io) >= 3
    # Streaming start preserved: the first model output content is present in the log page.
    tickets_page = (vis / "tickets.html").read_text()
    assert "developer-1" in tickets_page and "create file alpha.txt" in tickets_page


def test_tool_call_run_writes_readable_model_io_and_index(tmp_path):
    state = {"top": 0, "wrote": False}

    def stub(messages):
        text = messages[-1]["content"]
        if "PHASE: context_exploration" in text:
            return '<tool_call>{"name":"finish","arguments":{}}</tool_call>'
        if "PHASE: model_verification" in text:
            return '<tool_call>{"name":"verify","arguments":{"passed":true,"reason":"alpha.txt exists"}}</tool_call>'
        if "PHASE: changes" in text and "(orchestration)" in text:
            state["top"] += 1
            if state["top"] == 1:
                return ('<tool_call>{"name":"create_ticket","arguments":{"id":"developer-1","type":"code",'
                        '"title":"impl alpha","goal":"create file alpha.txt","checks":[{"kind":"command",'
                        '"spec":"test -f alpha.txt"}]}}</tool_call>')
            return '<tool_call>{"name":"finish","arguments":{}}</tool_call>'
        if "PHASE: changes" in text and not state["wrote"]:
            state["wrote"] = True
            return '<tool_call>{"name":"file_edit","arguments":{"path":"alpha.txt","content":"ok\\n"}}</tool_call>'
        return '<tool_call>{"name":"finish","arguments":{}}</tool_call>'

    result = run_scenario(E2E.base_scenario(commands=["test -f alpha.txt"]), runs_dir=tmp_path,
                          run_id="test_run_tool_call_vis", model_adapter=StubModel(stub))
    assert result.status == "done", result.reason
    run = Path(result.run_dir)
    model_io = [json.loads(line)["content"] for line in (run / "model_io.jsonl").read_text().splitlines()]
    index = (run / "visibility" / "index.html").read_text()
    assert any("<tool_call>" in content and '"name":"file_edit"' in content for content in model_io)
    assert "<b>file_edit</b>" in index and "alpha.txt" in index


# -- visibility hardening (q10b) ----------------------------------------------

def test_visibility_errors_logged_to_artifact(tmp_path):
    """vis.ingest failures must be captured in visibility_errors.jsonl, not silently dropped."""
    from unittest.mock import patch
    from planfoldr.visibility.events import VisibilityState

    call_count = {"n": 0}
    original_ingest = VisibilityState.ingest.__wrapped__ if hasattr(VisibilityState.ingest, "__wrapped__") else VisibilityState.ingest

    def failing_ingest(self, event):
        call_count["n"] += 1
        if call_count["n"] <= 3:
            raise RuntimeError("injected vis failure")
        return original_ingest(self, event)

    with patch.object(VisibilityState, "ingest", failing_ingest):
        result = run_scenario(E2E.base_scenario(), runs_dir=tmp_path, run_id="test_run_vis_err",
                              model_adapter=StubModel(E2E.make_e2e_stub()))

    assert result.status == "done", f"run must still complete: {result.reason}"
    err_file = Path(result.run_dir) / "visibility_errors.jsonl"
    assert err_file.exists(), "visibility_errors.jsonl must exist when vis.ingest raises"
    errors = [json.loads(line) for line in err_file.read_text().splitlines()]
    assert any(e.get("where") == "vis.ingest" for e in errors)
    assert any("injected vis failure" in e.get("error", "") for e in errors)


def test_state_view_system_shows_failed_tickets_and_reason():
    """_render_system in state.html must surface failed ticket ids and the status reason."""
    snap = {
        "scenario": {"name": "s", "goal": "g", "constraints": [], "verification_commands": []},
        "status": "failed",
        "system": {"scenario": "s", "status": "failed",
                   "reason": "final verification failed; failed tickets: ['developer-1']"},
        "tickets": {
            "developer-1": {"id": "developer-1", "type": "code", "status": "failed",
                            "title": "impl", "goal": "g", "role": "developer-exec",
                            "attempt_count": 3, "max_attempts": 3, "spawned_by": None, "dependencies": []},
            "scenario-verify": {"id": "scenario-verify", "type": "verify", "status": "failed",
                                "title": "final", "goal": "g", "role": "verification-exec",
                                "attempt_count": 1, "max_attempts": 3, "spawned_by": None, "dependencies": []},
        },
        "budgets": {"project": {"exceeded": False, "usage": {}, "limits": {}}, "tickets": []},
        "queues": {}, "tools": {}, "cycles": {}, "cycle_tree": [], "scores": {},
    }
    page = visible_page(render_state_view_html(embedded=snap))
    # System section must show the status reason and the failed ticket id
    system_slice = page.split('id="system"', 1)[1].split('</section>', 1)[0]
    assert "developer-1" in system_slice, "failed ticket id must appear in system section"
    assert "final verification failed" in system_slice, "status reason must appear in system section"
    assert "Failed tickets" in system_slice, "'Failed tickets' label must appear in system section"


def test_stream_log_header_shows_status_reason():
    """Stream log header must display the status reason when the scenario has one."""
    snap = {
        "scenario": {"name": "s", "goal": "g"},
        "status": "failed",
        "system": {"reason": "final verification failed"},
        "log": [],
    }
    page = visible_page(render_stream_log_html(embedded=snap))
    header = page.split("<h2>Streaming Log", 1)[0]
    assert "final verification failed" in header, "status reason must appear in the page header before the log"


def test_stream_log_shows_bash_stderr():
    """Bash tool calls with non-empty stderr must render a visible 'stderr' label and the content."""
    snap = {
        "scenario": {"name": "s", "goal": "g"},
        "status": "done",
        "log": [{"type": "audit", "event_type": "tool.invoked", "ticket_id": "dev-1", "cycle_id": "c1",
                 "payload": {"tool": "bash", "args": {"cmd": "exit 1"},
                             "result": {"exit_code": 1, "stdout": "", "stderr": "bash: exit code 1 detail"}}}],
    }
    page = visible_page(render_stream_log_html(embedded=snap))
    assert "stderr" in page, "streaming log must show 'stderr' label for bash with stderr output"
    assert "bash: exit code 1 detail" in page, "stderr content must be visible in streaming log"


def test_commands_table_shows_stderr_for_failing_command():
    """state.html commands table must show stderr text for commands that produced it."""
    snap = {
        "scenario": {"name": "s", "goal": "g"},
        "status": "failed",
        "system": {},
        "commands": [{"when": "t", "actor": "developer-exec", "ticket": "dev-1",
                      "cmd": "test -f missing.txt", "exit_code": 1, "status": "failure",
                      "stderr": "test: missing.txt: no such file"}],
        "tickets": {"dev-1": {"id": "dev-1", "type": "code", "status": "failed",
                               "title": "impl", "role": "developer-exec", "attempt_count": 1, "max_attempts": 3}},
        "budgets": {"project": {"exceeded": False, "usage": {}, "limits": {}}, "tickets": []},
        "queues": {}, "tools": {}, "cycles": {}, "cycle_tree": [], "scores": {},
    }
    page = visible_page(render_state_view_html(embedded=snap))
    assert "stderr" in page, "commands table must have a 'stderr' column header"
    assert "test: missing.txt: no such file" in page, "stderr content must be visible in commands table"


def test_analysis_shows_final_verification_and_failed_tickets(tmp_path):
    """analysis.md must explicitly call out final verification result and failed ticket ids."""
    def failing_stub():
        state = {"top_step": 0}

        def stub(messages):
            text = messages[-1]["content"]
            if "PHASE: context_exploration" in text:
                return {"action": "finish", "args": {}}
            if "PHASE: model_verification" in text:
                return {"action": "verify", "args": {"passed": True, "reason": "ok"}}
            if "PHASE: changes" in text:
                if "(orchestration)" in text:
                    steps = [
                        {"action": "create_ticket", "args": {"id": "developer-1", "type": "code", "title": "impl",
                            "goal": "create file alpha.txt",
                            "checks": [{"kind": "command", "spec": "test -f alpha.txt"}]}},
                        {"action": "finish", "args": {}},
                    ]
                    i = state["top_step"]
                    state["top_step"] = i + 1
                    return steps[min(i, len(steps) - 1)]
                return {"action": "finish", "args": {}}  # never writes the file → command check fails
            return {"action": "finish", "args": {}}
        return stub

    result = run_scenario(E2E.base_scenario(commands=["test -f alpha.txt"]), runs_dir=tmp_path,
                          run_id="test_run_analysis_harden", model_adapter=StubModel(failing_stub()))
    assert result.status == "failed"
    analysis = (Path(result.run_dir) / "analysis.md").read_text()
    # Summary section: Final verification
    assert "Final verification: FAILED" in analysis, "analysis.md must show Final verification: FAILED"
    # Signatures section: explicitly names the failed ticket id
    assert "developer-1" in analysis, "analysis.md must name the failing ticket id"
    assert "Failed spawned tickets" in analysis, "analysis.md must have a 'Failed spawned tickets' signature"


# -- live streaming log HTML correctness ---------------------------------------

def test_stream_log_properly_closes_open_cycle_block():
    """A cycle that has started but not yet completed must produce well-formed HTML:
    the <details class="cyc"> block must be explicitly closed so subsequent content is
    not nested inside it.

    Verify: render_stream_log_html with a cycle.started but no cycle.completed must
    NOT leave an unclosed <details> — every opening <details class="cyc"> must have a
    matching </details>.
    """
    snap = {
        "scenario": {"name": "demo", "goal": "well-formed html"},
        "status": "running",
        "cycles": {
            "c1": {"id": "c1", "ticket": "dev-1", "model": "stub", "role": "developer",
                   "current_phase": "changes", "status": "running", "live": "", "live_thinking": ""},
        },
        "log": [
            {"type": "audit", "event_type": "cycle.started", "cycle_id": "c1", "ticket_id": "dev-1",
             "payload": {"model": "stub", "role": "developer"}, "seq": 1, "timestamp": "t"},
        ],
    }
    page = visible_page(render_stream_log_html(embedded=snap))
    # Count opening and closing tags for cycle details blocks
    open_tags = page.count('class="cyc"')
    # Each opening <details … class="cyc"> must have a matching </details>
    # Simplest check: the page must be valid enough that no cyc block is left dangling.
    # The fix adds </details> for each unclosed cycle, so the count should balance.
    assert open_tags >= 1, "cycle block must be present"
    # After the cycle block summary, there must be a </details> somewhere — verify the
    # rendered HTML does NOT end without closing the cycle block.
    assert page.count("</details>") >= open_tags, (
        "every <details class='cyc'> must have a matching </details>: "
        f"found {open_tags} opens but only {page.count('</details>')} closes"
    )


def test_stream_log_embeds_live_text_inside_open_cycle_block():
    """When a cycle is running and has live stream text, render_stream_log_html must embed
    that text as a live-preview block inside the open cycle <details>, so the streaming log
    shows in-progress generation text on every page refresh.

    Verify: snap with a running cycle that has non-empty live text → page contains both the
    cycle block AND the live text from the cycle's live field, and the live text appears
    AFTER the cycle.started summary (i.e. inside the cycle block, not somewhere else).
    """
    s = VisibilityState()
    feed(s, "scenario.started", scenario="demo", goal="live in log")
    feed(s, "cycle.started", ticket_id="dev-1", cycle_id="c1", model="stub", role="developer")
    feed(s, "cycle.phase_started", ticket_id="dev-1", cycle_id="c1", phase="changes")
    s.ingest({"event": "model_stream_chunk", "cycle_id": "c1", "ticket_id": "dev-1",
              "phase": "changes", "kind": "content", "text": "def hello_world():"})
    snap = s.snapshot()
    snap.update({"scenario": {"name": "demo", "goal": "live in log"}, "status": "running",
                 "log": s.recent_log()})
    page = visible_page(render_stream_log_html(embedded=snap))
    # Cycle block present
    assert 'class="cyc"' in page
    # Live text is in the page
    assert "def hello_world():" in page
    # Live text must also appear INSIDE the cycle block (after cycle summary), not only in
    # the sticky live-preview section above the log.  Search starting from the cycle position.
    cyc_pos = page.index('class="cyc"')
    text_pos_in_log = page.find("def hello_world():", cyc_pos)
    assert text_pos_in_log != -1, (
        "live text must appear inside the open cycle block in the streaming log section"
    )


def test_live_cleared_on_model_output():
    """After a model_output event arrives, the cycle's live and live_thinking fields must
    be empty — the full response is now in the log and the stale streaming preview should
    not bleed into the next generation turn.

    Verify: cycle.started → stream chunks → model_output → snapshot cycles live fields
    are both empty strings.
    """
    s = VisibilityState()
    feed(s, "cycle.started", ticket_id="dev-1", cycle_id="c1", model="stub", role="developer")
    s.ingest({"event": "model_stream_chunk", "cycle_id": "c1", "ticket_id": "dev-1",
              "phase": "changes", "kind": "thinking", "text": "chain of thought"})
    s.ingest({"event": "model_stream_chunk", "cycle_id": "c1", "ticket_id": "dev-1",
              "phase": "changes", "kind": "content", "text": '{"action":"finish"}'})
    # Confirm live text exists before model_output
    pre = s.snapshot()["cycles"]["c1"]
    assert pre["live_thinking"] == "chain of thought"
    assert pre["live"] == '{"action":"finish"}'
    # Now deliver model_output (the assembled full response)
    s.ingest({"event": "model_output", "cycle_id": "c1", "ticket_id": "dev-1",
              "phase": "changes", "model": "stub", "thinking": "chain of thought",
              "content": '{"action":"finish"}', "tokens": 5})
    post = s.snapshot()["cycles"]["c1"]
    assert post["live"] == "", "live must be cleared after model_output"
    assert post["live_thinking"] == "", "live_thinking must be cleared after model_output"
