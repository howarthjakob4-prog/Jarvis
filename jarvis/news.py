"""Key-free headline fetching, shared by the news plugin and the UI ticker.

Uses public RSS feeds (BBC, Google News) over plain HTTPS — no API key.
Stdlib only (urllib + ElementTree) so it imports anywhere.
"""
import urllib.request
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen

FEEDS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
]
USER_AGENT = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Jarvis/2.0"}


class NewsError(Exception):
    """Raised when no feed could be reached. Message is human-readable."""


def _fetch(url, timeout=12):
    req = Request(url, headers=USER_AGENT)
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _parse_rss(data):
    root = ET.fromstring(data)
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if title:
            items.append(title)
    return items


def fetch_headlines(limit=8, timeout=12):
    """Return up to `limit` headline strings. Tries each feed in order.

    Raises NewsError if every feed failed (e.g. offline).
    """
    errors = []
    for url in FEEDS:
        try:
            titles = _parse_rss(_fetch(url, timeout))
        except Exception as exc:
            errors.append(f"{url}: {exc}")
            continue
        if titles:
            return titles[:limit]
    raise NewsError("Could not reach any news feed. " + "; ".join(errors[:2]))
