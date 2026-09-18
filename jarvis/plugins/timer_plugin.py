"""Timers and reminders. Try: 'set a timer for 10 minutes',
'remind me to take the trash out in 20 minutes', 'list my timers',
'cancel my timers'.

Fires on a background thread: spoken alert + activity-log entry + popup,
delivered through brain.alert() (wired to the UI by main.py).
Pending timers are visible to the schedule plugin via list_pending().
"""
import re
import threading
from datetime import datetime, timedelta
from threading import Timer

from .base import Plugin

_TIMER_RX = re.compile(
    r"\bset\s+(?:a\s+)?timer\s+for\s+(\d+)\s*(second|minute|hour)s?\b")
_REMIND_RX = re.compile(
    r"\bremind\s+me\s+to\s+(.+?)\s+in\s+(\d+)\s*(second|minute|hour)s?\b")
_LIST_RX = re.compile(r"\b(list|show|what are)\s+my\s+(timers|reminders)\b|\bmy\s+timers\b")
_CANCEL_RX = re.compile(r"\bcancel\s+(?:my\s+|all\s+)?(timers|reminders|alarms)\b")

_UNIT_SECONDS = {"second": 1, "minute": 60, "hour": 3600}

# Module-level registry so the schedule plugin can read pending items.
_pending = []
_lock = threading.Lock()


def list_pending():
    """Return [(fire_at_datetime, label), ...] for timers not yet fired."""
    with _lock:
        return [(p["fire_at"], p["label"]) for p in _pending]


def _fmt_delta(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    if seconds < 3600:
        m = seconds // 60
        return f"{m} minute{'s' if m != 1 else ''}"
    h = seconds // 3600
    return f"{h} hour{'s' if h != 1 else ''}"


class TimerPlugin(Plugin):
    name = "timer"
    description = "Timers & reminders: 'set a timer for 10 minutes'."

    def match(self, text):
        return bool(_TIMER_RX.search(text) or _REMIND_RX.search(text)
                    or _LIST_RX.search(text) or _CANCEL_RX.search(text))

    def run(self, text):
        if _CANCEL_RX.search(text):
            return self._cancel_all()
        if _LIST_RX.search(text):
            return self._list()
        m = _REMIND_RX.search(text)
        if m:
            task, amount, unit = m.group(1).strip(), int(m.group(2)), m.group(3)
            label = f"Reminder: {task}"
        else:
            m = _TIMER_RX.search(text)
            amount, unit = int(m.group(1)), m.group(2)
            label = f"{_fmt_delta(amount * _UNIT_SECONDS[unit])} timer"
        delay = amount * _UNIT_SECONDS[unit]
        fire_at = datetime.now() + timedelta(seconds=delay)
        entry = {"fire_at": fire_at, "label": label, "timer": None}
        timer = Timer(delay, self._fire, args=(entry,))
        timer.daemon = True
        entry["timer"] = timer
        with _lock:
            _pending.append(entry)
        timer.start()
        when = fire_at.strftime("%I:%M %p").lstrip("0")
        if label.startswith("Reminder:"):
            return f"Got it. I'll remind you to {m.group(1).strip()} at {when}."
        return f"Timer set for {_fmt_delta(delay)} — I'll let you know at {when}."

    def _fire(self, entry):
        with _lock:
            if entry in _pending:
                _pending.remove(entry)
        brain = getattr(self, "brain", None)
        if brain is not None:
            if entry["label"].startswith("Reminder:"):
                brain.alert(entry["label"] + ".")
            else:
                brain.alert(f"Your {entry['label']} is up.")

    def _list(self):
        items = list_pending()
        if not items:
            return "No timers or reminders set."
        lines = []
        for fire_at, label in sorted(items):
            mins = max(0, int((fire_at - datetime.now()).total_seconds() // 60))
            lines.append(f"{label} — in about {mins} minutes")
        return "Here's what's pending: " + "; ".join(lines) + "."

    def _cancel_all(self):
        with _lock:
            for p in _pending:
                p["timer"].cancel()
            n = len(_pending)
            _pending.clear()
        if n == 0:
            return "There was nothing to cancel."
        return f"Cancelled {n} timer{'s' if n != 1 else ''}."


plugin = TimerPlugin()
