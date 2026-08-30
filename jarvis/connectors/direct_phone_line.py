"""Direct JARVIS phone-line support using a connected cellular modem.

This module is intentionally provider-independent. JARVIS talks directly to a
cellular modem/SIM over a Windows COM port using standard AT commands. The SIM
owns the JARVIS phone number. No telephony vendor SDK or cloud provider is
required by this module.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Optional

from loguru import logger

try:
    import serial
    from serial.tools import list_ports
except Exception:  # pyserial may be absent in development environments
    serial = None
    list_ports = None


@dataclass
class PhoneLineResult:
    ok: bool
    message: str
    port: str = ""


def _normalize_number(number: str) -> str:
    value = re.sub(r"[^0-9+]", "", str(number or "").strip())
    if not value or value == "+":
        raise ValueError("Owner phone number is not configured")
    if "+" in value[1:]:
        raise ValueError("Invalid phone number")
    return value


def _candidate_ports(preferred: str = "auto") -> list[str]:
    if preferred and preferred.lower() != "auto":
        return [preferred]
    if list_ports is None:
        return []
    ranked: list[tuple[int, str]] = []
    for item in list_ports.comports():
        description = f"{item.description} {item.manufacturer or ''}".lower()
        score = 0
        if any(word in description for word in ("modem", "lte", "gsm", "cellular", "wwan", "mobile")):
            score += 10
        ranked.append((score, item.device))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [port for _, port in ranked]


def _command(handle, command: str, wait: float = 0.7) -> str:
    handle.reset_input_buffer()
    handle.write((command + "\r").encode("ascii", errors="ignore"))
    handle.flush()
    time.sleep(wait)
    return handle.read(handle.in_waiting or 1).decode("utf-8", errors="ignore")


def _open_working_modem(preferred: str = "auto"):
    if serial is None:
        raise RuntimeError("Phone-line driver is not installed")
    last_error: Optional[Exception] = None
    for port in _candidate_ports(preferred):
        try:
            handle = serial.Serial(port, 115200, timeout=1.5, write_timeout=2)
            reply = _command(handle, "AT", 0.35)
            if "OK" in reply:
                return handle, port
            handle.close()
        except Exception as exc:
            last_error = exc
    if last_error:
        raise RuntimeError(f"No working cellular modem found: {last_error}")
    raise RuntimeError("No cellular modem was detected")


def status(preferred_port: str = "auto") -> PhoneLineResult:
    """Check whether the direct JARVIS cellular line is ready."""
    try:
        handle, port = _open_working_modem(preferred_port)
        try:
            sim = _command(handle, "AT+CPIN?", 0.4)
            reg = _command(handle, "AT+CREG?", 0.4)
            if "READY" not in sim and "OK" not in sim:
                return PhoneLineResult(False, "SIM is not ready", port)
            if not any(marker in reg for marker in (",1", ",5", "OK")):
                return PhoneLineResult(False, "Cellular line is not registered", port)
            return PhoneLineResult(True, "JARVIS phone line is ready", port)
        finally:
            handle.close()
    except Exception as exc:
        return PhoneLineResult(False, str(exc))


def send_sms(owner_number: str, message: str, preferred_port: str = "auto") -> PhoneLineResult:
    """Send an owner alert directly from the JARVIS SIM line."""
    try:
        number = _normalize_number(owner_number)
        handle, port = _open_working_modem(preferred_port)
        try:
            _command(handle, "AT+CMGF=1", 0.4)
            handle.reset_input_buffer()
            handle.write(f'AT+CMGS="{number}"\r'.encode("ascii"))
            handle.flush()
            time.sleep(0.8)
            prompt = handle.read(handle.in_waiting or 1).decode("utf-8", errors="ignore")
            if ">" not in prompt:
                return PhoneLineResult(False, "Modem did not accept SMS request", port)
            clean = str(message or "JARVIS owner approval required")[:480]
            handle.write(clean.encode("utf-8", errors="ignore") + b"\x1a")
            handle.flush()
            time.sleep(2.0)
            reply = handle.read(handle.in_waiting or 1).decode("utf-8", errors="ignore")
            if "ERROR" in reply:
                return PhoneLineResult(False, "SMS failed", port)
            return PhoneLineResult(True, "Owner SMS sent", port)
        finally:
            handle.close()
    except Exception as exc:
        logger.warning(f"Direct phone SMS failed: {exc}")
        return PhoneLineResult(False, str(exc))


def place_call(owner_number: str, preferred_port: str = "auto", ring_seconds: int = 25) -> PhoneLineResult:
    """Place an owner alert call directly from the JARVIS SIM line."""
    try:
        number = _normalize_number(owner_number)
        handle, port = _open_working_modem(preferred_port)
        try:
            reply = _command(handle, f"ATD{number};", 0.8)
            if "ERROR" in reply or "NO CARRIER" in reply:
                return PhoneLineResult(False, "Call could not be started", port)
            # Leave enough time for the owner's phone to ring, then hang up if
            # the modem has not already ended the call. This is an alert call,
            # not an open-ended unattended call.
            time.sleep(max(5, min(int(ring_seconds), 60)))
            _command(handle, "ATH", 0.3)
            return PhoneLineResult(True, "Owner alert call placed", port)
        finally:
            handle.close()
    except Exception as exc:
        logger.warning(f"Direct phone call failed: {exc}")
        return PhoneLineResult(False, str(exc))


def alert_owner(owner_number: str, message: str, preferred_port: str = "auto", *, sms: bool = True, call: bool = True) -> bool:
    """Send the alert text and ring the owner using the direct JARVIS line."""
    results: list[PhoneLineResult] = []
    if sms:
        results.append(send_sms(owner_number, message, preferred_port))
    if call:
        results.append(place_call(owner_number, preferred_port))
    return any(result.ok for result in results)
