"""Strict output transport, defaults, failure visibility and audit data; no network."""
import json

import pytest

from critical.lm_engine import get_engine, openai_compat
from critical.lm_engine.creds import PlutoCreds
from critical.logging.llm_history import LLMHistoryWriter


SCHEMA = {"type": "object", "properties": {"label": {"type": "string", "enum": ["no", "partial", "yes"]}},
          "required": ["label"], "additionalProperties": False}


@pytest.mark.parametrize("failure", ["timeout", 429, 500, 400, 307])
def test_bounded_engine_never_retries_or_uses_mirror(monkeypatch, tmp_path, failure):
    from critical.lm_engine.creds import ProviderCreds
    from tests.unit.calitree.assumption3_probe import BudgetedEngine, ProviderUnavailable
    calls = []

    def post(url, **kwargs):
        assert kwargs["allow_redirects"] is False
        calls.append(url)
        if failure == "timeout":
            raise openai_compat.requests.Timeout("test timeout")
        return type("Response", (), {"status_code": failure, "text": "test failure", "headers": {}})()

    monkeypatch.setattr(openai_compat.requests, "post", post)
    monkeypatch.setattr(openai_compat.time, "sleep", lambda *a: pytest.fail("Must not wait for a retry"))
    provider = get_engine("gpt", creds=ProviderCreds(token="test", base_url="https://first.invalid/v1",
                                                    mirror_url="https://second.invalid/v1", provider="legacy"))
    budget = BudgetedEngine(provider, tmp_path / "budget.json", 2, 8192)
    with pytest.raises(ProviderUnavailable):
        budget.generate("offline failure test")
    assert len(calls) == 1 and calls[0].startswith("https://first.invalid/")
    assert budget.usage["pending_or_failed"] == 1
    assert budget.usage["completion_tokens_or_reserved"] == 4096


def engine(tmp_path, provider="openai"):
    url = "https://api.openai.com/v1" if provider == "openai" else "https://generativelanguage.googleapis.com/v1beta"
    return get_engine("gpt", model="gpt-4.1", creds=PlutoCreds(token="test", base_url=url, provider=provider),
                      history=LLMHistoryWriter(tmp_path / "history.jsonl"))


def mock_http(monkeypatch, choice):
    calls = []
    class Response:
        status_code = 200
        def json(self):
            return {"choices": [choice], "model": "gpt-4.1-2025-04-14", "usage": {"total_tokens": 3}}
    def post(url, **kwargs):
        calls.append(kwargs["json"])
        return Response()
    monkeypatch.setattr(openai_compat.requests, "post", post)
    return calls


def test_strict_schema_reaches_wire_and_history(monkeypatch, tmp_path):
    calls = mock_http(monkeypatch, {"message": {"content": '{"label":"partial"}'}, "finish_reason": "stop"})
    result = engine(tmp_path).generate("Return JSON", schema=SCHEMA, strict_schema=True)
    expected = {"type": "json_schema", "json_schema": {"name": "critical_output", "strict": True, "schema": SCHEMA}}
    assert calls[0]["response_format"] == expected
    assert result["parsed"] == {"label": "partial"}
    assert result["finishReason"] == "stop"
    log = json.loads((tmp_path / "history.jsonl").read_text())
    assert log["response_format"] == expected
    assert log["finish_reason"] == "stop"


def test_advisory_schema_does_not_change_wire(monkeypatch, tmp_path):
    calls = mock_http(monkeypatch, {"message": {"content": '{"label":"other"}'}})
    result = engine(tmp_path).generate("Return JSON", schema=SCHEMA)
    assert "response_format" not in calls[0]
    assert result["parsed"] == {"label": "other"}


@pytest.mark.parametrize("schema", [None, {}, {"label": "string"}, {"type": "array"}])
def test_strict_requires_actual_schema_without_http(monkeypatch, tmp_path, schema):
    calls = mock_http(monkeypatch, {})
    with pytest.raises(ValueError, match="nonempty object JSON Schema"):
        engine(tmp_path).generate("Return JSON", schema=schema, strict_schema=True)
    assert not calls


@pytest.mark.parametrize("provider", ["gemini", "compatible"])
def test_unsupported_provider_cannot_downgrade(monkeypatch, tmp_path, provider):
    calls = mock_http(monkeypatch, {})
    with pytest.raises(RuntimeError, match="cannot silently fall back"):
        engine(tmp_path, provider).generate("Return JSON", schema=SCHEMA, strict_schema=True)
    assert not calls
    log = json.loads((tmp_path / "history.jsonl").read_text())
    assert "cannot silently fall back" in log["error"]
    assert log["response_format"]["json_schema"]["schema"] == SCHEMA


@pytest.mark.parametrize("choice,extra", [
    ({"message": {"content": None, "refusal": "Declined"}, "finish_reason": "stop"}, {"refusal": "Declined", "finishReason": "stop"}),
    ({"message": {"content": '{"label":'}, "finish_reason": "length"}, {"finishReason": "length"}),
])
def test_refusal_and_truncation_are_visible(monkeypatch, tmp_path, choice, extra):
    mock_http(monkeypatch, choice)
    result = engine(tmp_path).generate("Return JSON", schema=SCHEMA, strict_schema=True)
    assert result["parsed"] is None
    for key, value in extra.items():
        assert result[key] == value
    log = json.loads((tmp_path / "history.jsonl").read_text())
    assert log["response"] == choice["message"]["content"]
    assert log["finish_reason"] == choice["finish_reason"]
