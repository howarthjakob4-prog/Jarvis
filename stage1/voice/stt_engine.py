"""Offline STT via faster-whisper."""
from __future__ import annotations
import numpy as np
from core.errors import DeviceError, ModelLoadError, error_bus
SAMPLE_RATE = 16000

class SpeechToText:
    def __init__(self, model_size: str = "base.en", device_index: int | None = None):
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise ModelLoadError(module="stt_engine", message=f"faster-whisper is not installed ({e}). Run: pip install faster-whisper", recoverable=False)
        try:
            self._model = WhisperModel(model_size, device="cpu", compute_type="int8")
        except Exception as e:
            raise ModelLoadError(module="stt_engine", message=f"Could not load Whisper model '{model_size}': {e}. First run needs internet to download it once; after that it's offline.", recoverable=False)
        self._device_index = device_index

    def record_and_transcribe(self, duration_seconds: float = 5.0) -> str:
        try:
            import sounddevice as sd
        except ImportError as e:
            raise DeviceError(module="stt_engine", message=f"sounddevice is not installed ({e}). Run: pip install sounddevice", recoverable=False)
        try:
            audio = sd.rec(int(duration_seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="float32", device=self._device_index)
            sd.wait()
        except Exception as e:
            err = DeviceError(module="stt_engine", message=f"Could not record from the microphone: {e}. Check Settings > Voice for the correct input device.")
            error_bus.report(err); raise err
        audio = np.squeeze(audio)
        try:
            segments, _info = self._model.transcribe(audio, language="en")
            text = " ".join(seg.text.strip() for seg in segments).strip()
        except Exception as e:
            err = ModelLoadError(module="stt_engine", message=f"Transcription failed: {e}")
            error_bus.report(err); raise err
        if not text:
            error_bus.report(DeviceError(module="stt_engine", message="No speech was recognized in that clip. Try again, closer to the mic."))
        return text

    @staticmethod
    def list_input_devices() -> list[dict]:
        try:
            import sounddevice as sd
        except ImportError:
            return []
        devices = sd.query_devices()
        return [{"index": i, "name": d["name"]} for i, d in enumerate(devices) if d["max_input_channels"] > 0]
