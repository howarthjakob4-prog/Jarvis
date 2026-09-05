from loguru import logger
from jarvis.plugins.base import Plugin
from jarvis.models import ToolDefinition


DEFAULT_PHONE_PORT = 8766
DEFAULT_TABLET_PORT = 8767


class WebRemotePlugin(Plugin):
    """Owner phone alerts plus tablet remote access over the local network."""

    def __init__(self):
        super().__init__("web_remote")
        self._phone_gateway = None

    async def initialize(self) -> None:
        """Start the owner phone gateway and tablet remote automatically.

        The phone gateway owns port 8766 so JARVIS can surface alerts/approval
        requests on the owner's phone. Tablet command access uses 8767 to avoid
        fighting the phone gateway for the same socket.
        """
        try:
            from jarvis.connectors.local_phone_gateway import start_local_phone_gateway
            self._phone_gateway = start_local_phone_gateway(DEFAULT_PHONE_PORT)
            logger.info("JARVIS phone notification gateway started automatically on port {}", DEFAULT_PHONE_PORT)
        except OSError as exc:
            logger.warning(f"JARVIS phone gateway could not bind port {DEFAULT_PHONE_PORT}: {exc}")
        except Exception as exc:
            logger.warning(f"JARVIS phone gateway auto-start failed: {exc}")

        try:
            from jarvis.control.web_remote import get_web_remote_server
            server = get_web_remote_server()
            if not server.is_running():
                server.port = DEFAULT_TABLET_PORT
            if server.start():
                logger.info("JARVIS tablet remote started automatically at {}", server.url())
            else:
                logger.warning("JARVIS tablet remote could not start automatically on port {}", server.port)
        except Exception as exc:
            logger.warning(f"JARVIS tablet remote auto-start failed: {exc}")

    async def shutdown(self) -> None:
        try:
            from jarvis.control.web_remote import get_web_remote_server
            get_web_remote_server().stop()
        except Exception:
            pass
        try:
            if self._phone_gateway is not None:
                self._phone_gateway.shutdown()
                self._phone_gateway.server_close()
                self._phone_gateway = None
        except Exception:
            pass

    def _phone_pair_tool(self, name: str, description: str):
        return (
            ToolDefinition(
                name=name,
                description=description,
                parameters={"type": "object", "properties": {}},
            ),
            self.start_phone_remote,
        )

    def get_tools(self):
        return [
            self._phone_pair_tool(
                "start_phone_remote",
                "Start or confirm the private JARVIS owner-phone notification gateway and return the phone pairing URL.",
            ),
            self._phone_pair_tool(
                "link_my_phone",
                "Use when the owner says 'link my phone' or asks JARVIS to link the phone. Starts phone pairing and returns the private pairing URL.",
            ),
            self._phone_pair_tool(
                "connect_my_phone",
                "Use when the owner says 'connect my phone' or asks JARVIS to connect the phone. Starts phone pairing and returns the private pairing URL.",
            ),
            self._phone_pair_tool(
                "pair_my_phone",
                "Use when the owner says 'pair my phone' or asks JARVIS to pair the phone. Starts phone pairing and returns the private pairing URL.",
            ),
            (
                ToolDefinition(
                    name="phone_remote_status",
                    description="Show the private owner-phone notification/approval URL and gateway status.",
                    parameters={"type": "object", "properties": {}},
                ),
                self.phone_remote_status,
            ),
            (
                ToolDefinition(
                    name="start_tablet_remote",
                    description=(
                        "Start the JARVIS tablet remote. Returns a private owner-control pairing link "
                        "and a separate read-only AIM demonstration link."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "port": {"type": "integer", "description": "Optional port (default 8767)"}
                        },
                    },
                ),
                self.start_tablet_remote,
            ),
            (
                ToolDefinition(
                    name="start_web_remote",
                    description="Compatibility alias for start_tablet_remote.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "port": {"type": "integer", "description": "Optional port (default 8767)"}
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

    async def start_phone_remote(self, **_) -> str:
        from jarvis.connectors.local_phone_gateway import get_access_url, start_local_phone_gateway
        try:
            if self._phone_gateway is None:
                self._phone_gateway = start_local_phone_gateway(DEFAULT_PHONE_PORT)
            return (
                "JARVIS phone notifications are live.\n"
                f"Owner phone: {get_access_url()}\n"
                "Open that private link on the phone, tap Enable ringing, and allow browser notifications. "
                "Keep the link private."
            )
        except Exception as exc:
            return f"JARVIS phone notification gateway could not start: {exc}"

    async def phone_remote_status(self, **_) -> str:
        from jarvis.connectors.local_phone_gateway import get_access_url
        running = self._phone_gateway is not None
        return (
            f"JARVIS phone gateway is {'running' if running else 'not confirmed running'}.\n"
            f"Owner phone: {get_access_url()}"
        )

    async def start_tablet_remote(self, port: int = DEFAULT_TABLET_PORT) -> str:
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
                "Keep the owner link private. Stopping tablet access invalidates both links."
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
        return "Tablet access is not running. It should auto-start with JARVIS; you can also run start_tablet_remote."
