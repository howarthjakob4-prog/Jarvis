from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

_STATE_DIR = Path.home() / ".jarvis"
_PROJECTS_PATH = _STATE_DIR / "projects.json"
_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".idea", ".vs", "bin", "obj",
}
_MODEL_EXTS = {".blend", ".fbx", ".obj", ".gltf", ".glb", ".stl", ".dae", ".3ds", ".abc", ".usd", ".usda", ".usdc"}
_TEXTURE_EXTS = {".png", ".jpg", ".jpeg", ".tga", ".bmp", ".tif", ".tiff", ".exr", ".hdr", ".webp", ".dds"}
_NAMING_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$", re.IGNORECASE)


def _ensure_state_dir() -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)


def _load_projects() -> list[dict]:
    _ensure_state_dir()
    if not _PROJECTS_PATH.exists():
        return []
    try:
        data = json.loads(_PROJECTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if isinstance(item, dict) and item.get("name") and item.get("path"):
            out.append({
                "name": str(item["name"]),
                "path": str(item["path"]),
                "description": str(item.get("description", "")),
            })
    return out


def _save_projects(projects: list[dict]) -> None:
    _ensure_state_dir()
    tmp = _PROJECTS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(projects, indent=2), encoding="utf-8")
    tmp.replace(_PROJECTS_PATH)


def _resolve_user_path(path: str) -> Path:
    resolved = Path(os.path.expandvars(os.path.expanduser(path))).resolve()
    home = Path.home().resolve()
    try:
        resolved.relative_to(home)
    except ValueError as exc:
        raise PermissionError(
            f"Project folders must be under your user folder ({home}). "
            f"Move or link the project there before registering it."
        ) from exc
    return resolved


def register_project(name: str, path: str, description: str = "") -> str:
    name = name.strip()
    if not name:
        raise ValueError("Project name cannot be empty.")
    root = _resolve_user_path(path)
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Project folder does not exist: {root}")

    projects = _load_projects()
    entry = {"name": name, "path": str(root), "description": description.strip()}
    for idx, existing in enumerate(projects):
        if existing["name"].casefold() == name.casefold():
            projects[idx] = entry
            _save_projects(projects)
            return f"Updated project '{name}' -> {root}"
    projects.append(entry)
    _save_projects(projects)
    return f"Registered project '{name}' -> {root}"


def remove_project(name: str) -> str:
    projects = _load_projects()
    kept = [p for p in projects if p["name"].casefold() != name.strip().casefold()]
    if len(kept) == len(projects):
        return f"No registered project named '{name}'."
    _save_projects(kept)
    return f"Removed project '{name}' from Jarvis project access."


def list_projects() -> list[dict]:
    return _load_projects()


def get_project(name: str) -> dict:
    projects = _load_projects()
    for project in projects:
        if project["name"].casefold() == name.strip().casefold():
            return project
    known = ", ".join(p["name"] for p in projects) or "none"
    raise KeyError(f"No project named '{name}'. Registered projects: {known}")


def _walk_project(project: dict, max_depth: int = 6, max_entries: int = 5000) -> list[dict]:
    root = Path(project["path"]).resolve()
    results: list[dict] = []
    root_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        depth = len(current.parts) - root_depth
        if depth >= max_depth:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in list(dirnames) + filenames:
            full = current / name
            try:
                resolved = full.resolve()
                resolved.relative_to(root)
                stat = resolved.stat()
            except (OSError, ValueError):
                continue
            results.append({
                "path": str(resolved.relative_to(root)),
                "is_dir": resolved.is_dir(),
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            })
            if len(results) >= max_entries:
                return results
    return results


def _time_ago(mtime: float) -> str:
    delta = max(0.0, time.time() - mtime)
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86400)}d ago"


def summarize_project(name: str, recent_count: int = 8) -> str:
    project = get_project(name)
    root = Path(project["path"])
    entries = _walk_project(project)
    files = [e for e in entries if not e["is_dir"]]
    folders = [e for e in entries if e["is_dir"]]
    counts: Counter[str] = Counter()
    for e in files:
        suffix = Path(e["path"]).suffix.lower().lstrip(".") or "(no extension)"
        counts[suffix] += 1
    recent = sorted(files, key=lambda e: e["mtime"], reverse=True)[:max(1, min(recent_count, 20))]
    try:
        top = sorted(p.name for p in root.iterdir())[:15]
    except OSError:
        top = []

    lines = [f"Project '{project['name']}' ({project['path']})", f"{len(files)} files, {len(folders)} folders."]
    if counts:
        lines.append("File types — " + ", ".join(f"{ext}: {count}" for ext, count in counts.most_common(8)))
    if top:
        lines.append("Top level: " + ", ".join(top))
    if recent:
        lines.append("Recently modified: " + "; ".join(f"{e['path']} ({_time_ago(e['mtime'])})" for e in recent))
    return "\n".join(lines)


def recent_project_files(name: str, count: int = 10) -> str:
    project = get_project(name)
    files = [e for e in _walk_project(project) if not e["is_dir"]]
    recent = sorted(files, key=lambda e: e["mtime"], reverse=True)[:max(1, min(count, 30))]
    if not recent:
        return f"No files found in '{project['name']}'."
    return "\n".join(f"{e['path']} — {_time_ago(e['mtime'])}" for e in recent)


def open_project_file(project_name: str, relative_path: str) -> str:
    project = get_project(project_name)
    root = Path(project["path"]).resolve()
    target = (root / relative_path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise PermissionError("The requested file escapes the registered project folder.") from exc
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(f"File not found in project: {relative_path}")
    if not hasattr(os, "startfile"):
        return "Opening project files with the default app is supported on Windows only."
    os.startfile(str(target))
    return f"Opening {relative_path} from {project['name']}."


@dataclass
class AssetReport:
    project_name: str
    model_files: list[tuple[str, int]] = field(default_factory=list)
    texture_files: list[tuple[str, int]] = field(default_factory=list)
    naming_issues: list[str] = field(default_factory=list)
    large_files: list[tuple[str, int]] = field(default_factory=list)
    missing_recommended_folders: list[str] = field(default_factory=list)


def scan_3d_assets(
    name: str,
    large_file_mb: int = 100,
    recommended_folders: str = "models,textures,exports",
) -> str:
    project = get_project(name)
    report = AssetReport(project_name=project["name"])
    threshold = max(1, int(large_file_mb)) * 1024 * 1024
    entries = _walk_project(project)

    for e in entries:
        if e["is_dir"]:
            continue
        p = Path(e["path"])
        suffix = p.suffix.lower()
        is_model = suffix in _MODEL_EXTS
        is_texture = suffix in _TEXTURE_EXTS
        if is_model:
            report.model_files.append((e["path"], e["size"]))
        if is_texture:
            report.texture_files.append((e["path"], e["size"]))
        if (is_model or is_texture) and not _NAMING_PATTERN.fullmatch(p.stem):
            report.naming_issues.append(e["path"])
        if (is_model or is_texture) and e["size"] > threshold:
            report.large_files.append((e["path"], e["size"]))

    root = Path(project["path"])
    try:
        top_level_dirs = {p.name.casefold() for p in root.iterdir() if p.is_dir()}
    except OSError:
        top_level_dirs = set()
    recommended = [x.strip() for x in recommended_folders.split(",") if x.strip()]
    report.missing_recommended_folders = sorted(f for f in recommended if f.casefold() not in top_level_dirs)

    def human_size(num_bytes: int) -> str:
        size = float(num_bytes)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    lines = [
        f"3D asset scan for '{report.project_name}':",
        f"{len(report.model_files)} model files, {len(report.texture_files)} texture files.",
    ]
    if report.model_files:
        preview = ", ".join(path for path, _ in report.model_files[:15])
        more = len(report.model_files) - 15
        lines.append("Models: " + preview + (f" (+{more} more)" if more > 0 else ""))
    if report.texture_files:
        preview = ", ".join(path for path, _ in report.texture_files[:15])
        more = len(report.texture_files) - 15
        lines.append("Textures: " + preview + (f" (+{more} more)" if more > 0 else ""))
    if report.naming_issues:
        lines.append(f"Naming issues: {len(report.naming_issues)} — " + ", ".join(report.naming_issues[:20]))
    if report.large_files:
        lines.append("Large files: " + ", ".join(f"{p} ({human_size(s)})" for p, s in report.large_files[:10]))
    if report.missing_recommended_folders:
        lines.append("Missing recommended folders: " + ", ".join(report.missing_recommended_folders))
    if not report.model_files and not report.texture_files:
        lines.append("No files matched the configured model/texture extensions.")
    lines.append("This scan is metadata-only: it does not render, validate, or modify 3D files.")
    return "\n".join(lines)
