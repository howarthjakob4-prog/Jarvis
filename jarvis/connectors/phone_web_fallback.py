"""Provider-free fallback for owner alerts using the owner's existing phone browser.

This does not create a telephone number. It gives JARVIS a second path when no
cellular modem is available: open/send an HTTPS approval alert to a configured
phone approval endpoint. The endpoint can be the JARVIS web phone page running
on Vercel or another HTTPS endpoint the owner controls.
"""

from __future__ import annotations

import json
from urllib import request

from loguru import logger


def send_web_alert(endpoint: str, payload: dict) -> bool:
    endpoint = str(endpoint or "").strip()
    if not endpoint:
        return False
    try:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=8) as response:
            return 200 <= int(response.status) < 300
    except Exception as exc:
        logger.warning(f"Phone web fallback failed: {exc}")
        return False
