"""Display-mode remodel for the Project Nova JARVIS command center.

Keeps the working assistant UI and command-center HUD, but removes the desktop-like
presentation: JARVIS opens as a full-screen command display so the Windows taskbar,
Start logo and ordinary window chrome are not part of the visual design.
"""
from __future__ import annotations

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QToolButton


def _hide_legacy_footer_controls(window) -> None:
    """Remove the old desktop-style footer strip without deleting its behavior."""
    legacy = {
        "Export", "History", "Bookmarks", "Macros", "Schedules",
        "New chat", "Clear", "A−", "A+", "A-",
    }
    for cls in (QPushButton, QToolButton):
        for widget in window.findChildren(cls):
            if widget.text().strip() in legacy:
                widget.hide()


def _hide_empty_legacy_frames(window) -> None:
    """Collapse frames left empty after the old footer controls are hidden."""
    for frame in window.findChildren(QFrame):
        layout = frame.layout()
        if layout is None or layout.count() == 0:
            continue
        visible = False
        for i in range(layout.count()):
            item = layout.itemAt(i)
            widget = item.widget()
            if widget is None or widget.isVisibleTo(window):
                visible = True
                break
        if not visible and frame.objectName() not in {"headerPanel", "panel", "chatPanel"}:
            frame.setMaximumHeight(0)
            frame.hide()


def install_jarvis_display_mode(window, runtime=None) -> None:
    """Turn the main JARVIS window into the dedicated Project Nova HUD display."""
    if getattr(window, "_nova_display_mode_installed", False):
        return

    window.setWindowTitle("JARVIS // PROJECT NOVA COMMAND CENTER")
    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

    _hide_legacy_footer_controls(window)
    QTimer.singleShot(0, lambda: _hide_empty_legacy_frames(window))

    # Dedicated assistant display: removes Windows taskbar / Start logo and normal
    # desktop chrome from the composition. F11 toggles this mode for maintenance.
    def toggle_fullscreen():
        if window.isFullScreen():
            window.showMaximized()
        else:
            window.showFullScreen()

    shortcut = QShortcut(QKeySequence("F11"), window)
    shortcut.activated.connect(toggle_fullscreen)
    window._nova_fullscreen_shortcut = shortcut

    # Esc intentionally does not exit full screen; this prevents accidental return
    # to the desktop-looking frame while using voice/chat controls.
    QTimer.singleShot(0, window.showFullScreen)
    window._nova_display_mode_installed = True
