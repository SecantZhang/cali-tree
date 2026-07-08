import threading

import pytest

from vejudge.interface.node_vejudge import judge_video_node
from vejudge.interface.node_vejudge.judge_video_node import VideoJudgeNodeExecutor
from vejudge.lm_engine import openai_compat
from vejudge.lm_engine.creds import PlutoCreds


def _sample(tmp_path, item_id, *, with_video=True):
    # Video-modality judges read the file at `output_video_path` for real (openai_compat's
    # `video_part()` base64-encodes it) before ever reaching a mocked `chat_completion` —
    # a fake, nonexistent path (e.g. "/tmp/x.mp4") fails there with a FileNotFoundError
    # long before the mock has a chance to intervene, so this needs a real (if tiny,
    # fake-content) file on disk, same as tests/e2e_fixture.py's convention.
    video_path = ""
    if with_video:
        p = tmp_path / f"{item_id.replace(':', '_')}.mp4"
        p.write_bytes(b"fake-mp4-bytes")
        video_path = str(p)
    return {
        "item_id": item_id,
        "project": "prj-x",
        "prompt_idx": 0,
        "model": "peanut",
        "use_case": "visual montage",
        "input": {"user_prompt": "do a thing"},
        "algorithm": "peanut",
        "output": {"output_video_path": video_path},
    }


def _fake_chat_result():
    return openai_compat.ChatResult(
        content='{"score_1_to_5": 4, "fully_complete": true, "missing_aspects": [], '
        '"reasoning_lines": ["a", "b"]}',
        prompt_tokens=1, completion_tokens=1, total_tokens=2,
        endpoint_host="primary", latency_s=0.01, model="m",
    )


def _engine_config(**overrides):
    # Every key has a fallback in judge_video_node.py's run() (via .get(...)), so an empty
    # dict is a valid, fully-default engine_config — tests only need to set the keys they
    # actually care about.
    return {"engine_kind": "gemini", **overrides}


@pytest.fixture(autouse=True)
def fake_creds(monkeypatch):
    monkeypatch.setattr(
        judge_video_node, "load_creds", lambda: PlutoCreds(token="sk-test", base_url="https://primary")
    )


def test_dry_run_estimates_calls_without_gateway(monkeypatch, make_ctx, tmp_path):
    def boom(**kwargs):
        raise AssertionError("dry-run must not call the gateway")

    monkeypatch.setattr(openai_compat, "chat_completion", boom)

    dataset = {"prj-x::0::peanut": _sample(tmp_path, "prj-x::0::peanut")}
    ctx = make_ctx(
        params={"metrics": ["M2", "M4"]},
        inputs={"dataset": dataset, "engine_config": _engine_config()}, dry_run=True,
    )
    result = VideoJudgeNodeExecutor().run(ctx)

    assert result.status == "done"
    assert result.meta["dry_run"] is True
    assert result.meta["estimated_calls"] == {"video_judge_calls": 2}
    assert result.outputs["judge_result"] == {}


def test_live_call_rejected_without_allow_live(make_ctx, tmp_path):
    dataset = {"prj-x::0::peanut": _sample(tmp_path, "prj-x::0::peanut")}
    ctx = make_ctx(
        params={"metrics": ["M2"]},
        inputs={"dataset": dataset, "engine_config": _engine_config()},
        dry_run=False, allow_live=False,
    )
    result = VideoJudgeNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "--live" in result.error


def test_missing_dataset_input_is_a_node_error(make_ctx):
    ctx = make_ctx(params={}, inputs={"engine_config": _engine_config()}, dry_run=True)
    result = VideoJudgeNodeExecutor().run(ctx)
    assert result.status == "error"


def test_missing_engine_config_input_is_a_node_error(make_ctx, tmp_path):
    dataset = {"prj-x::0::peanut": _sample(tmp_path, "prj-x::0::peanut")}
    ctx = make_ctx(params={"metrics": ["M2"]}, inputs={"dataset": dataset}, dry_run=True)
    result = VideoJudgeNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "engine_config" in result.error


def test_unknown_metric_is_a_node_error(make_ctx, tmp_path):
    dataset = {"prj-x::0::peanut": _sample(tmp_path, "prj-x::0::peanut")}
    ctx = make_ctx(
        params={"metrics": ["M9"]},
        inputs={"dataset": dataset, "engine_config": _engine_config()}, dry_run=True,
    )
    result = VideoJudgeNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "M9" in result.error


def test_text_metric_is_rejected_as_non_video(make_ctx, tmp_path):
    dataset = {"prj-x::0::peanut": _sample(tmp_path, "prj-x::0::peanut")}
    ctx = make_ctx(
        params={"metrics": ["M1"]},
        inputs={"dataset": dataset, "engine_config": _engine_config()}, dry_run=True,
    )
    result = VideoJudgeNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "M1" in result.error


def test_item_with_no_rendered_video_is_auto_skipped(monkeypatch, make_ctx, tmp_path):
    calls = {"n": 0}

    def fake_chat(**kwargs):
        calls["n"] += 1
        return _fake_chat_result()

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat)

    dataset = {
        "has_video::peanut": _sample(tmp_path, "has_video", with_video=True),
        "no_video::peanut": _sample(tmp_path, "no_video", with_video=False),
    }
    ctx = make_ctx(
        params={"metrics": ["M2"]},
        inputs={"dataset": dataset, "engine_config": _engine_config()},
        dry_run=False, allow_live=True,
    )
    result = VideoJudgeNodeExecutor().run(ctx)

    assert result.status == "done"
    assert calls["n"] == 1  # only the item with a rendered video made a real call
    assert result.outputs["judge_result"]["has_video::peanut"]["M2"].get("skipped") is not True
    assert result.outputs["judge_result"]["no_video::peanut"]["M2"]["skipped"] is True


def test_checkpoint_resume_skips_completed_pairs(monkeypatch, make_ctx, tmp_path):
    calls = {"n": 0}

    def fake_chat(**kwargs):
        calls["n"] += 1
        return _fake_chat_result()

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat)

    dataset = {"prj-x::0::peanut": _sample(tmp_path, "prj-x::0::peanut", with_video=True)}
    ctx = make_ctx(
        params={"metrics": ["M2", "M4"]},
        inputs={"dataset": dataset, "engine_config": _engine_config()},
        dry_run=False, allow_live=True,
    )

    result1 = VideoJudgeNodeExecutor().run(ctx)
    assert result1.status == "done", result1.outputs["judge_result"]
    assert calls["n"] == 2
    assert ctx.checkpoint.has("prj-x::0::peanut::M2")
    assert ctx.checkpoint.has("prj-x::0::peanut::M4")

    result2 = VideoJudgeNodeExecutor().run(ctx)
    assert result2.status == "done"
    assert calls["n"] == 2  # unchanged — served from checkpoint


def test_progress_init_reports_accurate_total_excluding_skipped_video(monkeypatch, make_ctx, tmp_path):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())

    dataset = {
        "item0::peanut": _sample(tmp_path, "item0", with_video=True),
        "item1::peanut": _sample(tmp_path, "item1", with_video=False),
    }
    ctx = make_ctx(
        params={"metrics": ["M2"]},
        inputs={"dataset": dataset, "engine_config": _engine_config()},
        dry_run=False, allow_live=True,
    )
    events: list[tuple[str, dict]] = []
    ctx.progress_cb = lambda event, payload: events.append((event, payload))

    VideoJudgeNodeExecutor().run(ctx)

    init_events = [payload for event, payload in events if event == "judge_progress_init"]
    assert init_events == [{"total": 1}]  # only item0 has a rendered video
    metric_events = [e for e in events if e[0] == "judge_metric"]
    assert len(metric_events) == 1


def test_concurrency_produces_the_same_results_as_sequential(monkeypatch, make_ctx, tmp_path):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())
    dataset = {f"item{i}::peanut": _sample(tmp_path, f"item{i}", with_video=True) for i in range(5)}
    ctx = make_ctx(
        params={"metrics": ["M2", "M4"]},
        inputs={"dataset": dataset, "engine_config": _engine_config(concurrency=4)},
        dry_run=False, allow_live=True,
    )
    result = VideoJudgeNodeExecutor().run(ctx)

    assert result.status == "done"
    per_item = result.outputs["judge_result"]
    assert set(per_item) == set(dataset)
    for item_id in dataset:
        assert set(per_item[item_id]) == {"M2", "M4"}
        for res in per_item[item_id].values():
            assert res["parsed"]["score_1_to_5"] == 4


def test_should_stop_cancels_not_yet_started_tasks(monkeypatch, make_ctx, tmp_path):
    calls = {"n": 0}
    lock = threading.Lock()

    def fake_chat(**kwargs):
        with lock:
            calls["n"] += 1
        return _fake_chat_result()

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat)

    dataset = {f"item{i}::peanut": _sample(tmp_path, f"item{i}", with_video=True) for i in range(20)}
    ctx = make_ctx(
        params={"metrics": ["M2"]},
        inputs={"dataset": dataset, "engine_config": _engine_config(concurrency=1)},
        dry_run=False, allow_live=True,
    )
    ctx.should_stop = lambda: calls["n"] >= 2

    result = VideoJudgeNodeExecutor().run(ctx)

    assert result.status == "done"
    assert result.meta["stopped"] is True
    assert 2 <= result.meta["n_items_done"] <= 5
    assert result.meta["n_items_total"] == 20


def test_batch_size_default_calls_on_batch_once_per_completed_item(monkeypatch, make_ctx, tmp_path):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())
    dataset = {f"item{i}::peanut": _sample(tmp_path, f"item{i}", with_video=True) for i in range(3)}
    ctx = make_ctx(
        params={"metrics": ["M2"]},
        inputs={"dataset": dataset, "engine_config": _engine_config()},
        dry_run=False, allow_live=True,
    )
    batches: list[dict] = []
    ctx.on_batch = lambda socket, value: batches.append((socket, dict(value)))

    result = VideoJudgeNodeExecutor().run(ctx)

    assert result.status == "done"
    assert len(batches) == 3
    for socket, snapshot in batches:
        assert socket == "judge_result"
    sizes = sorted(len(snap) for _, snap in batches)
    assert sizes == [1, 2, 3]


def test_engine_error_is_not_checkpointed(monkeypatch, make_ctx, tmp_path):
    def fake_chat(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat)

    dataset = {"prj-x::0::peanut": _sample(tmp_path, "prj-x::0::peanut", with_video=True)}
    ctx = make_ctx(
        params={"metrics": ["M2"]},
        inputs={"dataset": dataset, "engine_config": _engine_config()},
        dry_run=False, allow_live=True,
    )
    result = VideoJudgeNodeExecutor().run(ctx)
    assert result.status == "done"
    jr = result.outputs["judge_result"]["prj-x::0::peanut"]["M2"]
    assert jr.get("error")
    assert not ctx.checkpoint.has("prj-x::0::peanut::M2")
