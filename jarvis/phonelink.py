"""Phone link: let the phone dashboard see this PC and send it commands.

How it works
------------
The PC phones home on a loop (outbound HTTPS, so no router setup needed):

  POST {server}/link/heartbeat   {"secret": ..., "pc_name": ...}
      -> proves this PC is on; the phone dashboard shows ONLINE/OFFLINE
         from the last heartbeat.

  GET  {server}/link/commands?secret=...
      -> {"commands": [{"id": ..., "type": "lock"}, ...]}

  POST {server}/link/ack         {"secret": ..., "id": ...}
      -> tells the server a command was carried out.

Commands understood
-------------------
* ``lock`` -- locks the workstation (Windows: LockWorkStation).

Pairing
-------
Set ``phone_link_enabled: true`` and ``phone_link_server`` to the Jarvis
phone app's address. If ``phone_link_secret`` is empty, one is generated on
first run, saved to ``config/local.yaml`` (gitignored), and printed/logged
once -- enter that same secret in the phone app so only your phone can
command this PC.

Everything here is best-effort: network failures are swallowed and logged,
never crash the panel.
"""

import ctypes
import secrets
import threading
import time
from datetime import datetime, timezone

import requests

from .config import save_local

HEARTBEAT_PATH = "/link/heartbeat"
COMMANDS_PATH = "/link/commands"
ACK_PATH = "/link/ack"

COMMAND_LOCK = "lock"


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PhoneLink:
    """Background link between this PC and the phone dashboard."""

    def __init__(self, config, log=None, http=None):
        self.config = config
        self.log = log or (lambda msg: print(f"[phonelink] {msg}"))
        self.http = http or requests
        self._stop = threading.Event()
        self._thread = None
        self.server = (config.get("phone_link_server") or "").rstrip("/")
        self.secret = config.get("phone_link_secret") or ""
        self.pc_name = config.get("phone_link_pc_name") or "My PC"
        try:
            self.interval = max(5, int(config.get("phone_link_interval") or 20))
        except (TypeError, ValueError):
            self.interval = 20

    # -- lifecycle ------------------------------------------------------
    def start(self):
        """Start the background loop. No-op when disabled or unconfigured."""
        if not self.config.get("phone_link_enabled"):
            return self
        if not self.server:
            self.log("Phone link enabled but phone_link_server is not set.")
            return self
        if not self.secret:
            self.secret = secrets.token_urlsafe(24)
            try:
                save_local({"phone_link_secret": self.secret})
            except OSError as exc:
                self.log(f"Could not save phone link secret: {exc}")
            self.log("Phone link secret generated. Enter it in the phone app:")
            self.log(self.secret)
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="jarvis-phonelink")
        self._thread.start()
        self.log(f"Phone link on: checking in as '{self.pc_name}' "
                 f"every {self.interval}s.")
        return self

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.wait(self.interval):
            try:
                self.beat()
            except Exception as exc:  # never kill the panel over the link
                self.log(f"Phone link error: {exc}")

    # -- protocol -------------------------------------------------------
    def beat(self):
        """One check-in: heartbeat, fetch commands, run them, ack them.

        Never raises: network failures are logged and swallowed so a
        dead connection can never crash the panel.
        """
        try:
            self._post(HEARTBEAT_PATH, {
                "secret": self.secret,
                "pc_name": self.pc_name,
                "at": _utcnow_iso(),
            })
            resp = self._get(COMMANDS_PATH, {"secret": self.secret})
            commands = []
            try:
                commands = resp.json().get("commands") or []
            except Exception:
                pass
            for cmd in commands:
                cmd_id = cmd.get("id")
                if self.handle_command(cmd):
                    self._post(ACK_PATH, {"secret": self.secret, "id": cmd_id})
        except Exception as exc:
            self.log(f"Phone link check-in failed: {exc}")

    def handle_command(self, cmd):
        """Carry out one command dict. Returns True when handled."""
        ctype = (cmd or {}).get("type")
        if ctype == COMMAND_LOCK:
            self._lock_workstation()
            return True
        if ctype:
            self.log(f"Ignoring unknown phone command: {ctype!r}")
        return False

    # -- actions --------------------------------------------------------
    def _lock_workstation(self):
        try:
            user32 = getattr(ctypes, "windll", None)
            if user32 is None:
                raise RuntimeError("not Windows")
            user32.LockWorkStation()
            self.log("Computer locked from phone.")
        except Exception as exc:
            self.log(f"Lock failed: {exc}")

    # -- http helpers ---------------------------------------------------
    def _post(self, path, payload):
        try:
            resp = self.http.post(self.server + path, json=payload, timeout=10)
            resp.raise_for_status()
            return resp
        except Exception as exc:
            self.log(f"Phone link POST {path} failed: {exc}")
            raise

    def _get(self, path, params):
        try:
            resp = self.http.get(self.server + path, params=params, timeout=10)
            resp.raise_for_status()
            return resp
        except Exception as exc:
            self.log(f"Phone link GET {path} failed: {exc}")
            raise
