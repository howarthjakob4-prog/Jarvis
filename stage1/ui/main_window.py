from __future__ import annotations

import html

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenuBar, QPushButton,
    QTextEdit, QVBoxLayout, QWidget,
)

from core.errors import JarvisError, error_bus
from core.event_bus import event_bus
from core.settings_manager import settings
from voice.voice_controller import VoiceController


class ListenThread(QThread):
    """Runs a single blocking voice capture off the UI thread."""
    finished_with_text = Signal(str)

    def __init__(self, voice_controller: VoiceController):
        super().__init__()
        self._voice_controller = voice_controller

    def run(self) -> None:
        text = self._voice_controller.listen_once()
        self.finished_with_text.emit(text or "")


class DispatchThread(QThread):
    """Runs command/AI routing off the GUI thread."""
    finished_with_result = Signal(object, bool)
    failed = Signal(object)

    def __init__(self, text: str, speak_reply: bool):
        super().__init__()
        self._text = text
        self._speak_reply = speak_reply

    def run(self) -> None:
        try:
            from brain.command_router import route
            result = route(self._text)
            self.finished_with_result.emit(result, self._speak_reply)
        except JarvisError as exc:
            self.failed.emit(exc)
        except Exception as exc:
            self.failed.emit(JarvisError(
                module="command_router",
                message=f"Command processing failed: {exc}",
            ))


class MainWindow(QMainWindow):
    voice_transcript_signal = Signal(str)
    jarvis_error_signal = Signal(object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jarvis")
        self.resize(760, 640)

        # Subscribe before voice initialization so startup failures are not lost.
        self._startup_errors: list[JarvisError] = []
        self._ui_ready = False
        self.jarvis_error_signal.connect(self._on_jarvis_error)
        error_bus.subscribe(self._forward_error)

        self.voice_controller = VoiceController()
        self._listen_thread: ListenThread | None = None
        self._dispatch_threads: set[DispatchThread] = set()
        self._resume_wake_after_manual = False

        self._build_ui()
        self._wire_events()
        self._ui_ready = True
        for startup_error in self._startup_errors:
            self.jarvis_error_signal.emit(startup_error)
        self._startup_errors.clear()

        if settings.get("features", "wake_word", default=True):
            self.voice_controller.start_wake_word()
            if self.voice_controller.wake_word_active:
                self._set_status("Listening for wake word.", "ok")
            else:
                self._set_status("Wake word unavailable — use the mic button.", "error")
        else:
            self._set_status("Ready.", "ok")

    def _forward_error(self, error: JarvisError) -> None:
        if not self._ui_ready:
            self._startup_errors.append(error)
            return
        self.jarvis_error_signal.emit(error)

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)
        menu_bar = QMenuBar()
        settings_menu = menu_bar.addMenu("Settings")
        open_settings_action = settings_menu.addAction("Open Settings...")
        open_settings_action.triggered.connect(self._open_settings)
        self.setMenuBar(menu_bar)
        self.chat_log = QTextEdit()
        self.chat_log.setObjectName("chatLog")
        self.chat_log.setReadOnly(True)
        layout.addWidget(self.chat_log, stretch=1)
        input_row = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setObjectName("chatInput")
        self.chat_input.setPlaceholderText("Type a message or command...")
        self.chat_input.returnPressed.connect(self._on_text_submitted)
        input_row.addWidget(self.chat_input, stretch=1)
        self.mic_button = QPushButton("🎤 Hold to Talk")
        self.mic_button.setObjectName("micButton")
        self.mic_button.pressed.connect(self._on_mic_pressed)
        input_row.addWidget(self.mic_button)
        send_button = QPushButton("Send")
        send_button.clicked.connect(self._on_text_submitted)
        input_row.addWidget(send_button)
        layout.addLayout(input_row)
        self.status_label = QLabel("Starting...")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)
        self.setCentralWidget(central)

    def _wire_events(self) -> None:
        self.voice_transcript_signal.connect(self._on_voice_transcript)
        event_bus.subscribe("user_voice_transcript", lambda text: self.voice_transcript_signal.emit(text))

    def _on_text_submitted(self) -> None:
        text = self.chat_input.text().strip()
        if not text:
            return
        self.chat_input.clear()
        self._append_chat("You", text)
        self._dispatch(text, speak_reply=False)

    def _on_mic_pressed(self) -> None:
        if self._listen_thread and self._listen_thread.isRunning():
            return

        # Many Windows audio drivers reject two simultaneous input streams.
        # Pause wake-word capture while manual recording owns the microphone.
        self._resume_wake_after_manual = self.voice_controller.wake_word_active
        if self._resume_wake_after_manual:
            self.voice_controller.stop_wake_word()

        self._set_status("Listening...", "ok")
        self._listen_thread = ListenThread(self.voice_controller)
        self._listen_thread.finished_with_text.connect(self._on_manual_listen_finished)
        self._listen_thread.start()

    def _on_manual_listen_finished(self, text: str) -> None:
        if self._resume_wake_after_manual and settings.get("features", "wake_word", default=True):
            self.voice_controller.start_wake_word()
        self._resume_wake_after_manual = False
        self._on_mic_result(text)

    def _on_mic_result(self, text: str) -> None:
        if not text:
            self._set_status("Didn't catch that — try again.", "error")
            return
        self._append_chat("You (voice)", text)
        self._dispatch(text, speak_reply=True)

    def _on_voice_transcript(self, text: str) -> None:
        if not text:
            return
        self._append_chat("You (voice)", text)
        self._dispatch(text, speak_reply=True)

    def _dispatch(self, text: str, speak_reply: bool) -> None:
        self._set_status("Working...", "ok")
        worker = DispatchThread(text, speak_reply)
        self._dispatch_threads.add(worker)
        worker.finished_with_result.connect(self._on_dispatch_result)
        worker.failed.connect(self._on_dispatch_error)
        worker.finished.connect(lambda w=worker: self._dispatch_threads.discard(w))
        worker.start()

    def _on_dispatch_result(self, result, speak_reply: bool) -> None:
        self._append_chat("Jarvis", result.text)
        if speak_reply and result.should_speak:
            self.voice_controller.speak(result.text)
        self._set_status("Ready.", "ok")

    def _on_dispatch_error(self, error: JarvisError) -> None:
        error_bus.report(error)
        self._set_status("Ready.", "ok")

    def _on_jarvis_error(self, error: JarvisError) -> None:
        self._append_chat("Jarvis [error]", f"({error.module}) {error.message}")
        self._set_status(f"Error in {error.module} — see chat log.", "error")

    def _open_settings(self) -> None:
        from ui.settings_window import SettingsWindow
        dialog = SettingsWindow(self.voice_controller, parent=self)
        dialog.exec()

    def _append_chat(self, speaker: str, text: str) -> None:
        safe_speaker = html.escape(speaker)
        safe_text = html.escape(text).replace("\n", "<br>")
        self.chat_log.append(f"<b>{safe_speaker}:</b> {safe_text}")

    def _set_status(self, text: str, state: str) -> None:
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def closeEvent(self, event) -> None:
        self.voice_controller.stop_wake_word()

        # Do not let Qt destroy a running QThread during app teardown.
        if self._listen_thread and self._listen_thread.isRunning():
            self._listen_thread.requestInterruption()
            self._listen_thread.wait(6500)

        for worker in list(self._dispatch_threads):
            if worker.isRunning():
                worker.requestInterruption()
                worker.wait(1000)

        super().closeEvent(event)
