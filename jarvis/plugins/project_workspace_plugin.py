from __future__ import annotations

from loguru import logger

from jarvis.models import ToolDefinition
from jarvis.plugins.base import Plugin
from jarvis.brain.project_workspace import (
    list_projects,
    open_project_file,
    recent_project_files,
    register_project,
    remove_project,
    scan_3d_assets,
    summarize_project,
)


class ProjectWorkspacePlugin(Plugin):
    """Stage 2 project assistance plus read-only 3D asset-folder scanning."""

    def __init__(self):
        super().__init__("project_workspace")

    async def initialize(self) -> None:
        logger.info("ProjectWorkspacePlugin ready")

    async def shutdown(self) -> None:
        pass

    def get_tools(self):
        return [
            (
                ToolDefinition(
                    name="register_project",
                    description=(
                        "Register or update a named project folder for Jarvis project assistance. "
                        "Use only when the user explicitly asks Jarvis to add/approve that project folder. "
                        "The folder must be under the user's home folder."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Friendly project name"},
                            "path": {"type": "string", "description": "Absolute or ~ project folder path"},
                            "description": {"type": "string", "description": "Optional description"},
                        },
                        "required": ["name", "path"],
                    },
                ),
                register_project,
            ),
            (
                ToolDefinition(
                    name="remove_project",
                    description="Remove a named folder from Jarvis's project registry/access list.",
                    parameters={
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                ),
                remove_project,
            ),
            (
                ToolDefinition(
                    name="list_projects",
                    description="List folders currently registered for Jarvis project assistance.",
                    parameters={"type": "object", "properties": {}},
                ),
                self._list_projects,
            ),
            (
                ToolDefinition(
                    name="summarize_project",
                    description=(
                        "Summarize a registered project with file/folder counts, top-level entries, "
                        "file-type breakdown, and recently modified files. Read-only."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "recent_count": {"type": "integer", "minimum": 1, "maximum": 20},
                        },
                        "required": ["name"],
                    },
                ),
                summarize_project,
            ),
            (
                ToolDefinition(
                    name="recent_project_files",
                    description="List the most recently modified files in a registered project. Read-only.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "count": {"type": "integer", "minimum": 1, "maximum": 30},
                        },
                        "required": ["name"],
                    },
                ),
                recent_project_files,
            ),
            (
                ToolDefinition(
                    name="open_project_file",
                    description=(
                        "Open one specific file inside a registered project with the Windows default app. "
                        "The path is containment-checked so it cannot escape the registered project."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "project_name": {"type": "string"},
                            "relative_path": {"type": "string"},
                        },
                        "required": ["project_name", "relative_path"],
                    },
                ),
                open_project_file,
            ),
            (
                ToolDefinition(
                    name="scan_project_3d_assets",
                    description=(
                        "Read-only 3D asset-folder scan for a registered project. Reports model and texture "
                        "files, naming issues, large files, and missing recommended folders. It inspects only "
                        "file metadata and folder structure; it does not render, validate, or modify 3D models."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Registered project name"},
                            "large_file_mb": {"type": "integer", "minimum": 1, "maximum": 100000},
                            "recommended_folders": {
                                "type": "string",
                                "description": "Comma-separated recommended top-level folders",
                            },
                        },
                        "required": ["name"],
                    },
                ),
                scan_3d_assets,
            ),
        ]

    async def _list_projects(self, **_) -> str:
        projects = list_projects()
        if not projects:
            return "No projects are registered yet."
        return "\n".join(
            f"{p['name']} -> {p['path']}" + (f" ({p['description']})" if p.get('description') else "")
            for p in projects
        )
