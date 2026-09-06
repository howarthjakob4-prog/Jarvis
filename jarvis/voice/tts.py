import asyncio
import io
import json
import os
import tempfile
import threading
import urllib.request
from pathlib import Path

from loguru import logger
import edge_tts
import soundfile as sf

try:
    import pyttsx3
    _PYTTSX3_AVAILABLE = True
except ImportError:
    _PYTTSX3_AVAILABLE = False

try:
    from kokoro_onnx import Kokoro
    _KOKORO_AVAILABLE = True
except ImportError:
    Kokoro = None
    _KOKORO_AVAILABLE = False


DEFAULT_JARVIS_VOICE = "kokoro:bm_george"
EDGE_FALLBACK_VOICE = "en-GB-RyanNeural"
DEFAULT_RATE = "+5%"
DEFAULT_PITCH = "+0Hz"

_KOKORO_MODEL_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files-v1.0/kokoro-v1.0.int8.onnx"
)
_KOKORO_VOICES_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files-v1.0/voices-v1.0.bin"
)
_KOKORO_MODEL_FILE = "kokoro-v1.0.int8.onnx"
_KOKORO_VOICES_FILE = "voices-v1.0.bin"
_KOKORO_LANG = "en-gb"
_LEGACY_DEFAULT_VOICES = {"en-GB-RyanNeural"}


class VoiceBox:
    """Built-in JARVIS voice box.

    JARVIS prefers the local Kokoro British male voice ``bm_george``. The
    quantized model is downloaded once into the user's JARVIS profile on first
    use. If Kokoro is unavailable, speech falls back to Microsoft Edge TTS and
    then to the local Windows speech engine.
    """

    def __init__(
        self,
        voice: str = DEFAULT_JARVIS_VOICE,
        rate: str = DEFAULT_RATE,
        pitch: str = DEFAULT_PITCH,
    ):
        self._settings_path = self._get_settings_path()
        saved = self._load_settings()
        saved_voice = saved.get("voice")

        # Migrate the old built-in Ryan voice to the new local George voice,
        # while preserving any genuinely custom voice selected by the user.
        if voice == DEFAULT_JARVIS_VOICE and saved_voice in _LEGACY_DEFAULT_VOICES:
            saved_voice = None

        self.voice = saved_voice or voice or DEFAULT_JARVIS_VOICE
        self.rate = saved.get("rate") or rate or DEFAULT_RATE
        self.pitch = saved.get("pitch") or pitch or DEFAULT_PITCH
        self.ready = True
        self.last_engine = "not-tested"
        self._kokoro = None
        self._kokoro_lock = threading.Lock()
        self._save_settings()
        logger.info(f"JARVIS voice box loaded: {self.voice}")

    @staticmethod
    def _get_profile_dir() -> Path:
        base = Path(os.getenv("APPDATA") or Path.home()) / "JARVIS"
        base.mkdir(parents=True, exist_ok=True)
        return base

    @classmethod
    def _get_settings_path(cls) -> Path:
        return cls._get_profile_dir() / "voice_box.json"

    @classmethod
    def _get_kokoro_dir(cls) -> Path:
        path = cls._get_profile_dir() / "voices" / "kokoro"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _load_settings(self) -> dict:
        try:
            if self._settings_path.exists():
                data = json.loads(self._settings_path.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.warning(f"Could not read JARVIS voice-box settings: {exc}")
        return {}

    def _save_settings(self) -> None:
        try:
            self._settings_path.write_text(
                json.dumps(
                    {
                        "voice": self.voice,
                        "rate": self.rate,
                        "pitch": self.pitch,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning(f"Could not save JARVIS voice-box settings: {exc}")

    def set_voice(self, voice: str, rate: str = "+0%", pitch: str = "+0Hz") -> None:
        self.voice = voice or DEFAULT_JARVIS_VOICE
        self.rate = rate or DEFAULT_RATE
        self.pitch = pitch or DEFAULT_PITCH
        self._save_settings()
        logger.info(f"JARVIS voice box changed to: {self.voice}")

    def status(self) -> dict:
        return {
            "ready": self.ready,
            "voice": self.voice,
            "rate": self.rate,
            "pitch": self.pitch,
            "engine": self.last_engine,
        }

    async def test_voice(self, text: str = "JARVIS voice box online. Systems ready.") -> bytes:
        return await self.synthesize(text)

    @staticmethod
    def _download_file(url: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_path = destination.with_suffix(destination.suffix + ".part")
        logger.info(f"Downloading JARVIS voice asset: {destination.name}")
        request = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response, open(temp_path, "wb") as out:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
            if temp_path.stat().st_size == 0:
                raise RuntimeError(f"Downloaded empty voice asset: {destination.name}")
            temp_path.replace(destination)
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    def _ensure_kokoro_assets(self) -> tuple[Path, Path]:
        voice_dir = self._get_kokoro_dir()
        model_path = voice_dir / _KOKORO_MODEL_FILE
        voices_path = voice_dir / _KOKORO_VOICES_FILE
        if not model_path.exists():
            self._download_file(_KOKORO_MODEL_URL, model_path)
        if not voices_path.exists():
            self._download_file(_KOKORO_VOICES_URL, voices_path)
        return model_path, voices_path

    def _get_kokoro(self):
        if not _KOKORO_AVAILABLE or Kokoro is None:
            raise RuntimeError("kokoro-onnx is not installed")
        if self._kokoro is not None:
            return self._kokoro
        with self._kokoro_lock:
            if self._kokoro is None:
                model_path, voices_path = self._ensure_kokoro_assets()
                logger.info("Loading local Kokoro JARVIS voice model")
                self._kokoro = Kokoro(str(model_path), str(voices_path))
        return self._kokoro

    @staticmethod
    def _rate_to_speed(rate: str) -> float:
        try:
            clean = str(rate).strip().replace("%", "")
            percent = float(clean)
            return max(0.65, min(1.45, 1.0 + (percent / 100.0)))
        except Exception:
            return 1.0

    def _synthesize_kokoro_sync(self, text: str) -> bytes:
        kokoro = self._get_kokoro()
        voice_id = self.voice.split(":", 1)[1] if ":" in self.voice else "bm_george"
        speed = self._rate_to_speed(self.rate)
        samples, sample_rate = kokoro.create(
            text,
            voice=voice_id,
            speed=speed,
            lang=_KOKORO_LANG,
        )
        if samples is None or len(samples) == 0:
            raise RuntimeError("Kokoro produced no audio")
        buffer = io.BytesIO()
        sf.write(buffer, samples, sample_rate, format="WAV", subtype="PCM_16")
        data = buffer.getvalue()
        if not data:
            raise RuntimeError("Kokoro produced an empty WAV")
        self.last_engine = "kokoro-onnx"
        self.ready = True
        return data

    async def _synthesize_kokoro(self, text: str) -> bytes:
        return await asyncio.to_thread(self._synthesize_kokoro_sync, text)

    async def _synthesize_edge_once(self, text: str) -> bytes:
        edge_voice = self.voice if not self.voice.startswith("kokoro:") else EDGE_FALLBACK_VOICE
        audio_buffer = io.BytesIO()
        communicate = edge_tts.Communicate(
            text=text,
            voice=edge_voice,
            rate=self.rate,
            pitch=self.pitch,
        )
        async with asyncio.timeout(20):
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio" and chunk.get("data"):
                    audio_buffer.write(chunk["data"])

        data = audio_buffer.getvalue()
        if not data:
            raise RuntimeError("edge-tts returned no audio")
        self.last_engine = "edge-tts"
        self.ready = True
        return data

    async def _synthesize_edge_with_retry(self, text: str, attempts: int = 2) -> bytes:
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return await self._synthesize_edge_once(text)
            except Exception as exc:
                last_error = exc
                logger.warning(f"JARVIS voice box online attempt {attempt}/{attempts} failed: {exc}")
                if attempt < attempts:
                    await asyncio.sleep(0.4 * attempt)
        if last_error is not None:
            raise last_error
        raise RuntimeError("JARVIS voice box failed without an error")

    async def synthesize_stream(self, text: str):
        logger.debug(f"JARVIS voice box synthesizing: {text[:50]}...")
        text = text.strip()
        if not text:
            return

        if self.voice.startswith("kokoro:"):
            try:
                data = await self._synthesize_kokoro(text)
                yield data
                return
            except Exception as exc:
                logger.warning(f"Local Kokoro JARVIS voice failed ({exc}); trying online fallback")

        try:
            data = await self._synthesize_edge_with_retry(text)
            yield data
            return
        except Exception as exc:
            logger.warning(f"Online JARVIS voice failed ({exc}); trying Windows fallback")

        data = await self._synthesize_local(text)
        if data:
            yield data
            return

        self.ready = False
        self.last_engine = "failed"
        raise RuntimeError("JARVIS voice box could not produce speech")

    async def synthesize(self, text: str) -> bytes:
        audio_buffer = io.BytesIO()
        async for chunk in self.synthesize_stream(text):
            audio_buffer.write(chunk)
        data = audio_buffer.getvalue()
        if not data:
            self.ready = False
            raise RuntimeError("JARVIS voice box produced no audio")
        return data

    async def _synthesize_local(self, text: str) -> bytes | None:
        if not _PYTTSX3_AVAILABLE:
            logger.warning("pyttsx3 not installed — Windows voice fallback unavailable")
            return None
        try:
            def _run() -> bytes:
                engine = pyttsx3.init()
                voices = engine.getProperty("voices") or []
                for candidate in voices:
                    gender = str(getattr(candidate, "gender", "")).lower()
                    name = str(getattr(candidate, "name", "")).lower()
                    if "male" in gender or "david" in name or "mark" in name:
                        engine.setProperty("voice", candidate.id)
                        break
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp.close()
                try:
                    engine.save_to_file(text, tmp.name)
                    engine.runAndWait()
                    engine.stop()
                    with open(tmp.name, "rb") as f:
                        return f.read()
                finally:
                    try:
                        os.unlink(tmp.name)
                    except OSError:
                        pass

            data = await asyncio.to_thread(_run)
            if not data:
                raise RuntimeError("Windows voice fallback produced no audio")
            self.last_engine = "windows-local"
            self.ready = True
            logger.info("JARVIS voice box Windows fallback succeeded")
            return data
        except Exception as exc:
            logger.error(f"JARVIS voice box Windows fallback failed: {exc}")
            return None

    async def get_available_voices(self) -> list[str]:
        names = [DEFAULT_JARVIS_VOICE]
        try:
            voices = await edge_tts.list_voices()
            names.extend(v["Name"] for v in voices if v.get("Name"))
        except Exception as exc:
            logger.warning(f"Could not load online voice list: {exc}")
        return list(dict.fromkeys(names))


class TTS(VoiceBox):
    """Backward-compatible name used by the rest of JARVIS."""

    pass
