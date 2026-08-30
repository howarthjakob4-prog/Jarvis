"""Add phone/remote approval setup controls to the first-run JARVIS wizard."""

from __future__ import annotations

import re

import yaml
from loguru import logger
from PyQt6.QtWidgets import QCheckBox, QFrame, QLabel, QLineEdit, QVBoxLayout


def _normalize_phone(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    leading_plus = value.startswith("+")
    digits = re.sub(r"\D", "", value)
    return ("+" if leading_plus else "") + digits


def install_phone_setup_patch() -> None:
    """Patch the setup wizard so first-run setup asks for the owner's phone number."""
    from jarvis.ui import setup_wizard as sw

    if getattr(sw.VoicePage, "_phone_setup_patch_installed", False):
        return

    original_voice_init = sw.VoicePage.__init__
    original_get_config = sw.VoicePage.get_config
    original_write_config = sw.SetupWizard._write_config

    def voice_init(self, parent=None):
        original_voice_init(self, parent)
        layout = self.layout()

        phone_card = QFrame()
        phone_card.setObjectName("card")
        phone_layout = QVBoxLayout(phone_card)
        phone_layout.setContentsMargins(16, 14, 16, 14)
        phone_layout.setSpacing(7)

        title = QLabel("PHONE & REMOTE APPROVALS")
        title.setObjectName("section")
        phone_layout.addWidget(title)

        detail = QLabel(
            "Enter the phone number JARVIS should contact when an owner approval or security alert is needed."
        )
        detail.setObjectName("subtitle")
        detail.setWordWrap(True)
        phone_layout.addWidget(detail)

        self._owner_phone = QLineEdit()
        self._owner_phone.setPlaceholderText("Your phone number, for example +1 555 123 4567")
        self._owner_phone.setInputMask("")
        phone_layout.addWidget(self._owner_phone)

        self._phone_calls = QCheckBox("Allow JARVIS approval calls")
        self._phone_calls.setChecked(True)
        phone_layout.addWidget(self._phone_calls)

        self._phone_texts = QCheckBox("Allow JARVIS approval text notifications")
        self._phone_texts.setChecked(True)
        phone_layout.addWidget(self._phone_texts)

        note = QLabel(
            "No phone-company choice is required here. JARVIS stores the approved destination number and uses the configured phone-line connection when available."
        )
        note.setObjectName("subtitle")
        note.setWordWrap(True)
        phone_layout.addWidget(note)

        # Put the card before the existing stretch so it stays visible in the page.
        insert_at = max(0, layout.count() - 1)
        layout.insertWidget(insert_at, phone_card)

    def get_config(self):
        cfg = original_get_config(self)
        phone = _normalize_phone(self._owner_phone.text()) if hasattr(self, "_owner_phone") else ""
        cfg.update({
            "phone_approvals_enabled": bool(phone),
            "owner_phone": phone,
            "phone_allow_calls": self._phone_calls.isChecked() if hasattr(self, "_phone_calls") else True,
            "phone_allow_texts": self._phone_texts.isChecked() if hasattr(self, "_phone_texts") else True,
        })
        return cfg

    def write_config(self):
        original_write_config(self)
        try:
            path = sw.get_user_config_path()
            data = {}
            if path.exists():
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            data["phone_approvals"] = {
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
            path.write_text(yaml.safe_dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8")

            try:
                from jarvis.ui.settings_store import SettingsStore
                store = SettingsStore()
                settings = store.load()
                settings.setdefault("phone_approvals", {})
                settings["phone_approvals"].update(data["phone_approvals"])
                store.save(settings)
            except Exception as exc:
                logger.warning(f"Could not mirror phone approval settings: {exc}")
        except Exception as exc:
            logger.warning(f"Could not save phone approval setup: {exc}")

    sw.VoicePage.__init__ = voice_init
    sw.VoicePage.get_config = get_config
    sw.SetupWizard._write_config = write_config
    sw.VoicePage._phone_setup_patch_installed = True
