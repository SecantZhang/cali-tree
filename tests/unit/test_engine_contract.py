"""Engine contract + failover, with the HTTP transport mocked (no network)."""

import pytest

from vejudge.lm_engine import openai_compat
from vejudge.lm_engine.creds import PlutoCreds
from vejudge.lm_engine.lm_gemini import GeminiEngine
from vejudge.lm_engine.lm_gpt import GptEngine


def _creds():
    return PlutoCreds(
        token="sk-test", base_url="https://primary", mirror_url="https://mirror"
    )


def _fake_result(model="m"):
    return openai_compat.ChatResult(
        content='{"ok": true}',
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        endpoint_host="primary",
        latency_s=0.01,
        model=model,
    )


def test_generate_returns_contract_keys(monkeypatch):
    captured = {}

    def fake_chat(**kwargs):
        captured.update(kwargs)
        return _fake_result(kwargs["model"])

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat)
    eng = GptEngine(creds=_creds())
    out = eng.generate("hello", schema={"ok": "bool"})

    assert set(["content", "promptTokens", "completionTokens", "totalTokens"]) <= set(out)
    assert out["parsed"] == {"ok": True}
    assert captured["model"] == GptEngine.default_model
    # text engine sends a plain-string user message (no media parts)
    assert captured["messages"][-1]["content"] == "hello"


def test_video_engine_attaches_media(monkeypatch, tmp_path):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_result())
    # avoid reading a real file: stub the base64 part builder
    monkeypatch.setattr(openai_compat, "video_part", lambda p: {"type": "image_url"})
    eng = GeminiEngine(creds=_creds())
    out = eng.generate("judge this", media_inputs=[{"type": "video", "path": "x.mp4"}])
    assert out["content"] == '{"ok": true}'


def test_text_engine_rejects_video():
    eng = GptEngine(creds=_creds())
    with pytest.raises(ValueError):
        eng.generate("x", media_inputs=[{"type": "video", "path": "x.mp4"}])


def test_retries_429_then_succeeds(monkeypatch):
    import requests

    seq = []

    class Resp:
        def __init__(self, status):
            self.status_code = status
            self.headers = {"Retry-After": "0"} if status == 429 else {}
            self.text = "rate limited" if status == 429 else ""

        def json(self):
            return {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }

    statuses = [429, 429, 200]

    def fake_post(url, **kwargs):
        s = statuses[len(seq)]
        seq.append(s)
        return Resp(s)

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(openai_compat.time, "sleep", lambda s: None)  # no real wait

    res = openai_compat.chat_completion(
        endpoints=["https://primary"],
        token="t",
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        max_retries=4,
    )
    assert res.content == "ok"
    assert seq == [429, 429, 200]  # retried twice, then succeeded


def test_retries_503_then_succeeds(monkeypatch):
    import requests

    seq = []

    class Resp:
        def __init__(self, status):
            self.status_code = status
            self.headers = {}
            self.text = "upstream connect error" if status >= 500 else ""

        def json(self):
            return {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }

    statuses = [503, 502, 200]

    def fake_post(url, **kwargs):
        s = statuses[len(seq)]
        seq.append(s)
        return Resp(s)

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(openai_compat.time, "sleep", lambda s: None)

    res = openai_compat.chat_completion(
        endpoints=["https://primary"],
        token="t",
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        max_retries=4,
    )
    assert res.content == "ok"
    assert seq == [503, 502, 200]  # transient 5xx retried on the same endpoint


def test_retries_connection_error_then_succeeds(monkeypatch):
    import requests

    calls = {"n": 0}

    class Resp:
        status_code = 200
        headers: dict = {}

        def json(self):
            return {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }

    def fake_post(url, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.ConnectionError("Remote end closed connection")
        return Resp()

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(openai_compat.time, "sleep", lambda s: None)

    res = openai_compat.chat_completion(
        endpoints=["https://primary"],
        token="t",
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        max_retries=4,
    )
    assert res.content == "ok"
    assert calls["n"] == 2  # retried the same endpoint after a connection reset


def test_does_not_retry_non_retryable_4xx(monkeypatch):
    import requests

    calls = {"n": 0}

    class Resp:
        status_code = 400
        headers: dict = {}
        text = "bad request"

        def json(self):  # pragma: no cover - never reached
            return {}

    def fake_post(url, **kwargs):
        calls["n"] += 1
        return Resp()

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(openai_compat.time, "sleep", lambda s: None)

    # Single endpoint, 400 -> no retry, raises immediately after one attempt.
    try:
        openai_compat.chat_completion(
            endpoints=["https://primary"],
            token="t",
            model="m",
            messages=[{"role": "user", "content": "hi"}],
            max_retries=4,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError on 400")
    assert calls["n"] == 1  # 400 is not retried


def test_failover_uses_mirror_when_primary_fails(monkeypatch):
    import requests

    calls = []

    class Resp:
        status_code = 200

        def json(self):
            return {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }

    def fake_post(url, **kwargs):
        calls.append(url)
        if "primary" in url:
            raise requests.RequestException("primary down")
        return Resp()

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(openai_compat.time, "sleep", lambda s: None)
    res = openai_compat.chat_completion(
        endpoints=["https://primary", "https://mirror"],
        token="t",
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        max_retries=2,
    )
    assert res.content == "ok"
    # primary is retried (max_retries+1 = 3 times) before falling over to the mirror.
    assert calls.count("https://primary/chat/completions") == 3
    assert calls[-1] == "https://mirror/chat/completions"


def test_embeddings_preserve_input_order_and_usage(monkeypatch):
    import requests

    class Resp:
        status_code = 200
        headers: dict = {}
        text = ""

        def json(self):
            # Deliberately reversed: the adapter must restore API index order.
            return {
                "data": [
                    {"index": 1, "embedding": [0, 1]},
                    {"index": 0, "embedding": [1, 0]},
                ],
                "usage": {"prompt_tokens": 7, "total_tokens": 7},
            }

    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: Resp())
    result = openai_compat.embeddings(
        endpoints=["https://primary"], token="t", model="embed", inputs=["a", "b"]
    )
    assert result.vectors == [[1.0, 0.0], [0.0, 1.0]]
    assert result.prompt_tokens == result.total_tokens == 7
    assert result.endpoint_host == "primary"
