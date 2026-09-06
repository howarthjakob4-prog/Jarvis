"""Always-available local GGUF model loader for the Jarvis desktop UI.

This gives users a direct way to select an existing .gguf model even when the
Local AI settings card or one-click download control is not reachable.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QFileDialog, QToolBar

from jarvis.ui.notification_toast import NotificationToast


def install_local_model_loader(window, runtime) -> None:
    """Attach a persistent 'Load AI Model (.gguf)' action to the main window."""
    if getattr(window, "_jarvis_local_model_loader_installed", False):
        return
    window._jarvis_local_model_loader_installed = True

    toolbar = QToolBar("Local AI Model", window)
    toolbar.setObjectName("jarvisLocalModelToolbar")
    toolbar.setMovable(False)
    toolbar.setFloatable(False)

    action = QAction("Load AI Model (.gguf)", window)
    action.setToolTip("Choose an existing GGUF model file for Jarvis local AI")
    action.setShortcut(QKeySequence("Ctrl+M"))
    action.setEnabled(True)

    def choose_model() -> None:
        path, _ = QFileDialog.getOpenFileName(
            window,
            "Select Jarvis local AI model (.gguf)",
            str(Path.home()),
            "GGUF Models (*.gguf);;All Files (*)",
        )
        if not path:
            return

        model_path = Path(path)
        if not model_path.is_file() or model_path.suffix.lower() != ".gguf":
            NotificationToast.show_toast(
                "That file is not a valid .gguf model.",
                "error",
                window,
                "llm_model_loader",
                8000,
            )
            return

        settings = deepcopy(getattr(runtime, "settings", {}) or {})
        providers = settings.setdefault("providers", {})
        local = dict(providers.get("llamacpp", {}) or {})
        local["enabled"] = True
        local["model_path"] = str(model_path)
        local.setdefault("port", 8080)
        local.setdefault("base_url", f"http://127.0.0.1:{local['port']}/v1")
        providers["llamacpp"] = local

        runtime.apply_settings(settings)
        action.setText(f"AI Model: {model_path.name}")
        NotificationToast.show_toast(
            f"Local AI model selected: {model_path.name}",
            "success",
            window,
            "llm_model_loader",
            8000,
        )

    action.triggered.connect(choose_model)
    toolbar.addAction(action)
    window.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

    # Keep references alive for PyQt and make the action easy to test.
    window._jarvis_local_model_toolbar = toolbar
    window._jarvis_local_model_action = action
