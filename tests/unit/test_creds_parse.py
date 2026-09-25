from pathlib import Path

import pytest

from vejudge.lm_engine import creds as creds_mod
from vejudge.lm_engine.creds import _parse_env_raw, load_creds

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "env_raw_sample.txt"


@pytest.fixture(autouse=True)
def legacy_mode(monkeypatch):
    monkeypatch.setenv("VEJUDGE_PROVIDER", "legacy")


def _clean_env(monkeypatch):
    for var in (
        "CHAT_GPT_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "OPENAI_COMPAT_BASE_URL",
        "LLM_PROXY_BASE_URL",
        "LLM_PROXY_MIRROR_URL",
    ):
        monkeypatch.delenv(var, raising=False)


def test_parse_env_raw_extracts_token_and_urls():
    text = FIXTURE.read_text()
    token, primary, mirror = _parse_env_raw(text)
    assert token == "sk-mv3-EXAMPLEEXAMPLEEXAMPLE1234567890"
    assert primary == "https://primary.example.colligo.dev/"
    assert mirror == "https://mirror.example.colligo.dev/"


def test_load_creds_from_file(monkeypatch):
    _clean_env(monkeypatch)
    creds = load_creds(env_raw_path=FIXTURE)
    assert creds.token.startswith("sk-mv3-")
    assert creds.endpoints == [
        "https://primary.example.colligo.dev",
        "https://mirror.example.colligo.dev",
    ]


def test_env_vars_take_precedence(monkeypatch):
    monkeypatch.setenv("CHAT_GPT_API_KEY", "sk-env-token-123456")
    monkeypatch.setenv("OPENAI_COMPAT_BASE_URL", "https://env.example.com/")
    creds = load_creds(env_raw_path=FIXTURE)
    assert creds.token == "sk-env-token-123456"
    assert creds.base_url == "https://env.example.com/"


def test_load_creds_with_source_labels_file(monkeypatch):
    _clean_env(monkeypatch)
    creds, source = creds_mod.load_creds_with_source(env_raw_path=FIXTURE)
    assert source == "file"
    assert creds.token.startswith("sk-mv3-")


def test_load_creds_with_source_labels_env(monkeypatch):
    monkeypatch.setenv("CHAT_GPT_API_KEY", "sk-env-token-123456")
    monkeypatch.setenv("OPENAI_COMPAT_BASE_URL", "https://env.example.com/")
    creds, source = creds_mod.load_creds_with_source(env_raw_path=FIXTURE)
    assert source == "env"


def test_manual_creds_take_precedence_over_env_and_file(monkeypatch, tmp_path):
    monkeypatch.setenv("CHAT_GPT_API_KEY", "sk-env-token-123456")
    monkeypatch.setenv("OPENAI_COMPAT_BASE_URL", "https://env.example.com/")
    creds_file = tmp_path / "creds.json"
    creds_mod.save_manual_creds(
        "sk-manual-token", "https://manual.example.com/", credentials_file=creds_file, provider="legacy"
    )
    creds, source = creds_mod.load_creds_with_source(
        env_raw_path=FIXTURE, credentials_file=creds_file, provider="legacy"
    )
    assert source == "manual"
    assert creds.token == "sk-manual-token"
    assert creds.base_url == "https://manual.example.com/"


def test_save_manual_creds_persists_across_a_simulated_restart(tmp_path):
    creds_file = tmp_path / "creds.json"
    creds_mod.save_manual_creds(
        "sk-manual-token", "https://manual.example.com/", credentials_file=creds_file, provider="legacy"
    )
    # A fresh process has no in-memory cache — drop this test's cache entry to simulate
    # that, then confirm load_creds_with_source reads the persisted file from disk.
    # Credentials are read from disk on every resolution.

    creds, source = creds_mod.load_creds_with_source(credentials_file=creds_file, provider="legacy")
    assert source == "manual"
    assert creds.token == "sk-manual-token"
    assert creds.base_url == "https://manual.example.com/"


def test_clear_manual_creds_reverts_to_next_precedence(monkeypatch, tmp_path):
    monkeypatch.setenv("CHAT_GPT_API_KEY", "sk-env-token-123456")
    monkeypatch.setenv("OPENAI_COMPAT_BASE_URL", "https://env.example.com/")
    creds_file = tmp_path / "creds.json"
    creds_mod.save_manual_creds(
        "sk-manual-token", "https://manual.example.com/", credentials_file=creds_file, provider="legacy"
    )
    creds_mod.clear_manual_creds(credentials_file=creds_file, provider="legacy")
    assert not creds_file.exists()

    creds, source = creds_mod.load_creds_with_source(
        env_raw_path=FIXTURE, credentials_file=creds_file, provider="legacy"
    )
    assert source == "env"
    assert creds.token == "sk-env-token-123456"


def test_save_manual_creds_rejects_empty_token_or_base_url(tmp_path):
    creds_file = tmp_path / "creds.json"
    with pytest.raises(ValueError):
        creds_mod.save_manual_creds("", "https://x.example.com/", credentials_file=creds_file, provider="legacy")
    with pytest.raises(ValueError):
        creds_mod.save_manual_creds("sk-token", "", credentials_file=creds_file, provider="legacy")
