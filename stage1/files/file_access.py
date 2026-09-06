"""
Every file/folder operation in Jarvis routes through here. Nothing else in
the codebase should call open(), Path.read_text(), os.listdir(), etc.
directly on a user-supplied path. If a path isn't approved, this raises
PermissionDeniedError — it never silently returns empty results, and it
never falls back to "just this once."
"""
from __future__ import annotations

from pathlib import Path

from core.errors import PermissionDeniedError, error_bus
from core.permission_manager import permissions


def _check(path: str | Path) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not permissions.is_approved(resolved):
        err = PermissionDeniedError(str(resolved))
        error_bus.report(err)
        raise err
    return resolved


def list_folder(path: str | Path) -> list[str]:
    resolved = _check(path)
    if not resolved.is_dir():
        err = PermissionDeniedError(str(resolved))
        err.message = f"'{resolved}' is not a folder Jarvis can list."
        error_bus.report(err)
        raise err
    return sorted(p.name for p in resolved.iterdir())


def read_text_file(path: str | Path, max_chars: int = 200_000) -> str:
    resolved = _check(path)
    if resolved.is_dir():
        raise PermissionDeniedError(str(resolved))
    try:
        text = resolved.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        from core.errors import JarvisError
        err = JarvisError(module="file_access", message=f"Could not read '{resolved}': {e}")
        error_bus.report(err)
        raise err
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n...[truncated, {len(text) - max_chars} more characters]"
    return text


def write_text_file(path: str | Path, content: str, overwrite: bool = False) -> None:
    resolved_parent = Path(path).expanduser().resolve().parent
    target = Path(path).expanduser().resolve()
    if not permissions.is_approved(target) and not permissions.is_approved(resolved_parent):
        err = PermissionDeniedError(str(target))
        error_bus.report(err)
        raise err
    if target.exists() and not overwrite:
        from core.errors import JarvisError
        err = JarvisError(
            module="file_access",
            message=f"'{target}' already exists. Pass overwrite=True to replace it — "
                     f"Jarvis will not silently overwrite files.",
        )
        error_bus.report(err)
        raise err
    try:
        target.write_text(content, encoding="utf-8")
    except OSError as e:
        from core.errors import JarvisError
        err = JarvisError(module="file_access", message=f"Could not write '{target}': {e}")
        error_bus.report(err)
        raise err


def file_exists(path: str | Path) -> bool:
    resolved = _check(path)
    return resolved.exists()
