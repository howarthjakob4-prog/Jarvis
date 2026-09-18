"""First-run console wizard. Everything is optional — offline mode works with no keys."""
from .config import load, save_local


def run():
    print("=== Jarvis setup ===")
    print("Jarvis works with zero keys: offline answers, Windows voice, mic or typing.")
    print("Keys only unlock extras. All are optional — press Enter to skip.\n")

    groq = input("Groq API key for AI answers (free at console.groq.com, Enter to skip): ").strip()
    fish = input("Fish Audio API key for a cloud voice (Enter to skip): ").strip()

    updates = {}
    if groq:
        updates["groq_api_key"] = groq
    if fish:
        updates["fish_api_key"] = fish
        updates["tts_engine"] = "fish"
        ref = input("Fish Audio voice reference ID (Enter for default): ").strip()
        if ref:
            updates["fish_reference_id"] = ref
    if updates:
        path = save_local(updates)
        print(f"Saved to {path}")
    else:
        print("No keys saved — running offline.")

    from .voice.speak import Speaker

    speaker = Speaker(load())
    print("\nTesting voice: you should hear 'Jarvis online' now.")
    if speaker.ok:
        speaker.speak("Jarvis online.")
        print("If you heard it, voice works. If not, check your speakers.")
    else:
        print(f"Voice unavailable: {speaker.error}")
        print("Typing still works.")


if __name__ == "__main__":
    run()
