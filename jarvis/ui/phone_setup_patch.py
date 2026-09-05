"""First-run phone setup, login phone prompt, and responsive setup wizard fixes."""

from __future__ import annotations

import re
import sys

import yaml
from loguru import logger
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QWidget,
)


def _normalize_phone(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    leading_plus = value.startswith("+")
    digits = re.sub(r"\D", "", value)
    return ("+" if leading_plus else "") + digits


def _configured_owner_phone() -> str:
    """Return an already configured owner number without exposing it elsewhere."""
    try:
        from jarvis.ui.settings_store import SettingsStore
        settings = SettingsStore().load()
        phone_line = settings.get("phone_line", {}) or {}
        phone_approvals = settings.get("phone_approvals", {}) or {}
        return _normalize_phone(
            str(phone_line.get("owner_number") or phone_approvals.get("owner_phone") or "")
        )
    except Exception:
        return ""


def _save_owner_phone(phone: str) -> bool:
    """Persist the number locally in JARVIS settings only."""
    phone = _normalize_phone(phone)
    if not phone:
        return False
    try:
        from jarvis.ui.settings_store import SettingsStore
        store = SettingsStore()
        settings = store.load()
        settings.setdefault("phone_line", {})
        settings["phone_line"]["owner_number"] = phone
        settings["phone_line"]["enabled"] = True
        settings["phone_line"].setdefault("call_on_alert", True)
        settings["phone_line"].setdefault("sms_on_alert", True)
        settings["phone_line"].setdefault("serial_port", "auto")
        settings["phone_line"].setdefault("transport", "direct_cellular")
        settings.setdefault("phone_approvals", {})
        settings["phone_approvals"]["owner_phone"] = phone
        settings["phone_approvals"]["enabled"] = True
        settings["phone_approvals"].setdefault("verified", False)
        settings["phone_approvals"].setdefault("allow_calls", True)
        settings["phone_approvals"].setdefault("allow_texts", True)
        store.save(settings)
        return True
    except Exception as exc:
        logger.warning(f"Could not save owner phone number: {exc}")
        return False


def _show_login_phone_notice(parent) -> None:
    """Ask for the owner's phone number after login/startup if it is missing."""
    if _configured_owner_phone():
        return
    if getattr(parent, "_jarvis_phone_notice_open", False):
        return

    parent._jarvis_phone_notice_open = True
    dialog = QDialog(parent)
    dialog.setWindowTitle("JARVIS Phone Setup")
    dialog.setModal(False)
    dialog.setMinimumWidth(430)
    dialog.setStyleSheet(
        "QDialog{background:#0A0E1A;color:#F0F4FF;}"
        "QLabel{color:#F0F4FF;font-size:13px;}"
        "QLineEdit{background:#1F2937;color:#F0F4FF;border:1px solid #1E3A5F;"
        "border-radius:8px;padding:10px;}"
        "QPushButton{border-radius:8px;padding:9px 16px;font-weight:600;}"
    )
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(24, 22, 24, 22)
    layout.setSpacing(12)

    title = QLabel("Phone Setup Required")
    title.setStyleSheet("font-size:20px;font-weight:700;color:#00E5FF;")
    layout.addWidget(title)

    detail = QLabel(
        "Please enter your phone number to enable JARVIS mobile notifications, "
        "owner alerts, and approval messages. Your number is stored locally in JARVIS settings."
    )
    detail.setWordWrap(True)
    layout.addWidget(detail)

    phone_input = QLineEdit()
    phone_input.setPlaceholderText("Phone number, for example +1 555 123 4567")
    layout.addWidget(phone_input)

    status = QLabel("")
    status.setWordWrap(True)
    layout.addWidget(status)

    buttons = QHBoxLayout()
    later = QPushButton("Not Now")
    later.setStyleSheet("background:#1F2937;color:#CBD5E1;border:1px solid #1E3A5F;")
    save = QPushButton("Save Phone Number")
    save.setStyleSheet("background:#00E5FF;color:#001018;border:none;")
    buttons.addWidget(later)
    buttons.addStretch()
    buttons.addWidget(save)
    layout.addLayout(buttons)

    def close_notice():
        parent._jarvis_phone_notice_open = False
        dialog.close()

    def save_number():
        phone = _normalize_phone(phone_input.text())
        if len(re.sub(r"\D", "", phone)) < 7:
            status.setText("Please enter a valid phone number.")
            status.setStyleSheet("color:#FBBF24;")
            return
        if _save_owner_phone(phone):
            status.setText("Phone number saved. JARVIS notifications can now use this number.")
            status.setStyleSheet("color:#34D399;")
            QTimer.singleShot(700, close_notice)
        else:
            status.setText("JARVIS could not save the number. Please try again.")
            status.setStyleSheet("color:#FB7185;")

    save.clicked.connect(save_number)
    later.clicked.connect(close_notice)
    dialog.finished.connect(lambda _result: setattr(parent, "_jarvis_phone_notice_open", False))
    parent._jarvis_phone_notice_dialog = dialog
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()


class PhoneApprovalsPage(QWidget):
    def __init__(self, sw, parent=None):
        super().__init__(parent)
        self._sw = sw
        self.setObjectName("page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 18, 32, 18)
        layout.setSpacing(10)

        section = QLabel("PHONE & REMOTE APPROVALS")
        section.setObjectName("section")
        layout.addWidget(section)

        title = QLabel("Connect your phone")
        title.setObjectName("title")
        title.setWordWrap(True)
        layout.addWidget(title)

        detail = QLabel(
            "Enter the number JARVIS should contact for owner approvals and security alerts."
        )
        detail.setObjectName("subtitle")
        detail.setWordWrap(True)
        layout.addWidget(detail)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(8)

        number_label = QLabel("Owner phone number")
        number_label.setStyleSheet(f"color: {sw.TEXT}; font-size: 12px; font-weight: 600;")
        card_layout.addWidget(number_label)

        self.owner_phone = QLineEdit()
        self.owner_phone.setPlaceholderText("Example: +1 555 123 4567")
        card_layout.addWidget(self.owner_phone)

        self.calls = QCheckBox("Allow JARVIS approval calls")
        self.calls.setChecked(True)
        card_layout.addWidget(self.calls)

        self.texts = QCheckBox("Allow JARVIS approval text notifications")
        self.texts.setChecked(True)
        card_layout.addWidget(self.texts)

        self.line_status = QLabel("Cellular line: not checked yet")
        self.line_status.setObjectName("subtitle")
        self.line_status.setWordWrap(True)
        card_layout.addWidget(self.line_status)

        self.detect_btn = QPushButton("Check Cellular Connection")
        self.detect_btn.setObjectName("secondary")
        self.detect_btn.clicked.connect(self._check_cellular)
        card_layout.addWidget(self.detect_btn)

        self.test_btn = QPushButton("Test My Phone")
        self.test_btn.setObjectName("primary")
        self.test_btn.clicked.connect(self._test_phone)
        card_layout.addWidget(self.test_btn)

        note = QLabel(
            "JARVIS automatically looks for a connected cellular modem/SIM. "
            "If one is ready, Test My Phone sends an alert text and/or places a short test call."
        )
        note.setObjectName("subtitle")
        note.setWordWrap(True)
        card_layout.addWidget(note)

        layout.addWidget(card)
        layout.addStretch()

    def _set_status(self, text: str, ok: bool | None = None) -> None:
        color = self._sw.TEXT_MUTED
        if ok is True:
            color = self._sw.SUCCESS
        elif ok is False:
            color = self._sw.WARNING
        self.line_status.setText(text)
        self.line_status.setStyleSheet(f"color: {color}; font-size: 12px;")

    def _check_cellular(self) -> None:
        self.detect_btn.setEnabled(False)
        self._set_status("Checking for a cellular modem/SIM…")
        QApplication.processEvents()
        try:
            from jarvis.connectors.direct_phone_line import status
            result = status("auto")
            if result.ok:
                suffix = f" on {result.port}" if result.port else ""
                self._set_status(f"Cellular line ready{suffix} ✅", True)
            else:
                self._set_status(f"Cellular line not ready: {result.message}", False)
        except Exception as exc:
            self._set_status(f"Cellular check failed: {exc}", False)
        finally:
            self.detect_btn.setEnabled(True)

    def _test_phone(self) -> None:
        phone = _normalize_phone(self.owner_phone.text())
        if not phone:
            self._set_status("Enter your phone number first.", False)
            return
        if not self.calls.isChecked() and not self.texts.isChecked():
            self._set_status("Turn on calls, texts, or both before testing.", False)
            return

        self.test_btn.setEnabled(False)
        self._set_status("Testing JARVIS phone connection…")
        QApplication.processEvents()
        try:
            from jarvis.connectors.direct_phone_line import alert_owner
            ok = alert_owner(
                phone,
                "JARVIS test alert. Your owner phone connection is working.",
                "auto",
                sms=self.texts.isChecked(),
                call=self.calls.isChecked(),
            )
            if ok:
                self._set_status("Test sent successfully ✅", True)
            else:
                self._set_status(
                    "Test could not be sent. Connect/activate a cellular modem or SIM and try again.",
                    False,
                )
        except Exception as exc:
            self._set_status(f"Phone test failed: {exc}", False)
        finally:
            self.test_btn.setEnabled(True)

    def get_config(self) -> dict:
        phone = _normalize_phone(self.owner_phone.text())
        return {
            "phone_approvals_enabled": bool(phone),
            "owner_phone": phone,
            "phone_allow_calls": self.calls.isChecked(),
            "phone_allow_texts": self.texts.isChecked(),
        }


def _install_playwright_without_relaunch(worker) -> None:
    """Install Chromium correctly from a frozen EXE without relaunching JARVIS.exe -m."""
    worker.item_started.emit("browser")
    try:
        if getattr(sys, "frozen", False):
            import playwright.__main__ as playwright_main
            old_argv = list(sys.argv)
            try:
                sys.argv = ["playwright", "install", "chromium"]
                try:
                    result = playwright_main.main()
                    code = 0 if result is None else int(result)
                except SystemExit as exc:
                    code = int(exc.code or 0)
            finally:
                sys.argv = old_argv
            if code == 0:
                worker.item_done.emit("browser", True, "Chromium ready")
            else:
                worker.item_done.emit("browser", False, f"Chromium installer exited with code {code}")
            return

        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            worker.item_done.emit("browser", True, "Chromium ready")
        else:
            err = (result.stderr or result.stdout or "unknown error").strip()[:120]
            worker.item_done.emit("browser", False, err)
    except Exception as exc:
        worker.item_done.emit("browser", False, str(exc)[:120])


def install_phone_setup_patch() -> None:
    """Install phone/setup fixes before the main window and SetupWizard are created."""
    from jarvis.ui import setup_wizard as sw

    if not getattr(sw.SetupWizard, "_jarvis_setup_fixes_installed", False):
        original_init = sw.SetupWizard.__init__
        original_write_config = sw.SetupWizard._write_config
        original_show_finish = sw.SetupWizard._show_finish

        def wizard_init(self, parent=None):
            original_init(self, parent)

            self.setMinimumSize(520, 430)
            screen = QApplication.primaryScreen()
            if screen is not None:
                area = screen.availableGeometry()
                width = max(540, min(700, int(area.width() * 0.84)))
                height = max(450, min(560, int(area.height() * 0.80)))
                self.resize(width, height)

            self._phone = PhoneApprovalsPage(sw)
            self._stack.insertWidget(5, self._phone)
            self._steps._total = 7
            self._steps.update()

        def go_next(self):
            page = self._current_page
            if page == 0:
                self._syscheck.start_checks()
                self._animate_to(1)
                return
            if page == 1:
                self._next_btn.setEnabled(False)
                self._next_btn.setText("Installing…")
                self._animate_to(2)
                self._downloads.start_downloads()
                return
            if page == 2:
                self._animate_to(3)
                return
            if page == 3:
                self._config.update(self._provider.get_config())
                self._animate_to(4)
                return
            if page == 4:
                self._config.update(self._voice.get_config())
                self._animate_to(5)
                return
            if page == 5:
                self._config.update(self._phone.get_config())
                self._show_finish()
                self._animate_to(6)
                return
            if page == 6:
                self._complete_setup()

        def update_nav(self, page=None):
            if page is None:
                page = self._current_page
            self._back_btn.setVisible(page > 0 and page != 2)
            labels = {
                0: "Get Started →",
                1: "Continue →",
                2: "Continue →",
                3: "Continue →",
                4: "Continue →",
                5: "Continue →",
                6: "Launch JARVIS  🚀",
            }
            self._next_btn.setText(labels.get(page, "Next →"))

        def show_finish(self):
            original_show_finish(self)
            phone = self._config.get("owner_phone", "")
            if phone:
                provider_name = self._config.get("provider", "unknown")
                voice_on = self._config.get("voice_enabled", False)
                summary = [
                    f"Engine: {provider_name}",
                    f"Voice: {'enabled' if voice_on else 'disabled'}",
                    "Phone approvals: configured",
                    "Config saved to %APPDATA%\\JARVIS",
                ]
                self._finish.set_summary(summary)

        def write_config(self):
            original_write_config(self)
            try:
                path = sw.get_user_config_path()
                data = {}
                if path.exists():
                    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                phone_cfg = {
                    "enabled": self._config.get("phone_approvals_enabled", False),
                    "owner_phone": self._config.get("owner_phone", ""),
                    "verified": False,
                    "allow_calls": self._config.get("phone_allow_calls", True),
                    "allow_texts": self._config.get("phone_allow_texts", True),
                    "notify_when_lid_closed": True,
                    "call_if_notification_unanswered": True,
                    "approval_timeout_seconds": 300,
                    "require_verification_code": True,
                }
                data["phone_approvals"] = phone_cfg
                path.write_text(
                    yaml.safe_dump(data, default_flow_style=False, allow_unicode=True),
                    encoding="utf-8",
                )

                from jarvis.ui.settings_store import SettingsStore
                store = SettingsStore()
                settings = store.load()
                settings.setdefault("phone_approvals", {}).update(phone_cfg)
                settings.setdefault("phone_line", {})["owner_number"] = phone_cfg["owner_phone"]
                settings["phone_line"]["enabled"] = bool(phone_cfg["owner_phone"])
                settings["phone_line"]["call_on_alert"] = phone_cfg["allow_calls"]
                settings["phone_line"]["sms_on_alert"] = phone_cfg["allow_texts"]
                settings["phone_line"].setdefault("serial_port", "auto")
                settings["phone_line"].setdefault("transport", "direct_cellular")
                store.save(settings)
            except Exception as exc:
                logger.warning(f"Could not save phone approval setup: {exc}")

        def downloads_done(self):
            failures = []
            for row in getattr(self, "_rows", {}).values():
                text = row["status"].text()
                if text.startswith("⚠️"):
                    failures.append(text)
            self._title.setText("Components ready ✅" if not failures else "Setup finished with warnings")
            self.all_complete.emit()

        sw.SetupWizard.__init__ = wizard_init
        sw.SetupWizard._go_next = go_next
        sw.SetupWizard._update_nav = update_nav
        sw.SetupWizard._show_finish = show_finish
        sw.SetupWizard._write_config = write_config
        sw.DownloadWorker._install_playwright = _install_playwright_without_relaunch
        sw.DownloadsPage._on_all_done = downloads_done
        sw.SetupWizard._jarvis_setup_fixes_installed = True

    # Existing installations may never see the first-run wizard again. Patch the
    # normal desktop window so a missing owner number is requested after login/startup.
    try:
        from jarvis.ui.advanced_chat_window import AdvancedChatWindow
        if not getattr(AdvancedChatWindow, "_jarvis_phone_login_prompt_installed", False):
            original_window_init = AdvancedChatWindow.__init__

            def window_init(self, *args, **kwargs):
                original_window_init(self, *args, **kwargs)
                if not _configured_owner_phone():
                    QTimer.singleShot(1200, lambda: _show_login_phone_notice(self))

            AdvancedChatWindow.__init__ = window_init
            AdvancedChatWindow._jarvis_phone_login_prompt_installed = True
    except Exception as exc:
        logger.warning(f"Could not install login phone prompt: {exc}")
