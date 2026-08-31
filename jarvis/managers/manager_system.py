"""JARVIS multi-manager coordinator.

JARVIS remains the single user-facing coordinator. Requests are routed to a
specialized manager with an explicit capability and permission boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

ManagerHandler = Callable[["ManagerRequest"], Awaitable[Any]]


@dataclass(slots=True)
class ManagerRequest:
    text: str
    action: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class JarvisManager:
    name: str
    description: str
    keywords: tuple[str, ...]
    permissions: frozenset[str]
    handler: ManagerHandler | None = None

    def score(self, request: ManagerRequest) -> int:
        haystack = f"{request.action} {request.text}".lower()
        return sum(1 for keyword in self.keywords if keyword in haystack)

    async def handle(self, request: ManagerRequest) -> Any:
        if self.handler is None:
            return {
                "manager": self.name,
                "status": "routed",
                "message": f"{self.name} accepted the request.",
                "action": request.action,
            }
        return await self.handler(request)


class ManagerSystem:
    """Routes commands from JARVIS to isolated specialist managers."""

    def __init__(self) -> None:
        self._managers: dict[str, JarvisManager] = {}
        self._register_defaults()

    def register(self, manager: JarvisManager) -> None:
        self._managers[manager.name] = manager

    def get(self, name: str) -> JarvisManager | None:
        return self._managers.get(name)

    def list_managers(self) -> list[dict[str, Any]]:
        return [
            {
                "name": m.name,
                "description": m.description,
                "permissions": sorted(m.permissions),
            }
            for m in self._managers.values()
        ]

    def route(self, request: ManagerRequest) -> JarvisManager:
        ranked = sorted(
            self._managers.values(),
            key=lambda manager: manager.score(request),
            reverse=True,
        )
        if ranked and ranked[0].score(request) > 0:
            return ranked[0]
        return self._managers["system"]

    async def dispatch(self, request: ManagerRequest) -> Any:
        manager = self.route(request)
        return await manager.handle(request)

    def _register_defaults(self) -> None:
        self.register(JarvisManager(
            name="system",
            description="Windows, applications, desktop automation and system operations.",
            keywords=("windows", "window", "computer", "desktop", "app", "system", "screen", "keyboard", "mouse"),
            permissions=frozenset({"system.read", "desktop.control"}),
        ))
        self.register(JarvisManager(
            name="files",
            description="Works only with files and folders explicitly approved for JARVIS.",
            keywords=("file", "folder", "document", "save", "open", "move", "export"),
            permissions=frozenset({"files.approved.read", "files.approved.write"}),
        ))
        self.register(JarvisManager(
            name="3d",
            description="Coordinates Blender and approved 3D-design workflows.",
            keywords=("3d", "blender", "model", "mesh", "render", "rig", "animation"),
            permissions=frozenset({"blender.control", "files.approved.read", "files.approved.write"}),
        ))
        self.register(JarvisManager(
            name="projects",
            description="Coordinates project plans, tasks, assets and project-specific context.",
            keywords=("project", "task", "milestone", "asset", "nova frontier", "plan"),
            permissions=frozenset({"projects.read", "projects.write"}),
        ))
        self.register(JarvisManager(
            name="communications",
            description="Coordinates approved communication services and drafts.",
            keywords=("email", "message", "discord", "gmail", "calendar", "reply", "send"),
            permissions=frozenset({"communications.read", "communications.write"}),
        ))
        self.register(JarvisManager(
            name="security",
            description="Owns permission checks, approvals and access boundaries.",
            keywords=("security", "permission", "approve", "access", "allowed", "block", "authorize"),
            permissions=frozenset({"security.policy", "security.audit"}),
        ))
        self.register(JarvisManager(
            name="memory",
            description="Coordinates JARVIS conversation and project memory.",
            keywords=("remember", "memory", "history", "conversation", "recall"),
            permissions=frozenset({"memory.read", "memory.write"}),
        ))
