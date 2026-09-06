"""
Offline wake-word listening via openWakeWord.

The microphone stream is intentionally closed before `on_detected()` is
called. This matters on Windows: speech-to-text may need to open the same
microphone immediately after the wake phrase, and two live input streams can
otherwise conflict on some devices/drivers.
"""
from __future__ import annotations

import threading
from typing import Callable

import numpy as np

from core.errors import ModelLoadError, error_bus

FRAME_SAMPLES = 1280


class WakeWordListener:
    def __init__(self, model_name: str = "hey_jarvis", sensitivity: float = 0.5,
                 device_index: int | None = None):
        try:
            from openwakeword.model import Model
        except ImportError as e:
            raise ModelLoadError(module="wake_word", message=f"openwakeword is not installed ({e}). Run: pip install openwakeword. Wake word is disabled; use the manual talk button instead.", recoverable=False)
        try:
            self._model = Model(wakeword_models=[model_name])
        except Exception as e:
            raise ModelLoadError(module="wake_word", message=f"Could not load wake-word model '{model_name}': {e}. Wake word is disabled; use the manual talk button instead.", recoverable=False)
        self._model_name = model_name
        self._sensitivity = sensitivity
        self._device_index = device_index
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self, on_detected: Callable[[], None]) -> None:
        if self._running:
            return
        try:
            import sounddevice as sd
        except ImportError as e:
            raise ModelLoadError(module="wake_word", message=f"sounddevice is not installed ({e}).", recoverable=False)
        self._running = True

        def _loop():
            detected = False
            try:
                with sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=FRAME_SAMPLES, device=self._device_index) as stream:
                    while self._running:
                        frame, _ = stream.read(FRAME_SAMPLES)
                        frame = np.squeeze(frame)
                        scores = self._model.predict(frame)
                        if scores.get(self._model_name, 0.0) > self._sensitivity:
                            detected = True
                            self._running = False
                            break
            except Exception as e:
                error_bus.report(ModelLoadError(module="wake_word", message=f"Wake-word listening stopped unexpectedly: {e}. Use the manual talk button until this is resolved."))
                self._running = False
                return
            if detected:
                try:
                    on_detected()
                except Exception as e:
                    error_bus.report(ModelLoadError(module="wake_word", message=f"Wake-word callback failed: {e}"))

        self._thread = threading.Thread(target=_loop, daemon=True, name="jarvis-wake-word")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)
