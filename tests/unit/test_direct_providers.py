"""Direct-provider routing and wire contracts; every HTTP call is mocked."""
import importlib.util
from pathlib import Path

import pytest

from vejudge import config
from vejudge.lm_engine import get_engine, openai_compat
from vejudge.lm_engine.creds import DEFAULT_URLS, load_creds, load_creds_with_source, save_manual_creds, clear_manual_creds


@pytest.fixture(autouse=True)
def isolated_credentials(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(config, "CREDENTIALS_FILE", tmp_path / "credentials.json")
    monkeypatch.setattr(config, "ENV_RAW_PATH", tmp_path / ".env-raw")
    for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_BASE_URL", "VEJUDGE_PROVIDER", "CHAT_GPT_API_KEY", "OPENAI_COMPAT_BASE_URL", "LLM_PROXY_MIRROR_URL"):
        monkeypatch.delenv(key, raising=False)


def test_official_keys_are_isolated_from_old_proxy(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret")
    monkeypatch.setenv("CHAT_GPT_API_KEY", "old-proxy-secret")
    monkeypatch.setenv("OPENAI_COMPAT_BASE_URL", "https://old-proxy.example")
    monkeypatch.setenv("LLM_PROXY_MIRROR_URL", "https://old-mirror.example")
    config.CREDENTIALS_FILE.write_text('{"token":"old-manual-secret","base_url":"https://old.example"}')
    config.ENV_RAW_PATH.write_text('sk-oldtoken123\nhttps://old.example')
    for engine, token, provider in [("gpt", "openai-secret", "openai"), ("gemini", "gemini-secret", "gemini")]:
        creds = get_engine(engine).creds
        assert creds.token == token
        assert creds.endpoints == [DEFAULT_URLS[provider]]
        assert creds.mirror_url is None
        assert token not in repr(creds)


def test_proxy_alone_does_not_configure_official_api(monkeypatch):
    monkeypatch.setenv("CHAT_GPT_API_KEY", "old-key")
    monkeypatch.setenv("OPENAI_COMPAT_BASE_URL", "https://old.example")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        load_creds()


def test_dotenv_and_shell_precedence(monkeypatch):
    (config.PROJECT_ROOT / ".env").write_text('OPENAI_API_KEY=from-file\nGEMINI_API_KEY=google-file\n')
    assert load_creds().token == "from-file"
    monkeypatch.setenv("OPENAI_API_KEY", "from-shell")
    assert load_creds().token == "from-shell"
    assert load_creds(model="gemini-2.5-pro").token == "google-file"


def test_google_key_alias_and_missing_gemini_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        load_creds(engine="gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "google")
    assert load_creds(engine="gemini").token == "google"
    monkeypatch.setenv("GEMINI_API_KEY", "preferred")
    assert load_creds(engine="gemini").token == "preferred"


def test_manual_keys_persist_independently_and_clear_one(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "ambient")
    save_manual_creds("Bearer manual-openai", provider="openai")
    save_manual_creds("manual-gemini", provider="gemini")
    assert load_creds().token == "manual-openai"
    assert load_creds_with_source(provider="gemini")[1] == "manual"
    assert config.CREDENTIALS_FILE.stat().st_mode & 0o777 == 0o600
    clear_manual_creds(provider="openai")
    assert load_creds().token == "ambient"
    assert load_creds(provider="gemini").token == "manual-gemini"


@pytest.mark.parametrize("model,provider", [("gpt-5.4-mini", "openai"), ("text-embedding-3-small", "openai"), ("models/gemini-2.5-flash", "gemini")])
def test_model_based_routing(model, provider, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "oa")
    monkeypatch.setenv("GEMINI_API_KEY", "gm")
    assert load_creds(model=model).provider == provider


def fake_http(monkeypatch, response):
    calls = []
    class Response:
        status_code = 200
        headers = {}
        def json(self):
            return response
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()
    monkeypatch.setattr(openai_compat.requests, "post", post)
    return calls


@pytest.mark.parametrize("model", ["gpt-4.1-mini", "gpt-5.4-mini"])
def test_openai_endpoint_auth_images_token_limit(monkeypatch, tmp_path, model):
    monkeypatch.setenv("OPENAI_API_KEY", "oa-key")
    calls = fake_http(monkeypatch, {"model": model + "-snapshot", "choices": [{"message": {"content": '{"label":"yes"}'}}], "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6}})
    image = tmp_path / "a.jpg"
    image.write_bytes(b"test-image")
    result = get_engine("gpt", model=model).generate("judge", [{"type": "image", "path": str(image)}], schema={}, system="rubric")
    url, call = calls[0]
    assert url == "https://api.openai.com/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer oa-key"
    assert call["json"]["max_completion_tokens"] == 4096
    assert "max_tokens" not in call["json"]
    assert call["json"]["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;")
    if model == "gpt-5.4-mini":
        assert call["json"]["reasoning_effort"] == "none"
    assert result["parsed"] == {"label": "yes"}
    assert result["model"] == model + "-snapshot"
    assert result["totalTokens"] == 6


@pytest.mark.parametrize("media_type,suffix,mime", [("image", "png", "image/png"), ("video", "mp4", "video/mp4")])
def test_gemini_native_media_auth_system_usage(monkeypatch, tmp_path, media_type, suffix, mime):
    monkeypatch.setenv("GEMINI_API_KEY", "gm-key")
    calls = fake_http(monkeypatch, {"modelVersion": "gemini-snapshot", "candidates": [{"content": {"parts": [{"text": "private", "thought": True}, {"text": '{"label":"yes"}'}]}}], "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 3, "thoughtsTokenCount": 2, "totalTokenCount": 10}})
    media = tmp_path / ("a." + suffix)
    media.write_bytes(b"test-media")
    result = get_engine("gemini", model="gemini-2.5-pro").generate("judge", [{"type": media_type, "path": str(media)}], schema={}, system="rubric")
    url, call = calls[0]
    assert url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent"
    assert call["headers"]["x-goog-api-key"] == "gm-key"
    assert "Authorization" not in call["headers"]
    assert "gm-key" not in url
    assert call["json"]["systemInstruction"] == {"parts": [{"text": "rubric"}]}
    assert call["json"]["contents"][0]["parts"][1]["inlineData"]["mimeType"] == mime
    assert result["parsed"] == {"label": "yes"}
    assert result["completionTokens"] == 5
    assert result["model"] == "gemini-snapshot"


def test_gemini_blocked_response_is_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gm")
    fake_http(monkeypatch, {"promptFeedback": {"blockReason": "SAFETY"}})
    with pytest.raises(RuntimeError, match="Gemini returned no text"):
        get_engine("gemini").generate("hi")


def test_health_check_uses_native_gemini(monkeypatch):
    from vejudge.lm_engine.health import healthy_order
    monkeypatch.setenv("GEMINI_API_KEY", "gm")
    calls = fake_http(monkeypatch, {})
    _, results = healthy_order(load_creds(engine="gemini"))
    assert results[0]["ok"]
    assert ":generateContent" in calls[0][0]


def test_aurora_judge_and_gepa_worker_use_gemini(monkeypatch):
    from vejudge.checkpoint import CheckpointStore
    from run.aurora_prompt_repair import LiveJudge
    monkeypatch.setenv("GEMINI_API_KEY", "gm")
    judge = LiveJudge(model="gemini-2.5-flash", checkpoint=CheckpointStore(config.PROJECT_ROOT / "checkpoint.jsonl"), history=None, max_tokens=40, timeout=10)
    assert judge.creds.provider == "gemini"
    worker_path = Path(__file__).resolve().parents[2] / "run/aurora_prompt_repair/gepa_worker.py"
    spec = importlib.util.spec_from_file_location("worker_under_test", worker_path)
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    calls = fake_http(monkeypatch, {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})
    monkeypatch.setenv("AURORA_GEPA_PROVIDER", "gemini")
    usage = {"calls": [], "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    result, _ = worker.Client([DEFAULT_URLS["gemini"]], "gm", usage).chat([{"role": "user", "content": "hello"}], model="gemini-2.5-flash", temperature=0, max_tokens=32, timeout=10, call_type="test")
    assert result == "ok"
    assert calls[0][0].endswith(":generateContent")
    assert len(usage["calls"]) == 1


def test_gemini_concurrency_probe_uses_provider_payload(monkeypatch):
    from vejudge.lm_engine.probe import _one_call
    calls = fake_http(monkeypatch, {})
    assert _one_call(DEFAULT_URLS['gemini'], 'gm', 'gemini-2.5-flash', 10, 'gemini')['ok']
    assert calls[0][0].endswith(':generateContent')


def test_gemini_retries_without_falling_back_to_openai(monkeypatch):
    from vejudge.lm_engine import openai_compat
    monkeypatch.setenv('GEMINI_API_KEY', 'gm')
    monkeypatch.setenv('OPENAI_API_KEY', 'oa')
    calls = []
    class Response:
        headers = {'Retry-After': '0'}
        text = 'busy'
        def __init__(self, status):
            self.status_code = status
        def json(self):
            return {'candidates': [{'content': {'parts': [{'text': 'ok'}]}}]}
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response(429 if len(calls) == 1 else 200)
    monkeypatch.setattr(openai_compat.requests, 'post', post)
    monkeypatch.setattr(openai_compat.time, 'sleep', lambda _: None)
    assert get_engine('gemini').generate('hi')['content'] == 'ok'
    assert len(calls) == 2
    assert all(call[1]['headers']['x-goog-api-key'] == 'gm' for call in calls)


def test_gemini_inline_size_limit_is_explicit():
    from vejudge.lm_engine.provider_api import chat_request
    with pytest.raises(ValueError, match='shorter clips'):
        chat_request(DEFAULT_URLS['gemini'], 'gm', 'gemini-2.5-pro', [{'role': 'user', 'content': [
            {'type': 'image_url', 'image_url': {'url': 'data:video/mp4;base64,' + 'A' * 19_000_001}}
        ]}], 64, 0)


def test_gemini_judge_uses_separate_openai_embedding_credentials(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from vejudge.checkpoint import CheckpointStore
    from vejudge.interface.node_calibration.calitree_nodes import _CaliTreeRuntime
    monkeypatch.setenv('OPENAI_API_KEY', 'embedding-key')
    monkeypatch.setenv('GEMINI_API_KEY', 'judge-key')
    calls = fake_http(monkeypatch, {'data': [{'index': 0, 'embedding': [1.0, 0.5]}], 'usage': {'prompt_tokens': 4, 'total_tokens': 4}})
    ctx = SimpleNamespace(node_id='train', checkpoint=CheckpointStore(config.PROJECT_ROOT / 'embeddings.jsonl'), run=SimpleNamespace(history=Mock()))
    runtime = _CaliTreeRuntime(ctx, judge_engine=get_engine('gemini'), optimizer_engine=None, embedding_model='text-embedding-3-small', optimizer_budget=1)
    assert runtime.embed(['rubric']) == [[1.0, 0.5]]
    assert calls[0][0] == 'https://api.openai.com/v1/embeddings'
    assert calls[0][1]['headers']['Authorization'] == 'Bearer embedding-key'
    assert runtime.judge_engine.creds.token == 'judge-key'
    assert runtime.embed(['rubric']) == [[1.0, 0.5]]
    assert len(calls) == 1
