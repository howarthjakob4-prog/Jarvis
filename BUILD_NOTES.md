# Jarvis-v2 — build notes (2026-09-16)

Clean-room rebuild. 100% original code, written from scratch for this reset.
Nothing was copied from the old Jarvis repo, the Ultron project, or anywhere else.

## What was built

- `jarvis/config.py` — `config.yaml` defaults + `config/local.yaml` overrides (gitignored).
- `jarvis/voice/speak.py` — TTS. Default engine `sapi` via pyttsx3 (Windows built-in,
  zero-config — this is the #1 fix for "it won't speak at all"). Optional `fish`
  engine: Fish Audio `POST https://api.fish.audio/v1/tts` with `reference_id`,
  WAV response played through `winsound` (Windows stdlib, no audio-player dep).
  `Speaker` wraps engine + on/off toggle; voice and typed input share one speak path.
- `jarvis/voice/listen.py` — Vosk offline STT. `vosk-model-small-en-us-0.15`
  (~40MB) auto-downloads from alphacephei.com on first mic use into `models/`
  (`.ready` sentinel so it never re-downloads). `capture_once()` for push-to-talk,
  `WakeWordListener` thread for "hey jarvis" (opt-in). All third-party imports are
  lazy; missing mic/packages produce clear messages, never crashes.
- `jarvis/brain.py` — offline-first: plugins → small talk → Groq (only with key).
  Without a key it answers time/apps/volume/small talk and says plainly when a
  question needs a Groq key.
- `jarvis/control/pc.py` — `open_app` (`os.startfile` on Windows), `type_text`,
  `press_key`, `volume_up/down/mute` via pynput media keys (no pycaw). Every
  function returns `(ok, message)`, never raises.
- `jarvis/plugins/` — tiny API (`Plugin`: `match`/`run`), auto-loads `*_plugin.py`.
  Ships 3 working examples: `time`, `apps` (open notepad/calculator/browser/...),
  `volume`.
- `jarvis/ui.py` — tkinter (stdlib): conversation log, Push-to-Talk button,
  type-in entry + Send (Return works too), voice on/off toggle, Quit, status bar.
  Listening/speaking run on worker threads; UI updates via `after()`. Every
  control is wired — no decorative buttons.
- `jarvis/setup_wizard.py` — first-run console wizard. All keys optional and
  skippable; ends with a live "Jarvis online." voice test.
- `jarvis/main.py` / `__main__.py` — entry point: speaks "Jarvis online." on boot
  (plus a spoken notice when no mic is found), then opens the UI.
- `JARVIS.bat` — checks python, pip-installs requirements, runs wizard on first
  launch, starts the app.
- `requirements.txt` — pinned (see below).
- `tests/test_smoke.py` — 27 mocked tests, no mic/speaker/network needed.
- `README.md` — honest: lists only what exists today.

## Deliberately left out

- pygame (no Python 3.14 wheel) — Fish Audio playback uses `winsound` instead.
- pycaw for volume — pynput media keys need no extra dep.
- Screenshot control — optional per spec, skipped to keep the reset lean.
- A web/Electron UI — tkinter is stdlib and always works.
- Dozens of plugins — 3 working ones beat 50 dead ones.
- Auto-start / installer EXE — out of scope for the reset; JARVIS.bat is the launcher.
- Wake word defaults to OFF (mic capture costs CPU); enable with `wake_word: true`.

## Exact pip versions (requirements.txt)

| Package | Version | Why this one |
|---|---|---|
| pyttsx3 | 2.99 | latest; pure-Python, SAPI via comtypes on Windows |
| vosk | 0.3.45 | py3-none-win_amd64 wheel (version-agnostic, 3.14-safe) |
| sounddevice | 0.5.6 | py3-none-win_amd64 wheel (bundles PortAudio) |
| pynput | 1.8.2 | latest; pure-Python |
| requests | 2.34.2 | pure-Python |
| pyyaml | 6.0.3 | has cp314-win_amd64 wheel |

Wheel availability verified against the PyPI JSON API on 2026-09-16.
`vosk`/`sounddevice` ship `py3-none-*` wheels, which install on any Python 3,
including 3.14.

## Test results

`python -m pytest tests/ -q` on the Linux build VM: **26/26 pass**
(see test file for the list). Also `py_compile` clean on all 19 source files.

## Panel upgrade (2026-09-18)

The user asked for Jarvis to work like a persistent desktop assistant panel
(voice greeting, news briefing, YouTube music on command, HUD, news ticker,
activity log, listening/speaking states) — plus more. Built:

- `jarvis/ui.py` — redesigned as a persistent panel: always-on-top (toggleable
  via "On top" checkbox, default from `always_on_top`), collapse button ("—"
  hides the conversation log so the panel stays out of the way), LISTENING
  (blue) / SPEAKING (orange) / IDLE (gray) status light, scrolling
  "TOP WORLD NEWS TODAY" ticker (refetches every `ticker_refresh_minutes`,
  default 15), live CPU/RAM/disk monitors (2s refresh, `psutil` added to
  requirements.txt), timestamped activity log (`[HH:MM:SS] You/Jarvis/...`).
  Timer/reminder alerts arrive as spoken + logged + popup (30s auto-dismiss).
  All background threads marshal UI updates through `after()` — they never
  touch tkinter directly.
- `jarvis/main.py` — time-aware boot greeting ("Good morning/afternoon/evening.
  Jarvis online."); wires `brain.alert_handler = ui.announce_alert`.
- `jarvis/news.py` — key-free RSS headline fetcher (BBC, then Google News),
  stdlib only, shared by the news plugin and the ticker.
- `jarvis/monitors.py` — `read_stats()`/`format_stats()`; returns None when
  psutil is missing so the panel degrades to `--%` instead of crashing.
- `jarvis/plugins/base.py` — new optional `bind(brain)` hook (default stores
  the brain); `Brain.__init__` calls it for every plugin, and `Brain.alert()`
  fans out to `alert_handler` for out-of-band announcements.
- New plugins (single small files, same pattern as before):
  `news_plugin.py` ("brief me" → top 5 headlines aloud),
  `music_plugin.py` ("play <song> on youtube" → YouTube search in browser),
  `weather_plugin.py` ("what's the weather in Paris"; Open-Meteo geocoding +
  forecast, no key; `weather_city` default),
  `timer_plugin.py` ("set a timer for 10 minutes", "remind me to ... in 20
  minutes", "list/cancel my timers"; module-level pending registry),
  `schedule_plugin.py` ("what's my schedule today" → pending timers/reminders
  + `config/schedule.yaml` daily plan).
- `config/schedule.yaml` — sample daily plan (clearly-marked examples to delete).
- `config.yaml` / `jarvis/config.py` — new keys: `always_on_top`,
  `ticker_refresh_minutes`, `weather_city`, `schedule_file`.
- `tests/test_panel.py` — 28 mocked tests (RSS parse/fallback/failure, all five
  plugins incl. offline paths, timer fire → alert, schedule file + pending,
  brain bind/alert wiring, daypart/boot_line, monitors formatting, new config
  defaults). Suite: **54/54 pass** on the Linux build VM; `py_compile` clean on
  all source files. Live-verified on the VM: real BBC RSS headlines parse and
  the real Open-Meteo call returns a spoken-format forecast.
- `README.md` — "What it does today" rewritten for the panel feature set.

## 3D design (2026-09-18)

Jarvis designs printable 3D models on voice command — parametric, offline,
stdlib only (math/struct), no new dependencies.

- `jarvis/threed.py` — mesh toolkit: `Mesh` (vertices/faces, translate /
  rotate / scale, merge), primitives (`box`, `cylinder`, `sphere`,
  `lathe` with optional closed-profile stitching for toruses),
  `extrude_annulus` (2D outline + concentric round hole, used by the gear
  and keychain), binary STL exporter (80-byte header + uint32 facet count)
  and text OBJ exporter. All files are written in millimeters; the plugin
  converts spoken cm/inches to mm.
- Parametric catalog (`threed.CATALOG`, each a function returning a closed
  solid — every edge used exactly twice, verified in tests):
  phone stand (base + leaning back plate + lip), desk tray (bottom + four
  walls, 160 x 110 mm), hollow watertight vase (closed lathe profile:
  outer wall, rim, inner wall, floor), gear (trapezoid teeth, parametric
  teeth/diameter/thickness, center hole), keychain (fob disc + hanging
  torus loop), custom box (W x D x H parsed from speech).
- `jarvis/plugins/design_plugin.py` — single-file plugin, named
  `3d_design` so it sorts before the `apps` plugin: otherwise "open the
  design" would reach the app-opener first and try to launch an app
  literally called "design". Handles "design a 3D model of a phone
  stand", "make me a 3D vase", "3d print a gear", "design a box 10 by 5
  by 2 cm" (also "10x5x2cm", inches with `in`/`"`), "a gear with 20
  teeth", "what 3D designs can you make", and "show the design" / "open
  the design" (opens the latest file via `os.startfile` on Windows).
  Unknown requests never fake a model: the reply lists the catalog and
  offers the closest match via difflib ("vaze" → vase).
- Output: `designs/<name>_<timestamp>.stl` + `.obj` next to the project
  folder. The spoken confirmation includes the filename and approximate
  size; the activity log records it through the normal reply path.
- `jarvis/brain.py` — offline capability text and the help text now
  mention 3D design.
- `tests/test_threed.py` — 34 mocked tests: STL header/facet count,
  OBJ vertex/face validity, STL normal sanity, every catalog design
  non-empty and watertight, transforms preserve closedness, all example
  phrases parse to the right design, unknown design suggests the catalog
  and writes nothing, box asks for dimensions when missing, gear teeth
  parsing, open-with-nothing-saved. Suite: **88/88 pass** on the Linux
  build VM; `py_compile` clean.

Example voice commands: "design a 3D model of a phone stand", "make me a
3D vase", "3d print a gear with 16 teeth", "design a box 10 by 5 by 2
centimeters", "what 3D designs can you make", "show the design".

## Future: freeform text-to-3D

This build does parametric designs from a fixed catalog — "describe
anything and get a model" (true text-to-3D) needs a paid AI 3D API key
(e.g. a mesh-generation service) called from a new plugin. Not in this
build; the catalog covers the common printable objects honestly instead
of faking geometry.

## Running it on the PC

Same as before: copy the whole `jarvis-v2` folder to the Windows 11 PC,
double-click **JARVIS.bat** (installs requirements including psutil, runs the
setup wizard on first launch). Optional: set `weather_city: "Your City"` in
`config.yaml`, and edit `config/schedule.yaml` with the real daily plan.
Say "brief me" or "play some jazz on youtube" to try the new skills.

## Future: Google Calendar

"What's my schedule today" deliberately does NOT claim Google Calendar
integration. That needs OAuth (a Google Cloud client + token) set up on the
user's PC — a guided per-machine setup, not something shippable in this
folder. If the user wants it later: add an optional `calendar_plugin.py`
that reads a local token file and calls the Calendar API; keep it behind the
same offline-first rule (works fine without it).

## Could NOT verify on Linux (needs the user's Windows PC)

- The tkinter panel rendering, always-on-top, collapse, ticker scroll,
  monitor labels, and popup on Windows 11 (his eyes needed).
- SAPI speech, mic capture, `os.startfile`, media keys (as before).
- Timer alert speaking through the real SAPI engine from the UI thread.

- Actual SAPI speech out of the speakers (pyttsx3 needs Windows SAPI).
- Fish Audio end-to-end (needs a real key + Windows `winsound`).
- Microphone capture + Vosk model download (no mic on this VM).
- `os.startfile`, media keys, and the tkinter window rendering on Windows 11.
- JARVIS.bat itself (Windows-only).
