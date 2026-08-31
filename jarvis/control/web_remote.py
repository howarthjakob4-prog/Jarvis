import asyncio
import hmac
import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from loguru import logger

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1"><title>JARVIS Remote</title></head>
<body style="background:#070b14;color:#dfe5f0;font-family:Segoe UI,system-ui;padding:24px"><h2>JARVIS Remote</h2><p>Use the authorized JARVIS companion app for remote control.</p></body></html>"""


def _lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def _remote_token() -> str:
    return os.getenv("JARVIS_REMOTE_TOKEN", "").strip()


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
    def __init__(self, port: int = 8765):
        self.port = port
        self._httpd = None
        self._thread = None
        self._bridge = None

    def is_running(self) -> bool:
        return self._httpd is not None

    def url(self) -> str:
        return f"http://{_lan_ip()}:{self.port}"

    def start(self) -> bool:
        if self._httpd is not None:
            return True
        token = _remote_token()
        if not token:
            logger.warning("Web remote disabled: set JARVIS_REMOTE_TOKEN before enabling remote access")
            return False

        from jarvis.app import get_runtime
        runtime = get_runtime()
        if runtime is None or runtime.async_runtime.loop is None:
            return False
        self._bridge = _Bridge(runtime)
        loop = runtime.async_runtime.loop
        bridge = self._bridge
        page = _PAGE.encode("utf-8")

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _reply(self, code, body, ctype="application/json; charset=utf-8"):
                data = body if isinstance(body, bytes) else body.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                try:
                    self.wfile.write(data)
                except Exception:
                    pass

            def _authorized(self) -> bool:
                auth = self.headers.get("Authorization", "")
                expected = f"Bearer {token}"
                return hmac.compare_digest(auth, expected)

            def do_GET(self):
                if self.path == "/" or self.path.startswith("/?"):
                    self._reply(200, page, "text/html; charset=utf-8")
                elif self.path == "/api/status":
                    if not self._authorized():
                        self._reply(401, json.dumps({"error": "unauthorized"}))
                        return
                    self._reply(200, json.dumps({"ok": True}))
                else:
                    self._reply(404, json.dumps({"error": "not found"}))

            def do_POST(self):
                if self.path != "/api/send":
                    self._reply(404, json.dumps({"error": "not found"}))
                    return
                if not self._authorized():
                    self._reply(401, json.dumps({"error": "unauthorized"}))
                    return
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    if length <= 0 or length > 65536:
                        self._reply(400, json.dumps({"error": "invalid request size"}))
                        return
                    raw = self.rfile.read(length)
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
                    logger.warning(f"Remote command failed: {e}")
                    reply = "JARVIS could not complete that remote request."
                self._reply(200, json.dumps({"response": reply}))

        try:
            self._httpd = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        except OSError as e:
            logger.warning(f"Web remote could not bind port {self.port}: {e}")
            self._httpd = None
            return False
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True, name="JarvisWebRemote")
        self._thread.start()
        logger.info(f"Authenticated web remote serving at {self.url()}")
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


_instance: "WebRemoteServer | None" = None


def get_web_remote_server() -> "WebRemoteServer":
    global _instance
    if _instance is None:
        _instance = WebRemoteServer()
    return _instance
