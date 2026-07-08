import threading

import pytest

from vejudge.interface.node_vejudge import judge_text_node
from vejudge.interface.node_vejudge.judge_text_node import TextJudgeNodeExecutor
from vejudge.lm_engine import openai_compat
from vejudge.lm_engine.creds import PlutoCreds


def _sample(item_id):
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


def _fake_chat_result():
    return openai_compat.ChatResult(
        content='{"score_1_to_5": 4, "fully_complete": true, "missing_aspects": [], '
        '"reasoning_lines": ["a", "b"]}',
        prompt_tokens=1, completion_tokens=1, total_tokens=2,
        endpoint_host="primary", latency_s=0.01, model="m",
    )


def _engine_config(**overrides):
    # Every key has a fallback in judge_text_node.py's run() (via .get(...)), so an empty
    # dict is a valid, fully-default engine_config — tests only need to set the keys they
    # actually care about.
    return {"engine_kind": "gpt", **overrides}


@pytest.fixture(autouse=True)
def fake_creds(monkeypatch):
    monkeypatch.setattr(
        judge_text_node, "load_creds", lambda: PlutoCreds(token="sk-test", base_url="https://primary")
    )


def test_dry_run_estimates_calls_without_gateway(monkeypatch, make_ctx):
    def boom(**kwargs):
        raise AssertionError("dry-run must not call the gateway")

    monkeypatch.setattr(openai_compat, "chat_completion", boom)

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(
        params={"metrics": ["M1", "M3"]},
        inputs={"dataset": dataset, "engine_config": _engine_config()}, dry_run=True,
    )
    result = TextJudgeNodeExecutor().run(ctx)

    assert result.status == "done"
    assert result.meta["dry_run"] is True
    assert result.meta["estimated_calls"] == {"text_judge_calls": 2}
    assert result.outputs["judge_result"] == {}


def test_live_call_rejected_without_allow_live(make_ctx):
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(
        params={"metrics": ["M1"]},
        inputs={"dataset": dataset, "engine_config": _engine_config()},
        dry_run=False, allow_live=False,
    )
    result = TextJudgeNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "--live" in result.error


def test_missing_dataset_input_is_a_node_error(make_ctx):
    ctx = make_ctx(params={}, inputs={"engine_config": _engine_config()}, dry_run=True)
    result = TextJudgeNodeExecutor().run(ctx)
    assert result.status == "error"


def test_missing_engine_config_input_is_a_node_error(make_ctx):
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(params={"metrics": ["M1"]}, inputs={"dataset": dataset}, dry_run=True)
    result = TextJudgeNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "engine_config" in result.error


def test_unknown_metric_is_a_node_error(make_ctx):
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(
        params={"metrics": ["M9"]},
        inputs={"dataset": dataset, "engine_config": _engine_config()}, dry_run=True,
    )
    result = TextJudgeNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "M9" in result.error


def test_video_metric_is_rejected_as_non_text(make_ctx):
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(
        params={"metrics": ["M2"]},
        inputs={"dataset": dataset, "engine_config": _engine_config()}, dry_run=True,
    )
    result = TextJudgeNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "M2" in result.error


def test_checkpoint_resume_skips_completed_pairs(monkeypatch, make_ctx):
    calls = {"n": 0}

    def fake_chat(**kwargs):
        calls["n"] += 1
        return _fake_chat_result()

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat)

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(
        params={"metrics": ["M1", "M3"]},
        inputs={"dataset": dataset, "engine_config": _engine_config()},
        dry_run=False, allow_live=True,
    )

    result1 = TextJudgeNodeExecutor().run(ctx)
    assert result1.status == "done"
    assert calls["n"] == 2  # one call per metric
    jr1 = result1.outputs["judge_result"]["prj-x::0::peanut"]
    assert set(jr1) == {"M1", "M3"}
    assert ctx.checkpoint.has("prj-x::0::peanut::M1")
    assert ctx.checkpoint.has("prj-x::0::peanut::M3")

    # Re-run with the same checkpoint store -> both metrics are cached, no new calls.
    result2 = TextJudgeNodeExecutor().run(ctx)
    assert result2.status == "done"
    assert calls["n"] == 2  # unchanged
    assert set(result2.outputs["judge_result"]["prj-x::0::peanut"]) == {"M1", "M3"}


def test_progress_events_report_one_per_item_metric_pair(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())

    dataset = {
        "prj-x::0::peanut": _sample("prj-x::0::peanut"),
        "prj-x::1::peanut": _sample("prj-x::1::peanut"),
    }
    ctx = make_ctx(
        params={"metrics": ["M1", "M3"]},
        inputs={"dataset": dataset, "engine_config": _engine_config()},
        dry_run=False, allow_live=True,
    )
    events: list[tuple[str, dict]] = []
    ctx.progress_cb = lambda event, payload: events.append((event, payload))

    TextJudgeNodeExecutor().run(ctx)

    init_events = [payload for event, payload in events if event == "judge_progress_init"]
    assert init_events == [{"total": 4}]  # 2 items x 2 metrics
    metric_events = [e for e in events if e[0] == "judge_metric"]
    assert len(metric_events) == 4


def test_concurrency_produces_the_same_results_as_sequential(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())
    dataset = {f"item{i}::peanut": _sample(f"item{i}") for i in range(5)}
    ctx = make_ctx(
        params={"metrics": ["M1", "M3"]},
        inputs={"dataset": dataset, "engine_config": _engine_config(concurrency=4)},
        dry_run=False, allow_live=True,
    )
    result = TextJudgeNodeExecutor().run(ctx)

    assert result.status == "done"
    per_item = result.outputs["judge_result"]
    assert set(per_item) == set(dataset)
    for item_id in dataset:
        assert set(per_item[item_id]) == {"M1", "M3"}
        for res in per_item[item_id].values():
            assert res["parsed"]["score_1_to_5"] == 4
        assert ctx.checkpoint.has(f"{item_id}::M1")
        assert ctx.checkpoint.has(f"{item_id}::M3")


def test_judge_item_start_fires_exactly_once_per_item_under_concurrency(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())
    dataset = {f"item{i}::peanut": _sample(f"item{i}") for i in range(3)}
    ctx = make_ctx(
        params={"metrics": ["M1", "M3"]},
        inputs={"dataset": dataset, "engine_config": _engine_config(concurrency=3)},
        dry_run=False, allow_live=True,
    )
    events: list[tuple[str, dict]] = []
    ctx.progress_cb = lambda event, payload: events.append((event, payload))

    TextJudgeNodeExecutor().run(ctx)

    start_events = [p["item_id"] for e, p in events if e == "judge_item_start"]
    assert sorted(start_events) == sorted(dataset)  # each item exactly once, no dupes


def test_should_stop_cancels_not_yet_started_tasks(monkeypatch, make_ctx):
    calls = {"n": 0}
    lock = threading.Lock()

    def fake_chat(**kwargs):
        with lock:
            calls["n"] += 1
        return _fake_chat_result()

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat)

    dataset = {f"item{i}::peanut": _sample(f"item{i}") for i in range(20)}
    ctx = make_ctx(
        params={"metrics": ["M1"]},
        inputs={"dataset": dataset, "engine_config": _engine_config(concurrency=1)},
        dry_run=False, allow_live=True,
    )
    ctx.should_stop = lambda: calls["n"] >= 2

    result = TextJudgeNodeExecutor().run(ctx)

    assert result.status == "done"  # cut short, but not an error
    assert result.meta["stopped"] is True
    assert 2 <= result.meta["n_items_done"] <= 5
    assert result.meta["n_items_total"] == 20
    assert calls["n"] == result.meta["n_items_done"]
    completed_items = [iid for iid, m in result.outputs["judge_result"].items() if "M1" in m]
    assert len(completed_items) == result.meta["n_items_done"]
    for item_id in completed_items:
        assert ctx.checkpoint.has(f"{item_id}::M1")


def test_batch_size_default_calls_on_batch_once_per_completed_item(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())
    dataset = {f"item{i}::peanut": _sample(f"item{i}") for i in range(3)}
    ctx = make_ctx(
        params={"metrics": ["M1"]},
        inputs={"dataset": dataset, "engine_config": _engine_config()},
        dry_run=False, allow_live=True,
    )
    batches: list[dict] = []
    ctx.on_batch = lambda socket, value: batches.append((socket, dict(value)))

    result = TextJudgeNodeExecutor().run(ctx)

    assert result.status == "done"
    assert len(batches) == 3
    for socket, snapshot in batches:
        assert socket == "judge_result"
    sizes = sorted(len(snap) for _, snap in batches)
    assert sizes == [1, 2, 3]
    for _, snap in batches:
        for metrics_done in snap.values():
            assert metrics_done  # every included item is genuinely fully judged


def test_batch_size_n_groups_completions(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())
    dataset = {f"item{i}::peanut": _sample(f"item{i}") for i in range(4)}
    ctx = make_ctx(
        params={"metrics": ["M1"], "batch_size": 2},
        inputs={"dataset": dataset, "engine_config": _engine_config()},
        dry_run=False, allow_live=True,
    )
    batches: list[dict] = []
    ctx.on_batch = lambda socket, value: batches.append(dict(value))

    result = TextJudgeNodeExecutor().run(ctx)

    assert result.status == "done"
    assert len(batches) == 2
    complete_counts = [len(snap) for snap in batches]
    assert complete_counts == [2, 4]


def test_fully_cached_items_never_trigger_on_batch(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(
        params={"metrics": ["M1"]},
        inputs={"dataset": dataset, "engine_config": _engine_config()},
        dry_run=False, allow_live=True,
    )
    TextJudgeNodeExecutor().run(ctx)  # first pass: real call, checkpointed

    batches: list[dict] = []
    ctx.on_batch = lambda socket, value: batches.append(value)
    result = TextJudgeNodeExecutor().run(ctx)  # second pass: fully served from checkpoint

    assert result.status == "done"
    assert batches == []  # nothing "completed" during this run — it was already done


def test_no_on_batch_calls_when_ctx_on_batch_is_none(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(
        params={"metrics": ["M1"]},
        inputs={"dataset": dataset, "engine_config": _engine_config()},
        dry_run=False, allow_live=True,
    )
    assert ctx.on_batch is None
    result = TextJudgeNodeExecutor().run(ctx)
    assert result.status == "done"


def test_engine_error_is_not_checkpointed(monkeypatch, make_ctx):
    def fake_chat(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat)

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(
        params={"metrics": ["M1"]},
        inputs={"dataset": dataset, "engine_config": _engine_config()},
        dry_run=False, allow_live=True,
    )
    result = TextJudgeNodeExecutor().run(ctx)
    assert result.status == "done"  # per-judge errors don't abort the node
    jr = result.outputs["judge_result"]["prj-x::0::peanut"]["M1"]
    assert jr.get("error")
    assert not ctx.checkpoint.has("prj-x::0::peanut::M1")
