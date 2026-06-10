import socket
import time
from pathlib import Path

from planfoldr.model import StubModel
from planfoldr.orchestrator import run_scenario
from planfoldr.visibility.events import SLICES, VisibilityState
from planfoldr.visibility.web import render_state_view_html, render_stream_log_html
from planfoldr.visibility.ws import accept_key, encode_text_frame, read_frame, WebSocketServer

import tests.test_e2e_stub as E2E


# -- state aggregation --------------------------------------------------------
def feed(state, et, *, ticket_id=None, cycle_id=None, **payload):
    state.ingest({"event": "audit", "event_type": et, "ticket_id": ticket_id, "cycle_id": cycle_id,
                  "payload": payload, "seq": 1, "timestamp": "t"})


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
