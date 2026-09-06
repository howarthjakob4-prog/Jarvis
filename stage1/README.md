# Jarvis — Personal Desktop Assistant

A modular, permission-first desktop assistant. Built in stages so new
capabilities (project assistance, 3D design tools, tablet support) can be
added later without rewriting the core.

## Important — read before running

This was written and organized in a sandboxed environment with no internet
access and no display, so **it has not been executed or tested on a real
machine**. It's built from well-established library APIs, but you should
expect to hit a few setup issues (missing system dependency, a model file
that needs downloading, a microphone device index that needs picking) the
first time you run it on your Windows machine. The app is built to fail
loudly with a specific message in the UI and the log file when something
isn't working — it will never silently pretend a feature succeeded — so if
something's wrong you'll see exactly what and where.

## Stage 1 (this delivery)

- Clean desktop GUI (PySide6): chat log + text input + mic button + status bar
- Voice input: offline speech-to-text (faster-whisper, runs locally)
- Voice output: offline text-to-speech (pyttsx3 by default — reliable,
  built on Windows' own SAPI5 voices; optional upgrade path to Piper for a
  more natural neural voice, see "Upgrading voice quality" below)
- Wake word: offline wake-word detection (openWakeWord) with a manual
  "hold to talk" button as a guaranteed fallback if the wake model fails
  to load
- Text chat that works independently of voice
- **Permission system**: Jarvis cannot read, write, or list any file or
  folder you have not explicitly approved. There is no background
  scanning of your drive, ever. See "Permissions" below.
- App launching, restricted to an explicit approved-apps list
- Centralized error/status system: every module reports failures to the
  same place, so the UI always shows real state, never a fake "done"

## Not in Stage 1 (coming in later stages, scaffolded but not built out)

- Full project-assistance workflows (`brain/command_router.py` has the
  extension point)
- 3D design assistance (stub module noted in `STAGES.md`)
- Tablet support
- Deeper development-task assistance (running builds, git operations, etc.)

## Windows quick start

1. Install Python 3.11.
2. Double-click `SETUP_WINDOWS.bat`.
3. When setup finishes, double-click `RUN_JARVIS.bat`.
4. The first speech-to-text/wake-word setup may download model files once.

The batch files keep dependencies inside `.venv`, so they do not overwrite your
system Python packages. If startup fails, Jarvis leaves the real error visible
and writes details to `logs/jarvis.log`.

## Manual setup

1. Install Python 3.11 (3.11 has the widest wheel support for these
   packages on Windows; 3.12+ may work but isn't what this was written
   against).
2. `cd jarvis`
3. `python -m venv venv && venv\Scripts\activate`
4. `pip install -r requirements.txt`
5. First run will download a small Whisper model (~150MB, `base.en`) and
   an openWakeWord model on first use — this needs internet once, then
   works offline.
6. `python main.py`

## Permissions — how they actually work

Nothing in `files/file_access.py` touches disk without first calling
`PermissionManager.is_approved(path)`. Approved paths live in
`config/permissions.json`, edited only through the Settings window (or by
hand-editing that file). There is no "approve my whole C: drive" shortcut
in the UI on purpose — you add folders one at a time, and you can revoke
any of them instantly. If Jarvis (or a future feature) tries to touch a
path outside that list, it gets a `PermissionDeniedError`, and you'll see
that denial in the chat log, not silence.

## Configuring the AI backend (for Q&A / natural-language commands)

Stage 1 ships with a `brain/ai_backend.py` wrapper for the Claude API,
used to interpret free-form questions and commands. It's fully optional:
without an API key configured in Settings, Jarvis still works for voice
control, file access within approved folders, and app launching — it will
just tell you plainly that AI-backed Q&A isn't configured, rather than
guessing.

## Upgrading voice quality (Piper, optional)

`voice/tts_engine.py` is written against a `TTSBackend` interface.
pyttsx3 is the default because it needs zero extra setup. If you want a
more natural neural voice, install Piper separately and download a voice
model, then point `settings.json` -> `voice.tts_backend` to `"piper"` and
`voice.piper_model_path` to the `.onnx` file. The code path exists
(`PiperTTS` class) but treat it as the thing most likely to need a small
fix once you're on real hardware, since it depends on the exact Piper
release you install.

## Project layout

```
jarvis/
  main.py                 entry point
  core/                   settings, permissions, error/event plumbing
  voice/                  STT, TTS, wake word, orchestration
  brain/                  AI backend + command routing
  files/                  the ONLY code path allowed to touch disk
  apps/                   the ONLY code path allowed to launch programs
  ui/                     PySide6 windows
  config/                 settings.json, permissions.json (created on first run)
```

See `STAGES.md` for the full feature roadmap and what's stubbed vs built.
