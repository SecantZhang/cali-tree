import pytest

from critical.lm_engine.gate import LiveCallNotAllowed, live_allowed, require_live


def test_explicit_flag_wins(monkeypatch):
    monkeypatch.delenv("CRITICAL_ALLOW_LIVE", raising=False)
    assert live_allowed(True) is True
    assert live_allowed(False) is False


def test_env_var_enables(monkeypatch):
    monkeypatch.setenv("CRITICAL_ALLOW_LIVE", "1")
    assert live_allowed() is True
    monkeypatch.setenv("CRITICAL_ALLOW_LIVE", "no")
    assert live_allowed() is False


def test_default_is_disallowed(monkeypatch):
    monkeypatch.delenv("CRITICAL_ALLOW_LIVE", raising=False)
    assert live_allowed() is False
    with pytest.raises(LiveCallNotAllowed):
        require_live(None)
    require_live(True)  # does not raise
