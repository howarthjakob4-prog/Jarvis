import asyncio
import json
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from loguru import logger


_TABLET_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>JARVIS Tablet</title>
<style>
  :root { --bg:#070b14; --panel:#0e1422; --line:rgba(148,163,184,.14);
          --blue:#3b9eff; --text:#dfe5f0; --muted:#7c879d; --warn:#ffb454; }
  * { box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
  body { margin:0; background:var(--bg); color:var(--text);
         font-family:'Segoe UI',system-ui,-apple-system,sans-serif;
         display:flex; flex-direction:column; min-height:100vh; }
  header { padding:18px 22px; border-bottom:1px solid var(--line);
           display:flex; align-items:center; gap:12px; }
  header .dot { width:10px; height:10px; border-radius:50%; background:var(--blue);
                box-shadow:0 0 12px var(--blue); }
  header b { letter-spacing:4px; font-size:17px; }
  header span { color:var(--muted); font-size:12px; margin-left:auto; text-transform:uppercase; }
  #banner { padding:10px 18px; text-align:center; color:var(--muted); font-size:12px; border-bottom:1px solid var(--line); }
  #log { flex:1; overflow-y:auto; padding:20px; display:flex; flex-direction:column; gap:12px; min-height:45vh; }
  .msg { max-width:82%; padding:12px 15px; border-radius:15px; font-size:17px;
         line-height:1.45; white-space:pre-wrap; word-wrap:break-word; }
  .you { align-self:flex-end; background:var(--blue); color:#04121f; border-bottom-right-radius:4px; }
  .jarvis { align-self:flex-start; background:var(--panel); border:1px solid var(--line);
            border-bottom-left-radius:4px; }
  .meta { font-size:12px; color:var(--muted); align-self:flex-start; }
  form { display:flex; gap:10px; padding:16px; border-top:1px solid var(--line); }
  input { flex:1; background:var(--panel); border:1px solid var(--line); color:var(--text);
          border-radius:13px; padding:15px 16px; font-size:18px; outline:none; }
  input:focus { border-color:var(--blue); }
  button { background:var(--blue); color:#04121f; border:none; border-radius:13px;
           padding:0 24px; font-size:17px; font-weight:700; }
  button:disabled { opacity:.5; }
  #viewer { display:none; padding:28px; text-align:center; color:var(--muted); }
  #blocked { display:none; padding:48px 24px; text-align:center; color:var(--warn); font-size:18px; }
</style>
</head>
<body>
  <header><span class="dot"></span><b>JARVIS</b><span id="role">__ROLE__ tablet</span></header>
  <div id="banner">Tablet access only • paired session</div>
  <div id="blocked">This JARVIS remote is for tablets only. Phone access is disabled.</div>
  <div id="log"></div>
  <div id="viewer">AIM demonstration mode is read-only. JARVIS is online and available for viewing.</div>
  <form id="f">
    <input id="t" placeholder="Tell JARVIS what to do..." autocomplete="off" autofocus>
    <button id="b" type="submit">Send</button>
  </form>
<script>
  const ROLE = '__ROLE__';
  const TOKEN = '__TOKEN__';
  const log = document.getElementById('log');
  const form = document.getElementById('f');
  const input = document.getElementById('t');
  const btn = document.getElementById('b');
  const viewer = document.getElementById('viewer');
  const blocked = document.getElementById('blocked');

  function isTabletViewport() {
    const shortSide = Math.min(screen.width || innerWidth, screen.height || innerHeight);
    return shortSide >= 600;
  }
  function add(text, cls) {
    const d = document.createElement('div');
    d.className = 'msg ' + cls;
    d.textContent = text;
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
    return d;
  }

  if (!isTabletViewport()) {
    blocked.style.display = 'block';
    log.style.display = 'none';
    form.style.display = 'none';
    viewer.style.display = 'none';
  } else if (ROLE === 'viewer') {
    form.style.display = 'none';
    viewer.style.display = 'block';
    add('JARVIS tablet demonstration connected.', 'jarvis');
  } else {
    add('JARVIS owner tablet connected.', 'jarvis');
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (ROLE !== 'owner') return;
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    add(text, 'you');
    btn.disabled = true;
    const thinking = add('thinking...', 'meta');
    try {
      const r = await fetch('/api/send', {
        method:'POST',
        headers:{'Content-Type':'application/json', 'X-JARVIS-TABLET-TOKEN': TOKEN},
        body: JSON.stringify({text})
      });
      const j = await r.json();
      thinking.remove();
      add(j.response || j.error || '(no response)', 'jarvis');
    } catch (err) {
      thinking.remove();
      add('Connection error: ' + err, 'jarvis');
    } finally {
      btn.disabled = false;
      input.focus();
    }
  });
</script>
</body>
</html>"""


def _lan_ip() -> str:
    """Best-effort LAN address for the JARVIS Windows host."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def _looks_like_tablet(user_agent: str) -> bool:
    """Reject common phone/desktop user agents; allow common tablet families.

    This is a product gate, not an authentication boundary. Authentication is
    handled separately with per-session cryptographic tokens.
    """
    ua = (user_agent or "").lower()
    if not ua:
        return False
    if "iphone" in ua or "windows phone" in ua:
        return False
    if "ipad" in ua or "tablet" in ua or "kindle" in ua or "silk/" in ua:
        return True
    if "android" in ua:
        return "mobile" not in ua
    return False


class _Bridge:
    def __init__(self, runtime):
        self.runtime = runtime
        self._pending = None
        self._lock = asyncio.Lock()
        self._subscribed = False

    def _on_response(self, event) -> None:
        if self._pending is not None and not self._pending.done():
            self._pending.set_result(getattr(event, "text", "") or "")

    async def ask(self, text: str, timeout: float = 120.0) -> str:
        from jarvis.models import AIResponseEvent
        if not self._subscribed:
            self.runtime.async_runtime.bus.subscribe(AIResponseEvent, self._on_response)
            self._subscribed = True
        async with self._lock:
            loop = asyncio.get_running_loop()
            self._pending = loop.create_future()
            try:
                self.runtime.send_text(text)
                return await asyncio.wait_for(self._pending, timeout)
            except asyncio.TimeoutError:
                return "(JARVIS took too long to respond)"
            finally:
                self._pending = None


class WebRemoteServer:
    """Tablet-only JARVIS remote with owner and read-only demonstration roles."""

    def __init__(self, port: int = 8765):
        self.port = port
        self._httpd = None
        self._thread = None
        self._bridge = None
        self._owner_token = secrets.token_urlsafe(24)
        self._viewer_token = secrets.token_urlsafe(24)

    def is_running(self) -> bool:
        return self._httpd is not None

    def url(self) -> str:
        return f"http://{_lan_ip()}:{self.port}"

    def owner_url(self) -> str:
        return f"{self.url()}/?access={self._owner_token}"

    def viewer_url(self) -> str:
        return f"{self.url()}/?access={self._viewer_token}"

    def rotate_tokens(self) -> None:
        self._owner_token = secrets.token_urlsafe(24)
        self._viewer_token = secrets.token_urlsafe(24)

    def _role_for_token(self, token: str) -> str | None:
        if token and secrets.compare_digest(token, self._owner_token):
            return "owner"
        if token and secrets.compare_digest(token, self._viewer_token):
            return "viewer"
        return None

    def start(self) -> bool:
        if self._httpd is not None:
            return True
        from jarvis.app import get_runtime
        runtime = get_runtime()
        if runtime is None or runtime.async_runtime.loop is None:
            return False
        self.rotate_tokens()
        self._bridge = _Bridge(runtime)
        loop = runtime.async_runtime.loop
        bridge = self._bridge
        server_ref = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _reply(self, code, body, ctype="application/json; charset=utf-8"):
                data = body if isinstance(body, bytes) else body.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                try:
                    self.wfile.write(data)
                except Exception:
                    pass

            def _tablet_ok(self) -> bool:
                return _looks_like_tablet(self.headers.get("User-Agent", ""))

            def _token(self) -> str:
                header_token = (self.headers.get("X-JARVIS-TABLET-TOKEN") or "").strip()
                if header_token:
                    return header_token
                return (parse_qs(urlparse(self.path).query).get("access") or [""])[0]

            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path == "/" or parsed.path == "":
                    if not self._tablet_ok():
                        self._reply(403, "Tablet access only. Phone and desktop browser access are disabled.", "text/plain; charset=utf-8")
                        return
                    token = self._token()
                    role = server_ref._role_for_token(token)
                    if role is None:
                        self._reply(401, "Pairing link required.", "text/plain; charset=utf-8")
                        return
                    page = _TABLET_PAGE.replace("__ROLE__", role).replace("__TOKEN__", token)
                    self._reply(200, page, "text/html; charset=utf-8")
                    return
                if parsed.path == "/api/status":
                    role = server_ref._role_for_token(self._token())
                    if role is None:
                        self._reply(401, json.dumps({"error": "unauthorized"}))
                    else:
                        self._reply(200, json.dumps({"ok": True, "role": role, "tablet_only": True}))
                    return
                self._reply(404, json.dumps({"error": "not found"}))

            def do_POST(self):
                parsed = urlparse(self.path)
                if parsed.path != "/api/send":
                    self._reply(404, json.dumps({"error": "not found"}))
                    return
                role = server_ref._role_for_token(self._token())
                if role != "owner":
                    self._reply(403, json.dumps({"error": "owner tablet access required"}))
                    return
                if not self._tablet_ok():
                    self._reply(403, json.dumps({"error": "tablet access only"}))
                    return
                try:
                    length = min(int(self.headers.get("Content-Length", 0)), 16384)
                    raw = self.rfile.read(length) if length else b"{}"
                    text = (json.loads(raw.decode("utf-8")).get("text") or "").strip()
                except Exception:
                    text = ""
                if not text:
                    self._reply(400, json.dumps({"error": "empty message"}))
                    return
                try:
                    fut = asyncio.run_coroutine_threadsafe(bridge.ask(text), loop)
                    reply = fut.result(timeout=125)
                except Exception as e:
                    logger.warning(f"Tablet remote command failed: {e}")
                    reply = "JARVIS could not complete that request."
                self._reply(200, json.dumps({"response": reply}))

        try:
            self._httpd = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        except OSError as e:
            logger.warning(f"Tablet remote could not bind port {self.port}: {e}")
            self._httpd = None
            return False
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, daemon=True, name="JarvisTabletRemote"
        )
        self._thread.start()
        logger.info(f"Tablet remote serving at {self.url()}")
        return True

    def stop(self) -> None:
        if self._httpd is not None:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception:
                pass
            self._httpd = None
            self._thread = None
            self.rotate_tokens()


_instance: "WebRemoteServer | None" = None


def get_web_remote_server() -> "WebRemoteServer":
    global _instance
    if _instance is None:
        _instance = WebRemoteServer()
    return _instance
