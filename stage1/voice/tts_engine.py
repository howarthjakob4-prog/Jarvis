"""
TTS behind a small interface so the "natural voice" upgrade (Piper) can be
swapped in later without touching any calling code. pyttsx3 is the default
because it has no extra setup on Windows (uses SAPI5 voices already on the
system) and fails predictably if something's wrong, rather than needing a
model download to even test.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from core.errors import ModelLoadError, error_bus


class TTSBackend(ABC):
    @abstractmethod
    def speak(self, text: str) -> None:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...

    @abstractmethod
    def list_voices(self) -> list[dict[str, str]]:
        ...

    @abstractmethod
    def set_voice(self, voice_id: str) -> None:
        ...

    @abstractmethod
    def set_rate(self, rate: int) -> None:
        ...


class Pyttsx3TTS(TTSBackend):
    def __init__(self, rate: int = 185, voice_id: str | None = None):
        try:
            import pyttsx3
        except ImportError as e:
            raise ModelLoadError(module="tts_engine", message=f"pyttsx3 is not installed ({e}). Run: pip install pyttsx3", recoverable=False)
        try:
            self._engine = pyttsx3.init()
        except Exception as e:
            raise ModelLoadError(module="tts_engine", message=f"Could not initialize the system speech engine (SAPI5): {e}. Voice output will not work until this is resolved.", recoverable=False)
        self._engine.setProperty("rate", rate)
        if voice_id:
            self.set_voice(voice_id)

    def speak(self, text: str) -> None:
        if not text.strip():
            return
        try:
            self._engine.say(text)
            self._engine.runAndWait()
        except Exception as e:
            error_bus.report(ModelLoadError(module="tts_engine", message=f"Speech playback failed: {e}"))

    def stop(self) -> None:
        try:
            self._engine.stop()
        except Exception:
            pass

    def list_voices(self) -> list[dict[str, str]]:
        return [{"id": v.id, "name": v.name} for v in self._engine.getProperty("voices")]

    def set_voice(self, voice_id: str) -> None:
        self._engine.setProperty("voice", voice_id)

    def set_rate(self, rate: int) -> None:
        self._engine.setProperty("rate", rate)


class PiperTTS(TTSBackend):
    def __init__(self, model_path: str, rate: int = 185):
        import shutil
        self._piper_binary = shutil.which("piper")
        if not self._piper_binary:
            raise ModelLoadError(module="tts_engine", message="Piper backend selected, but the 'piper' executable was not found on PATH. Install Piper and/or switch voice.tts_backend back to 'pyttsx3' in Settings.", recoverable=False)
        from pathlib import Path
        if not Path(model_path).exists():
            raise ModelLoadError(module="tts_engine", message=f"Piper voice model not found at '{model_path}'. Download a .onnx voice model and set voice.piper_model_path.", recoverable=False)
        self._model_path = model_path
        self._rate = rate

    def speak(self, text: str) -> None:
        import subprocess, tempfile, os
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                wav_path = f.name
            subprocess.run([self._piper_binary, "--model", self._model_path, "--output_file", wav_path], input=text.encode("utf-8"), check=True)
            import winsound
            winsound.PlaySound(wav_path, winsound.SND_FILENAME)
            os.remove(wav_path)
        except Exception as e:
            error_bus.report(ModelLoadError(module="tts_engine", message=f"Piper playback failed: {e}"))

    def stop(self) -> None:
        pass

    def list_voices(self) -> list[dict[str, str]]:
        return [{"id": self._model_path, "name": "Piper (configured model)"}]

    def set_voice(self, voice_id: str) -> None:
        self._model_path = voice_id

    def set_rate(self, rate: int) -> None:
        self._rate = rate


def build_tts_backend(backend_name: str, rate: int, voice_id: str | None, piper_model_path: str | None) -> TTSBackend:
    if backend_name == "piper":
        if not piper_model_path:
            raise ModelLoadError(module="tts_engine", message="voice.tts_backend is 'piper' but voice.piper_model_path is not set.", recoverable=False)
        return PiperTTS(piper_model_path, rate=rate)
    return Pyttsx3TTS(rate=rate, voice_id=voice_id)
