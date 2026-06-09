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


def test_stream_log_html_embeds_log_and_details():
    html = render_stream_log_html(embedded=({"system": {}}, [{"type": "audit", "event_type": "cycle.started"}]))
    assert "__LOG__" in html and "__SNAPSHOT__" in html
    assert "details" in html  # expandable executions


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
