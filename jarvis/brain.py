"""Conversation brain.

Offline-first: plugins, then built-in small talk, then Groq if a key is set.
With no key it still answers time/apps/volume/small talk, and says plainly
when a question needs an AI key instead of failing silently.
"""
import re

import requests

from .plugins import load_plugins

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
SYSTEM_PROMPT = (
    "You are Jarvis, a concise Windows voice assistant. "
    "Keep replies short — they will be spoken aloud."
)


class Brain:
    def __init__(self, config):
        self.config = config
        self.plugins = load_plugins()
        # Optional: main.py sets this to ui.announce_alert so plugins doing
        # background work (timers, reminders) can speak + log + pop up later.
        self.alert_handler = None
        for plugin in self.plugins:
            try:
                plugin.bind(self)
            except Exception:
                pass

    def alert(self, text: str):
        """Announce something outside the normal request/reply flow."""
        if self.alert_handler:
            try:
                self.alert_handler(text)
            except Exception:
                pass

    def get_plugin(self, name: str):
        for plugin in self.plugins:
            if plugin.name == name:
                return plugin
        return None

    def has_ai(self) -> bool:
        return bool(self.config.get("groq_api_key"))

    def respond(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return "I didn't catch that."
        low = text.lower()

        for plugin in self.plugins:
            try:
                if plugin.match(low):
                    return plugin.run(low)
            except Exception as exc:
                return f"The {plugin.name} plugin hit an error: {exc}"

        smalltalk = self._offline_smalltalk(low)
        if smalltalk:
            return smalltalk

        if self.has_ai():
            return self._ask_groq(text)
        return (
            "I can handle the time, apps, volume, news, weather, music, "
            "timers, your schedule, and 3D model designs offline. "
            "For anything else I need a Groq API key — it's free. "
            "Run the setup wizard to add one."
        )

    def _offline_smalltalk(self, low: str):
        if re.search(r"\b(hello|hi|hey|greetings|good morning|good evening)\b", low):
            return "Hello. How can I help?"
        if "your name" in low:
            return "I'm Jarvis, your Windows assistant."
        if "how are you" in low:
            return "Running fine. How can I help?"
        if re.search(r"\b(help|what can you do)\b", low):
            return (
                "I can tell you the time, open apps like notepad, change the "
                "volume, brief you on the news, play music on YouTube, check "
                "the weather, set timers and reminders, read your "
                "schedule, and design 3D models for printing. "
                "Try 'brief me', 'play some jazz on YouTube', or "
                "'design a 3D model of a phone stand'."
            )
        if re.search(r"\b(thanks|thank you)\b", low):
            return "You're welcome."
        if re.search(r"\b(bye|goodbye|see you)\b", low):
            return "Goodbye."
        return None

    def _ask_groq(self, text: str) -> str:
        try:
            resp = requests.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {self.config['groq_api_key']}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.config.get("groq_model", "llama-3.3-70b-versatile"),
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": text},
                    ],
                    "max_tokens": 150,
                    "temperature": 0.7,
                },
                timeout=30,
            )
        except requests.RequestException as exc:
            return f"I couldn't reach Groq: {exc}"
        if resp.status_code != 200:
            return (
                f"Groq returned an error (HTTP {resp.status_code}). "
                "Your key may be invalid."
            )
        try:
            return resp.json()["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, ValueError):
            return "Groq gave back something I couldn't understand."
