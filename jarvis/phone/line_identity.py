"""Internal JARVIS phone-line identity generator.

This module creates JARVIS-owned internal identifiers for the phone/approval
system. These are application call IDs, not public telephone-network numbers.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

JARVIS_LINE_REFERENCE = "527847"


def _digits(length: int) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def generate_line_id() -> str:
    """Return a stable-format internal JARVIS line identifier."""
    return f"JARVIS-{JARVIS_LINE_REFERENCE}-{_digits(6)}"


def generate_call_id() -> str:
    """Return a unique internal ID for one outbound approval/security call."""
    millis = int(time.time() * 1000)
    return f"CALL-{JARVIS_LINE_REFERENCE}-{millis}-{_digits(4)}"


def generate_approval_id() -> str:
    """Return a short-lived approval request identifier."""
    return f"APR-{JARVIS_LINE_REFERENCE}-{_digits(8)}"


@dataclass(frozen=True)
class LineIdentity:
    line_reference: str
    line_id: str


def create_line_identity() -> LineIdentity:
    return LineIdentity(
        line_reference=JARVIS_LINE_REFERENCE,
        line_id=generate_line_id(),
    )
