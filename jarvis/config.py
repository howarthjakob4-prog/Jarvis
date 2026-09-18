"""Configuration: config.yaml holds defaults, config/local.yaml holds secrets.

local.yaml is gitignored. Anything set there overrides config.yaml.
"""
from pathlib import Path

import yaml

DEFAULTS = {
    # "sapi" = Windows built-in voice, zero-config. "fish" = Fish Audio cloud
    # voice. "elevenlabs" = ElevenLabs cloud voice.
    "tts_engine": "sapi",
    "voice_enabled": True,
    "fish_api_key": "",
    "fish_reference_id": "",
    "fish_model": "s2.1-pro-free",
    # ElevenLabs: key + voice live in config/local.yaml (gitignored), never in git.
    "elevenlabs_api_key": "",
    "elevenlabs_voice_id": "",  # blank = stock default voice
    "elevenlabs_model": "eleven_multilingual_v2",
    # Groq = free-tier AI answers. Empty = offline mode (still fully usable).
    "groq_api_key": "",
    "groq_model": "llama-3.3-70b-versatile",
    # Voice input
    "wake_word": False,
    "wake_phrase": "hey jarvis",
    "mic_timeout": 8,  # seconds per push-to-talk capture
    # Panel (see ui.py)
    "always_on_top": True,   # keep the panel above other windows
    "ticker_refresh_minutes": 15,  # how often the news ticker refetches
    # Weather plugin: default city for "what's the weather" (blank = ask).
    "weather_city": "",
    # Schedule plugin: user-editable daily plan, relative to project root.
    "schedule_file": "config/schedule.yaml",
}


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_config_path() -> Path:
    return project_root() / "config.yaml"


def local_config_path() -> Path:
    return project_root() / "config" / "local.yaml"


def load(default_path=None, local_path=None):
    """Load config. Optional paths exist so tests can use temp files."""
    cfg = dict(DEFAULTS)
    for path in (default_path or default_config_path(),
                 local_path or local_config_path()):
        if path.is_file():
            with open(path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            if isinstance(data, dict):
                cfg.update(data)
    return cfg


def save_local(values, local_path=None):
    """Merge values into config/local.yaml. Returns the path written."""
    path = Path(local_path) if local_path else local_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if path.is_file():
        with open(path, encoding="utf-8") as fh:
            existing = yaml.safe_load(fh) or {}
    existing.update(values)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(existing, fh, default_flow_style=False, sort_keys=True)
    return path
