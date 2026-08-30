import asyncio
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import psutil
from loguru import logger

from jarvis.models import ToolDefinition
from jarvis.plugins.base import Plugin


# JARVIS may work across the owner's normal files and drives, but it does not
# bypass Windows security, read credential stores, or alter protected OS areas.
_PROTECTED_WRITE_ROOTS = [
    Path(os.environ.get("WINDIR", r"C:\Windows")),
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
    Path(os.environ.get("ProgramData", r"C:\ProgramData")),
]

_SENSITIVE_PARTS = {
    ".ssh", ".gnupg", "credentials", "credential manager", "vault",
    "login data", "cookies", "web data", "local state",
}


def _resolved(path: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path))).resolve()


def _contains_sensitive_part(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    return any(s in parts for s in _SENSITIVE_PARTS)


def _safe_for_read(path: Path) -> None:
    if _contains_sensitive_part(path):
        raise PermissionError("JARVIS will not read credential or secret-store files.")


def _safe_for_write(path: Path) -> None:
    if _contains_sensitive_part(path):
        raise PermissionError("JARVIS will not modify credential or secret-store files.")
    for root in _PROTECTED_WRITE_ROOTS:
        try:
            path.relative_to(root.resolve())
            raise PermissionError(f"JARVIS will not modify protected Windows area: {root}")
        except ValueError:
            pass


async def _owner_confirm(action: str) -> bool:
    """Use JARVIS's normal approval UI for destructive/overwrite actions."""
    try:
        from jarvis.app import get_runtime
        runtime = get_runtime()
        if runtime is None:
            return False
        # In fully autonomous mode the owner already selected auto-run.
        if getattr(runtime, "automation_policy", "ask") == "full_auto":
            return True
        return await runtime._approval_callback(action, "confirm")
    except Exception:
        return False


class OwnerPCAccessPlugin(Plugin):
    """Broad owner-approved Windows PC controls for files, drives and apps.

    This intentionally stops short of bypassing Windows security controls,
    credential stores, protected OS directories, or silent destructive actions.
    """

    def __init__(self):
        super().__init__("owner_pc_access")

    async def initialize(self) -> None:
        logger.info("OwnerPCAccessPlugin ready")

    async def shutdown(self) -> None:
        pass

    def get_tools(self):
        return [
            (ToolDefinition(
                name="pc_list_drives",
                description="List drives currently available on the owner's Windows PC, including free space.",
                parameters={"type": "object", "properties": {}},
            ), self.list_drives),
            (ToolDefinition(
                name="pc_list_folder",
                description="List files and folders at any normal owner-accessible path on the PC.",
                parameters={"type": "object", "properties": {
                    "path": {"type": "string"},
                    "limit": {"type": "integer", "default": 200}
                }, "required": ["path"]},
            ), self.list_folder),
            (ToolDefinition(
                name="pc_read_text_file",
                description="Read a normal text/code/config file from an owner-accessible path. Credential stores are blocked.",
                parameters={"type": "object", "properties": {
                    "path": {"type": "string"},
                    "max_chars": {"type": "integer", "default": 12000}
                }, "required": ["path"]},
            ), self.read_text_file),
            (ToolDefinition(
                name="pc_write_text_file",
                description="Create or update a normal text/code/config file anywhere the owner can write. Protected Windows areas and credential stores are blocked; overwrites require approval unless full-auto mode is selected.",
                parameters={"type": "object", "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "overwrite": {"type": "boolean", "default": False}
                }, "required": ["path", "content"]},
            ), self.write_text_file),
            (ToolDefinition(
                name="pc_copy_path",
                description="Copy a file or folder to another normal owner-accessible location.",
                parameters={"type": "object", "properties": {
                    "source": {"type": "string"}, "destination": {"type": "string"}
                }, "required": ["source", "destination"]},
            ), self.copy_path),
            (ToolDefinition(
                name="pc_move_path",
                description="Move or rename a file/folder. Requires owner approval unless full-auto mode is selected.",
                parameters={"type": "object", "properties": {
                    "source": {"type": "string"}, "destination": {"type": "string"}
                }, "required": ["source", "destination"]},
            ), self.move_path),
            (ToolDefinition(
                name="pc_delete_path",
                description="Delete a file or folder only after owner approval unless full-auto mode is selected.",
                parameters={"type": "object", "properties": {
                    "path": {"type": "string"}, "recursive": {"type": "boolean", "default": False}
                }, "required": ["path"]},
            ), self.delete_path),
            (ToolDefinition(
                name="pc_open_path",
                description="Open a file, folder, document or URL with Windows default handling.",
                parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            ), self.open_path),
            (ToolDefinition(
                name="pc_launch_program",
                description="Launch a Windows program or executable with optional arguments.",
                parameters={"type": "object", "properties": {
                    "program": {"type": "string"},
                    "args": {"type": "array", "items": {"type": "string"}}
                }, "required": ["program"]},
            ), self.launch_program),
            (ToolDefinition(
                name="pc_running_apps",
                description="List currently running applications/processes so JARVIS can find and work with installed software.",
                parameters={"type": "object", "properties": {"limit": {"type": "integer", "default": 150}}},
            ), self.running_apps),
        ]

    async def list_drives(self, **_: Any) -> str:
        rows = []
        for p in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(p.mountpoint)
                rows.append(f"{p.device}  {p.mountpoint}  free={usage.free // (1024**3)} GB  total={usage.total // (1024**3)} GB")
            except Exception:
                rows.append(f"{p.device}  {p.mountpoint}")
        return "\n".join(rows) or "No drives found."

    async def list_folder(self, path: str, limit: int = 200) -> str:
        p = _resolved(path)
        _safe_for_read(p)
        if not p.exists():
            return f"Not found: {p}"
        if not p.is_dir():
            return f"Not a folder: {p}"
        limit = max(1, min(int(limit), 1000))
        items = []
        for child in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))[:limit]:
            kind = "DIR" if child.is_dir() else "FILE"
            try:
                size = "" if child.is_dir() else f" {child.stat().st_size} bytes"
            except OSError:
                size = ""
            items.append(f"[{kind}] {child.name}{size}")
        return f"Folder: {p}\n" + "\n".join(items)

    async def read_text_file(self, path: str, max_chars: int = 12000) -> str:
        p = _resolved(path)
        _safe_for_read(p)
        if not p.is_file():
            return f"Not a file: {p}"
        max_chars = max(100, min(int(max_chars), 100000))
        def _read():
            with p.open("r", encoding="utf-8", errors="replace") as f:
                return f.read(max_chars)
        text = await asyncio.to_thread(_read)
        return text

    async def write_text_file(self, path: str, content: str, overwrite: bool = False) -> str:
        p = _resolved(path)
        _safe_for_write(p)
        if p.exists() and not overwrite:
            return f"File already exists: {p}. Set overwrite=true only when the owner wants it replaced."
        if p.exists() and not await _owner_confirm(f"Overwrite file: {p}"):
            return "Overwrite declined."
        p.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(p.write_text, content, encoding="utf-8")
        return f"Saved: {p}"

    async def copy_path(self, source: str, destination: str) -> str:
        src, dst = _resolved(source), _resolved(destination)
        _safe_for_read(src); _safe_for_write(dst)
        if not src.exists():
            return f"Source not found: {src}"
        if src.is_dir():
            await asyncio.to_thread(shutil.copytree, src, dst, dirs_exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(shutil.copy2, src, dst)
        return f"Copied {src} -> {dst}"

    async def move_path(self, source: str, destination: str) -> str:
        src, dst = _resolved(source), _resolved(destination)
        _safe_for_read(src); _safe_for_write(src); _safe_for_write(dst)
        if not src.exists():
            return f"Source not found: {src}"
        if not await _owner_confirm(f"Move/rename: {src} -> {dst}"):
            return "Move declined."
        dst.parent.mkdir(parents=True, exist_ok=True)
        result = await asyncio.to_thread(shutil.move, str(src), str(dst))
        return f"Moved to: {result}"

    async def delete_path(self, path: str, recursive: bool = False) -> str:
        p = _resolved(path)
        _safe_for_write(p)
        if not p.exists():
            return f"Not found: {p}"
        if not await _owner_confirm(f"Delete: {p}"):
            return "Delete declined."
        if p.is_dir():
            if not recursive:
                try:
                    await asyncio.to_thread(p.rmdir)
                except OSError:
                    return "Folder is not empty. Set recursive=true only if the owner wants the entire folder deleted."
            else:
                await asyncio.to_thread(shutil.rmtree, p)
        else:
            await asyncio.to_thread(p.unlink)
        return f"Deleted: {p}"

    async def open_path(self, path: str) -> str:
        value = os.path.expandvars(os.path.expanduser(path))
        if value.lower().startswith(("http://", "https://")):
            await asyncio.to_thread(os.startfile, value)
            return f"Opened: {value}"
        p = _resolved(value)
        _safe_for_read(p)
        if not p.exists():
            return f"Not found: {p}"
        await asyncio.to_thread(os.startfile, str(p))
        return f"Opened: {p}"

    async def launch_program(self, program: str, args: list[str] | None = None) -> str:
        args = args or []
        expanded = os.path.expandvars(os.path.expanduser(program))
        p = Path(expanded)
        if p.exists():
            _safe_for_read(p.resolve())
            proc = await asyncio.to_thread(subprocess.Popen, [str(p)] + [str(a) for a in args])
        else:
            # Let Windows resolve Start-menu/PATH applications without using shell=True.
            proc = await asyncio.to_thread(subprocess.Popen, [expanded] + [str(a) for a in args])
        return f"Launched {program} (PID {proc.pid})"

    async def running_apps(self, limit: int = 150) -> str:
        limit = max(1, min(int(limit), 500))
        rows = []
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                info = proc.info
                rows.append(f"{info.get('pid')}  {info.get('name') or '?'}  {info.get('exe') or ''}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return "\n".join(rows[:limit])
