from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from jarvis.models import ToolDefinition
from jarvis.plugins.base import Plugin


@dataclass
class ModerationDecision:
    action: str
    reason: str


class SnapchatGuardPlugin(Plugin):
    """Owner-only Snapchat safety guard.

    This plugin does not store Snapchat credentials and does not bypass login,
    CAPTCHA, or device security. It operates only in an already-authenticated
    Snapchat Web session that the owner has opened in JARVIS' browser.
    """

    def __init__(self):
        super().__init__("snapchat_guard")

    async def initialize(self) -> None:
        logger.info("Snapchat safety guard loaded")

    async def shutdown(self) -> None:
        pass

    def get_tools(self):
        return [
            (
                ToolDefinition(
                    name="snapchat_guard_status",
                    description="Check whether the JARVIS Snapchat safety guard is available.",
                    parameters={"type": "object", "properties": {}},
                ),
                self.status,
            ),
            (
                ToolDefinition(
                    name="snapchat_review_text",
                    description=(
                        "Classify a Snapchat message for owner safety. Clearly sexual harassment, "
                        "threats, coercion, scams, or repeated abusive contact can be marked BLOCK."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "message": {"type": "string"},
                        },
                        "required": ["message"],
                    },
                ),
                self.review_text,
            ),
            (
                ToolDefinition(
                    name="snapchat_block_current_contact",
                    description=(
                        "Block the currently open Snapchat Web contact when the owner has already "
                        "signed in. Does not enter credentials or bypass Snapchat security."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "reason": {"type": "string"},
                        },
                    },
                ),
                self.block_current_contact,
            ),
        ]

    async def status(self, **_) -> str:
        return (
            "Snapchat Guard is installed. It can review text and can block the currently open "
            "contact in an already-authenticated Snapchat Web session. It will never store your "
            "Snapchat password or bypass login/security checks."
        )

    @staticmethod
    def _decision(message: str) -> ModerationDecision:
        text = " ".join(str(message or "").casefold().split())
        if not text:
            return ModerationDecision("ALLOW", "empty message")

        severe = (
            "kill yourself", "i will kill you", "i'm going to kill you", "im going to kill you",
            "send nudes", "send nude", "show me naked", "show your body",
            "i know where you live", "i'll hurt you", "ill hurt you",
            "give me your password", "send me your password", "verification code",
        )
        abusive = (
            "slut", "whore", "bitch", "fuck you", "stupid idiot",
        )
        scam = (
            "send me money", "cashapp me", "gift card code", "crypto wallet",
            "click this link to verify", "account will be deleted",
        )

        if any(term in text for term in severe):
            return ModerationDecision("BLOCK", "clear threat, sexual coercion, or credential abuse")
        if any(term in text for term in scam):
            return ModerationDecision("BLOCK", "likely scam or account-takeover attempt")
        if any(term in text for term in abusive):
            return ModerationDecision("REVIEW", "abusive or harassing language")
        return ModerationDecision("ALLOW", "no clear blocking trigger detected")

    async def review_text(self, message: str, **_) -> str:
        d = self._decision(message)
        return f"Snapchat Guard: {d.action}. Reason: {d.reason}."

    async def block_current_contact(self, reason: str = "owner safety", **_) -> str:
        try:
            from jarvis.brain.browser_agent import get_browser_agent
            agent = get_browser_agent(headless=False)
            if not agent.ready:
                await agent.start()
            if "snapchat.com" not in agent.current_url.casefold():
                return (
                    "Open Snapchat Web in JARVIS' browser and sign in yourself first. "
                    "JARVIS will not enter or store your Snapchat credentials."
                )

            page = agent._page
            if page is None:
                return "Snapchat browser page is unavailable."

            # Snapchat Web changes its DOM frequently. Use visible labels instead of brittle IDs.
            menu_candidates = [
                "button[aria-label*='More']",
                "button[aria-label*='Menu']",
                "button:has-text('More')",
            ]
            clicked = False
            for selector in menu_candidates:
                try:
                    if await page.locator(selector).count():
                        await page.locator(selector).first.click(timeout=3000)
                        clicked = True
                        break
                except Exception:
                    continue
            if not clicked:
                return "I could not find Snapchat's contact menu. Snapchat Web may have changed its layout."

            block_candidates = [
                "text=Block",
                "button:has-text('Block')",
                "[role='menuitem']:has-text('Block')",
            ]
            for selector in block_candidates:
                try:
                    loc = page.locator(selector)
                    if await loc.count():
                        await loc.first.click(timeout=3000)
                        # Confirm only when Snapchat shows an explicit Block confirmation.
                        confirm = page.locator("button:has-text('Block')")
                        if await confirm.count():
                            try:
                                await confirm.last.click(timeout=3000)
                            except Exception:
                                pass
                        logger.info("Snapchat contact blocked by owner safety guard: {}", reason[:120])
                        return f"Blocked the current Snapchat contact. Reason: {reason[:200]}"
                except Exception:
                    continue
            return "I opened the Snapchat contact menu but could not find the Block action."
        except Exception as exc:
            logger.warning(f"Snapchat block attempt failed: {exc}")
            return f"Snapchat Guard could not block the current contact: {exc}"
