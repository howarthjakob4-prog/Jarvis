"""Smoke tests. Everything is mocked: no mic, speaker, or network needed."""
import sys
import types

import pytest

# ---- stub pyttsx3 BEFORE importing jarvis.voice.speak ----
fake_pyttsx3 = types.ModuleType("pyttsx3")


class FakeEngine:
    def __init__(self):
        self.said = []

    def say(self, text):
        self.said.append(text)

    def runAndWait(self):
        pass


_fake_engine = FakeEngine()
fake_pyttsx3.init = lambda: _fake_engine
sys.modules["pyttsx3"] = fake_pyttsx3

from jarvis import config as config_mod  # noqa: E402
from jarvis.brain import Brain  # noqa: E402
from jarvis.plugins import load_plugins  # noqa: E402
from jarvis.voice import listen as listen_mod  # noqa: E402
from jarvis.voice.speak import (  # noqa: E402
    ElevenLabsTTS,
    FishTTS,
    SapiTTS,
    Speaker,
    TTSError,
    create_engine,
)


# ----- config ---------------------------------------------------------------

def test_config_defaults_and_local_override(tmp_path):
    default = tmp_path / "config.yaml"
    default.write_text("tts_engine: fish\n")
    local = tmp_path / "local.yaml"
    local.write_text("fish_api_key: secret\n")
    cfg = config_mod.load(default_path=default, local_path=local)
    assert cfg["tts_engine"] == "fish"
    assert cfg["fish_api_key"] == "secret"
    assert cfg["groq_model"] == "llama-3.3-70b-versatile"  # default intact


def test_config_missing_files_uses_defaults(tmp_path):
    cfg = config_mod.load(default_path=tmp_path / "nope.yaml",
                          local_path=tmp_path / "nope2.yaml")
    assert cfg["tts_engine"] == "sapi"
    assert cfg["groq_api_key"] == ""


def test_save_local_roundtrip(tmp_path):
    path = tmp_path / "local.yaml"
    config_mod.save_local({"groq_api_key": "abc"}, local_path=path)
    cfg = config_mod.load(default_path=tmp_path / "nope.yaml", local_path=path)
    assert cfg["groq_api_key"] == "abc"


# ----- brain (offline) -------------------------------------------------------

def _offline_brain():
    return Brain({"groq_api_key": "", "groq_model": "x"})


def test_brain_empty_input():
    assert _offline_brain().respond("") == "I didn't catch that."


def test_brain_time_plugin_answers():
    assert ":" in _offline_brain().respond("what time is it")


def test_brain_greeting():
    assert "hello" in _offline_brain().respond("hello").lower()


def test_brain_help():
    assert "notepad" in _offline_brain().respond("help").lower()


def test_brain_unknown_offline_mentions_key():
    reply = _offline_brain().respond("explain quantum tunneling")
    assert "groq" in reply.lower()


def test_brain_plugin_error_is_reported():
    brain = _offline_brain()

    class BadPlugin:
        name = "bad"

        def match(self, text):
            return True

        def run(self, text):
            raise RuntimeError("boom")

    brain.plugins = [BadPlugin()]
    assert "bad" in brain.respond("anything").lower()


# ----- brain (groq, mocked) --------------------------------------------------

def test_brain_groq_path(monkeypatch):
    class Resp:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "mocked answer"}}]}

    monkeypatch.setattr("jarvis.brain.requests.post", lambda *a, **k: Resp())
    brain = Brain({"groq_api_key": "k", "groq_model": "m"})
    assert brain.respond("explain quantum tunneling") == "mocked answer"


def test_brain_groq_http_error(monkeypatch):
    class Resp:
        status_code = 401
        text = "bad key"

    monkeypatch.setattr("jarvis.brain.requests.post", lambda *a, **k: Resp())
    brain = Brain({"groq_api_key": "k", "groq_model": "m"})
    assert "401" in brain.respond("explain quantum tunneling")


def test_brain_groq_network_failure(monkeypatch):
    import requests as real_requests

    def fail(*a, **k):
        raise real_requests.ConnectionError("down")

    monkeypatch.setattr("jarvis.brain.requests.post", fail)
    brain = Brain({"groq_api_key": "k", "groq_model": "m"})
    assert "couldn't reach groq" in brain.respond("explain quantum tunneling").lower()


# ----- plugins ---------------------------------------------------------------

def test_plugins_autoload():
    names = {p.name for p in load_plugins()}
    assert {"time", "apps", "volume"} <= names


def test_time_plugin_match_and_run():
    plugins = {p.name: p for p in load_plugins()}
    p = plugins["time"]
    assert p.match("what time is it")
    assert not p.match("open notepad")
    assert ":" in p.run("what time is it")
    assert "20" in p.run("what's today's date")  # year contains 20xx


def test_app_plugin_match_and_run(monkeypatch):
    plugins = {p.name: p for p in load_plugins()}
    p = plugins["apps"]
    assert p.match("open notepad")
    assert p.match("launch calculator")
    assert not p.match("hello there")
    monkeypatch.setattr("jarvis.control.pc.open_app",
                        lambda name: (True, f"Opening {name}."))
    assert p.run("open notepad") == "Opening notepad."


def test_volume_plugin_match_and_run(monkeypatch):
    plugins = {p.name: p for p in load_plugins()}
    p = plugins["volume"]
    assert p.match("volume up")
    assert p.match("mute")
    assert not p.match("open notepad")
    monkeypatch.setattr("jarvis.control.pc.volume_up", lambda: (True, "Volume up."))
    assert p.run("volume up") == "Volume up."


# ----- TTS engine selection ---------------------------------------------------

def test_create_engine_sapi_default():
    assert isinstance(create_engine({"tts_engine": "sapi"}), SapiTTS)


def test_create_engine_fish():
    eng = create_engine({"tts_engine": "fish", "fish_api_key": "k",
                         "fish_reference_id": "r", "fish_model": "m"})
    assert isinstance(eng, FishTTS)


def test_create_engine_unknown():
    with pytest.raises(TTSError):
        create_engine({"tts_engine": "bogus"})


def test_create_engine_fish_needs_key():
    with pytest.raises(TTSError):
        create_engine({"tts_engine": "fish", "fish_api_key": ""})


def test_create_engine_elevenlabs():
    eng = create_engine({"tts_engine": "elevenlabs", "elevenlabs_api_key": "k",
                         "elevenlabs_voice_id": "v", "elevenlabs_model": "m"})
    assert isinstance(eng, ElevenLabsTTS)
    assert eng.voice_id == "v"


def test_create_engine_elevenlabs_needs_key():
    with pytest.raises(TTSError):
        create_engine({"tts_engine": "elevenlabs", "elevenlabs_api_key": ""})


def test_create_engine_elevenlabs_default_voice():
    eng = create_engine({"tts_engine": "elevenlabs", "elevenlabs_api_key": "k"})
    assert eng.voice_id  # stock default voice when none configured


class _FakeResp:
    def __init__(self, status_code=200, content=b"", text=""):
        self.status_code = status_code
        self.content = content
        self.text = text


def test_elevenlabs_synthesize_uses_key_header_and_wraps_wav(monkeypatch):
    import wave

    calls = {}

    def fake_post(url, params=None, json=None, headers=None, timeout=None):
        calls["url"] = url
        calls["params"] = params
        calls["json"] = json
        calls["headers"] = headers
        return _FakeResp(200, content=b"\x00\x01" * 8000)  # 16kHz mono PCM

    monkeypatch.setattr("jarvis.voice.speak.requests.post", fake_post)
    eng = ElevenLabsTTS(api_key="sekret", voice_id="voice123")
    wav = eng._synthesize("hello")
    assert "voice123" in calls["url"]
    assert calls["headers"]["xi-api-key"] == "sekret"
    assert calls["params"]["output_format"] == "pcm_16000"
    assert calls["json"]["text"] == "hello"
    assert wav[:4] == b"RIFF"
    with wave.open(__import__("io").BytesIO(wav), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 16000


def test_elevenlabs_http_error_raises(monkeypatch):
    def fake_post(url, params=None, json=None, headers=None, timeout=None):
        return _FakeResp(401, content=b"", text="invalid api key")
    monkeypatch.setattr("jarvis.voice.speak.requests.post", fake_post)
    eng = ElevenLabsTTS(api_key="bad")
    with pytest.raises(TTSError):
        eng._synthesize("hello")


def test_speaker_toggle_mutes():
    _fake_engine.said.clear()
    spk = Speaker({"tts_engine": "sapi", "voice_enabled": False})
    assert spk.ok
    assert spk.speak("hello") is False
    assert _fake_engine.said == []


def test_speaker_speaks_when_enabled():
    _fake_engine.said.clear()
    spk = Speaker({"tts_engine": "sapi", "voice_enabled": True})
    assert spk.speak("hello") is True
    assert _fake_engine.said == ["hello"]


def test_speaker_bad_engine_reports_error():
    spk = Speaker({"tts_engine": "bogus", "voice_enabled": True})
    assert not spk.ok
    assert spk.error
    assert spk.speak("hello") is False
    assert spk.last_error


def test_fish_synthesize_request_shape(monkeypatch):
    captured = {}

    class Resp:
        status_code = 200
        content = b"FAKEWAV"

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return Resp()

    monkeypatch.setattr("jarvis.voice.speak.requests.post", fake_post)
    eng = FishTTS(api_key="k", reference_id="r", model="m")
    assert eng._synthesize("hi", fmt="wav") == b"FAKEWAV"
    assert captured["url"] == "https://api.fish.audio/v1/tts"
    assert captured["json"]["reference_id"] == "r"
    assert captured["json"]["format"] == "wav"
    assert captured["headers"]["Authorization"] == "Bearer k"


# ----- listen module safety ---------------------------------------------------

def test_mic_available_never_raises():
    assert isinstance(listen_mod.mic_available(), bool)


def test_listen_module_imports_without_third_party():
    assert hasattr(listen_mod, "capture_once")
    assert hasattr(listen_mod, "WakeWordListener")
