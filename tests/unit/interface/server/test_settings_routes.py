"""FastAPI TestClient coverage for GET/POST/DELETE /api/settings/credentials."""

import pytest
from fastapi.testclient import TestClient

import vejudge.config as config
from vejudge.interface.server.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CREDENTIALS_FILE", tmp_path / "creds.json")
    for var in (
        "OPENAI_API_KEY", "OPENAI_BASE_URL", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_BASE_URL", "VEJUDGE_PROVIDER",
        "CHAT_GPT_API_KEY", "AZURE_OPENAI_API_KEY",
        "OPENAI_COMPAT_BASE_URL", "LLM_PROXY_BASE_URL", "LLM_PROXY_MIRROR_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    # No env vars and no real .env-raw on this machine should leak into these tests.
    monkeypatch.setattr(config, "ENV_RAW_PATH", tmp_path / "no-such-env-raw")
    return TestClient(create_app())


def test_status_reports_none_when_nothing_configured(client):
    resp = client.get("/api/settings/credentials")
    assert resp.status_code == 200
    assert resp.json() == {"configured": False, "source": "none", "base_url": None}


def test_post_then_get_reports_manual_source_and_base_url_never_token(client):
    resp = client.post(
        "/api/settings/credentials",
        json={"token": "sk-super-secret-token", "base_url": "https://manual.example.com/"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "configured": True, "source": "manual", "base_url": "https://manual.example.com/",
    }
    assert "sk-super-secret-token" not in resp.text

    resp = client.get("/api/settings/credentials")
    assert resp.json()["source"] == "manual"
    assert "sk-super-secret-token" not in resp.text


def test_post_rejects_empty_token(client):
    resp = client.post(
        "/api/settings/credentials",
        json={"token": "", "base_url": "https://manual.example.com/"},
    )
    assert resp.status_code == 400
    assert "token" in resp.json()["detail"]


def test_delete_reverts_to_none_when_no_other_source_configured(client):
    client.post(
        "/api/settings/credentials",
        json={"token": "sk-token", "base_url": "https://manual.example.com/"},
    )
    resp = client.delete("/api/settings/credentials")
    assert resp.status_code == 200
    assert resp.json() == {"configured": False, "source": "none", "base_url": None}

    resp = client.get("/api/settings/credentials")
    assert resp.json()["source"] == "none"


def test_delete_reverts_to_env_when_env_vars_are_set(client, monkeypatch):
    client.post(
        "/api/settings/credentials",
        json={"token": "sk-token", "base_url": "https://manual.example.com/"},
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-token")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://env.example.com/")

    resp = client.delete("/api/settings/credentials")
    assert resp.status_code == 200
    assert resp.json() == {
        "configured": True, "source": "env", "base_url": "https://env.example.com/",
    }


def test_provider_keys_are_independent_and_use_official_defaults(client):
    oa = client.post('/api/settings/credentials', json={'token': 'oa-secret', 'provider': 'openai'})
    gm = client.post('/api/settings/credentials', json={'token': 'gm-secret', 'provider': 'gemini'})
    assert oa.json()['base_url'] == 'https://api.openai.com/v1'
    assert gm.json()['base_url'] == 'https://generativelanguage.googleapis.com/v1beta'
    assert 'gm-secret' not in gm.text
    assert client.get('/api/settings/credentials?provider=gemini').json()['configured']
    client.delete('/api/settings/credentials?provider=openai')
    assert not client.get('/api/settings/credentials').json()['configured']
    assert client.get('/api/settings/credentials?provider=gemini').json()['configured']


def test_invalid_provider_returns_client_error(client):
    assert client.get('/api/settings/credentials?provider=unknown').status_code == 400
    assert client.delete('/api/settings/credentials?provider=unknown').status_code == 400
    assert client.post('/api/settings/credentials', json={'token': 'key', 'provider': 'unknown'}).status_code == 400
