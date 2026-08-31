from jarvis.control.web_remote import _looks_like_tablet


def test_ipad_allowed():
    assert _looks_like_tablet("Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X)")


def test_android_tablet_allowed():
    assert _looks_like_tablet("Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36")


def test_android_phone_rejected():
    assert not _looks_like_tablet("Mozilla/5.0 (Linux; Android 14; SM-S901U) Mobile Safari/537.36")


def test_iphone_rejected():
    assert not _looks_like_tablet("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile")


def test_desktop_rejected():
    assert not _looks_like_tablet("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0")
