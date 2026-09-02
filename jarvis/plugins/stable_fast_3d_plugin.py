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

    REPO_URL = "https://github.com/Stability-AI/stable-fast-3d.git"

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
                        "is available to JARVIS and report its location and readiness."
                    ),
                    parameters={"type": "object", "properties": {}},
                ),
                self.status,
            ),
            (
                ToolDefinition(
                    name="sf3d_install",
                    description=(
                        "Prepare the official Stable Fast 3D runtime for JARVIS in an isolated "
                        "per-user tools folder. This clones the official repository and installs "
                        "its Python requirements. It does not bundle SF3D into JARVIS and does "
                        "not bypass the model's separate license/access requirements."
                    ),
                    parameters={"type": "object", "properties": {}},
                ),
                self.install_runtime,
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
                f"is not present. Expected it at {self.default_home} or at the folder set in SF3D_HOME."
            )

        python_exe = self._python_for(home)
        venv_ready = (home / ".venv" / "Scripts" / "python.exe").is_file()
        torch_ready = False
        try:
            probe = await asyncio.to_thread(
                lambda: subprocess.run(
                    [python_exe, "-c", "import torch; print(torch.__version__)"],
                    cwd=str(home), capture_output=True, text=True, timeout=30,
                )
            )
            torch_ready = probe.returncode == 0
        except Exception:
            pass

        return (
            f"Stable Fast 3D checkout found at {home}. "
            f"Isolated environment: {'ready' if venv_ready else 'missing'}. "
            f"PyTorch: {'ready' if torch_ready else 'missing'}. "
            "Model access/login is still required by Stable Fast 3D before the first real generation."
        )

    async def install_runtime(self, **_) -> str:
        """Prepare SF3D without changing the normal JARVIS installation."""
        git = shutil.which("git")
        python = shutil.which("python") or shutil.which("py")
        if not git:
            return "SF3D setup cannot start because Git is not installed or not on PATH."
        if not python:
            return "SF3D setup cannot start because a normal Python installation was not found on PATH."

        home = self.default_home
        home.parent.mkdir(parents=True, exist_ok=True)

        def _run(cmd, cwd=None, timeout=1800):
            return subprocess.run(
                cmd, cwd=str(cwd) if cwd else None,
                capture_output=True, text=True, timeout=timeout,
            )

        try:
            if not (home / "run.py").is_file():
                if home.exists() and any(home.iterdir()):
                    return f"SF3D setup stopped because {home} already exists and is not empty."
                clone = await asyncio.to_thread(
                    _run, [git, "clone", "--depth", "1", self.REPO_URL, str(home)], None, 600
                )
                if clone.returncode != 0:
                    return f"SF3D clone failed: {(clone.stderr or clone.stdout)[-1600:]}"

            venv_python = home / ".venv" / "Scripts" / "python.exe"
            if not venv_python.is_file():
                make_venv = await asyncio.to_thread(
                    _run, [python, "-m", "venv", str(home / ".venv")], home, 300
                )
                if make_venv.returncode != 0:
                    return f"SF3D virtual environment creation failed: {(make_venv.stderr or make_venv.stdout)[-1600:]}"

            setup = await asyncio.to_thread(
                _run,
                [str(venv_python), "-m", "pip", "install", "-U", "pip", "setuptools==69.5.1", "wheel"],
                home,
                600,
            )
            if setup.returncode != 0:
                return f"SF3D Python setup failed: {(setup.stderr or setup.stdout)[-1600:]}"

            requirements = await asyncio.to_thread(
                _run,
                [str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"],
                home,
                1800,
            )
            if requirements.returncode != 0:
                return f"SF3D requirements failed to install: {(requirements.stderr or requirements.stdout)[-1600:]}"

        except subprocess.TimeoutExpired:
            return "SF3D setup timed out. No JARVIS profile or settings were changed."
        except Exception as exc:
            return f"SF3D setup could not complete: {exc}"

        return (
            f"Stable Fast 3D runtime prepared at {home}. "
            "Before generation, complete Stable Fast 3D's required model access/login and ensure "
            "a compatible PyTorch installation is available in the SF3D environment."
        )

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

        def _run_generation():
            return subprocess.run(
                cmd,
                cwd=str(home),
                env=env,
                capture_output=True,
                text=True,
                timeout=1800,
            )

        try:
            result = await asyncio.to_thread(_run_generation)
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
