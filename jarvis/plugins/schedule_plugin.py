"""Schedule readout. Try: "what's my schedule today", "what's on today".

Reads two sources:
1. Pending timers/reminders from the timer plugin (live).
2. An optional user-editable file (config/schedule.yaml by default —
   see config/schedule.yaml for the format): a simple list of
   time -> event entries for today.

No Google Calendar integration here: that needs OAuth set up on the
user's PC. See BUILD_NOTES.md ("Future: Google Calendar").
"""
import re
from datetime import datetime
from pathlib import Path

import yaml

from ..config import project_root
from . import timer_plugin
from .base import Plugin

_RX = re.compile(
    r"\bschedule\b|\bagenda\b|\bwhat'?s on today\b|\bmy day\b|\btoday'?s plan\b")


def _schedule_path(config):
    raw = (config or {}).get("schedule_file", "config/schedule.yaml")
    path = Path(raw)
    if not path.is_absolute():
        path = project_root() / path
    return path


def _load_events(config):
    path = _schedule_path(config)
    if not path.is_file():
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or []
    except Exception:
        return []
    events = []
    for row in data if isinstance(data, list) else []:
        if isinstance(row, dict) and row.get("time") and row.get("event"):
            events.append((str(row["time"]), str(row["event"])))
    return sorted(events)


class SchedulePlugin(Plugin):
    name = "schedule"
    description = "Reads your schedule: \"what's my schedule today\"."

    def match(self, text):
        return bool(_RX.search(text))

    def run(self, text):
        parts = []

        pending = timer_plugin.list_pending()
        if pending:
            bits = []
            for fire_at, label in sorted(pending):
                when = fire_at.strftime("%I:%M %p").lstrip("0")
                bits.append(f"{label} at {when}")
            parts.append("Timers and reminders: " + "; ".join(bits))

        brain = getattr(self, "brain", None)
        events = _load_events(brain.config if brain else None)
        if events:
            today = datetime.now().strftime("%A")
            bits = [f"{t} — {e}" for t, e in events]
            parts.append(f"{today}'s plan: " + "; ".join(bits))

        if not parts:
            return ("Nothing on your schedule. Set a reminder with "
                    "\"remind me to ... in 20 minutes\", or add events to "
                    "config/schedule.yaml.")
        return "Here's your schedule. " + " ".join(parts) + "."


plugin = SchedulePlugin()
