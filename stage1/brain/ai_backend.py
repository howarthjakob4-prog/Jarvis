"""
Wraps the Anthropic API for free-form Q&A. Fully optional — if no API key
is configured, callers get a clear AIBackendError instead of a fake reply.
This module never receives file contents or paths unless the calling code
in command_router.py explicitly passes them in (and that code only does so
for paths that already passed permission_manager).
"""
from __future__ import annotations

import os

from core.errors import AIBackendError, error_bus
from core.settings_manager import settings


class AIBackend:
    def __init__(self):
        self._client = None
        self._model = settings.get("ai_backend", "model", default="claude-sonnet-4-6")

    def _ensure_client(self):
        if self._client is not None:
            return
        if not settings.get("features", "ai_backend", default=False):
            raise AIBackendError(
                module="ai_backend",
                message="The AI backend feature is turned off in Settings > Connected Features.",
            )
        env_var = settings.get("ai_backend", "api_key_env_var", default="ANTHROPIC_API_KEY")
        api_key = os.environ.get(env_var)
        if not api_key:
            raise AIBackendError(
                module="ai_backend",
                message=f"No API key found in the {env_var} environment variable. "
                         f"Set it and restart Jarvis, or turn off AI backend in Settings.",
            )
        try:
            import anthropic
        except ImportError as e:
            raise AIBackendError(
                module="ai_backend",
                message=f"The 'anthropic' package is not installed ({e}). Run: pip install anthropic",
            )
        self._client = anthropic.Anthropic(api_key=api_key)

    def ask(self, prompt: str, system: str | None = None) -> str:
        self._ensure_client()
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=system or "You are Jarvis, a concise personal desktop assistant.",
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(block.text for block in response.content if block.type == "text")
        except Exception as e:
            err = AIBackendError(module="ai_backend", message=f"AI request failed: {e}")
            error_bus.report(err)
            raise err
