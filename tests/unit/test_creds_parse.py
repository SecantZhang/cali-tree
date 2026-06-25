from pathlib import Path

from vejudge.lm_engine.creds import _parse_env_raw, load_creds

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "env_raw_sample.txt"


def test_parse_env_raw_extracts_token_and_urls():
    text = FIXTURE.read_text()
    token, primary, mirror = _parse_env_raw(text)
    assert token == "sk-mv3-EXAMPLEEXAMPLEEXAMPLE1234567890"
    assert primary == "https://primary.example.colligo.dev/"
    assert mirror == "https://mirror.example.colligo.dev/"


def test_load_creds_from_file(monkeypatch):
    for var in (
        "CHAT_GPT_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "OPENAI_COMPAT_BASE_URL",
        "LLM_PROXY_BASE_URL",
        "LLM_PROXY_MIRROR_URL",
    ):
        monkeypatch.delenv(var, raising=False)
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
