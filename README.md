# Jarvis-v2

A clean, minimal voice assistant for Windows. A full reset of the old Jarvis:
it talks out of the box, it listens, and every button in the window works.

## What it does today

- **Talks** — Windows built-in voice (SAPI), zero setup. Optional Fish Audio cloud voice.
- **Listens** — offline speech recognition (Vosk, ~40MB model auto-downloads once).
  Push-to-talk button, or say "hey jarvis" (opt-in via `wake_word: true`).
- **No mic?** Still runs — type in the box instead. It tells you that's what's happening.
- **Persistent panel** — always-on-top (toggleable), collapsible, with a
  LISTENING / SPEAKING / IDLE status light, a scrolling "TOP WORLD NEWS TODAY"
  ticker, live CPU/RAM/disk monitors, and a timestamped activity log.
- **Time-aware greeting** — "Good morning/afternoon/evening. Jarvis online."
- **Basic PC control** — open apps ("open notepad"), volume up/down/mute.
- **News briefing** — "brief me" reads the top 5 headlines (key-free RSS).
- **Music** — "play <song> on youtube" opens the YouTube search in your browser.
- **Weather** — "what's the weather in Paris" (key-free Open-Meteo;
  set a default city with `weather_city` in config.yaml).
- **Timers & reminders** — "set a timer for 10 minutes",
  "remind me to take the trash out in 20 minutes". Fires a spoken alert,
  a log entry, and a popup. "list my timers", "cancel my timers".
- **Schedule** — "what's my schedule today" reads your timers/reminders plus
  your own daily plan in `config/schedule.yaml`.
- **3D model design** — "design a 3D model of a phone stand" builds a
  printable mesh and saves STL + OBJ into the `designs/` folder.
  Catalog: phone stand, desk tray, vase, gear (say teeth/diameter),
  keychain, and custom boxes ("a box 10 by 5 by 2 cm").
  "show the design" opens the latest file.
- **9 plugins** — time/date, open apps, volume, news, music, weather,
  timers, schedule, 3D design. Adding one is a single small file.
- **AI answers (optional)** — Groq key for anything beyond the offline skills. Free tier, no card.

Everything above works with zero API keys.

## Install (Windows 11)

1. Install Python 3.12+ from https://www.python.org/downloads/
   (tick **"Add python.exe to PATH"**).
2. Unzip this folder anywhere, double-click **JARVIS.bat**.
3. First run: a setup wizard asks for optional keys (Groq, Fish Audio).
   Press Enter through all of it — offline mode works fine.
4. The Jarvis window opens and says "Jarvis online."

## Keys (all optional)

They go in `config/local.yaml` (created by the wizard, never committed):

```yaml
groq_api_key: "gsk_..."        # AI answers. Free at console.groq.com
fish_api_key: "..."            # cloud voice
fish_reference_id: "..."      # your Fish Audio voice
tts_engine: "fish"            # switch voice from "sapi" to "fish"
```

## Project layout

```
JARVIS.bat            Windows launcher
config.yaml           defaults (safe to read, no secrets)
config/local.yaml     your keys (gitignored)
jarvis/voice/speak.py TTS: SAPI default, Fish Audio optional
jarvis/voice/listen.py Vosk STT, push-to-talk + wake word
jarvis/brain.py       offline brain, Groq when a key is set
jarvis/control/pc.py  open apps, type, keys, volume
jarvis/plugins/       tiny plugin API + 3 working examples
jarvis/ui.py          tkinter window
jarvis/setup_wizard.py first-run console wizard
tests/                mocked smoke tests (pytest)
```

## Running tests

```
pip install -r requirements.txt
python -m pytest tests/ -q
```

No mic, speaker, or network needed — everything is mocked.
