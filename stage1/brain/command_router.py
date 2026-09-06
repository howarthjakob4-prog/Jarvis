"""
Every piece of text Jarvis receives (typed or transcribed) comes through
here. Built-in handlers cover Stage 1 (open <app>, list <folder>, read
<file>); anything else falls through to the AI backend if configured, or
a clear "not configured" message if not.

To add a Stage 2+ capability: call register_command() with a predicate and
a handler, rather than editing the built-ins below. Handlers are tried in
registration order; built-ins are registered first so new commands can
override or extend behavior by matching more specific patterns first if
they're registered before the fallback.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from apps.app_launcher import launch_app
from core.errors import AIBackendError, AppLaunchError, JarvisError, PermissionDeniedError, error_bus
from files.file_access import list_folder, read_text_file


@dataclass
class CommandResult:
    text: str
    should_speak: bool = True


Predicate = Callable[[str], bool]
Handler = Callable[[str], CommandResult]

_registered: list[tuple[Predicate, Handler]] = []


def register_command(predicate: Predicate, handler: Handler) -> None:
    _registered.append((predicate, handler))


# ---------- Stage 1 built-in commands ----------

_OPEN_APP_RE = re.compile(r"^\s*open\s+(.+?)\s*$", re.IGNORECASE)
_LIST_FOLDER_RE = re.compile(r"^\s*(?:list|show)\s+(?:files in\s+)?(.+?)\s*$", re.IGNORECASE)
_READ_FILE_RE = re.compile(r"^\s*read\s+(.+?)\s*$", re.IGNORECASE)


def _handle_open_app(text: str) -> CommandResult:
    match = _OPEN_APP_RE.match(text)
    app_name = match.group(1)
    try:
        launch_app(app_name)
        return CommandResult(f"Opening {app_name}.")
    except AppLaunchError as e:
        return CommandResult(e.message, should_speak=True)


def _handle_list_folder(text: str) -> CommandResult:
    match = _LIST_FOLDER_RE.match(text)
    folder = match.group(1)
    try:
        entries = list_folder(folder)
        if not entries:
            return CommandResult(f"'{folder}' is empty.")
        preview = ", ".join(entries[:20])
        more = f" (+{len(entries) - 20} more)" if len(entries) > 20 else ""
        return CommandResult(f"Contents of '{folder}': {preview}{more}")
    except PermissionDeniedError as e:
        return CommandResult(e.message)
    except JarvisError as e:
        return CommandResult(e.message)


def _handle_read_file(text: str) -> CommandResult:
    match = _READ_FILE_RE.match(text)
    path = match.group(1)
    try:
        content = read_text_file(path)
        snippet = content if len(content) < 1000 else content[:1000] + "...[truncated for chat]"
        return CommandResult(snippet, should_speak=False)
    except JarvisError as e:
        return CommandResult(e.message)


register_command(lambda t: bool(_OPEN_APP_RE.match(t)), _handle_open_app)
register_command(lambda t: bool(_LIST_FOLDER_RE.match(t)), _handle_list_folder)
register_command(lambda t: bool(_READ_FILE_RE.match(t)), _handle_read_file)


# ---------- fallback: AI backend for open-ended Q&A ----------
def _handle_ai_fallback(text: str) -> CommandResult:
    from brain.ai_backend import AIBackend
    try:
        backend = AIBackend()
        reply = backend.ask(text)
        return CommandResult(reply)
    except AIBackendError as e:
        return CommandResult(
            f"I can't answer that yet — {e.message}"
        )


def route(text: str) -> CommandResult:
    text = text.strip()
    if not text:
        return CommandResult("I didn't catch anything.", should_speak=False)
    for predicate, handler in _registered:
        if predicate(text):
            try:
                return handler(text)
            except Exception as e:
                err = JarvisError(module="command_router", message=f"Command handling failed: {e}")
                error_bus.report(err)
                return CommandResult(f"Something went wrong handling that: {e}")
    return _handle_ai_fallback(text)
