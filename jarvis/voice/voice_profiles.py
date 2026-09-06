from copy import deepcopy

# Voice profiles used by the desktop assistant.
#
# JARVIS now uses Kokoro's bm_george British male voice locally. This avoids
# depending on a celebrity/actor voice clone and gives JARVIS a consistent
# British assistant voice that can be packaged under permissive licenses.
#
# Other built-in profiles continue to use Microsoft Neural voices through
# edge-tts. Edge TTS pitch MUST be integer Hz (for example +0Hz or -5Hz).
_VOICE_PROFILES = [
    {
        "id": "jarvis",
        "label": "JARVIS — British male, calm & authoritative",
        "description": (
            "Local Kokoro British male voice with a measured, technical assistant tone. "
            "Runs locally after its one-time voice-model download."
        ),
        "voice": "kokoro:bm_george",
        "rate": "+5%",
        "pitch": "+0Hz",
    },
    {
        "id": "friday",
        "label": "FRIDAY — Irish, warm & conversational",
        "description": (
            "Irish accent with a lighter register and conversational delivery. "
            "Great for everyday assistant tasks."
        ),
        "voice": "en-IE-EmilyNeural",
        "rate": "+8%",
        "pitch": "+0Hz",
    },
    {
        "id": "atlas",
        "label": "Atlas — deep American male, analytical",
        "description": (
            "Deep broadcast-quality American voice. Calm, deliberate cadence suits "
            "mission-critical or system-status announcements."
        ),
        "voice": "en-US-BrianNeural",
        "rate": "-5%",
        "pitch": "-8Hz",
    },
    {
        "id": "nova",
        "label": "Nova — warm American female, friendly",
        "description": (
            "Natural, articulate, approachable American female voice for general use."
        ),
        "voice": "en-US-JennyNeural",
        "rate": "+0%",
        "pitch": "+2Hz",
    },
    {
        "id": "sage",
        "label": "Sage — British female, precise & composed",
        "description": (
            "Clear British female voice. Professional and composed; works well for "
            "documents, summaries, and formal reports."
        ),
        "voice": "en-GB-SoniaNeural",
        "rate": "+0%",
        "pitch": "-3Hz",
    },
    {
        "id": "aria",
        "label": "Aria — neutral US, fast & clear",
        "description": (
            "Speed-optimised neutral American voice with high clarity for quick responses."
        ),
        "voice": "en-US-AnaNeural",
        "rate": "+18%",
        "pitch": "+0Hz",
    },
]

_DEFAULT_CUSTOM_PROFILE = {
    "id": "custom",
    "label": "Custom imported profile",
    "description": "User-configured custom voice profile.",
    "voice": "en-US-EricNeural",
    "rate": "-2%",
    "pitch": "+0Hz",
}


def builtin_voice_profiles(custom_profile: dict | None = None) -> list[dict]:
    profiles = [deepcopy(profile) for profile in _VOICE_PROFILES]
    profiles.append(normalize_custom_profile(custom_profile))
    return profiles


def get_voice_profile(profile_id: str, custom_profile: dict | None = None) -> dict:
    if profile_id == "custom":
        return normalize_custom_profile(custom_profile)

    for profile in _VOICE_PROFILES:
        if profile["id"] == profile_id:
            return deepcopy(profile)
    return deepcopy(_VOICE_PROFILES[0])


def normalize_custom_profile(profile: dict | None) -> dict:
    merged = deepcopy(_DEFAULT_CUSTOM_PROFILE)
    if profile:
        merged.update({key: value for key, value in profile.items() if value not in (None, "")})
    merged["id"] = "custom"
    return merged
