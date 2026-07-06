import pytest

from vejudge.interface.node_vejudge import judge_node
from vejudge.interface.node_vejudge.judge_node import JudgeNodeExecutor
from vejudge.lm_engine import openai_compat
from vejudge.lm_engine.creds import PlutoCreds


def _sample(item_id, *, with_video=True):
    return {
        "item_id": item_id,
        "project": "prj-x",
        "prompt_idx": 0,
        "model": "peanut",
        "use_case": "visual montage",
        "input": {"user_prompt": "do a thing"},
        "algorithm": "peanut",
        "output": {"output_video_path": "/tmp/x.mp4" if with_video else ""},
    }


def _fake_chat_result():
    return openai_compat.ChatResult(
        content='{"score_1_to_5": 4, "fully_complete": true, "missing_aspects": [], '
        '"reasoning_lines": ["a", "b"]}',
        prompt_tokens=1, completion_tokens=1, total_tokens=2,
        endpoint_host="primary", latency_s=0.01, model="m",
    )


@pytest.fixture(autouse=True)
def fake_creds(monkeypatch):
    monkeypatch.setattr(
        judge_node, "load_creds", lambda: PlutoCreds(token="sk-test", base_url="https://primary")
    )


def test_dry_run_estimates_calls_without_gateway(monkeypatch, make_ctx):
    def boom(**kwargs):
        raise AssertionError("dry-run must not call the gateway")

    monkeypatch.setattr(openai_compat, "chat_completion", boom)

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(params={"metrics": ["M1", "M2"]}, inputs={"dataset": dataset}, dry_run=True)
    result = JudgeNodeExecutor().run(ctx)

    assert result.status == "done"
    assert result.meta["dry_run"] is True
    assert result.meta["estimated_calls"] == {"video_judge_calls": 1, "text_judge_calls": 1}
    assert result.outputs["judge_result"] == {}


def test_live_call_rejected_without_allow_live(make_ctx):
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(
        params={"metrics": ["M1"]}, inputs={"dataset": dataset}, dry_run=False, allow_live=False,
    )
    result = JudgeNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "--live" in result.error


def test_missing_dataset_input_is_a_node_error(make_ctx):
    ctx = make_ctx(params={}, inputs={}, dry_run=True)
    result = JudgeNodeExecutor().run(ctx)
    assert result.status == "error"


def test_unknown_metric_is_a_node_error(make_ctx):
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(params={"metrics": ["M9"]}, inputs={"dataset": dataset}, dry_run=True)
    result = JudgeNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "M9" in result.error


def test_checkpoint_resume_skips_completed_pairs(monkeypatch, make_ctx):
    calls = {"n": 0}

    def fake_chat(**kwargs):
        calls["n"] += 1
        return _fake_chat_result()

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat)

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut", with_video=False)}
    ctx = make_ctx(
        params={"metrics": ["M1", "M3"]}, inputs={"dataset": dataset},
        dry_run=False, allow_live=True,
    )

    result1 = JudgeNodeExecutor().run(ctx)
    assert result1.status == "done"
    assert calls["n"] == 2  # one text call per metric
    jr1 = result1.outputs["judge_result"]["prj-x::0::peanut"]
    assert set(jr1) == {"M1", "M3"}
    assert ctx.checkpoint.has("prj-x::0::peanut::M1")
    assert ctx.checkpoint.has("prj-x::0::peanut::M3")

    # Re-run with the same checkpoint store -> both metrics are cached, no new calls.
    result2 = JudgeNodeExecutor().run(ctx)
    assert result2.status == "done"
    assert calls["n"] == 2  # unchanged
    assert set(result2.outputs["judge_result"]["prj-x::0::peanut"]) == {"M1", "M3"}


def test_progress_init_reports_accurate_total_excluding_skipped_video(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())

    dataset = {
        "prj-x::0::peanut": _sample("prj-x::0::peanut", with_video=True),
        "prj-x::1::peanut": _sample("prj-x::1::peanut", with_video=False),
    }
    ctx = make_ctx(
        params={"metrics": ["M3", "M5"]}, inputs={"dataset": dataset},
        dry_run=False, allow_live=True,
    )
    events: list[tuple[str, dict]] = []
    ctx.progress_cb = lambda event, payload: events.append((event, payload))

    JudgeNodeExecutor().run(ctx)

    init_events = [payload for event, payload in events if event == "judge_progress_init"]
    assert init_events == [{"total": 3}]  # item0: M3+M5(video,has video); item1: M3 only (M5 video, no video)
    # exactly one judge_metric event per counted call
    metric_events = [e for e in events if e[0] == "judge_metric"]
    assert len(metric_events) == 3


def test_engine_error_is_not_checkpointed(monkeypatch, make_ctx):
    def fake_chat(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat)

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut", with_video=False)}
    ctx = make_ctx(
        params={"metrics": ["M1"]}, inputs={"dataset": dataset}, dry_run=False, allow_live=True,
    )
    result = JudgeNodeExecutor().run(ctx)
    assert result.status == "done"  # per-judge errors don't abort the node
    jr = result.outputs["judge_result"]["prj-x::0::peanut"]["M1"]
    assert jr.get("error")
    assert not ctx.checkpoint.has("prj-x::0::peanut::M1")
