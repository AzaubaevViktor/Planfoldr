"""Visibility web layer (level 6): two HTML pages + a JSON API, fed live over WebSocket.

- Streaming Log page (`/`): thinking → output → tool calls → results, each execution an expandable
  details/summary block with its input/context/tools.
- State View page (`/state`): live slices -- queues / tickets / models / commands / tools / cycles /
  cycle tree / system / budgets -- with drill-down.

The same HTML works live (served by this server, updating over the WebSocket) and as a static file
(embedded snapshot, opens with no server -- "Не требует сервера для чтения").
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from planfoldr.visibility.events import SLICES, VisibilityState
from planfoldr.visibility.ws import WebSocketServer


def render_stream_log_html(ws_port: Optional[int] = None, embedded: Optional[Tuple[dict, list]] = None) -> str:
    snap, log = embedded or ({}, [])
    return _PAGE.format(
        title="Planfoldr — Streaming Log", ws_port=ws_port or 0,
        snapshot=json.dumps(snap, default=str), log=json.dumps(log, default=str),
        body=_STREAM_BODY, script=_STREAM_SCRIPT,
    )


def render_state_view_html(ws_port: Optional[int] = None, embedded: Optional[Tuple[dict, list]] = None) -> str:
    snap, log = embedded or ({}, [])
    sections = "\n".join(
        f'<section id="{s}"><details open><summary>{s.replace("_", " ").title()}</summary>'
        f'<div class="slice" data-slice="{s}"></div></details></section>'
        for s in SLICES
    )
    return _PAGE.format(
        title="Planfoldr — State View", ws_port=ws_port or 0,
        snapshot=json.dumps(snap, default=str), log=json.dumps(log, default=str),
        body=f'<h1>State View</h1><nav>{" · ".join(f"<a href=#{s}>{s}</a>" for s in SLICES)}</nav>{sections}',
        script=_STATE_SCRIPT,
    )


class VisibilityServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.http_port = port
        self.ws_port = 0
        self.state = VisibilityState()
        self.ws = WebSocketServer(host, 0)
        self._httpd: Optional[ThreadingHTTPServer] = None
        self.run_dir: Optional[Path] = None

    def start(self) -> "VisibilityServer":
        self.ws_port = self.ws.start()
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silence
                pass

            def _send(self, body: str, ctype: str = "text/html") -> None:
                payload = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", f"{ctype}; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):  # noqa: N802
                if self.path.startswith("/state"):
                    self._send(render_state_view_html(server.ws_port))
                elif self.path.startswith("/snapshot.json"):
                    self._send(json.dumps(server.state.snapshot(), default=str), "application/json")
                elif self.path.startswith("/log.json"):
                    self._send(json.dumps(server.state.recent_log(2000), default=str), "application/json")
                else:
                    self._send(render_stream_log_html(server.ws_port))

        self._httpd = ThreadingHTTPServer((self.host, self.http_port), Handler)
        self.http_port = self._httpd.server_address[1]
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self

    def sink(self, event: Dict[str, Any]) -> None:
        self.state.ingest(event)
        try:
            self.ws.broadcast(json.dumps(event, default=str))
        except Exception:  # noqa: BLE001 -- visibility must never break the run
            pass

    def attach_run(self, run_dir: Path | str) -> None:
        self.run_dir = Path(run_dir)

    def write_static(self, run_dir: Optional[Path | str] = None) -> Path:
        target = Path(run_dir) if run_dir else (self.run_dir or Path("."))
        vis = target / "visibility"
        vis.mkdir(parents=True, exist_ok=True)
        embedded = (self.state.snapshot(), self.state.recent_log(5000))
        (vis / "index.html").write_text(render_stream_log_html(embedded=embedded), encoding="utf-8")
        (vis / "state.html").write_text(render_state_view_html(embedded=embedded), encoding="utf-8")
        return vis

    def stop(self) -> None:
        self.ws.stop()
        if self._httpd is not None:
            self._httpd.shutdown()


# --------------------------------------------------------------------------- #
# HTML / JS (kept dependency-free and small)
# --------------------------------------------------------------------------- #
_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
 body{{background:#0b0e14;color:#cdd6f4;font:13px/1.5 ui-monospace,Menlo,monospace;margin:0;padding:16px}}
 h1{{font-size:16px}} nav a{{color:#89b4fa;margin-right:6px}}
 section{{border:1px solid #313244;border-radius:8px;margin:10px 0;padding:8px}}
 summary{{cursor:pointer;color:#a6e3a1;font-weight:bold}}
 .thinking{{color:#9399b2}} .content{{color:#cdd6f4}} .tool{{color:#f9e2af}}
 .evt{{border-left:2px solid #45475a;padding:2px 8px;margin:2px 0;white-space:pre-wrap}}
 details details{{margin-left:14px}} table{{border-collapse:collapse}} td,th{{border:1px solid #313244;padding:2px 6px}}
 .status-done{{color:#a6e3a1}} .status-failed{{color:#f38ba8}} .status-running{{color:#f9e2af}}
</style></head>
<body>
<nav><a href="/">Streaming Log</a> · <a href="/state">State View</a></nav>
{body}
<script>
window.__SNAPSHOT__ = {snapshot};
window.__LOG__ = {log};
window.__WS_PORT__ = {ws_port};
{script}
</script></body></html>
"""

_STREAM_BODY = '<h1>Streaming Log</h1><div id="log"></div>'

_STREAM_SCRIPT = r"""
const logEl = document.getElementById('log');
function esc(s){return String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function render(e){
  if(e.type==='audit'){
    const p=e.payload||{};
    if(e.event_type==='cycle.started'){
      const d=document.createElement('details'); d.open=true; d.id='cyc_'+(e.cycle_id||'');
      d.innerHTML='<summary>▶ cycle '+esc(e.cycle_id||'')+' · ticket '+esc(e.ticket_id)+' · model '+esc(p.model)+' · role '+esc(p.role)+'</summary>'+
        '<div class="evt">input: ticket='+esc(e.ticket_id)+' type='+esc(p.type)+'</div>';
      logEl.appendChild(d); return;
    }
    const host=document.getElementById('cyc_'+(e.cycle_id||''))||logEl;
    const div=document.createElement('div'); div.className='evt';
    if(e.event_type==='cycle.phase_completed') div.textContent='● phase: '+p.phase;
    else if(e.event_type==='tool.invoked'){
      const det=document.createElement('details'); det.innerHTML='<summary class="tool">🔧 '+esc(p.tool)+'</summary><div class="evt">args: '+esc(JSON.stringify(p.args))+'\nresult: '+esc(JSON.stringify(p.result))+'</div>';
      host.appendChild(det); return;
    }
    else if(e.event_type==='cycle.completed') div.textContent='■ cycle '+p.status;
    else if(e.event_type==='ticket.status_changed') div.textContent='~ '+e.ticket_id+': '+p.from+' → '+p.to;
    else div.textContent=e.event_type+' '+esc(JSON.stringify(p)).slice(0,200);
    host.appendChild(div);
  } else if(e.type==='model_stream_chunk'){
    const host=logEl.lastElementChild||logEl;
    let span=host.querySelector('.live'); if(!span){span=document.createElement('div');span.className='evt live '+(e.kind||'content');host.appendChild(span);}
    span.className='evt live '+(e.kind||'content'); span.textContent=(span.textContent||'')+e.text;
  } else if(e.type==='tool_result'){
    const host=logEl.lastElementChild||logEl; const div=document.createElement('div'); div.className='evt tool';
    div.textContent='→ '+esc(JSON.stringify(e.result)).slice(0,200); host.appendChild(div);
  }
  window.scrollTo(0,document.body.scrollHeight);
}
(window.__LOG__||[]).forEach(render);
if(window.__WS_PORT__){try{const ws=new WebSocket('ws://'+location.hostname+':'+window.__WS_PORT__);ws.onmessage=m=>render(JSON.parse(m.data));}catch(e){}}
"""

_STATE_SCRIPT = r"""
function esc(s){return String(s==null?'':s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function table(rows){if(!rows.length)return '<i>none</i>';const ks=Object.keys(rows[0]);
  return '<table><tr>'+ks.map(k=>'<th>'+k+'</th>').join('')+'</tr>'+rows.map(r=>'<tr>'+ks.map(k=>'<td>'+esc(typeof r[k]==='object'?JSON.stringify(r[k]):r[k])+'</td>').join('')+'</tr>').join('')+'</table>';}
function tree(nodes){return '<ul>'+nodes.map(n=>'<li>cycle '+esc(n.id)+' ['+esc(n.status)+'] ticket='+esc(n.ticket)+(n.children&&n.children.length?tree(n.children):'')+'</li>').join('')+'</ul>';}
function render(s){
  const set=(id,html)=>{const el=document.querySelector('#'+id+' .slice'); if(el)el.innerHTML=html;};
  set('queues', table(Object.values(s.queues||{})));
  set('tickets', table(Object.values(s.tickets||{})));
  set('models', table(Object.values(s.models||{})));
  set('commands', table(s.commands||[]));
  set('tools', table(Object.entries(s.tools||{}).map(([k,v])=>({tool:k,count:v}))));
  set('cycles', table(Object.values(s.cycles||{}).map(c=>({id:c.id,ticket:c.ticket,model:c.model,role:c.role,phase:c.phase,status:c.status,stream:(c.stream||'').slice(-80)}))));
  set('cycle_tree', tree(s.cycle_tree||[]));
  set('system', table([s.system||{}]));
  set('budgets', '<pre>'+esc(JSON.stringify(s.budgets||{},null,2))+'</pre>');
}
function refresh(){if(location.protocol==='file:'){render(window.__SNAPSHOT__||{});return;} fetch('/snapshot.json').then(r=>r.json()).then(render).catch(()=>render(window.__SNAPSHOT__||{}));}
refresh();
if(window.__WS_PORT__){try{const ws=new WebSocket('ws://'+location.hostname+':'+window.__WS_PORT__);ws.onmessage=()=>refresh();}catch(e){}}
else setInterval(refresh,1000);
"""
