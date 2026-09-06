"""
Every module in Jarvis reports failures through here instead of printing,
swallowing, or faking success. The UI subscribes to `error_bus` and shows
every JarvisError it receives. If you're adding a new module: raise a
JarvisError (or a subclass) rather than returning None/False on failure.
"""
from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "jarvis.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger("jarvis")


class JarvisError(Exception):
    """Base class for all Jarvis-raised errors. Carries a module name and
    a user-facing message so the UI never has to guess what happened."""

    def __init__(self, module: str, message: str, *, recoverable: bool = True):
        self.module = module
        self.message = message
        self.recoverable = recoverable
        self.timestamp = datetime.now()
        super().__init__(f"[{module}] {message}")


class PermissionDeniedError(JarvisError):
    def __init__(self, path: str):
        super().__init__(
            module="permissions",
            message=f"Access to '{path}' was denied. This folder/file is not "
                     f"in the approved list. Add it in Settings > Permissions "
                     f"if you want Jarvis to be able to use it.",
            recoverable=True,
        )


class DeviceError(JarvisError):
    """Microphone/speaker/audio device problems."""
    pass


class ModelLoadError(JarvisError):
    """STT/TTS/wake-word model failed to load (missing file, bad format, etc.)."""
    pass


class ConfigError(JarvisError):
    pass


class AppLaunchError(JarvisError):
    pass


class AIBackendError(JarvisError):
    pass


@dataclass
class ErrorBus:
    """Simple pub/sub so the UI (and logs) hear about every JarvisError,
    regardless of which module raised it."""

    _subscribers: list[Callable[[JarvisError], None]] = field(default_factory=list)

    def subscribe(self, callback: Callable[[JarvisError], None]) -> None:
        self._subscribers.append(callback)

    def report(self, error: JarvisError) -> None:
        logger.error("%s: %s\n%s", error.module, error.message, traceback.format_exc()
                      if error.__cause__ else "")
        for callback in list(self._subscribers):
            try:
                callback(error)
            except Exception:
                logger.exception("An error-bus subscriber itself raised while handling an error")


# One shared instance for the whole app.
error_bus = ErrorBus()
