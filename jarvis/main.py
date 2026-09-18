"""Jarvis entry point: wire config -> brain -> voice -> UI."""
from datetime import datetime

from .brain import Brain
from .config import load
from .phonelink import PhoneLink
from .ui import JarvisUI
from .voice.listen import mic_available
from .voice.speak import Speaker


def daypart(hour=None):
    """'morning' / 'afternoon' / 'evening' for the boot greeting."""
    h = datetime.now().hour if hour is None else hour
    if h < 12:
        return "morning"
    if h < 17:
        return "afternoon"
    return "evening"


def boot_line(mic_ok):
    line = f"Good {daypart()}. Jarvis online."
    if not mic_ok:
        line += " No microphone detected. You can type instead."
    return line


def main():
    config = load()
    brain = Brain(config)
    speaker = Speaker(config)
    mic_ok = mic_available()

    print("Jarvis starting…")
    print("Mic:", "ready" if mic_ok else "not found — type-in mode")

    line = boot_line(mic_ok)
    if speaker.enabled and speaker.ok:
        speaker.speak(line)
    elif speaker.error:
        print("Voice unavailable:", speaker.error)

    ui = JarvisUI(brain, speaker, mic_ok, config)
    # Let background work (timers, reminders) announce through the panel:
    # spoken + timestamped in the activity log + popup.
    brain.alert_handler = ui.announce_alert
    ui.log_line("Jarvis", line)
    # Phone link: PC checks in with the phone dashboard (on/off status)
    # and picks up commands like "lock". Best-effort background thread.
    PhoneLink(config, log=lambda msg: ui.log_line("Link", msg)).start()
    ui.run()


if __name__ == "__main__":
    main()
