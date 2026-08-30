"""Christian-only owner approval gate for JARVIS requests."""

from __future__ import annotations

import asyncio
import os

from jarvis.connectors.owner_alerts import notify_owner_approval_request
from jarvis.phone.line_identity import generate_approval_id, generate_call_id


def _account_name(runtime) -> str:
    settings = getattr(runtime, "settings", {}) or {}
    account = settings.get("account", {}) if isinstance(settings, dict) else {}
    configured = str(account.get("display_name", "") or "").strip()
    return configured or os.environ.get("USERNAME") or os.environ.get("USER") or "Unknown user"


def _is_christian(runtime) -> bool:
    return _account_name(runtime).strip().casefold() == "christian"


def install_christian_approval_gate() -> None:
    """Patch JarvisRuntime so Christian's every request waits for owner approval."""
    from jarvis.app import JarvisRuntime

    if getattr(JarvisRuntime, "_christian_gate_installed", False):
        return

    original = JarvisRuntime._handle_user_input

    async def gated_handle_user_input(self, event):
        if not _is_christian(self):
            return await original(self, event)

        request_text = str(getattr(event, "text", "") or "").strip()
        approval_id = generate_approval_id()
        call_id = generate_call_id()
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        self._pending_approvals[approval_id] = (
            future,
            f"Christian request: {request_text[:200] or 'JARVIS request'}",
        )

        self._emit_ui_event({
            "type": "approval_request",
            "id": approval_id,
            "call_id": call_id,
            "account": "Christian",
            "action": request_text or "JARVIS request",
            "risk": "owner_required",
            "message": "Christian's request is waiting for owner approval.",
        })

        await asyncio.to_thread(
            notify_owner_approval_request,
            "Christian",
            request_text or "JARVIS request",
            f"{approval_id} / {call_id}",
        )

        try:
            approved = await asyncio.wait_for(asyncio.shield(future), timeout=300)
        except asyncio.TimeoutError:
            self._pending_approvals.pop(approval_id, None)
            approved = False

        if not approved:
            self._emit_ui_event({
                "type": "approval_denied",
                "id": approval_id,
                "call_id": call_id,
                "account": "Christian",
                "message": "Request denied or approval timed out.",
            })
            return None

        self._emit_ui_event({
            "type": "approval_granted",
            "id": approval_id,
            "call_id": call_id,
            "account": "Christian",
        })
        return await original(self, event)

    JarvisRuntime._handle_user_input = gated_handle_user_input
    JarvisRuntime._christian_gate_installed = True
