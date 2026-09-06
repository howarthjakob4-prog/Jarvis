"""
Jarvis entry point.

Run with: python main.py
(after `pip install -r requirements.txt` inside a venv — see README.md)
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> int:
    app = QApplication(sys.argv)
    style_path = Path(__file__).resolve().parent / "ui" / "styles.qss"
    if style_path.exists():
        app.setStyleSheet(style_path.read_text(encoding="utf-8"))
    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
