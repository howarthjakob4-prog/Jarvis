from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QInputDialog, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QSlider, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from core.event_bus import event_bus
from core.permission_manager import permissions
from core.settings_manager import settings


class SettingsWindow(QDialog):
    def __init__(self, voice_controller, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Jarvis Settings")
        self.resize(560, 480)
        self._voice_controller = voice_controller
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._build_voice_tab(), "Voice")
        tabs.addTab(self._build_permissions_tab(), "Permissions")
        tabs.addTab(self._build_features_tab(), "Connected Features")
        layout.addWidget(tabs)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

    def _build_voice_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        self.tts_backend_combo = QComboBox()
        self.tts_backend_combo.addItems(["pyttsx3", "piper"])
        self.tts_backend_combo.setCurrentText(settings.get("voice", "tts_backend", default="pyttsx3"))
        self.tts_backend_combo.currentTextChanged.connect(lambda v: self._update_setting(("voice", "tts_backend"), v))
        form.addRow("TTS backend:", self.tts_backend_combo)
        self.rate_spin = QSpinBox()
        self.rate_spin.setRange(80, 400)
        self.rate_spin.setValue(settings.get("voice", "tts_rate", default=185))
        self.rate_spin.valueChanged.connect(lambda v: self._update_setting(("voice", "tts_rate"), v))
        form.addRow("Speech rate:", self.rate_spin)
        self.wake_word_check = QCheckBox("Enabled")
        self.wake_word_check.setChecked(settings.get("features", "wake_word", default=True))
        self.wake_word_check.stateChanged.connect(lambda v: self._update_setting(("features", "wake_word"), bool(v)))
        form.addRow("Wake word:", self.wake_word_check)
        sensitivity_row = QHBoxLayout()
        self.sensitivity_slider = QSlider(Qt.Horizontal)
        self.sensitivity_slider.setRange(0, 100)
        self.sensitivity_slider.setValue(int(settings.get("voice", "wake_word_sensitivity", default=0.5) * 100))
        self.sensitivity_slider.valueChanged.connect(lambda v: self._update_setting(("voice", "wake_word_sensitivity"), v / 100))
        sensitivity_row.addWidget(self.sensitivity_slider)
        sensitivity_container = QWidget()
        sensitivity_container.setLayout(sensitivity_row)
        form.addRow("Wake sensitivity:", sensitivity_container)
        test_voice_button = QPushButton("Test voice output")
        test_voice_button.clicked.connect(lambda: self._voice_controller.speak("Hello, this is a voice test."))
        form.addRow(test_voice_button)
        apply_button = QPushButton("Apply voice changes (reloads voice engine)")
        apply_button.clicked.connect(self._voice_controller.reload)
        form.addRow(apply_button)
        return widget

    def _build_permissions_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("Approved folders:"))
        self.folder_list = QListWidget(); self._refresh_folder_list(); layout.addWidget(self.folder_list)
        folder_buttons = QHBoxLayout()
        add_folder_btn = QPushButton("Add folder..."); add_folder_btn.clicked.connect(self._add_folder)
        remove_folder_btn = QPushButton("Remove selected"); remove_folder_btn.clicked.connect(self._remove_folder)
        folder_buttons.addWidget(add_folder_btn); folder_buttons.addWidget(remove_folder_btn); layout.addLayout(folder_buttons)
        layout.addWidget(QLabel("Approved files:"))
        self.file_list = QListWidget(); self._refresh_file_list(); layout.addWidget(self.file_list)
        file_buttons = QHBoxLayout()
        add_file_btn = QPushButton("Add file..."); add_file_btn.clicked.connect(self._add_file)
        remove_file_btn = QPushButton("Remove selected"); remove_file_btn.clicked.connect(self._remove_file)
        file_buttons.addWidget(add_file_btn); file_buttons.addWidget(remove_file_btn); layout.addLayout(file_buttons)
        layout.addWidget(QLabel("Approved apps:"))
        self.app_list = QListWidget(); self._refresh_app_list(); layout.addWidget(self.app_list)
        app_buttons = QHBoxLayout()
        add_app_btn = QPushButton("Add app..."); add_app_btn.clicked.connect(self._add_app)
        remove_app_btn = QPushButton("Remove selected"); remove_app_btn.clicked.connect(self._remove_app)
        app_buttons.addWidget(add_app_btn); app_buttons.addWidget(remove_app_btn); layout.addLayout(app_buttons)
        return widget

    def _refresh_folder_list(self) -> None:
        self.folder_list.clear()
        for folder in permissions.list_approved_folders(): self.folder_list.addItem(QListWidgetItem(folder))

    def _refresh_file_list(self) -> None:
        self.file_list.clear()
        for path in permissions.list_approved_files(): self.file_list.addItem(QListWidgetItem(path))

    def _refresh_app_list(self) -> None:
        self.app_list.clear()
        for app in permissions.list_approved_apps(): self.app_list.addItem(QListWidgetItem(f"{app['name']}  ->  {app['path']}"))

    def _add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select a folder to approve")
        if folder: permissions.approve_folder(folder); self._refresh_folder_list()

    def _remove_folder(self) -> None:
        item = self.folder_list.currentItem()
        if item: permissions.revoke_folder(item.text()); self._refresh_folder_list()

    def _add_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select a file to approve")
        if path: permissions.approve_file(path); self._refresh_file_list()

    def _remove_file(self) -> None:
        item = self.file_list.currentItem()
        if item: permissions.revoke_file(item.text()); self._refresh_file_list()

    def _add_app(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select application executable", filter="Executables (*.exe)")
        if not path: return
        name, ok = QInputDialog.getText(self, "App name", "Friendly name for this app:")
        if ok and name: permissions.approve_app(name, path); self._refresh_app_list()

    def _remove_app(self) -> None:
        item = self.app_list.currentItem()
        if item:
            name = item.text().split("  ->  ")[0]
            permissions.revoke_app(name); self._refresh_app_list()

    def _build_features_tab(self) -> QWidget:
        widget = QWidget(); form = QFormLayout(widget)
        self.ai_backend_check = QCheckBox("Enabled (requires API key in environment variable)")
        self.ai_backend_check.setChecked(settings.get("features", "ai_backend", default=False))
        self.ai_backend_check.stateChanged.connect(lambda v: self._update_setting(("features", "ai_backend"), bool(v)))
        form.addRow("AI backend (Q&A):", self.ai_backend_check)
        env_var_label = QLabel(settings.get("ai_backend", "api_key_env_var", default="ANTHROPIC_API_KEY"))
        form.addRow("Reads API key from:", env_var_label)
        self.app_launch_check = QCheckBox("Enabled")
        self.app_launch_check.setChecked(settings.get("features", "app_launching", default=True))
        self.app_launch_check.stateChanged.connect(lambda v: self._update_setting(("features", "app_launching"), bool(v)))
        form.addRow("App launching:", self.app_launch_check)
        return widget

    def _update_setting(self, keys: tuple, value) -> None:
        settings.set(*keys, value=value)
        event_bus.publish("settings_changed", keys[0])
