"""
Loads config/settings.json (creating it from settings.default.json on first
run), and lets other modules read/update it. Every write is saved to disk
immediately — there's no "unsaved changes" state to lose track of.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from core.errors import ConfigError, error_bus

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
SETTINGS_DEFAULT_PATH = CONFIG_DIR / "settings.default.json"


class SettingsManager:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not SETTINGS_PATH.exists():
            if not SETTINGS_DEFAULT_PATH.exists():
                error_bus.report(ConfigError(
                    module="settings_manager",
                    message=f"No settings.default.json found at {SETTINGS_DEFAULT_PATH}. "
                             f"Jarvis cannot start without default settings.",
                    recoverable=False,
                ))
                self._data = {}
                return
            default_data = json.loads(SETTINGS_DEFAULT_PATH.read_text(encoding="utf-8"))
            SETTINGS_PATH.write_text(json.dumps(default_data, indent=2), encoding="utf-8")
            self._data = default_data
            return

        try:
            self._data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            error_bus.report(ConfigError(
                module="settings_manager",
                message=f"settings.json is corrupted or invalid JSON ({e}). "
                         f"Fix or delete the file at {SETTINGS_PATH} and restart.",
                recoverable=False,
            ))
            self._data = {}

    def save(self) -> None:
        try:
            SETTINGS_PATH.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except OSError as e:
            error_bus.report(ConfigError(
                module="settings_manager",
                message=f"Could not save settings to {SETTINGS_PATH}: {e}",
            ))

    def get(self, *keys: str, default: Any = None) -> Any:
        node: Any = self._data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return copy.deepcopy(node)

    def set(self, *keys: str, value: Any) -> None:
        if not keys:
            raise ValueError("set() requires at least one key")
        node = self._data
        for key in keys[:-1]:
            node = node.setdefault(key, {})
        node[keys[-1]] = value
        self.save()

    def all(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)


settings = SettingsManager()
