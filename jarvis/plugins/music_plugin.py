"""YouTube music. Try: 'play bohemian rhapsody on youtube', 'play some jazz'.

Opens the YouTube search results for the song in the default browser —
no API key needed. Nothing streams inside Jarvis; your browser plays it.
"""
import re
import webbrowser
from urllib.parse import quote_plus

from .base import Plugin

_RX = re.compile(r"\bplay\s+(.+?)(?:\s+on\s+youtube)?\s*$")


class MusicPlugin(Plugin):
    name = "music"
    description = "Plays music on YouTube: 'play <song> on youtube'."

    def match(self, text):
        m = _RX.search(text)
        return bool(m and m.group(1).strip())

    def run(self, text):
        query = _RX.search(text).group(1).strip().rstrip(".")
        url = "https://www.youtube.com/results?search_query=" + quote_plus(query)
        try:
            webbrowser.open(url)
        except Exception:
            return "I couldn't open the browser."
        return f"Playing {query} on YouTube."


plugin = MusicPlugin()
