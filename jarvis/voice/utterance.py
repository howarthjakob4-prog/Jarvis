import re


def is_meaningful_transcript(text: str, min_alnum: int = 2) -> bool:
    """Ignore empty/noise transcripts before they reach JARVIS."""
    t = text.strip()
    if not t:
        return False
    alnum = sum(1 for c in t if c.isalnum())
    return alnum >= min_alnum


def extract_command_from_transcript(
    transcript: str,
    wake_phrase: str,
    require_wake_phrase: bool,
) -> str:
    """Return the command after a supported JARVIS wake phrase.

    Besides the configured phrase, accept natural variants such as
    "Hi Jarvis", "Hello Jarvis", and just "Jarvis" so the assistant does
    not appear unresponsive when the user greets it naturally.
    """
    cleaned = " ".join(transcript.strip().split())
    if not cleaned:
        return ""

    if not require_wake_phrase:
        return cleaned

    tokens = _normalize_tokens(cleaned)
    wake_tokens = _normalize_tokens(wake_phrase)
    if not tokens or not wake_tokens:
        return ""

    name = wake_tokens[-1]
    aliases = [
        wake_tokens,
        ["hey", name],
        ["hi", name],
        ["hello", name],
        [name],
    ]

    # Longest aliases first prevents the single-name alias from matching before
    # "hey jarvis" / "hi jarvis".
    aliases.sort(key=len, reverse=True)
    for alias in aliases:
        index = _find_subsequence(tokens, alias)
        if index == -1:
            continue
        command_tokens = tokens[index + len(alias):]
        return " ".join(command_tokens).strip()

    return ""


def is_wake_only_transcript(transcript: str, wake_phrase: str) -> bool:
    """True when the user only greeted/woke JARVIS without giving a command."""
    tokens = _normalize_tokens(transcript)
    wake_tokens = _normalize_tokens(wake_phrase)
    if not tokens or not wake_tokens:
        return False
    name = wake_tokens[-1]
    aliases = [wake_tokens, ["hey", name], ["hi", name], ["hello", name], [name]]
    return any(tokens == alias for alias in aliases)


def _normalize_tokens(text: str) -> list[str]:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return [token for token in normalized.split() if token]


def _find_subsequence(tokens: list[str], needle: list[str]) -> int:
    limit = len(tokens) - len(needle) + 1
    for index in range(max(limit, 0)):
        if tokens[index:index + len(needle)] == needle:
            return index
    return -1
