"""Panel-upgrade tests. Everything is mocked: no mic, speaker, or network."""
import pytest

from jarvis import monitors as monitors_mod
from jarvis import news as news_mod
from jarvis.brain import Brain
from jarvis.main import boot_line, daypart
from jarvis.news import NewsError, fetch_headlines
from jarvis.plugins import load_plugins
from jarvis.plugins import timer_plugin as timer_mod

RSS = """<?xml version="1.0"?>
<rss><channel>
<item><title>Headline One</title></item>
<item><title>Headline Two</title></item>
<item><title>Headline Three</title></item>
</channel></rss>"""


class FakeResp:
    def __init__(self, data):
        self._data = data

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _brain(**over):
    cfg = {"groq_api_key": "", "groq_model": "x"}
    cfg.update(over)
    return Brain(cfg)


@pytest.fixture(autouse=True)
def _clean_timers():
    timer_mod._pending.clear()
    yield
    for p in list(timer_mod._pending):
        try:
            p["timer"].cancel()
        except Exception:
            pass
    timer_mod._pending.clear()


# ----- news helper ------------------------------------------------------------

def test_fetch_headlines_parses_rss(monkeypatch):
    monkeypatch.setattr(news_mod, "urlopen",
                        lambda req, timeout=None: FakeResp(RSS.encode()))
    assert fetch_headlines(limit=2) == ["Headline One", "Headline Two"]


def test_fetch_headlines_falls_back_to_second_feed(monkeypatch):
    calls = []

    def fake(req, timeout=None):
        calls.append(req.full_url)
        if "bbci" in req.full_url:
            raise OSError("down")
        return FakeResp(RSS.encode())

    monkeypatch.setattr(news_mod, "urlopen", fake)
    assert fetch_headlines(limit=1) == ["Headline One"]
    assert len(calls) == 2


def test_fetch_headlines_raises_when_all_fail(monkeypatch):
    def boom(req, timeout=None):
        raise OSError("down")

    monkeypatch.setattr(news_mod, "urlopen", boom)
    with pytest.raises(NewsError):
        fetch_headlines()


# ----- news plugin ------------------------------------------------------------

def test_news_plugin(monkeypatch):
    p = {x.name: x for x in load_plugins()}["news"]
    assert p.match("brief me")
    assert p.match("what are the headlines")
    assert not p.match("open notepad")
    monkeypatch.setattr("jarvis.plugins.news_plugin.fetch_headlines",
                        lambda limit=5: [f"H{i}" for i in range(1, 6)])
    reply = p.run("brief me")
    assert "1. H1" in reply and "5. H5" in reply


def test_news_plugin_offline_message(monkeypatch):
    p = {x.name: x for x in load_plugins()}["news"]

    def boom(limit=5):
        raise NewsError("nope")

    monkeypatch.setattr("jarvis.plugins.news_plugin.fetch_headlines", boom)
    assert "couldn't fetch" in p.run("brief me").lower()


# ----- music plugin -----------------------------------------------------------

def test_music_plugin(monkeypatch):
    p = {x.name: x for x in load_plugins()}["music"]
    assert p.match("play bohemian rhapsody on youtube")
    assert p.match("play some jazz")
    assert not p.match("open notepad")
    opened = []
    monkeypatch.setattr("jarvis.plugins.music_plugin.webbrowser.open",
                        lambda url: opened.append(url))
    reply = p.run("play bohemian rhapsody on youtube")
    assert "bohemian rhapsody" in reply.lower()
    assert opened and "youtube.com/results" in opened[0]
    assert "bohemian+rhapsody" in opened[0]
    assert "on+youtube" not in opened[0].split("search_query=")[1]


# ----- weather plugin ---------------------------------------------------------

def _fake_weather_get(url, params=None, timeout=None):
    class R:
        def json(self):
            if "geocoding" in url:
                return {"results": [{"name": "Paris", "country": "France",
                                     "latitude": 48.85, "longitude": 2.35}]}
            return {"current": {"temperature_2m": 72.4, "weather_code": 1,
                                "wind_speed_10m": 8.0}}

    return R()


def test_weather_plugin_with_city(monkeypatch):
    brain = _brain(weather_city="")
    p = brain.get_plugin("weather")
    assert p.match("what's the weather in paris")
    monkeypatch.setattr("jarvis.plugins.weather_plugin.requests.get",
                        _fake_weather_get)
    reply = p.run("what's the weather in paris")
    assert "Paris" in reply and "72" in reply


def test_weather_plugin_default_city(monkeypatch):
    brain = _brain(weather_city="Austin")
    p = brain.get_plugin("weather")
    monkeypatch.setattr("jarvis.plugins.weather_plugin.requests.get",
                        _fake_weather_get)
    assert "72" in p.run("what's the weather")


def test_weather_plugin_no_city_no_default():
    brain = _brain(weather_city="")
    p = brain.get_plugin("weather")
    assert "which city" in p.run("what's the weather").lower()


def test_weather_plugin_time_word_falls_back_to_default(monkeypatch):
    brain = _brain(weather_city="Austin")
    p = brain.get_plugin("weather")
    monkeypatch.setattr("jarvis.plugins.weather_plugin.requests.get",
                        _fake_weather_get)
    assert "72" in p.run("what's the weather in the morning")


def test_weather_plugin_unknown_city(monkeypatch):
    brain = _brain()

    class R:
        def json(self):
            return {"results": []}

    monkeypatch.setattr("jarvis.plugins.weather_plugin.requests.get",
                        lambda *a, **k: R())
    assert "couldn't find" in brain.get_plugin("weather").run(
        "what's the weather in nowhereville").lower()


def test_weather_plugin_offline(monkeypatch):
    import requests as real_requests
    brain = _brain()

    def fail(*a, **k):
        raise real_requests.ConnectionError("down")

    monkeypatch.setattr("jarvis.plugins.weather_plugin.requests.get", fail)
    assert "offline" in brain.get_plugin("weather").run(
        "what's the weather in paris").lower()


# ----- timer plugin -----------------------------------------------------------

class FakeTimer:
    def __init__(self, delay, fn, args=()):
        self.delay = delay
        self.fn = fn
        self.args = args
        self.daemon = False
        self.cancelled = False

    def start(self):
        if not self.cancelled:
            self.fn(*self.args)

    def cancel(self):
        self.cancelled = True


@pytest.fixture()
def fake_timer(monkeypatch):
    monkeypatch.setattr(timer_mod, "Timer", FakeTimer)
    return FakeTimer


def test_timer_set_and_fire(fake_timer):
    brain = _brain()
    alerts = []
    brain.alert_handler = alerts.append
    p = brain.get_plugin("timer")
    assert p.match("set a timer for 10 minutes")
    reply = p.run("set a timer for 10 minutes")
    assert "10 minutes" in reply
    assert len(alerts) == 1 and "timer is up" in alerts[0].lower()


def test_reminder_set_and_fire(fake_timer):
    brain = _brain()
    alerts = []
    brain.alert_handler = alerts.append
    p = brain.get_plugin("timer")
    assert p.match("remind me to take the trash out in 20 minutes")
    reply = p.run("remind me to take the trash out in 20 minutes")
    assert "trash" in reply.lower()
    assert alerts and "take the trash out" in alerts[0]


def test_timer_list_and_cancel(monkeypatch):
    created = []

    class NoFireTimer(FakeTimer):
        def start(self):
            created.append(self)

    monkeypatch.setattr(timer_mod, "Timer", NoFireTimer)
    brain = _brain()
    p = brain.get_plugin("timer")
    p.run("set a timer for 5 minutes")
    assert "5 minutes" in p.run("list my timers")
    assert "cancelled 1 timer" in p.run("cancel my timers").lower()
    assert "no timers" in p.run("list my timers").lower()


def test_timer_does_not_steal_other_intents():
    brain = _brain()
    p = brain.get_plugin("timer")
    assert not p.match("what time is it")
    assert not p.match("open notepad")


# ----- schedule plugin --------------------------------------------------------

def test_schedule_plugin_with_file_and_timers(monkeypatch, tmp_path):
    sched = tmp_path / "schedule.yaml"
    sched.write_text('- time: "09:00"\n  event: "Standup"\n')
    brain = _brain(schedule_file=str(sched))
    p = brain.get_plugin("schedule")
    assert p.match("what's my schedule today")
    from datetime import datetime as _dt
    monkeypatch.setattr(timer_mod, "list_pending",
                        lambda: [(_dt.now(), "Reminder: call mom")])
    reply = p.run("what's my schedule today")
    assert "Standup" in reply and "call mom" in reply


def test_schedule_plugin_empty():
    brain = _brain(schedule_file="/nonexistent/schedule.yaml")
    p = brain.get_plugin("schedule")
    assert "nothing on your schedule" in p.run("what's my schedule").lower()


# ----- brain wiring -----------------------------------------------------------

def test_plugins_bound_to_brain():
    brain = _brain()
    names = {p.name for p in brain.plugins}
    assert {"news", "music", "weather", "timer", "schedule"} <= names
    assert brain.get_plugin("weather").brain is brain


def test_brain_alert_calls_handler():
    brain = _brain()
    got = []
    brain.alert_handler = got.append
    brain.alert("hello")
    assert got == ["hello"]


def test_brain_alert_without_handler_is_safe():
    _brain().alert("hello")  # must not raise


def test_new_intents_reachable_through_brain(monkeypatch, fake_timer):
    brain = _brain(weather_city="Austin")
    monkeypatch.setattr("jarvis.plugins.weather_plugin.requests.get",
                        _fake_weather_get)
    monkeypatch.setattr("jarvis.plugins.music_plugin.webbrowser.open",
                        lambda url: True)
    assert "72" in brain.respond("what's the weather")
    assert "youtube" in brain.respond("play some jazz on youtube").lower()


def test_existing_intents_still_work():
    brain = _brain()
    assert ":" in brain.respond("what time is it")
    assert "notepad" in brain.respond("help").lower()


# ----- greeting -----------------------------------------------------------------

def test_daypart():
    assert daypart(9) == "morning"
    assert daypart(14) == "afternoon"
    assert daypart(20) == "evening"


def test_boot_line_is_time_aware():
    assert boot_line(mic_ok=True).startswith("Good ")
    assert "Jarvis online." in boot_line(mic_ok=True)
    assert "type instead" in boot_line(mic_ok=False)


# ----- monitors -----------------------------------------------------------------

def test_format_stats():
    assert "CPU 12%" in monitors_mod.format_stats({"cpu": 12, "ram": 34, "disk": 56})
    assert "--" in monitors_mod.format_stats(None)


def test_read_stats_without_psutil(monkeypatch):
    import sys
    monkeypatch.delitem(sys.modules, "psutil", raising=False)
    monkeypatch.setitem(sys.modules, "psutil", None)
    assert monitors_mod.read_stats() is None


# ----- config -------------------------------------------------------------------

def test_config_new_defaults(tmp_path):
    from jarvis import config as config_mod
    cfg = config_mod.load(default_path=tmp_path / "nope.yaml",
                          local_path=tmp_path / "nope2.yaml")
    assert cfg["always_on_top"] is True
    assert cfg["ticker_refresh_minutes"] == 15
    assert cfg["weather_city"] == ""
    assert cfg["schedule_file"] == "config/schedule.yaml"
