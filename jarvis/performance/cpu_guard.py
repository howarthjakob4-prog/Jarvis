"""Lightweight CPU guard for JARVIS on PCs without CUDA acceleration."""

from __future__ import annotations

import asyncio
import os

from loguru import logger


def install_cpu_guard() -> None:
    """Reduce runaway CPU use and force a lightweight Whisper model on CPU-only PCs."""
    os.environ.setdefault("OMP_NUM_THREADS", "2")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
    os.environ.setdefault("MKL_NUM_THREADS", "2")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "2")

    try:
        import torch
        torch.set_num_threads(2)
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            pass
    except Exception:
        pass

    try:
        from jarvis.voice import stt as stt_module

        if getattr(stt_module.STT, "_jarvis_cpu_guard_installed", False):
            return

        original_create_model = stt_module.STT._create_model

        async def guarded_create_model(self, device: str, compute_type: str):
            # CPU-only machines were spending too much time on medium/base Whisper.
            # Keep voice responsive by using tiny.en and just two CPU threads.
            if device == "cpu":
                if str(getattr(self, "model_name", "")).lower() not in {"tiny", "tiny.en"}:
                    logger.warning(
                        f"CPU guard: switching Whisper {self.model_name} -> tiny.en for responsiveness"
                    )
                    self.model_name = "tiny.en"

                from faster_whisper import WhisperModel
                return await asyncio.to_thread(
                    WhisperModel,
                    self.model_name,
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=2,
                )

            return await original_create_model(self, device, compute_type)

        stt_module.STT._create_model = guarded_create_model
        stt_module.STT._jarvis_cpu_guard_installed = True
        logger.info("JARVIS CPU guard enabled")
    except Exception as exc:
        logger.warning(f"JARVIS CPU guard could not patch STT: {exc}")
