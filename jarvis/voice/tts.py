import asyncio
import io
import os
import tempfile
from loguru import logger
import edge_tts

try:
    import pyttsx3
    _PYTTSX3_AVAILABLE = True
except ImportError:
    _PYTTSX3_AVAILABLE = False


class TTS:
    def __init__(self, voice: str = "en-GB-RyanNeural", rate: str = "+5%", pitch: str = "+0Hz"):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch

    def set_voice(self, voice: str, rate: str = "+0%", pitch: str = "+0Hz") -> None:
        self.voice = voice
        self.rate = rate
        self.pitch = pitch

    async def _synthesize_edge_once(self, text: str) -> bytes:
        """Synthesize one utterance with edge-tts and require actual audio bytes."""
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
        return data

    async def _synthesize_edge_with_retry(self, text: str, attempts: int = 3) -> bytes:
        """Retry transient online TTS failures before using the offline voice."""
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return await self._synthesize_edge_once(text)
            except Exception as exc:
                last_error = exc
                logger.warning(f"edge-tts attempt {attempt}/{attempts} failed: {exc}")
                if attempt < attempts:
                    await asyncio.sleep(0.4 * attempt)
        if last_error is not None:
            raise last_error
        raise RuntimeError("edge-tts failed without an error")

    async def synthesize_stream(self, text: str):
        """Yield synthesized audio, with retries and an offline Windows fallback."""
        logger.debug(f"Synthesizing stream: {text[:50]}...")
        text = text.strip()
        if not text:
            return

        try:
            data = await self._synthesize_edge_with_retry(text)
            yield data
            return
        except Exception as exc:
            logger.warning(f"edge-tts failed after retries ({exc}), trying local TTS fallback")

        data = await self._synthesize_local(text)
        if data:
            yield data
            return

        raise RuntimeError("Both online and local JARVIS voice synthesis failed")

    async def synthesize(self, text: str) -> bytes:
        """Collect synthesized audio into one byte buffer."""
        audio_buffer = io.BytesIO()
        async for chunk in self.synthesize_stream(text):
            audio_buffer.write(chunk)
        data = audio_buffer.getvalue()
        if not data:
            raise RuntimeError("JARVIS voice synthesis produced no audio")
        return data

    async def _synthesize_local(self, text: str) -> bytes | None:
        """Offline fallback using the Windows speech engine through pyttsx3."""
        if not _PYTTSX3_AVAILABLE:
            logger.warning("pyttsx3 not installed — offline TTS unavailable")
            return None
        try:
            def _run() -> bytes:
                engine = pyttsx3.init()
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
                raise RuntimeError("local TTS produced no audio")
            logger.info("Local TTS fallback succeeded")
            return data
        except Exception as exc:
            logger.error(f"Local TTS fallback failed: {exc}")
            return None

    async def get_available_voices(self) -> list[str]:
        voices = await edge_tts.list_voices()
        return [v["Name"] for v in voices]
