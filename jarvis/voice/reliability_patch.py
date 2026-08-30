"""Runtime voice reliability fixes for natural wake phrases."""

from __future__ import annotations

import asyncio


def install_voice_reliability_patch() -> None:
    from jarvis.voice.voice_manager import VoiceManager
    from jarvis.voice.utterance import (
        extract_command_from_transcript,
        is_meaningful_transcript,
        is_wake_only_transcript,
    )
    from jarvis.models import RuntimeLogEvent, TTSRequestEvent, UserSpeechEvent

    if getattr(VoiceManager, "_jarvis_voice_reliability_patch", False):
        return

    async def reliable_wake_word_mode(self) -> None:
        while self.is_running and self.enabled:
            if self.audio_player.is_playing or self._is_processing:
                await asyncio.sleep(0.05)
                continue

            self._drain_stale_audio()
            phrase = await self._capture_phrase()
            if not phrase:
                continue

            if is_wake_only_transcript(phrase, self.config.voice.wake_word):
                await self.event_bus.publish(
                    RuntimeLogEvent("info", f"JARVIS heard wake greeting: {phrase!r}")
                )
                await self.event_bus.publish(TTSRequestEvent(text="Yes?"))
                continue

            command = extract_command_from_transcript(
                transcript=phrase,
                wake_phrase=self.config.voice.wake_word,
                require_wake_phrase=True,
            )
            if not command:
                continue

            if is_meaningful_transcript(command):
                await self.event_bus.publish(
                    UserSpeechEvent(text=command, confidence=1.0, timestamp=0.0)
                )
            await self._publish_status("idle")

    VoiceManager._wake_word_mode = reliable_wake_word_mode
    VoiceManager._jarvis_voice_reliability_patch = True
