"""Provider-free JARVIS phone gateway over the local network.

This is the no-modem/no-telephony path: JARVIS serves a tiny approval dashboard
straight from the PC. A phone on the same Wi-Fi/LAN opens the dashboard and can
approve or deny pending JARVIS actions. No carrier, SIM, SMS vendor, or cloud
telephony provider is required.
"""
from __future__ import annotations

import html
import json
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from jarvis.ui.settings_store import SettingsStore

_LOCK = threading.RLock()
_ALERTS: list[dict] = []
_SERVER = None


def _settings() -> tuple[dict, SettingsStore]:
    store = SettingsStore()
    data = store.load()
    return data, store


def _access_code() -> str:
    data, store = _settings()
    gateway = data.setdefault("local_phone_gateway", {})
    code = str(gateway.get("access_code", "") or "").strip()
    if len(code) < 8:
        code = secrets.token_urlsafe(9)
        gateway["access_code"] = code
        gateway["enabled"] = True
        gateway["port"] = 8766
        store.save(data)
    return code


def _lan_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        sock.close()


def get_access_url() -> str:
    return f"http://{_lan_ip()}:8766/?code={_access_code()}"


def enqueue_alert(message: str, *, kind: str = "alert", approval_id: str = "", call_id: str = "") -> str:
    item = {
        "id": secrets.token_hex(8),
        "kind": str(kind or "alert"),
        "message": str(message or "JARVIS requires owner attention")[:1000],
        "approval_id": str(approval_id or ""),
        "call_id": str(call_id or ""),
        "status": "pending",
        "created_at": time.time(),
    }
    with _LOCK:
        _ALERTS.insert(0, item)
        del _ALERTS[100:]
    return item["id"]


def _snapshot() -> list[dict]:
    with _LOCK:
        return [dict(x) for x in _ALERTS]


def _respond(item_id: str, decision: str) -> bool:
    decision = decision.lower().strip()
    if decision not in {"approved", "denied", "closed"}:
        return False
    target = None
    with _LOCK:
        for item in _ALERTS:
            if item["id"] == item_id:
                item["status"] = decision
                target = dict(item)
                break
    if not target:
        return False
    approval_id = target.get("approval_id", "")
    if approval_id and decision in {"approved", "denied"}:
        try:
            from jarvis.app import get_runtime
            runtime = get_runtime()
            if runtime:
                if decision == "approved":
                    runtime.approve_action(approval_id)
                else:
                    runtime.decline_action(approval_id)
        except Exception:
            return False
    return True


_PAGE = """<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>JARVIS Phone Gateway</title><style>
body{font-family:system-ui;background:#0b1020;color:#eef2ff;margin:0;padding:20px}main{max-width:620px;margin:auto}.card{background:#151c33;border:1px solid #2d3b68;border-radius:16px;padding:16px;margin:12px 0}.pending{border-color:#6387ff}button{border:0;border-radius:10px;padding:12px 16px;margin:6px 8px 0 0;font-weight:700}.yes{background:#79e2a7}.no{background:#ff8d8d}.muted{opacity:.7;font-size:.9rem}h1{margin-bottom:4px}</style></head><body><main><h1>JARVIS</h1><div class='muted'>Owner Phone Gateway • direct local connection</div><div id='items'></div></main>
<script>
const code=new URLSearchParams(location.search).get('code')||'';
async function load(){let r=await fetch('/api/alerts?code='+encodeURIComponent(code)); if(!r.ok){document.getElementById('items').innerHTML='<div class=card>Access denied.</div>';return} let a=await r.json(); let el=document.getElementById('items'); el.innerHTML=a.length?'':'<div class=card>No alerts waiting.</div>'; for(const x of a){let d=document.createElement('div');d.className='card '+(x.status==='pending'?'pending':'');d.innerHTML='<b>'+esc(x.kind.toUpperCase())+'</b><p>'+esc(x.message)+'</p><div class=muted>'+new Date(x.created_at*1000).toLocaleString()+' • '+esc(x.status)+'</div>'; if(x.status==='pending'&&x.approval_id){d.innerHTML+='<button class=yes onclick="respond(\''+x.id+'\',\'approved\')">Approve</button><button class=no onclick="respond(\''+x.id+'\',\'denied\')">Deny</button>'} el.appendChild(d)}}
function esc(s){return String(s).replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]))}
async function respond(id,status){await fetch('/api/respond',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code,id,status})});load()}
load();setInterval(load,2000);if('Notification'in window)Notification.requestPermission().catch(()=>{});
</script></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self, code: str) -> bool:
        return secrets.compare_digest(str(code or ""), _access_code())

    def do_GET(self):
        parsed = urlparse(self.path)
        q = parse_qs(parsed.query)
        code = (q.get("code") or [""])[0]
        if parsed.path == "/api/alerts":
            if not self._authorized(code):
                self._send(403, b'{"error":"denied"}', "application/json")
                return
            self._send(200, json.dumps(_snapshot()).encode(), "application/json")
            return
        if parsed.path == "/":
            self._send(200, _PAGE.encode(), "text/html; charset=utf-8")
            return
        self._send(404, b"Not found", "text/plain")

    def do_POST(self):
        if urlparse(self.path).path != "/api/respond":
            self._send(404, b"Not found", "text/plain")
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._send(400, b'{"error":"bad request"}', "application/json")
            return
        if not self._authorized(body.get("code", "")):
            self._send(403, b'{"error":"denied"}', "application/json")
            return
        ok = _respond(str(body.get("id", "")), str(body.get("status", "")))
        self._send(200 if ok else 404, json.dumps({"ok": ok}).encode(), "application/json")

    def log_message(self, *_args):
        pass


def start_local_phone_gateway(port: int = 8766):
    global _SERVER
    if _SERVER is not None:
        return _SERVER
    _access_code()
    server = ThreadingHTTPServer(("0.0.0.0", int(port)), _Handler)
    thread = threading.Thread(target=server.serve_forever, name="JARVIS-PhoneGateway", daemon=True)
    thread.start()
    _SERVER = server
    print(f"JARVIS phone gateway ready: {get_access_url()}")
    return server
