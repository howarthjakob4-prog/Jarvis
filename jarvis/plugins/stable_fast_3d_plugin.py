import asyncio
import os
import shutil
import subprocess
from pathlib import Path

from loguru import logger

from jarvis.models import ToolDefinition
from jarvis.plugins.base import Plugin


class StableFast3DPlugin(Plugin):
    """Bridge JARVIS to a local Stable Fast 3D (SF3D) checkout.

    SF3D stays optional and external so the normal JARVIS patch remains small.
    JARVIS discovers SF3D through SF3D_HOME or the default per-user tools folder.
    """

    def __init__(self):
        super().__init__("stable_fast_3d")
        local_appdata = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        self.default_home = Path(local_appdata) / "JARVIS" / "tools" / "stable-fast-3d"

    async def initialize(self) -> None:
        if self._find_home() is not None:
            logger.info("StableFast3DPlugin ready")
        else:
            logger.info("StableFast3DPlugin loaded; SF3D runtime not installed yet")

    async def shutdown(self) -> None:
        pass

    def get_tools(self):
        return [
            (
                ToolDefinition(
                    name="sf3d_status",
                    description=(
                        "Check whether the optional local Stable Fast 3D image-to-3D runtime "
                        "is available to JARVIS and report its location."
                    ),
                    parameters={"type": "object", "properties": {}},
                ),
                self.status,
            ),
            (
                ToolDefinition(
                    name="sf3d_generate",
                    description=(
                        "Convert one local reference image into a textured GLB 3D model using "
                        "the locally installed Stable Fast 3D runtime. This uses no JARVIS "
                        "token/credit system."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "image_path": {
                                "type": "string",
                                "description": "Full path to the source PNG/JPG/WEBP image",
                            },
                            "output_dir": {
                                "type": "string",
                                "description": "Optional output folder for generated GLB files",
                            },
                            "force_cpu": {
                                "type": "boolean",
                                "description": "Force SF3D CPU mode for systems without a suitable GPU",
                            },
                        },
                        "required": ["image_path"],
                    },
                ),
                self.generate,
            ),
        ]

    def _find_home(self) -> Path | None:
        configured = os.environ.get("SF3D_HOME", "").strip()
        candidates = []
        if configured:
            candidates.append(Path(configured).expanduser())
        candidates.append(self.default_home)
        for candidate in candidates:
            if (candidate / "run.py").is_file():
                return candidate
        return None

    @staticmethod
    def _python_for(home: Path) -> str:
        candidates = [
            home / ".venv" / "Scripts" / "python.exe",
            home / "venv" / "Scripts" / "python.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        return shutil.which("python") or "python"

    async def status(self, **_) -> str:
        home = self._find_home()
        if home is None:
            return (
                "Stable Fast 3D bridge is installed in JARVIS, but the optional SF3D runtime "
                f"is not present. Expected it at {self.default_home} or at the folder set in SF3D_HOME. "
                "SF3D also requires its separately licensed/gated model access before real generation can run."
            )
        return f"Stable Fast 3D is available to JARVIS at {home}."

    async def generate(
        self,
        image_path: str,
        output_dir: str | None = None,
        force_cpu: bool = False,
        **_,
    ) -> str:
        home = self._find_home()
        if home is None:
            return await self.status()

        image = Path(image_path).expanduser().resolve()
        if not image.is_file():
            return f"SF3D could not find the source image: {image}"
        if image.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            return "SF3D source must be a PNG, JPG/JPEG, or WEBP image."

        if output_dir:
            output = Path(output_dir).expanduser().resolve()
        else:
            output = image.parent / f"{image.stem}_sf3d"
        output.mkdir(parents=True, exist_ok=True)

        cmd = [self._python_for(home), str(home / "run.py"), str(image), "--output-dir", str(output)]
        env = os.environ.copy()
        if force_cpu:
            env["SF3D_USE_CPU"] = "1"

        def _run():
            return subprocess.run(
                cmd,
                cwd=str(home),
                env=env,
                capture_output=True,
                text=True,
                timeout=1800,
            )

        try:
            result = await asyncio.to_thread(_run)
        except subprocess.TimeoutExpired:
            return "SF3D generation timed out after 30 minutes."
        except Exception as exc:
            return f"SF3D could not start: {exc}"

        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "unknown SF3D error").strip()
            return f"SF3D generation failed: {detail[-1800:]}"

        glbs = sorted(output.glob("*.glb"), key=lambda p: p.stat().st_mtime, reverse=True)
        if glbs:
            return f"SF3D generation complete. GLB: {glbs[0]}"
        return f"SF3D finished successfully. Output folder: {output}"
