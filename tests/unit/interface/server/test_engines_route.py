"""POST /api/engines/health-check — live-gating + result shape, no real gateway call."""

import pytest
from fastapi.testclient import TestClient

import vejudge.config as config
from vejudge.interface.server.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WORKFLOWS_ROOT", tmp_path / "workflows")
    monkeypatch.setattr(config, "LOGS_ROOT", tmp_path / "logs")
    return TestClient(create_app())


def test_health_check_refuses_without_allow_live(client):
    # Mirrors the Judge nodes' live-gating: a non-live request never touches the gateway.
    resp = client.post("/api/engines/health-check", json={"engine_kind": "gpt"})
    assert resp.status_code == 400
    assert "live" in resp.json()["detail"].lower()


def test_health_check_returns_endpoint_results(client, monkeypatch):
    from vejudge.lm_engine.creds import PlutoCreds

    # Stub creds + the actual probe so no real HTTP happens — we're testing the route's
    # gating + serialization, not the network probe (that's health.py's own concern).
    monkeypatch.setattr(
        "vejudge.interface.server.routes.engines.load_creds",
        lambda **kwargs: PlutoCreds(token="sk-test", base_url="https://primary"),
    )
    fake_results = [
        {"url": "https://primary", "ok": True, "status": 200, "latency": 0.05, "error": None},
        {"url": "https://mirror", "ok": False, "status": 503, "latency": 0.2, "error": "down"},
    ]
    monkeypatch.setattr(
        "vejudge.interface.server.routes.engines.health.healthy_order",
        lambda creds, model=None: (["https://primary", "https://mirror"], fake_results),
    )

    resp = client.post(
        "/api/engines/health-check",
        json={"engine_kind": "gpt", "model": "gpt-4.1", "allow_live": True},
    )
    assert resp.status_code == 200
    endpoints = resp.json()["endpoints"]
    assert [e["url"] for e in endpoints] == ["https://primary", "https://mirror"]
    assert endpoints[0]["ok"] is True and endpoints[0]["status"] == 200
    assert endpoints[1]["ok"] is False and endpoints[1]["error"] == "down"


def test_health_check_400_when_no_credentials(client, monkeypatch):
    def _raise(**kwargs):
        raise RuntimeError("No credentials configured")

    monkeypatch.setattr(
        "vejudge.interface.server.routes.engines.load_creds", _raise
    )
    resp = client.post(
        "/api/engines/health-check", json={"engine_kind": "gpt", "allow_live": True}
    )
    assert resp.status_code == 400
    assert "credential" in resp.json()["detail"].lower()
