from loguru import logger
from jarvis.plugins.base import Plugin
from jarvis.models import ToolDefinition


class WebRemotePlugin(Plugin):
    """Tablet-only remote with owner control and read-only AIM demo access."""

    def __init__(self):
        super().__init__("web_remote")

    async def initialize(self) -> None:
        logger.info("Tablet remote ready (start it with start_tablet_remote)")

    async def shutdown(self) -> None:
        try:
            from jarvis.control.web_remote import get_web_remote_server
            get_web_remote_server().stop()
        except Exception:
            pass

    def get_tools(self):
        return [
            (
                ToolDefinition(
                    name="start_tablet_remote",
                    description=(
                        "Start the JARVIS tablet-only remote. Returns a private owner-control "
                        "pairing link and a separate read-only AIM demonstration link. "
                        "Phone access is disabled."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "port": {
                                "type": "integer",
                                "description": "Optional port (default 8765)",
                            }
                        },
                    },
                ),
                self.start_tablet_remote,
            ),
            (
                ToolDefinition(
                    name="start_web_remote",
                    description=(
                        "Compatibility alias for start_tablet_remote. The remote is tablet-only; "
                        "phone browser access is rejected."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "port": {"type": "integer", "description": "Optional port (default 8765)"}
                        },
                    },
                ),
                self.start_tablet_remote,
            ),
            (
                ToolDefinition(
                    name="stop_tablet_remote",
                    description="Stop tablet access and invalidate the current pairing links.",
                    parameters={"type": "object", "properties": {}},
                ),
                self.stop_tablet_remote,
            ),
            (
                ToolDefinition(
                    name="tablet_remote_status",
                    description="Report whether tablet access is running and show fresh pairing links.",
                    parameters={"type": "object", "properties": {}},
                ),
                self.tablet_remote_status,
            ),
        ]

    async def start_tablet_remote(self, port: int = 8765) -> str:
        from jarvis.control.web_remote import get_web_remote_server
        server = get_web_remote_server()
        if port and int(port) != server.port and not server.is_running():
            server.port = int(port)
        if server.start():
            return (
                "JARVIS tablet access is live.\n\n"
                "OWNER TABLET — full JARVIS command access:\n"
                f"  {server.owner_url()}\n\n"
                "AIM DEMONSTRATION TABLET — read-only viewing:\n"
                f"  {server.viewer_url()}\n\n"
                "Phone browser access is disabled. Keep the owner link private. "
                "Stopping tablet access invalidates both links."
            )
        return "Could not start tablet access (runtime not ready or port in use)."

    async def stop_tablet_remote(self, **_) -> str:
        from jarvis.control.web_remote import get_web_remote_server
        get_web_remote_server().stop()
        return "Tablet access stopped. The old pairing links are no longer valid."

    async def tablet_remote_status(self, **_) -> str:
        from jarvis.control.web_remote import get_web_remote_server
        server = get_web_remote_server()
        if server.is_running():
            return (
                "Tablet access is running.\n"
                f"Owner: {server.owner_url()}\n"
                f"AIM read-only: {server.viewer_url()}"
            )
        return "Tablet access is not running. Start it with start_tablet_remote."
