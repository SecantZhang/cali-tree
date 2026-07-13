from vejudge.core.judge.base_judge import Judge
from vejudge.lm_engine import openai_compat
from vejudge.lm_engine.creds import PlutoCreds
from vejudge.lm_engine.lm_gpt.engine import GptEngine


def _sample(item_id="prj-x::0::peanut"):
    return {
        "item_id": item_id,
        "project": "prj-x",
        "prompt_idx": 0,
        "model": "peanut",
        "use_case": "visual montage",
        "input": {"user_prompt": "do a thing"},
        "algorithm": "peanut",
        "output": {"output_video_path": ""},
    }


def _engine():
    return GptEngine(creds=PlutoCreds(token="sk-test", base_url="https://primary"))


def test_run_includes_the_exact_prompt_text_sent_to_the_lm(monkeypatch):
    monkeypatch.setattr(
        openai_compat, "chat_completion",
        lambda **kwargs: openai_compat.ChatResult(
            content='{"score_1_to_5": 4, "fully_complete": true, "missing_aspects": [], '
            '"reasoning_lines": ["a"]}',
            prompt_tokens=1, completion_tokens=1, total_tokens=2,
            endpoint_host="primary", latency_s=0.01, model="m",
        ),
    )
    judge = Judge("M3", _engine())
    result = judge.run(_sample())

    assert isinstance(result["prompt_user"], str) and result["prompt_user"]
    assert isinstance(result["prompt_system"], str) and result["prompt_system"]
    # Real content, not a placeholder — the sample's own prompt text must actually be in
    # there (M3's user prompt is a JSON dump of the sample's relevant fields).
    assert "do a thing" in result["prompt_user"]


def test_prompt_text_is_present_even_when_the_engine_call_fails(monkeypatch):
    # A failed engine call still returns a result dict (with an "error" key) — the prompt
    # that WOULD have been sent is still useful to see, so it must survive that path too.
    def boom(**kwargs):
        raise RuntimeError("gateway down")

    monkeypatch.setattr(openai_compat, "chat_completion", boom)
    judge = Judge("M3", _engine())
    result = judge.run(_sample())

    assert "error" in result
    assert isinstance(result["prompt_user"], str) and result["prompt_user"]


def _fake_result():
    return openai_compat.ChatResult(
        content='{"score_1_to_5": 4, "fully_complete": true, "missing_aspects": [], '
        '"reasoning_lines": ["a"]}',
        prompt_tokens=1, completion_tokens=1, total_tokens=2,
        endpoint_host="primary", latency_s=0.01, model="m",
    )


def test_extra_context_defaults_to_none_and_leaves_the_prompt_unchanged(monkeypatch):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **kwargs: _fake_result())
    judge = Judge("M3", _engine())
    result = judge.run(_sample())
    assert "\n\ncalibration" not in result["prompt_system"].lower()


def test_extra_context_is_appended_to_the_system_prompt_and_actually_sent(monkeypatch):
    captured = {}

    def fake_chat(**kwargs):
        captured["messages"] = kwargs["messages"]
        return _fake_result()

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat)
    judge = Judge("M3", _engine())
    result = judge.run(_sample(), extra_context="Calibration note: watch for X.")

    assert result["prompt_system"].endswith("Calibration note: watch for X.")
    # The effective (calibrated) system text is what's actually sent to the engine, not
    # just recorded after the fact.
    system_message = next(m for m in captured["messages"] if m["role"] == "system")
    assert "Calibration note: watch for X." in system_message["content"]
    assert "do a thing" in result["prompt_user"]  # user text untouched by extra_context
