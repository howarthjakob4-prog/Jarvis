"""
The UI only ever talks to VoiceController — it doesn't know about
wake_word.py / stt_engine.py / tts_engine.py individually. This keeps the
voice layer swappable without touching ui/.
"""
from __future__ import annotations

import threading

from core.errors import JarvisError, error_bus
from core.event_bus import event_bus
from core.settings_manager import settings


class VoiceController:
    def __init__(self):
        self.tts = None
        self.stt = None
        self.wake_word = None
        self.wake_word_active = False
        self._wake_capture_lock = threading.Lock()
        self._init_from_settings()

    def _init_from_settings(self) -> None:
        self.tts = None
        self.stt = None
        self.wake_word = None
        self.wake_word_active = False
        voice_cfg = settings.get("voice", default={})
        features = settings.get("features", default={})
        if features.get("voice_output", True):
            try:
                from voice.tts_engine import build_tts_backend
                self.tts = build_tts_backend(voice_cfg.get("tts_backend", "pyttsx3"), voice_cfg.get("tts_rate", 185), voice_cfg.get("tts_voice_id"), voice_cfg.get("piper_model_path"))
            except JarvisError as e:
                error_bus.report(e)
        if features.get("voice_input", True):
            try:
                from voice.stt_engine import SpeechToText
                self.stt = SpeechToText(model_size=voice_cfg.get("stt_model_size", "base.en"), device_index=voice_cfg.get("input_device_index"))
            except JarvisError as e:
                error_bus.report(e)
        if features.get("wake_word", True) and self.stt is not None:
            try:
                from voice.wake_word import WakeWordListener
                self.wake_word = WakeWordListener(model_name=voice_cfg.get("wake_word_model", "hey_jarvis"), sensitivity=voice_cfg.get("wake_word_sensitivity", 0.5), device_index=voice_cfg.get("input_device_index"))
            except JarvisError as e:
                error_bus.report(e)

    def speak(self, text: str) -> None:
        if self.tts is None:
            error_bus.report(JarvisError(module="voice_controller", message="Voice output isn't available right now (TTS failed to initialize earlier). Replying in text only."))
            return
        self.tts.speak(text)

    def listen_once(self, duration_seconds: float = 5.0) -> str | None:
        if self.stt is None:
            error_bus.report(JarvisError(module="voice_controller", message="Voice input isn't available right now (STT failed to initialize earlier). Use text chat instead."))
            return None
        text = self.stt.record_and_transcribe(duration_seconds=duration_seconds)
        return text or None

    def start_wake_word(self) -> bool:
        if self.wake_word is None:
            error_bus.report(JarvisError(module="voice_controller", message="Wake word isn't available right now. Use the manual talk button."))
            return False
        if self.wake_word_active:
            return True

        def _on_detected():
            self.wake_word_active = False
            event_bus.publish("wake_word_detected")
            with self._wake_capture_lock:
                try:
                    text = self.listen_once()
                    if text:
                        event_bus.publish("user_voice_transcript", text)
                except JarvisError as e:
                    error_bus.report(e)
                finally:
                    if settings.get("features", "wake_word", default=True):
                        try:
                            self.wake_word.start(_on_detected)
                            self.wake_word_active = True
                        except JarvisError as e:
                            error_bus.report(e)
                            self.wake_word_active = False

        self.wake_word.start(_on_detected)
        self.wake_word_active = True
        return True

    def stop_wake_word(self) -> None:
        if self.wake_word:
            self.wake_word.stop()
        self.wake_word_active = False

    def reload(self) -> None:
        self.stop_wake_word()
        self._init_from_settings()
        if settings.get("features", "wake_word", default=True) and self.wake_word is not None:
            self.start_wake_word()
