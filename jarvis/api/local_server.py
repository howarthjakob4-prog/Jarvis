"""JARVIS local HTTP API — lets Sidefoid and local clients drive JARVIS.

Endpoints
---------
POST /chat          {"text": "show todo panel"}
                    Sends a message as if the user typed it in the chat.

POST /tool          {"tool": "show_panel", "args": {"panel": "todo"}}
                    Directly invokes a registered tool by name and returns result.

GET  /tools         List all registered tool names.
GET  /status        Runtime status (ready, provider, etc.).
GET  /sidefoid      Integration metadata for the Sidefoid dashboard.

The server binds only to 127.0.0.1. Browser access is restricted to localhost by
default. Additional trusted Sidefoid origins may be allowed with the
JARVIS_ALLOWED_ORIGINS environment variable, for example:

    JARVIS_ALLOWED_ORIGINS=https://example.sidefoid.com,https://sidefoid.pages.dev
"""

import json
import os
from typing import TYPE_CHECKING

from aiohttp import web
from loguru import logger

if TYPE_CHECKING:
    from jarvis.app import JarvisRuntime


_DEFAULT_PORT = 8765
_DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost",
    "https://localhost",
    "http://127.0.0.1",
    "https://127.0.0.1",
)


class LocalAPIServer:
    """Thin aiohttp wrapper that exposes the JarvisRuntime over HTTP."""

    def __init__(self, runtime: "JarvisRuntime", port: int = _DEFAULT_PORT) -> None:
        self._runtime = runtime
        self._port = port
        self._runner: web.AppRunner | None = None
        configured = [
            value.strip().rstrip("/")
            for value in os.getenv("JARVIS_ALLOWED_ORIGINS", "").split(",")
            if value.strip()
        ]
        self._allowed_origins = (*_DEFAULT_ALLOWED_ORIGINS, *configured)

    async def start(self) -> None:
        app = web.Application(middlewares=[self._cors_middleware])
        app.router.add_get("/status", self._handle_status)
        app.router.add_get("/tools", self._handle_tools)
        app.router.add_get("/sidefoid", self._handle_sidefoid)
        app.router.add_post("/chat", self._handle_chat)
        app.router.add_post("/tool", self._handle_tool)
        app.router.add_options("/{tail:.*}", self._handle_options)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", self._port)
        await site.start()
        logger.info(f"JARVIS local API listening on http://127.0.0.1:{self._port}")

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()
            logger.info("JARVIS local API stopped")

    def _origin_is_allowed(self, origin: str) -> bool:
        if not origin:
            return True
        normalized = origin.rstrip("/")
        return any(
            normalized == allowed or normalized.startswith(f"{allowed}:")
            for allowed in self._allowed_origins
        )

    def _check_origin(self, request: web.Request) -> "web.Response | None":
        """Reject browser requests from origins that the owner has not trusted."""
        origin = request.headers.get("Origin", "")
        if not self._origin_is_allowed(origin):
            return _error("Cross-origin requests not allowed", 403)
        return None

    @web.middleware
    async def _cors_middleware(self, request: web.Request, handler):
        blocked = self._check_origin(request)
        if blocked:
            return blocked

        response = await handler(request)
        origin = request.headers.get("Origin", "")
        if origin and self._origin_is_allowed(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Allow-Private-Network"] = "true"
        return response

    async def _handle_options(self, request: web.Request) -> web.Response:
        return web.Response(status=204)

    async def _handle_status(self, request: web.Request) -> web.Response:
        rt = self._runtime
        providers = []
        if rt.provider_router:
            providers = list(rt.provider_router._providers.keys())
        return _json({
            "ready": rt.ready,
            "providers": providers,
            "port": self._port,
            "integration": "sidefoid-jarvis-v1",
        })

    async def _handle_tools(self, request: web.Request) -> web.Response:
        rt = self._runtime
        if not rt.tool_registry:
            return _json({"tools": []})
        names = [d["name"] for d in rt.tool_registry.get_definitions()]
        return _json({"tools": names})

    async def _handle_sidefoid(self, request: web.Request) -> web.Response:
        rt = self._runtime
        tools = []
        if rt.tool_registry:
            tools = [d["name"] for d in rt.tool_registry.get_definitions()]
        return _json({
            "name": "Sidefoid + JARVIS",
            "bridgeVersion": 1,
            "ready": rt.ready,
            "capabilities": {
                "chat": True,
                "tools": bool(rt.tool_registry),
                "voice": True,
                "computerControl": True,
            },
            "toolCount": len(tools),
        })

    async def _handle_chat(self, request: web.Request) -> web.Response:
        """Send a text message as if the user typed it."""
        try:
            body = await request.json()
        except Exception:
            return _error("Body must be JSON with a 'text' field", 400)

        text = body.get("text", "").strip()
        if not text:
            return _error("'text' is required and must not be empty", 400)

        if not self._runtime.ready:
            return _error("Runtime not ready yet — try again in a moment", 503)

        self._runtime.send_text(text)
        return _json({"ok": True, "message": f"Message queued: {text!r}"})

    async def _handle_tool(self, request: web.Request) -> web.Response:
        """Directly call a registered tool by name."""
        try:
            body = await request.json()
        except Exception:
            return _error("Body must be JSON with 'tool' and optional 'args'", 400)

        tool_name = body.get("tool", "").strip()
        args: dict = body.get("args", {})

        if not tool_name:
            return _error("'tool' is required", 400)

        rt = self._runtime
        if not rt.ready:
            return _error("Runtime not ready yet — try again in a moment", 503)

        if not rt.tool_registry:
            return _error("Tool registry unavailable", 503)

        known = [d["name"] for d in rt.tool_registry.get_definitions()]
        if tool_name not in known:
            return _error(f"Unknown tool {tool_name!r}. Available: {known}", 404)

        try:
            result = await rt.tool_registry.execute(tool_name, args)
        except TypeError as exc:
            return _error(f"Bad args for {tool_name!r}: {exc}", 400)
        except Exception as exc:
            logger.exception(f"Tool {tool_name!r} raised an error")
            return _error(f"Tool error: {exc}", 500)

        return _json({"ok": True, "tool": tool_name, "result": result})


def _json(data: dict, status: int = 200) -> web.Response:
    return web.Response(
        text=json.dumps(data, ensure_ascii=False, default=str),
        content_type="application/json",
        status=status,
    )


def _error(message: str, status: int = 400) -> web.Response:
    return _json({"ok": False, "error": message}, status)
