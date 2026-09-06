"""
The single source of truth for "is Jarvis allowed to touch this?"

Design rules (do not weaken these without meaning to):
  1. Default is deny. A path is approved only if it's explicitly listed,
     or is inside an explicitly approved folder.
  2. Approval is by resolved absolute path, so "../" tricks or relative
     paths can't sneak something in or out of an approved folder.
  3. This module never scans, walks, or lists anything on its own. It only
     answers yes/no questions about specific paths it's asked about.
  4. Revoking is instant — remove_folder/remove_file/remove_app take effect
     on the very next check, no caching that could go stale.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.errors import ConfigError, error_bus

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
PERMISSIONS_PATH = CONFIG_DIR / "permissions.json"
PERMISSIONS_DEFAULT_PATH = CONFIG_DIR / "permissions.default.json"


class PermissionManager:
    def __init__(self) -> None:
        self._data: dict[str, list] = {"approved_folders": [], "approved_files": [], "approved_apps": []}
        self._load()

    def _load(self) -> None:
        source = PERMISSIONS_PATH if PERMISSIONS_PATH.exists() else PERMISSIONS_DEFAULT_PATH
        if not source.exists():
            error_bus.report(ConfigError(
                module="permission_manager",
                message="No permissions file found at all. Starting with zero "
                         "approved folders/files/apps (safest default).",
            ))
            return
        try:
            self._data = json.loads(source.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            error_bus.report(ConfigError(
                module="permission_manager",
                message=f"permissions.json is invalid ({e}). Starting with zero "
                         f"approved folders/files/apps until you fix or re-approve them.",
            ))
            self._data = {"approved_folders": [], "approved_files": [], "approved_apps": []}
            return
        if not PERMISSIONS_PATH.exists():
            self._save()

    def _save(self) -> None:
        try:
            PERMISSIONS_PATH.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except OSError as e:
            error_bus.report(ConfigError(
                module="permission_manager",
                message=f"Could not save permissions to {PERMISSIONS_PATH}: {e}",
            ))

    @staticmethod
    def _norm(path: str | Path) -> str:
        return str(Path(path).expanduser().resolve())

    def approve_folder(self, path: str | Path) -> None:
        p = self._norm(path)
        if p not in self._data["approved_folders"]:
            self._data["approved_folders"].append(p)
            self._save()

    def revoke_folder(self, path: str | Path) -> None:
        p = self._norm(path)
        if p in self._data["approved_folders"]:
            self._data["approved_folders"].remove(p)
            self._save()

    def approve_file(self, path: str | Path) -> None:
        p = self._norm(path)
        if p not in self._data["approved_files"]:
            self._data["approved_files"].append(p)
            self._save()

    def revoke_file(self, path: str | Path) -> None:
        p = self._norm(path)
        if p in self._data["approved_files"]:
            self._data["approved_files"].remove(p)
            self._save()

    def is_approved(self, path: str | Path) -> bool:
        target = self._norm(path)
        if target in self._data["approved_files"]:
            return True
        for folder in self._data["approved_folders"]:
            try:
                Path(target).relative_to(folder)
                return True
            except ValueError:
                continue
        return False

    def list_approved_folders(self) -> list[str]:
        return list(self._data["approved_folders"])

    def list_approved_files(self) -> list[str]:
        return list(self._data["approved_files"])

    def approve_app(self, name: str, path: str | Path) -> None:
        entry = {"name": name, "path": self._norm(path)}
        existing = [a for a in self._data["approved_apps"] if a["name"].lower() == name.lower()]
        if existing:
            existing[0]["path"] = entry["path"]
        else:
            self._data["approved_apps"].append(entry)
        self._save()

    def revoke_app(self, name: str) -> None:
        self._data["approved_apps"] = [
            a for a in self._data["approved_apps"] if a["name"].lower() != name.lower()
        ]
        self._save()

    def get_approved_app(self, name: str) -> dict[str, str] | None:
        for a in self._data["approved_apps"]:
            if a["name"].lower() == name.lower():
                return dict(a)
        return None

    def list_approved_apps(self) -> list[dict[str, str]]:
        return [dict(a) for a in self._data["approved_apps"]]


permissions = PermissionManager()
