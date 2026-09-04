import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from jarvis.models import ToolDefinition
from jarvis.plugins.base import Plugin


class SocialModerationPlugin(Plugin):
    """Local social-safety moderation for JARVIS.

    This module does not scrape or control Snapchat directly. Connectors can pass
    incoming message text into ``evaluate_message`` later. Clear violations are
    recorded as block recommendations so the owner can review or act on them.
    """

    HIGH_RISK_PATTERNS = {
        "sexual_or_explicit": [
            r"\b(send|show|trade)\b.{0,24}\b(nudes?|explicit|naked)\b",
            r"\b(nudes?|explicit pics?|naked pics?)\b",
            r"\b(sex|sexual)\b.{0,20}\b(pic|photo|video|meet)\b",
        ],
        "threat": [
            r"\b(i(?:'ll| will)|im going to|i am going to)\b.{0,28}\b(kill|hurt|attack|beat|shoot|stab)\b",
            r"\b(kill|hurt|attack|beat|shoot|stab) you\b",
        ],
        "scam_or_extortion": [
            r"\b(pay|send)\b.{0,24}\b(money|cash|gift card|bitcoin|crypto)\b",
            r"\bblackmail|extort|leak your|post your private\b",
            r"\bverification code|one[- ]time code|password\b",
        ],
        "harassment": [
            r"\b(i hate you|you should die|go die)\b",
            r"\bworthless|loser|idiot|stupid\b",
        ],
    }

    def __init__(self):
        super().__init__("social_moderation")
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        self.data_dir = Path(appdata) / "JARVIS"
        self.queue_path = self.data_dir / "social_block_recommendations.jsonl"

    async def initialize(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

    async def shutdown(self) -> None:
        pass

    def get_tools(self):
        return [
            (
                ToolDefinition(
                    name="social_moderation_check",
                    description=(
                        "Check a social message for clear inappropriate behavior and, when warranted, "
                        "add the sender to JARVIS's local block-recommendation queue."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "platform": {"type": "string", "description": "Social platform, for example Snapchat"},
                            "sender": {"type": "string", "description": "Display name or account handle"},
                            "message": {"type": "string", "description": "Incoming message text to review"},
                        },
                        "required": ["platform", "sender", "message"],
                    },
                ),
                self.check_message,
            ),
            (
                ToolDefinition(
                    name="social_block_recommendations",
                    description="Show recent JARVIS social block recommendations awaiting review.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "minimum": 1, "maximum": 50}
                        },
                    },
                ),
                self.list_recommendations,
            ),
        ]

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    def evaluate_message(self, platform: str, sender: str, message: str) -> dict:
        text = self._normalize(message)
        hits = []
        for category, patterns in self.HIGH_RISK_PATTERNS.items():
            if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
                hits.append(category)

        # One clear high-risk category is enough for a recommendation. Harassment
        # alone is kept as review-needed unless it contains a direct death wish.
        recommend_block = bool(hits) and not (hits == ["harassment"] and "go die" not in text and "you should die" not in text)
        severity = "high" if recommend_block else ("review" if hits else "clear")

        return {
            "platform": platform.strip() or "unknown",
            "sender": sender.strip() or "unknown",
            "categories": hits,
            "severity": severity,
            "recommend_block": recommend_block,
            "reason": ", ".join(hits) if hits else "no clear violation detected",
        }

    def _append_recommendation(self, result: dict, message: str) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        record = {
            **result,
            "message_excerpt": (message or "")[:240],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "recommended",
        }
        with self.queue_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    async def check_message(self, platform: str, sender: str, message: str, **_) -> str:
        result = self.evaluate_message(platform, sender, message)
        if result["recommend_block"]:
            self._append_recommendation(result, message)
            return (
                f"Block recommended for {result['sender']} on {result['platform']}. "
                f"Reason: {result['reason']}. Added to the local review queue. "
                "JARVIS has not blocked the account automatically because no approved Snapchat control connector is attached."
            )
        if result["categories"]:
            return (
                f"Message from {result['sender']} needs review. Detected: {result['reason']}. "
                "No automatic block was issued."
            )
        return f"No clear block-level violation detected for {result['sender']} on {result['platform']}."

    async def list_recommendations(self, limit: int = 20, **_) -> str:
        limit = max(1, min(int(limit or 20), 50))
        if not self.queue_path.is_file():
            return "There are no social block recommendations in the local JARVIS queue."
        rows = []
        try:
            with self.queue_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
        except Exception as exc:
            return f"JARVIS could not read the social moderation queue: {exc}"
        rows = rows[-limit:]
        if not rows:
            return "There are no social block recommendations in the local JARVIS queue."
        formatted = []
        for row in reversed(rows):
            formatted.append(
                f"{row.get('platform', 'unknown')}: {row.get('sender', 'unknown')} — {row.get('reason', 'review')}"
            )
        return "Recent block recommendations:\n" + "\n".join(formatted)
