"""Phone link tests. All HTTP is faked: no network, no Windows needed."""
import sys
import types

import pytest

from jarvis import config as config_mod
from jarvis.phonelink import PhoneLink


class FakeResponse:
    def __init__(self, payload=None):
        self._payload = payload or {}

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeHttp:
    """Scripted stand-in for requests."""
    def __init__(self, commands=()):
        self.posts = []
        self.gets = []
        self.commands = list(commands)
        self.fail = False

    def post(self, url, json=None, timeout=None):
        if self.fail:
            raise ConnectionError("offline")
        self.posts.append((url, json))
        return FakeResponse({})

    def get(self, url, params=None, timeout=None):
        if self.fail:
            raise ConnectionError("offline")
        self.gets.append((url, params))
        return FakeResponse({"commands": self.commands})


def make_config(**overrides):
    from pathlib import Path
    cfg = config_mod.load(
        default_path=Path("/nonexistent-default.yaml"),
        local_path=Path("/nonexistent-local.yaml"),
    )
    cfg.update({
        "phone_link_enabled": True,
        "phone_link_server": "https://phone.example",
        "phone_link_secret": "s3cret",
        "phone_link_pc_name": "TestPC",
        "phone_link_interval": 20,
    })
    cfg.update(overrides)
    return cfg


def make_link(http=None, **overrides):
    logs = []
    link = PhoneLink(make_config(**overrides),
                     log=logs.append, http=http or FakeHttp())
    return link, logs


# ----- lifecycle -----------------------------------------------------------

def test_disabled_does_not_start_thread():
    link, _ = make_link(phone_link_enabled=False)
    link.start()
    assert link._thread is None


def test_enabled_without_server_logs_and_stops():
    link, logs = make_link(phone_link_server="")
    link.start()
    assert link._thread is None
    assert any("phone_link_server" in m for m in logs)


def test_secret_generated_and_saved_when_missing(tmp_path, monkeypatch):
    import jarvis.phonelink as pl_mod
    local = tmp_path / "local.yaml"
    monkeypatch.setattr(pl_mod, "save_local",
                        lambda values: (local.write_text(
                            "\n".join(f"{k}: {v}" for k, v in values.items())), local)[1])
    link, logs = make_link(phone_link_secret="")
    link.start()
    try:
        assert link.secret  # generated
        assert local.is_file()
        assert link.secret in local.read_text()
        assert any("secret" in m.lower() for m in logs)
    finally:
        link.stop()


# ----- protocol ------------------------------------------------------------

def test_beat_posts_heartbeat_and_fetches_commands():
    http = FakeHttp()
    link, _ = make_link(http=http)
    link.beat()
    posted_paths = [url for url, _ in http.posts]
    assert any(u.endswith("/link/heartbeat") for u in posted_paths)
    heartbeat = next(p for u, p in http.posts if u.endswith("/link/heartbeat"))
    assert heartbeat["secret"] == "s3cret"
    assert heartbeat["pc_name"] == "TestPC"
    assert "at" in heartbeat
    assert any(u.endswith("/link/commands") for u, _ in http.gets)
    assert http.gets[0][1]["secret"] == "s3cret"


def test_lock_command_runs_and_acks(monkeypatch):
    http = FakeHttp(commands=[{"id": "c1", "type": "lock"}])
    link, logs = make_link(http=http)
    locked = []
    monkeypatch.setattr(link, "_lock_workstation",
                        lambda: locked.append(True) or True)
    link.beat()
    assert locked == [True]
    acks = [p for u, p in http.posts if u.endswith("/link/ack")]
    assert acks == [{"secret": "s3cret", "id": "c1"}]


def test_failed_lock_is_not_acked(monkeypatch):
    http = FakeHttp(commands=[{"id": "c2", "type": "lock"}])
    link, logs = make_link(http=http)
    monkeypatch.setattr(link, "_lock_workstation", lambda: False)
    link.beat()
    assert not any(u.endswith("/link/ack") for u, _ in http.posts)


def test_unknown_command_ignored_not_acked():
    http = FakeHttp(commands=[{"id": "c9", "type": "self_destruct"}])
    link, logs = make_link(http=http)
    link.beat()
    assert not any(u.endswith("/link/ack") for u, _ in http.posts)
    assert any("Ignoring unknown" in m for m in logs)


def test_network_failure_never_raises():
    http = FakeHttp()
    http.fail = True
    link, logs = make_link(http=http)
    link.beat()  # must not raise
    assert logs  # failure was logged, not raised


# ----- lock action ---------------------------------------------------------

def test_lock_uses_windows_api_when_present(monkeypatch):
    import ctypes
    calls = []
    fake_user32 = types.SimpleNamespace(LockWorkStation=lambda: calls.append(1))
    monkeypatch.setattr(ctypes, "windll", fake_user32, raising=False)
    link, _ = make_link()
    link._lock_workstation()
    assert calls == [1]


def test_lock_without_windows_logs_failure(monkeypatch):
    import ctypes
    monkeypatch.delattr(ctypes, "windll", raising=False)
    link, logs = make_link()
    link._lock_workstation()  # must not raise
    assert any("Lock failed" in m for m in logs)
