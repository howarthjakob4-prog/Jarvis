import asyncio
import json
import os
import shutil
from pathlib import Path

from loguru import logger

from jarvis.models import ToolDefinition
from jarvis.plugins.base import Plugin


class ClaudeCodeBuildPlugin(Plugin):
    """Give JARVIS a local 'hands' tool backed by the logged-in Claude Code CLI.

    The normal JARVIS voice/chat layer decides when to call this tool. The tool
    then starts a real Claude Code job in a local project directory and returns
    Claude's final result to JARVIS so it can announce completion aloud.
    """

    def __init__(self):
        super().__init__("claude_code_build")

    async def initialize(self) -> None:
        if shutil.which("claude"):
            logger.info("ClaudeCodeBuildPlugin ready — Claude CLI detected")
        else:
            logger.warning("ClaudeCodeBuildPlugin loaded, but Claude CLI is not installed/on PATH")

    async def shutdown(self) -> None:
        pass

    def get_tools(self):
        return [
            (
                ToolDefinition(
                    name="claude_code_build",
                    description=(
                        "Start a real local Claude Code coding/build job when the user explicitly asks "
                        "JARVIS to build, create, edit, fix, or implement code in a project. Uses the "
                        "user's locally installed and logged-in Claude Code CLI; no Anthropic API key "
                        "is required by this tool. By default Claude may read/write/edit project files. "
                        "Set allow_commands=true only when the user's request explicitly requires running "
                        "build, test, install, or command-line steps."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "The coding/build request to give Claude Code.",
                            },
                            "project_path": {
                                "type": "string",
                                "description": (
                                    "Local project folder. Leave empty to use the current working directory."
                                ),
                            },
                            "allow_commands": {
                                "type": "boolean",
                                "description": (
                                    "Allow Claude Code to use Bash in addition to Read/Write/Edit. "
                                    "Use only when the user explicitly requested command/build/test/install work."
                                ),
                                "default": False,
                            },
                        },
                        "required": ["task"],
                    },
                ),
                self.run_build,
            ),
            (
                ToolDefinition(
                    name="claude_code_status",
                    description="Check whether Claude Code is installed and available to JARVIS.",
                    parameters={"type": "object", "properties": {}},
                ),
                self.status,
            ),
        ]

    async def status(self, **_) -> str:
        cli = shutil.which("claude")
        if not cli:
            return "Claude Code is not installed or is not on PATH yet."
        try:
            proc = await asyncio.create_subprocess_exec(
                cli,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
            if proc.returncode == 0:
                version = stdout.decode(errors="replace").strip()
                return f"Claude Code is available. {version}" if version else "Claude Code is available."
            err = stderr.decode(errors="replace").strip()
            return f"Claude Code was found but did not start correctly: {err or 'unknown error'}"
        except Exception as exc:
            return f"Claude Code check failed: {exc}"

    async def run_build(
        self,
        task: str,
        project_path: str = "",
        allow_commands: bool = False,
        **_,
    ) -> str:
        task = (task or "").strip()
        if not task:
            return "No coding task was provided."

        cli = shutil.which("claude")
        if not cli:
            return (
                "Claude Code is not installed or is not on PATH. Install Claude Code, log in, "
                "then restart JARVIS."
            )

        cwd = Path(project_path).expanduser() if project_path else Path.cwd()
        try:
            cwd = cwd.resolve()
        except Exception:
            return "I could not resolve that project folder."
        if not cwd.exists() or not cwd.is_dir():
            return f"Project folder does not exist: {cwd}"

        allowed_tools = ["Read", "Write", "Edit"]
        if allow_commands:
            allowed_tools.append("Bash")

        args = [
            cli,
            "-p",
            "--output-format",
            "json",
            "--allowedTools",
            *allowed_tools,
            "--",
            task,
        ]

        logger.info(
            "Starting Claude Code job in {} with tools {}",
            cwd,
            ", ".join(allowed_tools),
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ.copy(),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=900)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return "The Claude Code job timed out after fifteen minutes."
        except Exception as exc:
            return f"Claude Code could not start: {exc}"

        out = stdout.decode(errors="replace").strip()
        err = stderr.decode(errors="replace").strip()
        if proc.returncode != 0:
            return f"Claude Code stopped with an error: {err[:800] or out[:800] or 'unknown error'}"

        try:
            data = json.loads(out)
            result = str(data.get("result") or "").strip()
        except Exception:
            result = out

        if not result:
            result = "Claude Code finished the requested job."

        # Keep the spoken/UI result useful without dumping a huge coding transcript.
        if len(result) > 1800:
            result = result[:1800].rstrip() + "…"
        return result
