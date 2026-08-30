import sys
import os
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# CUDA DLL bootstrap (MUST run before any ctranslate2 / faster_whisper import)
# When packaged with PyInstaller, NVIDIA CUDA DLLs land in sys._MEIPASS/nvidia/*/bin/.
# ctranslate2 searches os.add_dll_directory() paths for cublas/cudnn at import time,
# so we register those paths here before anything else in the process.
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    _nvidia_base = os.path.join(sys._MEIPASS, 'nvidia')
    if os.path.exists(_nvidia_base):
        for _lib in os.listdir(_nvidia_base):
            _bin = os.path.join(_nvidia_base, _lib, 'bin')
            if os.path.isdir(_bin):
                os.add_dll_directory(_bin)
else:
    try:
        import importlib.util, pathlib
        _nvidia_spec = importlib.util.find_spec("nvidia")
        if _nvidia_spec and _nvidia_spec.submodule_search_locations:
            for _loc in _nvidia_spec.submodule_search_locations:
                for _sub in pathlib.Path(_loc).iterdir():
                    _bin = _sub / "bin"
                    if _bin.is_dir():
                        os.add_dll_directory(str(_bin))
    except Exception:
        pass

from jarvis.app import main, get_runtime
from jarvis.connectors.mark_li_bridge import get_mark_li_bridge
from jarvis.connectors.owner_alerts import notify_owner_login
from jarvis.performance.cpu_guard import install_cpu_guard
from jarvis.security.christian_approval_gate import install_christian_approval_gate
from jarvis.ui.phone_setup_patch import install_phone_setup_patch

DEMO_MODE = False


class _EarlyBridgeHandler(BaseHTTPRequestHandler):
    def _origin_allowed(self):
        origin = self.headers.get("Origin", "")
        return (
            not origin
            or origin.startswith("http://127.0.0.1")
            or origin.startswith("http://localhost")
        )

    def _headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        origin = self.headers.get("Origin", "")
        if origin and self._origin_allowed():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()

    def _json(self, data, status=200):
        self._headers(status)
        self.wfile.write(json.dumps(data, default=str).encode("utf-8"))

    def do_OPTIONS(self):
        if not self._origin_allowed():
            self._json({"ok": False, "error": "Cross-origin requests not allowed"}, 403)
            return
        self._headers(204)

    def do_GET(self):
        if not self._origin_allowed():
            self._json({"ok": False, "error": "Cross-origin requests not allowed"}, 403)
            return

        if self.path == "/mark-li/status":
            result = get_mark_li_bridge().status()
            self._json({"ok": result.ok, **result.data}, 200 if result.ok else 503)
            return

        runtime = get_runtime()
        if self.path == "/status":
            providers = []
            if runtime and getattr(runtime, "provider_router", None):
                providers = list(runtime.provider_router._providers.keys())
            self._json({
                "ready": bool(runtime and runtime.ready),
                "providers": providers,
                "port": 8765,
                "integration": "jarvis-local-v2-mark-li",
                "phase": "ready" if runtime and runtime.ready else "starting",
                "mark_li": get_mark_li_bridge().status().data,
            })
            return
        if self.path == "/tools":
            tools = []
            if runtime and getattr(runtime, "tool_registry", None):
                tools = [d["name"] for d in runtime.tool_registry.get_definitions()]
            self._json({"tools": tools})
            return
        self._json({"ok": False, "error": "Not found"}, 404)

    def do_POST(self):
        if not self._origin_allowed():
            self._json({"ok": False, "error": "Cross-origin requests not allowed"}, 403)
            return

        length = int(self.headers.get("Content-Length", "0") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._json({"ok": False, "error": "Invalid JSON"}, 400)
            return

        # Optional Mark-LI engine. These routes stay local and never expose
        # Mark-LI directly to a public website.
        mark_li = get_mark_li_bridge()
        if self.path == "/mark-li/login":
            pin = str(body.get("pin", "")).strip()
            if not pin:
                self._json({"ok": False, "error": "'pin' is required"}, 400)
                return
            result = mark_li.login(pin)
            safe_data = {k: v for k, v in result.data.items() if k != "token"}
            self._json({"ok": result.ok, **safe_data}, 200 if result.ok else (result.status or 502))
            return

        if self.path == "/mark-li/command":
            result = mark_li.command(body.get("text", ""))
            self._json({"ok": result.ok, **result.data}, 200 if result.ok else (result.status or 502))
            return

        if self.path == "/mark-li/wake":
            result = mark_li.wake()
            self._json({"ok": result.ok, **result.data}, 200 if result.ok else (result.status or 502))
            return

        runtime = get_runtime()
        if not runtime or not runtime.ready:
            self._json({"ok": False, "error": "Runtime not ready yet — try again in a moment"}, 503)
            return

        if self.path == "/chat":
            text = str(body.get("text", "")).strip()
            if not text:
                self._json({"ok": False, "error": "'text' is required"}, 400)
                return
            runtime.send_text(text)
            self._json({"ok": True, "message": f"Message queued: {text!r}"})
            return
        self._json({"ok": False, "error": "Not found"}, 404)

    def log_message(self, *_args):
        pass


def _start_early_bridge():
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 8765), _EarlyBridgeHandler)
        thread = threading.Thread(target=server.serve_forever, name="JARVIS-EarlyBridge", daemon=True)
        thread.start()
        return server
    except OSError:
        return None


def _install_playwright() -> int:
    """Install Playwright Chromium browser. Called by the NSIS installer post-install."""
    import subprocess
    print("Installing Playwright Chromium browser...")
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=False,
    )
    if result.returncode == 0:
        print("Playwright Chromium installed successfully.")
    else:
        print(f"Playwright install failed (exit {result.returncode}).")
    return result.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JARVIS Desktop AI Assistant")
    parser.add_argument("--demo", action="store_true", help="Enable demo mode (skips voice init, shows auto-demo)")
    parser.add_argument("--minimized", action="store_true", help="Start minimized as floating orb")
    parser.add_argument("--install-playwright", action="store_true", help="Install Playwright Chromium and exit (used by installer)")
    args = parser.parse_args()

    if args.install_playwright:
        sys.exit(_install_playwright())

    if args.demo:
        DEMO_MODE = True
        sys.argv = [arg for arg in sys.argv if arg != "--demo"]

    install_cpu_guard()
    install_phone_setup_patch()
    install_christian_approval_gate()
    _early_bridge = _start_early_bridge()
    threading.Thread(target=notify_owner_login, name="JARVIS-OwnerLoginAlert", daemon=True).start()
    main(demo_mode=DEMO_MODE)
