"""Volume control via keyboard media keys. Try: 'volume up', 'quieter', 'mute'."""
import re

from ..control import pc
from .base import Plugin

_RULES = [
    (re.compile(r"\bvolume up\b|\bturn (it|the volume) up\b|\blouder\b"), "up"),
    (re.compile(r"\bvolume down\b|\bturn (it|the volume) down\b|\bquieter\b|\bsofter\b"), "down"),
    (re.compile(r"\bmute\b|\bsilence\b"), "mute"),
]


class VolumePlugin(Plugin):
    name = "volume"
    description = "Volume up / down / mute."

    def match(self, text):
        return any(rx.search(text) for rx, _ in _RULES)

    def run(self, text):
        for rx, action in _RULES:
            if rx.search(text):
                if action == "up":
                    _ok, msg = pc.volume_up()
                elif action == "down":
                    _ok, msg = pc.volume_down()
                else:
                    _ok, msg = pc.volume_mute()
                return msg
        return "Volume unchanged."


plugin = VolumePlugin()
