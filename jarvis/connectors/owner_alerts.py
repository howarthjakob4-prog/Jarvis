"""Owner alerts for JARVIS.

JARVIS first tries its direct cellular phone line. If that is unavailable, it
can fall back to the configured remote relay. Alerts are queued locally if no
path is currently available, so they are not silently lost.
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
    return os.environ.get("USERNAME") or os.environ.get("USER") or "Unknown user"


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


def _direct_phone_alert(settings: dict, payload: dict) -> bool:
    phone = settings.get("phone_line", {}) if isinstance(settings, dict) else {}
    if phone.get("enabled", True) is False:
        return False

    owner_number = str(phone.get("owner_number", "") or os.environ.get("JARVIS_OWNER_PHONE", "")).strip()
    if not owner_number:
        return False

    try:
        from jarvis.connectors.direct_phone_line import alert_owner

        username = payload.get("username", "Unknown user")
        device = payload.get("device_name", "Unknown device")
        event = payload.get("event", "jarvis_alert")
        detail = payload.get("message", "JARVIS requires owner attention.")
        message = f"JARVIS ALERT: {detail} User: {username}. Device: {device}. Event: {event}."

        return alert_owner(
            owner_number,
            message,
            str(phone.get("serial_port", "auto") or "auto"),
            sms=bool(phone.get("sms_on_alert", True)),
            call=bool(phone.get("call_on_alert", True)),
        )
    except Exception as exc:
        logger.warning(f"Direct JARVIS phone line unavailable: {exc}")
        return False


def _relay_alert(settings: dict, payload: dict) -> bool:
    alerts = settings.get("owner_alerts", {}) if isinstance(settings, dict) else {}
    relay_url = str(alerts.get("relay_url", "") or os.environ.get("JARVIS_OWNER_ALERT_URL", "")).strip()
    if not relay_url:
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
            return 200 <= int(response.status) < 300
    except Exception as exc:
        logger.warning(f"Owner alert relay could not be reached: {exc}")
        return False


def notify_owner(payload: dict) -> bool:
    """Deliver an owner alert using the direct line first, then relay fallback."""
    settings = _settings()
    alerts = settings.get("owner_alerts", {}) if isinstance(settings, dict) else {}
    if alerts.get("enabled", True) is False:
        return False

    if _direct_phone_alert(settings, payload):
        logger.info("Owner alert sent through direct JARVIS phone line")
        return True

    if _relay_alert(settings, payload):
        logger.info("Owner alert sent through remote relay")
        return True

    _queue_alert(payload)
    logger.info("Owner alert queued because no phone path is currently ready")
    return False


def notify_owner_login() -> bool:
    """Notify the owner that a JARVIS account/session has started."""
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
    return notify_owner(payload)


def notify_owner_approval_request(username: str, request_summary: str, request_id: str = "") -> bool:
    """Notify the owner that a user request is waiting for approval."""
    payload = {
        "event": "approval_required",
        "username": str(username or "Unknown user"),
        "device_name": socket.gethostname(),
        "platform": platform.platform(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": str(request_id or ""),
        "message": f"Approval required: {str(request_summary or 'JARVIS request')[:300]}",
    }
    return notify_owner(payload)


def notify_owner_security_lockdown(username: str, reason: str) -> bool:
    """Notify the owner that JARVIS security restrictions triggered a lockdown."""
    payload = {
        "event": "security_lockdown",
        "username": str(username or "Unknown user"),
        "device_name": socket.gethostname(),
        "platform": platform.platform(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": f"JARVIS security lockdown triggered: {str(reason or 'restriction bypass detected')[:300]}",
    }
    return notify_owner(payload)
