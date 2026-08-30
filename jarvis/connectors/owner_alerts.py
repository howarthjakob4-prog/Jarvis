"""Owner login alerts for JARVIS.

When a JARVIS session starts, this module identifies the local account and sends
an owner notification through the configured remote approval/phone relay.
If the relay is not configured or temporarily unavailable, the alert is queued
locally so it is not silently lost.
"""

from __future__ import annotations

import json
import os
import platform
import socket
from datetime import datetime, timezone
from pathlib import Path
from urllib import request

from loguru import logger


def _settings() -> dict:
    try:
        from jarvis.ui.settings_store import SettingsStore
        return SettingsStore().load()
    except Exception:
        return {}


def _display_name(settings: dict) -> str:
    account = settings.get("account", {}) if isinstance(settings, dict) else {}
    configured = str(account.get("display_name", "") or "").strip()
    if configured:
        return configured
    return (
        os.environ.get("USERNAME")
        or os.environ.get("USER")
        or "Unknown user"
    )


def _queue_path() -> Path:
    path = Path.home() / ".jarvis" / "pending_owner_alerts.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _queue_alert(payload: dict) -> None:
    try:
        with _queue_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning(f"Could not queue owner alert: {exc}")


def notify_owner_login() -> bool:
    """Notify the owner that a JARVIS account/session has started.

    The relay URL is intentionally not hard-coded. The phone-line setup will
    store the approved relay endpoint locally. No phone numbers or secrets are
    committed to the repository.
    """
    settings = _settings()
    alerts = settings.get("owner_alerts", {}) if isinstance(settings, dict) else {}

    if alerts.get("enabled", True) is False or alerts.get("notify_on_login", True) is False:
        return False

    payload = {
        "event": "jarvis_login",
        "username": _display_name(settings),
        "device_name": socket.gethostname(),
        "platform": platform.platform(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": "A JARVIS account/session has logged in.",
    }

    relay_url = str(alerts.get("relay_url", "") or os.environ.get("JARVIS_OWNER_ALERT_URL", "")).strip()
    if not relay_url:
        _queue_alert(payload)
        logger.info(f"Owner login alert queued for {payload['username']} (phone relay not configured yet)")
        return False

    try:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            relay_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=8) as response:
            ok = 200 <= int(response.status) < 300
        if ok:
            logger.info(f"Owner login alert sent for {payload['username']}")
            return True
    except Exception as exc:
        logger.warning(f"Owner login alert could not be sent: {exc}")

    _queue_alert(payload)
    return False
