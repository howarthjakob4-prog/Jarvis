"""
Generic event bus so voice/, brain/, files/, apps/, and ui/ don't import
each other directly. A module publishes an event by name; anything
interested subscribes to that name. This is what lets Stage 2+ features
get added by registering new subscribers instead of editing existing
modules.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from core.errors import logger


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[..., None]]] = defaultdict(list)

    def subscribe(self, event_name: str, callback: Callable[..., None]) -> None:
        self._subscribers[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: Callable[..., None]) -> None:
        if callback in self._subscribers.get(event_name, []):
            self._subscribers[event_name].remove(callback)

    def publish(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        logger.debug("event: %s args=%s kwargs=%s", event_name, args, kwargs)
        for callback in list(self._subscribers.get(event_name, [])):
            callback(*args, **kwargs)


# Shared instance for the whole app.
event_bus = EventBus()

# --- Known event names (documented here so new modules stay consistent) ---
# "user_text_input"        (text: str)                 -> chat box submit
# "user_voice_transcript"  (text: str)                 -> STT result
# "wake_word_detected"     ()                           -> mic should start listening
# "jarvis_reply_text"      (text: str)                 -> text to show in chat
# "jarvis_reply_speak"     (text: str)                 -> text to speak aloud
# "status_changed"         (status: str)               -> for the status bar
# "settings_changed"       (section: str)              -> "voice"/"permissions"/"features"
