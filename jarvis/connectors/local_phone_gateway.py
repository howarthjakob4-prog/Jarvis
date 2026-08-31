"""Provider-free JARVIS phone call gateway over the local network.

This path does not use a carrier, SIM, SMS vendor, or cloud telephony provider.
It gives the owner's phone a real incoming-call-style JARVIS screen over Wi-Fi:
ringtone, vibration where supported, Answer/Decline, spoken alert details, and
Approve/Deny for protected actions.
"""
from __future__ import annotations

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
    return store.load(), store


def _access_code() -> str:
    data, store = _settings()
    gateway = data.setdefault("local_phone_gateway", {})
    code = str(gateway.get("access_code", "") or "").strip()
    if len(code) < 8:
        code = secrets.token_urlsafe(9)
        gateway.update({"access_code": code, "enabled": True, "port": 8766})
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
        "call_id": str(call_id or secrets.token_hex(6)),
        "status": "ringing",
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
    if decision not in {"answered", "approved", "denied", "declined", "closed"}:
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
    if approval_id and decision in {"approved", "denied", "declined"}:
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


_PAGE = r"""<!doctype html><html><head>
<meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'>
<meta name='theme-color' content='#050816'><title>JARVIS Call</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#050816;color:#fff;font-family:system-ui,-apple-system,sans-serif;min-height:100vh}
main{max-width:620px;margin:auto;padding:20px}.muted{opacity:.65}.card{background:#11182a;border:1px solid #263657;border-radius:18px;padding:16px;margin:12px 0}
#call{position:fixed;inset:0;background:radial-gradient(circle at 50% 20%,#173464,#050816 62%);display:none;z-index:10;padding:env(safe-area-inset-top) 24px env(safe-area-inset-bottom)}
.call-inner{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:space-between;text-align:center;padding:60px 0 42px}.orb{width:132px;height:132px;border-radius:50%;border:2px solid #6dc7ff;box-shadow:0 0 45px #2a9cff;background:#0a1831;display:grid;place-items:center;font-size:30px;font-weight:800}.caller{font-size:34px;font-weight:800;margin-top:24px}.state{opacity:.72;margin-top:8px}
.controls{display:flex;gap:54px}.round{width:78px;height:78px;border-radius:50%;border:0;color:white;font-size:28px;font-weight:800}.answer{background:#21c66b}.decline{background:#ed4b55}
button.action{border:0;border-radius:12px;padding:14px 18px;font-weight:800;margin:6px 8px 0 0}.yes{background:#7be7ae}.no{background:#ff9299}
#answerPanel{display:none;max-width:560px;width:100%;background:#10192d;border:1px solid #31517e;border-radius:18px;padding:20px;text-align:left}.status{font-size:13px;opacity:.65}
</style></head><body>
<div id='call'><div class='call-inner'><div><div class='orb'>J</div><div class='caller'>JARVIS</div><div class='state' id='callState'>Incoming secure call…</div></div><div id='answerPanel'></div><div class='controls' id='controls'><button class='round decline' onclick='declineCall()'>×</button><button class='round answer' onclick='answerCall()'>✓</button></div></div></div>
<main><h1>JARVIS Phone</h1><div class='muted'>Private direct Wi-Fi calling gateway</div><div class='card'><b>Ready for JARVIS calls</b><p class='muted'>Keep this page open or add it to your home screen. JARVIS calls appear here without a cellular provider.</p><button class='action yes' onclick='armAudio()'>Enable ringing</button></div><div id='items'></div></main>
<script>
const code=new URLSearchParams(location.search).get('code')||'';let current=null,lastSeen='';let ctx=null,ringTimer=null;
function esc(s){return String(s).replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]))}
function armAudio(){try{ctx=ctx||new (window.AudioContext||window.webkitAudioContext)();ctx.resume();}catch(e){} if('Notification'in window&&Notification.permission==='default')Notification.requestPermission().catch(()=>{});}
function tone(){if(!ctx)return;let o=ctx.createOscillator(),g=ctx.createGain();o.frequency.value=740;g.gain.value=.07;o.connect(g);g.connect(ctx.destination);o.start();o.stop(ctx.currentTime+.28)}
function startRing(){armAudio();tone();ringTimer=setInterval(tone,1200);if(navigator.vibrate)navigator.vibrate([500,400,500,1200]);}
function stopRing(){if(ringTimer){clearInterval(ringTimer);ringTimer=null}if(navigator.vibrate)navigator.vibrate(0)}
function showCall(x){current=x;document.getElementById('call').style.display='block';document.getElementById('callState').textContent='Incoming secure call';document.getElementById('answerPanel').style.display='none';document.getElementById('controls').style.display='flex';startRing();if('Notification'in window&&Notification.permission==='granted')new Notification('JARVIS is calling',{body:x.message,tag:'jarvis-call'});}
async function answerCall(){if(!current)return;stopRing();await respond(current.id,'answered');document.getElementById('callState').textContent='Connected';let p=document.getElementById('answerPanel');p.style.display='block';document.getElementById('controls').style.display='none';p.innerHTML='<b>JARVIS</b><p>'+esc(current.message)+'</p>'+(current.approval_id?'<button class="action yes" onclick="finish(\'approved\')">Approve</button><button class="action no" onclick="finish(\'denied\')">Deny</button>':'<button class="action yes" onclick="finish(\'closed\')">End call</button>');if('speechSynthesis'in window){speechSynthesis.cancel();speechSynthesis.speak(new SpeechSynthesisUtterance(current.message));}}
async function declineCall(){if(!current)return;stopRing();await respond(current.id,'declined');document.getElementById('call').style.display='none';current=null;}
async function finish(status){if(!current)return;await respond(current.id,status);if('speechSynthesis'in window)speechSynthesis.cancel();document.getElementById('call').style.display='none';current=null;load();}
async function respond(id,status){return fetch('/api/respond',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code,id,status})})}
async function load(){let r=await fetch('/api/alerts?code='+encodeURIComponent(code));if(!r.ok){document.getElementById('items').innerHTML='<div class=card>Access denied.</div>';return}let a=await r.json();let ringing=a.find(x=>x.status==='ringing');if(ringing&&ringing.id!==lastSeen&&!current){lastSeen=ringing.id;showCall(ringing)}let el=document.getElementById('items');el.innerHTML=a.length?'':'<div class=card>No recent calls.</div>';for(const x of a.slice(0,20)){let d=document.createElement('div');d.className='card';d.innerHTML='<b>'+esc(x.kind.toUpperCase())+'</b><p>'+esc(x.message)+'</p><div class=status>'+new Date(x.created_at*1000).toLocaleString()+' • '+esc(x.status)+'</div>';el.appendChild(d)}}
armAudio();load();setInterval(load,1000);
</script></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
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
                self._send(403, b'{"error":"denied"}', "application/json"); return
            self._send(200, json.dumps(_snapshot()).encode(), "application/json"); return
        if parsed.path == "/":
            self._send(200, _PAGE.encode(), "text/html; charset=utf-8"); return
        self._send(404, b"Not found", "text/plain")

    def do_POST(self):
        if urlparse(self.path).path != "/api/respond":
            self._send(404, b"Not found", "text/plain"); return
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._send(400, b'{"error":"bad request"}', "application/json"); return
        if not self._authorized(body.get("code", "")):
            self._send(403, b'{"error":"denied"}', "application/json"); return
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
    print(f"JARVIS phone call gateway ready: {get_access_url()}")
    return server
