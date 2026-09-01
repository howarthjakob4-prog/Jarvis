import asyncio
import io
import numpy as np
import sounddevice as sd
import soundfile as sf
import miniaudio
from loguru import logger


def _decode_audio(audio_bytes: bytes) -> tuple[np.ndarray, int]:
    """Decode edge-tts MP3 first; fall back to soundfile for WAV/local TTS."""
    if not audio_bytes:
        raise ValueError("No audio bytes to play")

    try:
        decoded = miniaudio.mp3_read_s16(audio_bytes)
        data = np.frombuffer(decoded.samples.tobytes(), dtype=np.int16)
        if decoded.nchannels > 1:
            data = data.reshape(-1, decoded.nchannels)
        return data.astype(np.float32) / 32768.0, decoded.sample_rate
    except Exception as mp3_exc:
        logger.debug(f"MP3 decoder did not accept audio ({mp3_exc}); trying WAV/PCM decoder")

    try:
        data, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
        return data, sr
    except Exception as wav_exc:
        raise RuntimeError(f"Unable to decode JARVIS voice audio: {wav_exc}") from wav_exc


class AudioPlayer:
    def __init__(self, sample_rate: int = 24000, device: int | None = None):
        self.sample_rate = sample_rate
        self.device = device
        self.is_playing = False
        self._current_stream = None

    async def play_audio(self, audio_bytes: bytes) -> None:
        try:
            logger.debug(f"Playing audio ({len(audio_bytes)} bytes)")
            self.is_playing = True

            data, samplerate = await asyncio.to_thread(_decode_audio, audio_bytes)
            if data.size == 0:
                raise RuntimeError("Decoded JARVIS voice audio is empty")

            await asyncio.to_thread(
                sd.play, data, samplerate=samplerate, device=self.device, blocking=True
            )

            self.is_playing = False
            logger.debug("Audio playback completed")

        except Exception as e:
            logger.error(f"Audio playback error: {e}")
            self.is_playing = False
            raise

    async def stop_playback(self) -> None:
        if self.is_playing:
            await asyncio.to_thread(sd.stop)
            self.is_playing = False
            logger.debug("Audio playback stopped")

    def stop(self) -> None:
        """Synchronous immediate stop — safe to call from any thread/context."""
        try:
            sd.stop()
            self.is_playing = False
        except Exception:
            pass
