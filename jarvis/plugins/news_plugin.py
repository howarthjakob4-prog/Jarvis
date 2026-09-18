"""News briefing. Try: 'brief me', 'news briefing', 'headlines'.

Fetches key-free RSS headlines (BBC, then Google News) and reads the top 5
aloud. The panel ticker uses the same feed via jarvis.news.
"""
import re

from ..news import NewsError, fetch_headlines
from .base import Plugin

_RX = re.compile(r"\bbrief me\b|\bnews briefing\b|\bheadlines\b|\btop news\b|\bnews\b")


class NewsPlugin(Plugin):
    name = "news"
    description = "Reads the top headlines: 'brief me'."

    def match(self, text):
        return bool(_RX.search(text))

    def run(self, text):
        try:
            titles = fetch_headlines(limit=5)
        except NewsError:
            return "I couldn't fetch the headlines — check your internet connection."
        lines = [f"{i + 1}. {t}" for i, t in enumerate(titles)]
        return "Here are the top headlines: " + " ".join(lines)


plugin = NewsPlugin()
