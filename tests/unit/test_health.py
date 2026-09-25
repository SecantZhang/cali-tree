from vejudge.lm_engine import health
from vejudge.lm_engine.creds import PlutoCreds


def _creds():
    return PlutoCreds(token="t", base_url="https://primary", mirror_url="https://mirror")


def test_healthy_order_prefers_working(monkeypatch):
    # primary down, mirror up
    def fake_check(url, token, *, model=None, timeout=20, provider=None):
        ok = "mirror" in url
        return {"url": url.rstrip("/"), "ok": ok, "status": 200 if ok else 503,
                "latency": 0.1, "error": None if ok else "down"}

    monkeypatch.setattr(health, "check_endpoint", fake_check)
    ordered, results = healthy = health.healthy_order(_creds())
    assert ordered[0] == "https://mirror"          # working endpoint first
    assert ordered == ["https://mirror", "https://primary"]  # down kept as last resort


def test_reorder_sets_preferred(monkeypatch):
    def fake_check(url, token, *, model=None, timeout=20, provider=None):
        ok = "mirror" in url
        return {"url": url.rstrip("/"), "ok": ok, "status": 200 if ok else 503,
                "latency": 0.1, "error": None if ok else "down"}

    monkeypatch.setattr(health, "check_endpoint", fake_check)
    creds = _creds()
    health.reorder_creds_by_health(creds)
    assert creds.endpoints[0] == "https://mirror"  # preferred now wins over default order


def test_all_down_keeps_all(monkeypatch):
    def fake_check(url, token, *, model=None, timeout=20, provider=None):
        return {"url": url.rstrip("/"), "ok": False, "status": 503,
                "latency": 0.1, "error": "down"}

    monkeypatch.setattr(health, "check_endpoint", fake_check)
    ordered, _ = health.healthy_order(_creds())
    assert set(ordered) == {"https://primary", "https://mirror"}  # still attempt all


def test_default_endpoints_ignores_preferred():
    creds = _creds()
    creds.preferred = ["https://mirror"]
    assert creds.endpoints == ["https://mirror"]
    assert creds.default_endpoints == ["https://primary", "https://mirror"]
