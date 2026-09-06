"""
Launches apps by friendly name, looked up against the approved-apps list
in PermissionManager. There is no code path here that launches an
arbitrary, un-approved executable path.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from core.errors import AppLaunchError, error_bus
from core.permission_manager import permissions
from core.settings_manager import settings


def launch_app(name: str) -> None:
    if not settings.get("features", "app_launching", default=True):
        err = AppLaunchError(
            module="app_launcher",
            message="App launching is turned off in Settings > Connected Features.",
        )
        error_bus.report(err)
        raise err

    entry = permissions.get_approved_app(name)
    if entry is None:
        available = ", ".join(a["name"] for a in permissions.list_approved_apps()) or "(none approved yet)"
        err = AppLaunchError(
            module="app_launcher",
            message=f"'{name}' is not in the approved apps list. "
                     f"Approved apps: {available}. Add it in Settings > Permissions.",
        )
        error_bus.report(err)
        raise err

    exe_path = Path(entry["path"])
    if not exe_path.exists():
        err = AppLaunchError(
            module="app_launcher",
            message=f"'{name}' is approved, but its path no longer exists: {exe_path}. "
                     f"Update it in Settings > Permissions.",
        )
        error_bus.report(err)
        raise err

    try:
        subprocess.Popen([str(exe_path)], shell=False)
    except OSError as e:
        err = AppLaunchError(module="app_launcher", message=f"Failed to launch '{name}': {e}")
        error_bus.report(err)
        raise err
