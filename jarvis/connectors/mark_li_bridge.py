"""Optional bridge from JARVIS to the locally running Mark-LI dashboard.

This file does not copy Mark-LI source code. It talks to Mark-LI through its
local HTTP API (default: http://127.0.0.1:8000).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class MarkLIResult:
    ok: bool
    data: dict
    status: int = 0


class MarkLIBridge:
    def __init__(self, base_url: str | None = None, timeout: float = 5.0):
        self.base_url = (base_url or os.getenv("JARVIS_MARK_LI_URL") or "http://127.0.0.1:8000").rstrip("/")
        self.timeout = timeout
        self.token: str | None = None

    def _request(self, path: str, *, method: str = "GET", body: dict | None = None, auth: bool = False) -> MarkLIResult:
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        req = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
                try:
                    payload = json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    payload = {"text": raw}
                return MarkLIResult(True, payload, int(response.status))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {"error": raw or str(exc)}
            return MarkLIResult(False, payload, int(exc.code))
        except Exception as exc:
            return MarkLIResult(False, {"error": str(exc)}, 0)

    def status(self) -> MarkLIResult:
        """Check whether the local Mark-LI dashboard is reachable."""
        result = self._request("/")
        if result.ok:
            return MarkLIResult(True, {"reachable": True, "url": self.base_url}, result.status)
        return MarkLIResult(False, {"reachable": False, "url": self.base_url, **result.data}, result.status)

    def login(self, pin: str) -> MarkLIResult:
        """Exchange the one-time Mark-LI PIN for a local bearer token."""
        result = self._request("/login", method="POST", body={"pin": pin})
        if result.ok and result.data.get("token"):
            self.token = str(result.data["token"])
        return result

    def command(self, text: str) -> MarkLIResult:
        text = str(text).strip()
        if not text:
            return MarkLIResult(False, {"error": "text is required"}, 400)
        if not self.token:
            return MarkLIResult(False, {"error": "Mark-LI is not authenticated"}, 401)
        return self._request("/api/command", method="POST", body={"text": text}, auth=True)

    def wake(self) -> MarkLIResult:
        if not self.token:
            return MarkLIResult(False, {"error": "Mark-LI is not authenticated"}, 401)
        return self._request("/api/wake", method="POST", body={}, auth=True)


_bridge = MarkLIBridge()


def get_mark_li_bridge() -> MarkLIBridge:
    return _bridge
