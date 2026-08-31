"""Provider-free JARVIS phone and tablet demo gateway over the local network.

The owner phone path provides incoming-call-style alerts and approvals. The
separate tablet demo path is intentionally limited: it is free, expires at the
end of the local day, supports browser voice/text input and safe status/demo
abilities, and does not expose unrestricted PC-control actions.
"""
from __future__ import annotations

import json
import secrets
import socket
import threading
import time
from datetime import datetime
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


def _tablet_code() -> str:
    data, store = _settings()
    tablet = data.setdefault("tablet_demo", {})
    today = datetime.now().date().isoformat()
    code = str(tablet.get("access_code", "") or "").strip()
    if tablet.get("date") != today or len(code) < 8:
        code = secrets.token_urlsafe(8)
        tablet.update({
            "access_code": code,
            "enabled": True,
            "date": today,
            "expires_at": f"{today}T23:59:59",
            "access_level": "limited",
            "price": 0,
            "label": "AIM worker demo",
        })
        store.save(data)
    return code


def _tablet_active() -> bool:
    data, _ = _settings()
    tablet = data.get("tablet_demo", {}) if isinstance(data, dict) else {}
    return bool(tablet.get("enabled", True)) and tablet.get("date") == datetime.now().date().isoformat()


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


def get_tablet_demo_url() -> str:
    return f"http://{_lan_ip()}:8766/tablet?code={_tablet_code()}"


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


_BLOCKED_TABLET_TERMS = (
    "delete ", "remove file", "erase ", "format ", "shutdown", "restart computer",
    "powershell", "command prompt", "cmd.exe", "terminal", "shell", "registry",
    "password", "credential", "browser login", "ssh key", "install ", "uninstall ",
    "download file", "upload file", "move file", "rename file", "open app", "close app",
    "click ", "type into", "control the mouse", "take screenshot", "camera", "microphone access",
)


def _tablet_command(text: str) -> dict:
    text = str(text or "").strip()[:500]
    if not text:
        return {"ok": False, "message": "Say or type something first."}
    low = text.casefold()
    if any(term in low for term in _BLOCKED_TABLET_TERMS):
        return {
            "ok": False,
            "limited": True,
            "message": "That ability is locked in the limited AIM tablet demo.",
        }
    if low in {"status", "system status", "jarvis status", "show status"}:
        try:
            import psutil
            from jarvis.app import get_runtime
            runtime = get_runtime()
            return {
                "ok": True,
                "message": f"JARVIS is {'ready' if runtime and runtime.ready else 'starting'}. CPU {psutil.cpu_percent(interval=None):.0f} percent. Memory {psutil.virtual_memory().percent:.0f} percent.",
            }
        except Exception:
            return {"ok": True, "message": "JARVIS status is available, but detailed system readings are unavailable right now."}
    if low in {"time", "what time is it", "what's the time", "date", "what is the date", "what's the date"}:
        now = datetime.now()
        return {"ok": True, "message": now.strftime("It is %I:%M %p on %A, %B %d, %Y.").replace(" 0", " ")}
    try:
        from jarvis.app import get_runtime
        runtime = get_runtime()
        if not runtime or not runtime.ready:
            return {"ok": False, "message": "JARVIS is still starting on the computer."}
        guarded = (
            "LIMITED TABLET DEMO REQUEST. Do not use tools, control the PC, change files, settings, apps, "
            "accounts, or devices. Answer conversationally only. Visitor request: " + text
        )
        runtime.send_text(guarded)
        return {"ok": True, "message": "Request sent to JARVIS in limited demo mode."}
    except Exception:
        return {"ok": False, "message": "JARVIS could not accept that demo request right now."}


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


_TABLET_PAGE = r"""<!doctype html><html><head>
<meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'>
<meta name='theme-color' content='#08111f'><title>JARVIS Tablet Demo</title>
<style>*{box-sizing:border-box}body{margin:0;background:#08111f;color:#eef7ff;font-family:system-ui,-apple-system,sans-serif}main{max-width:820px;margin:auto;padding:28px}.hero{background:#0e1a2d;border:1px solid #29466b;border-radius:22px;padding:24px}.badge{display:inline-block;background:#17395f;border-radius:999px;padding:7px 11px;font-size:13px}.muted{opacity:.7}.row{display:flex;gap:10px;flex-wrap:wrap}button,input{font:inherit}button{border:0;border-radius:13px;padding:13px 17px;font-weight:800;background:#75d7ff;color:#05101a}button.secondary{background:#1b2b43;color:#eaf7ff;border:1px solid #365472}input{width:100%;border:1px solid #355273;background:#0a1627;color:#fff;border-radius:13px;padding:15px;margin-top:14px}.card{margin-top:16px;background:#0e1a2d;border:1px solid #29466b;border-radius:18px;padding:18px}#reply{min-height:52px}.orb{width:90px;height:90px;border-radius:50%;border:2px solid #75d7ff;box-shadow:0 0 35px #2479a8;display:grid;place-items:center;font-size:28px;font-weight:900;margin-bottom:14px}</style></head><body><main>
<div class='hero'><div class='orb'>J</div><span class='badge'>FREE • LIMITED AIM DEMO • TODAY ONLY</span><h1>JARVIS Tablet Demo</h1><p class='muted'>Voice, text, status and safe JARVIS demo abilities are enabled. Computer-control, files, credentials, installs and destructive actions are locked.</p>
<div class='row'><button onclick='startVoice()'>Talk to JARVIS</button><button class='secondary' onclick='quick("status")'>System Status</button><button class='secondary' onclick='quick("what time is it")'>Time & Date</button></div>
<input id='command' placeholder='Ask JARVIS something…' onkeydown='if(event.key==="Enter")send()'><div class='row' style='margin-top:10px'><button onclick='send()'>Send</button></div></div>
<div class='card'><b>JARVIS response</b><p id='reply' class='muted'>Ready.</p></div>
</main><script>
const code=new URLSearchParams(location.search).get('code')||'';const input=document.getElementById('command'),reply=document.getElementById('reply');
function speak(t){if('speechSynthesis'in window){speechSynthesis.cancel();speechSynthesis.speak(new SpeechSynthesisUtterance(t));}}
async function send(){let text=input.value.trim();if(!text)return;reply.textContent='Working…';let r=await fetch('/api/tablet-command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code,text})});let j=await r.json().catch(()=>({message:'No response.'}));reply.textContent=j.message||'Done.';if(j.message)speak(j.message);}
function quick(t){input.value=t;send()}
function startVoice(){let SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){reply.textContent='Voice input is not supported by this tablet browser. You can still type.';return}let rec=new SR();rec.lang='en-US';rec.interimResults=false;rec.onresult=e=>{input.value=e.results[0][0].transcript;send()};rec.onerror=()=>reply.textContent='I could not hear that. Try again.';rec.start();}
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

    def _tablet_authorized(self, code: str) -> bool:
        return _tablet_active() and secrets.compare_digest(str(code or ""), _tablet_code())

    def do_GET(self):
        parsed = urlparse(self.path)
        q = parse_qs(parsed.query)
        code = (q.get("code") or [""])[0]
        if parsed.path == "/api/alerts":
            if not self._authorized(code):
                self._send(403, b'{"error":"denied"}', "application/json"); return
            self._send(200, json.dumps(_snapshot()).encode(), "application/json"); return
        if parsed.path == "/tablet":
            if not self._tablet_authorized(code):
                self._send(403, b"Tablet demo access expired or denied.", "text/plain"); return
            self._send(200, _TABLET_PAGE.encode(), "text/html; charset=utf-8"); return
        if parsed.path == "/":
            self._send(200, _PAGE.encode(), "text/html; charset=utf-8"); return
        self._send(404, b"Not found", "text/plain")

    def do_POST(self):
        parsed_path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._send(400, b'{"error":"bad request"}', "application/json"); return
        if parsed_path == "/api/tablet-command":
            if not self._tablet_authorized(body.get("code", "")):
                self._send(403, b'{"ok":false,"message":"Tablet demo access expired or denied."}', "application/json"); return
            result = _tablet_command(body.get("text", ""))
            self._send(200 if result.get("ok") else 403, json.dumps(result).encode(), "application/json"); return
        if parsed_path != "/api/respond":
            self._send(404, b"Not found", "text/plain"); return
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
    _tablet_code()
    server = ThreadingHTTPServer(("0.0.0.0", int(port)), _Handler)
    thread = threading.Thread(target=server.serve_forever, name="JARVIS-PhoneGateway", daemon=True)
    thread.start()
    _SERVER = server
    print(f"JARVIS phone call gateway ready: {get_access_url()}")
    print(f"JARVIS limited tablet demo ready: {get_tablet_demo_url()}")
    return server
