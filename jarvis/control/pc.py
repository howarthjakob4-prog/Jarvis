"""Windows PC control.

Every function returns (ok, message) and never raises, so the brain and UI
can always show the user what happened. pynput is imported lazily so this
module imports fine even when it is not installed.
"""
import os
import subprocess
import sys
import webbrowser

APP_MAP = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
    "paint": "mspaint.exe",
    "command prompt": "cmd.exe",
    "terminal": "wt.exe",
    "settings": "ms-settings:",
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
}


def _pynput():
    try:
        from pynput.keyboard import Controller, Key
    except ImportError as exc:
        raise RuntimeError("Keyboard control needs pynput: pip install pynput") from exc
    return Controller(), Key


def open_app(name):
    """Open an app by name. Returns (ok, message)."""
    target = (name or "").strip()
    if not target:
        return False, "Open what?"
    key = target.lower()
    if key in ("browser", "web browser", "internet"):
        try:
            webbrowser.open("about:blank")
            return True, "Opening your browser."
        except Exception as exc:
            return False, f"Could not open the browser: {exc}"
    program = APP_MAP.get(key, target)
    if sys.platform == "win32":
        try:
            os.startfile(program)  # Windows only: handles exe, URLs, ms-settings:
            return True, f"Opening {target}."
        except OSError:
            pass
        try:
            subprocess.Popen(program, shell=True)
            return True, f"Opening {target}."
        except OSError as exc:
            return False, f"Could not open {target}: {exc}"
    # Non-Windows: best effort (dev machines / tests only).
    for cmd in (["xdg-open", program], ["open", program]):
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, f"Opening {target}."
        except OSError:
            continue
    return False, f"Could not open {target} on this system."


def type_text(text):
    """Type text with the keyboard. Returns (ok, message)."""
    try:
        controller, _ = _pynput()
    except RuntimeError as exc:
        return False, str(exc)
    try:
        controller.type(text or "")
        return True, "Typed."
    except Exception as exc:
        return False, f"Could not type: {exc}"


def press_key(name):
    """Press a key: 'enter', 'space', 'escape', 'tab', or a single character."""
    try:
        controller, Key = _pynput()
    except RuntimeError as exc:
        return False, str(exc)
    name = str(name)
    key = getattr(Key, name.lower(), None)
    if key is None:
        if len(name) == 1:
            key = name
        else:
            return False, f"Unknown key: {name}"
    try:
        controller.press(key)
        controller.release(key)
        return True, f"Pressed {name}."
    except Exception as exc:
        return False, f"Could not press {name}: {exc}"


def _media_key(key_name, label):
    try:
        controller, Key = _pynput()
    except RuntimeError as exc:
        return False, str(exc)
    key = getattr(Key, key_name, None)
    if key is None:
        return False, "Volume keys are not supported on this system."
    try:
        controller.press(key)
        controller.release(key)
        return True, label
    except Exception as exc:
        return False, f"Volume control failed: {exc}"


def volume_up():
    return _media_key("media_volume_up", "Volume up.")


def volume_down():
    return _media_key("media_volume_down", "Volume down.")


def volume_mute():
    return _media_key("media_volume_mute", "Volume muted.")
