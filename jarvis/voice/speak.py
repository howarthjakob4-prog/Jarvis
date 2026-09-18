"""Text-to-speech.

Engine "sapi" (default): Windows built-in voice via pyttsx3. Zero config,
no key, no network. This is why Jarvis speaks out of the box.

Engine "fish": Fish Audio cloud voice. Needs fish_api_key in config.
Audio comes back as WAV and plays through winsound (Windows stdlib),
so no extra audio player dependency is needed.
"""
import os
import tempfile

import requests

FISH_TTS_URL = "https://api.fish.audio/v1/tts"


class TTSError(Exception):
    """TTS problems, always with a human-readable message."""


class BaseTTS:
    name = "base"

    def speak(self, text: str) -> None:
        raise NotImplementedError


class SapiTTS(BaseTTS):
    """Windows SAPI voice via pyttsx3."""

    name = "sapi"

    def __init__(self):
        try:
            import pyttsx3
        except ImportError as exc:
            raise TTSError(
                "pyttsx3 is not installed. Run: pip install pyttsx3"
            ) from exc
        try:
            self._engine = pyttsx3.init()  # SAPI5 on Windows
        except Exception as exc:
            raise TTSError(f"Could not start the Windows voice engine: {exc}") from exc

    def speak(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        self._engine.say(text)
        self._engine.runAndWait()


class FishTTS(BaseTTS):
    """Fish Audio cloud voice. Downloads WAV, plays it with winsound."""

    name = "fish"

    def __init__(self, api_key="", reference_id="", model="s2.1-pro-free"):
        if not api_key:
            raise TTSError("Fish Audio needs fish_api_key in config/local.yaml.")
        self.api_key = api_key
        self.reference_id = reference_id
        self.model = model

    def _synthesize(self, text: str, fmt: str = "wav") -> bytes:
        body = {"text": text, "format": fmt, "latency": "normal"}
        if self.reference_id:
            body["reference_id"] = self.reference_id
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        if self.model:
            headers["model"] = self.model
        try:
            resp = requests.post(FISH_TTS_URL, json=body, headers=headers, timeout=120)
        except requests.RequestException as exc:
            raise TTSError(f"Fish Audio request failed: {exc}") from exc
        if resp.status_code != 200:
            raise TTSError(f"Fish Audio HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.content

    def _play_wav_bytes(self, data: bytes) -> None:
        import sys

        if sys.platform != "win32":
            raise TTSError("Fish Audio playback is only supported on Windows in this build.")
        import winsound

        fd, path = tempfile.mkstemp(suffix=".wav")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            winsound.PlaySound(path, winsound.SND_FILENAME)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def speak(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        self._play_wav_bytes(self._synthesize(text, fmt="wav"))


def create_engine(config) -> BaseTTS:
    """Pick the TTS engine from config. Raises TTSError on bad config."""
    engine = (config.get("tts_engine") or "sapi").lower()
    if engine == "sapi":
        return SapiTTS()
    if engine == "fish":
        return FishTTS(
            api_key=config.get("fish_api_key", ""),
            reference_id=config.get("fish_reference_id", ""),
            model=config.get("fish_model", "s2.1-pro-free"),
        )
    raise TTSError(f"Unknown tts_engine {engine!r}. Use 'sapi' or 'fish'.")


class Speaker:
    """Owns the TTS engine and the voice on/off toggle.

    Voice and typed input both speak through this one path.
    Never raises: check .ok / .last_error instead.
    """

    def __init__(self, config):
        self.enabled = bool(config.get("voice_enabled", True))
        self._engine = None
        self.error = None
        self.last_error = None
        try:
            self._engine = create_engine(config)
        except TTSError as exc:
            self.error = str(exc)

    @property
    def ok(self) -> bool:
        return self._engine is not None

    def speak(self, text: str) -> bool:
        """Speak text. Returns True if audio played."""
        self.last_error = None
        if not self.enabled or not (text or "").strip():
            return False
        if not self.ok:
            self.last_error = self.error or "no voice engine"
            return False
        try:
            self._engine.speak(text)
            return True
        except TTSError as exc:
            self.last_error = str(exc)
            return False
