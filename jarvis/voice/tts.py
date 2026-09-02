import asyncio
import io
import json
import os
import tempfile
from pathlib import Path

from loguru import logger
import edge_tts

try:
    import pyttsx3
    _PYTTSX3_AVAILABLE = True
except ImportError:
    _PYTTSX3_AVAILABLE = False


DEFAULT_JARVIS_VOICE = "en-GB-RyanNeural"
DEFAULT_RATE = "+5%"
DEFAULT_PITCH = "+0Hz"


class VoiceBox:
    """Built-in JARVIS voice box.

    The voice box always starts with a usable male JARVIS voice, remembers the
    selected voice between launches, and falls back to the local Windows speech
    engine when online synthesis is unavailable.
    """

    def __init__(
        self,
        voice: str = DEFAULT_JARVIS_VOICE,
        rate: str = DEFAULT_RATE,
        pitch: str = DEFAULT_PITCH,
    ):
        self._settings_path = self._get_settings_path()
        saved = self._load_settings()
        self.voice = saved.get("voice") or voice or DEFAULT_JARVIS_VOICE
        self.rate = saved.get("rate") or rate or DEFAULT_RATE
        self.pitch = saved.get("pitch") or pitch or DEFAULT_PITCH
        self.ready = True
        self.last_engine = "not-tested"
        self._save_settings()
        logger.info(f"JARVIS voice box loaded: {self.voice}")

    @staticmethod
    def _get_settings_path() -> Path:
        base = Path(os.getenv("APPDATA") or Path.home()) / "JARVIS"
        base.mkdir(parents=True, exist_ok=True)
        return base / "voice_box.json"

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
        """Generate a short voice-box test clip for the normal audio player."""
        return await self.synthesize(text)

    async def _synthesize_edge_once(self, text: str) -> bytes:
        audio_buffer = io.BytesIO()
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
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

    async def _synthesize_edge_with_retry(self, text: str, attempts: int = 3) -> bytes:
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
                # Prefer a male Windows voice when Windows exposes gender metadata.
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
        try:
            voices = await edge_tts.list_voices()
            names = [v["Name"] for v in voices if v.get("Name")]
            if DEFAULT_JARVIS_VOICE not in names:
                names.insert(0, DEFAULT_JARVIS_VOICE)
            return names
        except Exception as exc:
            logger.warning(f"Could not load online voice list: {exc}")
            return [DEFAULT_JARVIS_VOICE]


class TTS(VoiceBox):
    """Backward-compatible name used by the rest of JARVIS.

    Existing code can keep constructing TTS; it now receives the built-in VoiceBox.
    """

    pass
