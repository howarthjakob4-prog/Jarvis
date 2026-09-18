"""Opens apps. Try: 'open notepad', 'launch calculator', 'open browser'."""
import re

from ..control import pc
from .base import Plugin

_RX = re.compile(r"\b(?:open|launch|start)\s+(?:the\s+)?(.+?)\s*$")


class AppPlugin(Plugin):
    name = "apps"
    description = "Opens apps: 'open notepad'."

    def match(self, text):
        m = _RX.search(text)
        return bool(m and m.group(1).strip())

    def run(self, text):
        target = _RX.search(text).group(1).strip()
        _ok, message = pc.open_app(target)
        return message


plugin = AppPlugin()
