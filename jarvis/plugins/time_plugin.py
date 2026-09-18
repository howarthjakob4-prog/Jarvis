"""Tells the time and date. Try: 'what time is it', 'what's today's date'."""
import re
from datetime import datetime

from .base import Plugin

_PATTERNS = [
    (re.compile(r"\bwhat time\b|\bcurrent time\b|\bthe time\b|\bclock\b"), "time"),
    (re.compile(r"\bwhat date\b|\btoday'?s date\b|\bwhat day is it\b"), "date"),
]


class TimePlugin(Plugin):
    name = "time"
    description = "Tells the time and date."

    def match(self, text):
        return any(rx.search(text) for rx, _ in _PATTERNS)

    def run(self, text):
        now = datetime.now()
        for rx, kind in _PATTERNS:
            if rx.search(text):
                if kind == "time":
                    return "It's " + now.strftime("%I:%M %p").lstrip("0") + "."
                return "Today is " + now.strftime("%A, %B %d, %Y") + "."
        return "It's " + now.strftime("%I:%M %p").lstrip("0") + "."


plugin = TimePlugin()
