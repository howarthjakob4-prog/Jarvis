"""Text-to-speech.

Engine "sapi" (default): Windows built-in voice via pyttsx3. Zero config,
no key, no network. This is why Jarvis speaks out of the box.

Engine "fish": Fish Audio cloud voice. Needs fish_api_key in config.
Audio comes back as WAV and plays through winsound (Windows stdlib),
so no extra audio player dependency is needed.

Engine "elevenlabs": ElevenLabs cloud voice. Needs elevenlabs_api_key in
config (config/local.yaml, gitignored — same pattern as the Ultron build).
Audio comes back as raw PCM, is wrapped into WAV in memory, and plays
through winsound. No key ever leaves the user's own PC config file.
"""
import io
import os
import tempfile
import wave

import requests

FISH_TTS_URL = "https://api.fish.audio/v1/tts"
ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
# Jarvis's ElevenLabs voice: "George" — a deep, calm British male, the classic
# Jarvis-assistant pick (used as the default voice by the Iron-Man-style
# Jarvis assistant at github.com/eldarttyy/jarvis-voice-assistant). To use a
# different voice, put any voice ID from your ElevenLabs voice library in
# elevenlabs_voice_id.
ELEVENLABS_DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb"


class TTSError(Exception):
    """TTS problems, always with a human-readable message."""


def _play_wav_bytes(data: bytes) -> None:
    """Play WAV bytes on Windows via winsound (stdlib, no extra deps)."""
    import sys

    if sys.platform != "win32":
        raise TTSError("Cloud-voice playback is only supported on Windows in this build.")
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
        _play_wav_bytes(data)

    def speak(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        self._play_wav_bytes(self._synthesize(text, fmt="wav"))


class ElevenLabsTTS(BaseTTS):
    """ElevenLabs cloud voice.

    The API key lives in config/local.yaml (gitignored) — never in the repo,
    never in a browser. Asks for raw PCM and wraps it into a WAV in memory
    so playback still goes through winsound with no extra dependencies.
    """

    name = "elevenlabs"

    def __init__(self, api_key="", voice_id="", model="eleven_multilingual_v2"):
        if not api_key:
            raise TTSError("ElevenLabs needs elevenlabs_api_key in config/local.yaml.")
        self.api_key = api_key
        self.voice_id = voice_id or ELEVENLABS_DEFAULT_VOICE
        self.model = model or "eleven_multilingual_v2"

    def _synthesize(self, text: str) -> bytes:
        url = ELEVENLABS_TTS_URL.format(voice_id=self.voice_id)
        try:
            resp = requests.post(
                url,
                params={"output_format": "pcm_16000"},
                json={"text": text, "model_id": self.model},
                headers={
                    "Content-Type": "application/json",
                    "xi-api-key": self.api_key,
                },
                timeout=120,
            )
        except requests.RequestException as exc:
            raise TTSError(f"ElevenLabs request failed: {exc}") from exc
        if resp.status_code != 200:
            raise TTSError(f"ElevenLabs HTTP {resp.status_code}: {resp.text[:200]}")
        return self._pcm_to_wav(resp.content)

    @staticmethod
    def _pcm_to_wav(pcm: bytes, rate: int = 16000) -> bytes:
        """Wrap 16-bit mono PCM bytes in a WAV container (stdlib only)."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            wav.writeframes(pcm)
        return buf.getvalue()

    def speak(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        _play_wav_bytes(self._synthesize(text))


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
    if engine == "elevenlabs":
        return ElevenLabsTTS(
            api_key=config.get("elevenlabs_api_key", ""),
            voice_id=config.get("elevenlabs_voice_id", ""),
            model=config.get("elevenlabs_model", "eleven_multilingual_v2"),
        )
    raise TTSError(f"Unknown tts_engine {engine!r}. Use 'sapi', 'fish', or 'elevenlabs'.")


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
