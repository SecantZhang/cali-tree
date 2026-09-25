import threading

import pytest

from vejudge.interface.node_vejudge import judge_node
from vejudge.interface.node_vejudge.judge_node import JudgeNodeExecutor
from vejudge.interface.node_vejudge.judge_spec import builtin_spec
from vejudge.lm_engine import openai_compat
from vejudge.lm_engine.creds import PlutoCreds


def _sample(item_id, *, video=""):
    return {
        "item_id": item_id,
        "project": "prj-x",
        "prompt_idx": 0,
        "model": "peanut",
        "use_case": "visual montage",
        "input": {"user_prompt": "do a thing"},
        "algorithm": "peanut",
        "output": {"output_video_path": video},
    }


def _fake_chat_result():
    return openai_compat.ChatResult(
        content='{"score_1_to_5": 4, "fully_complete": true, "missing_aspects": [], '
        '"reasoning_lines": ["a", "b"]}',
        prompt_tokens=1, completion_tokens=1, total_tokens=2,
        endpoint_host="primary", latency_s=0.01, model="m",
    )


def _engine_config(**overrides):
    return {"engine_kind": "gpt", **overrides}


def _custom_spec(**overrides):
    spec = {
        "kind": "custom",
        "spec_id": "cust",
        "label": "cust",
        "modality": "text",
        "system": None,
        "user_template": "Rate this: {user_prompt}",
        "expected_fields": ["score_1_to_5"],
        "score_path": "score_1_to_5",
        "target_dimension": "story_flow_visuals",
        "version": "custom-v1",
    }
    spec.update(overrides)
    return spec


@pytest.fixture(autouse=True)
def fake_creds(monkeypatch):
    monkeypatch.setattr(
        judge_node, "load_creds", lambda **kwargs: PlutoCreds(token="sk-test", base_url="https://primary")
    )


def _inputs(dataset, spec=None, **eng):
    return {"samples": dataset, "engine_config": _engine_config(**eng), "judge_spec": spec or builtin_spec("M1")}


def test_dry_run_estimates_calls_without_gateway(monkeypatch, make_ctx):
    def boom(**kwargs):
        raise AssertionError("dry-run must not call the gateway")

    monkeypatch.setattr(openai_compat, "chat_completion", boom)

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(inputs=_inputs(dataset), dry_run=True)
    result = JudgeNodeExecutor().run(ctx)

    assert result.status == "done"
    assert result.meta["dry_run"] is True
    assert result.meta["estimated_calls"] == {"judge_calls": 1}
    assert result.outputs["judge_result"] == {}


def test_live_call_rejected_without_allow_live(make_ctx):
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(inputs=_inputs(dataset), dry_run=False, allow_live=False)
    result = JudgeNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "--live" in result.error


def test_missing_samples_input_is_a_node_error(make_ctx):
    ctx = make_ctx(inputs={"engine_config": _engine_config(), "judge_spec": builtin_spec("M1")}, dry_run=True)
    result = JudgeNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "samples" in result.error


def test_missing_engine_config_input_is_a_node_error(make_ctx):
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(inputs={"samples": dataset, "judge_spec": builtin_spec("M1")}, dry_run=True)
    result = JudgeNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "engine_config" in result.error


def test_missing_judge_spec_input_is_a_node_error(make_ctx):
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(inputs={"samples": dataset, "engine_config": _engine_config()}, dry_run=True)
    result = JudgeNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "judge_spec" in result.error


def test_checkpoint_resume_skips_completed_items(monkeypatch, make_ctx):
    calls = {"n": 0}

    def fake_chat(**kwargs):
        calls["n"] += 1
        return _fake_chat_result()

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat)

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(inputs=_inputs(dataset), dry_run=False, allow_live=True)

    result1 = JudgeNodeExecutor().run(ctx)
    assert result1.status == "done"
    assert calls["n"] == 1  # one call per item for the single spec
    assert set(result1.outputs["judge_result"]["prj-x::0::peanut"]) == {"M1"}
    assert any(key.endswith("::prj-x::0::peanut::M1") for key in ctx.checkpoint.keys())

    result2 = JudgeNodeExecutor().run(ctx)
    assert result2.status == "done"
    assert calls["n"] == 1  # unchanged — served from checkpoint


def test_changing_temperature_invalidates_judge_checkpoint(monkeypatch, make_ctx):
    calls = {"n": 0}

    def fake_chat(**kwargs):
        calls["n"] += 1
        return _fake_chat_result()

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat)
    item = "prj-x::0::peanut"
    ctx = make_ctx(
        inputs=_inputs({item: _sample(item)}, temperature=0.0),
        dry_run=False, allow_live=True,
    )
    first = JudgeNodeExecutor().run(ctx)
    assert first.outputs["judge_result"][item]["M1"]["judge_provenance"]["temperature"] == 0.0
    ctx.inputs["engine_config"]["temperature"] = 0.8
    second = JudgeNodeExecutor().run(ctx)
    assert calls["n"] == 2
    assert second.outputs["judge_result"][item]["M1"]["judge_provenance"]["temperature"] == 0.8
    assert len([key for key in ctx.checkpoint.keys() if key.endswith(f"::{item}::M1")]) == 2


def test_progress_events_report_one_per_item(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())
    dataset = {
        "prj-x::0::peanut": _sample("prj-x::0::peanut"),
        "prj-x::1::peanut": _sample("prj-x::1::peanut"),
    }
    ctx = make_ctx(inputs=_inputs(dataset), dry_run=False, allow_live=True)
    events: list[tuple[str, dict]] = []
    ctx.progress_cb = lambda event, payload: events.append((event, payload))

    JudgeNodeExecutor().run(ctx)

    init_events = [payload for event, payload in events if event == "judge_progress_init"]
    assert init_events == [{"total": 2}]  # 2 items x 1 spec
    assert len([e for e in events if e[0] == "judge_metric"]) == 2


def test_concurrency_produces_the_same_results_as_sequential(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())
    dataset = {f"item{i}::peanut": _sample(f"item{i}") for i in range(5)}
    ctx = make_ctx(inputs=_inputs(dataset, concurrency=4), dry_run=False, allow_live=True)
    result = JudgeNodeExecutor().run(ctx)

    assert result.status == "done"
    per_item = result.outputs["judge_result"]
    assert set(per_item) == set(dataset)
    for item_id in dataset:
        assert set(per_item[item_id]) == {"M1"}
        assert per_item[item_id]["M1"]["parsed"]["score_1_to_5"] == 4
        assert any(key.endswith(f"::{item_id}::M1") for key in ctx.checkpoint.keys())


def test_judge_item_start_fires_once_per_item(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())
    dataset = {f"item{i}::peanut": _sample(f"item{i}") for i in range(3)}
    ctx = make_ctx(inputs=_inputs(dataset, concurrency=3), dry_run=False, allow_live=True)
    events: list[tuple[str, dict]] = []
    ctx.progress_cb = lambda event, payload: events.append((event, payload))

    JudgeNodeExecutor().run(ctx)

    start_events = [p["item_id"] for e, p in events if e == "judge_item_start"]
    assert sorted(start_events) == sorted(dataset)


def test_should_stop_cancels_not_yet_started_tasks(monkeypatch, make_ctx):
    calls = {"n": 0}
    lock = threading.Lock()

    def fake_chat(**kwargs):
        with lock:
            calls["n"] += 1
        return _fake_chat_result()

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat)

    dataset = {f"item{i}::peanut": _sample(f"item{i}") for i in range(20)}
    ctx = make_ctx(inputs=_inputs(dataset, concurrency=1), dry_run=False, allow_live=True)
    ctx.should_stop = lambda: calls["n"] >= 2

    result = JudgeNodeExecutor().run(ctx)

    assert result.status == "done"
    assert result.meta["stopped"] is True
    assert 2 <= result.meta["n_items_done"] <= 5
    assert result.meta["n_items_total"] == 20


def test_batch_size_default_calls_on_batch_once_per_completed_item(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())
    dataset = {f"item{i}::peanut": _sample(f"item{i}") for i in range(3)}
    ctx = make_ctx(inputs=_inputs(dataset), dry_run=False, allow_live=True)
    batches: list = []
    ctx.on_batch = lambda socket, value: batches.append((socket, dict(value)))

    result = JudgeNodeExecutor().run(ctx)

    assert result.status == "done"
    assert len(batches) == 3
    assert sorted(len(snap) for _, snap in batches) == [1, 2, 3]


def test_batch_size_n_groups_completions(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())
    dataset = {f"item{i}::peanut": _sample(f"item{i}") for i in range(4)}
    ctx = make_ctx(params={"batch_size": 2}, inputs=_inputs(dataset), dry_run=False, allow_live=True)
    batches: list = []
    ctx.on_batch = lambda socket, value: batches.append(dict(value))

    result = JudgeNodeExecutor().run(ctx)

    assert result.status == "done"
    assert [len(snap) for snap in batches] == [2, 4]


def test_engine_error_is_not_checkpointed(monkeypatch, make_ctx):
    def fake_chat(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat)

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(inputs=_inputs(dataset), dry_run=False, allow_live=True)
    result = JudgeNodeExecutor().run(ctx)
    assert result.status == "done"  # per-judge errors don't abort the node
    jr = result.outputs["judge_result"]["prj-x::0::peanut"]["M1"]
    assert jr.get("error")
    assert not ctx.checkpoint.has("n1::prj-x::0::peanut::M1")


def test_custom_spec_fills_template_and_carries_alignment(monkeypatch, make_ctx):
    captured = {}

    def fake_chat(**kwargs):
        captured["messages"] = kwargs["messages"]
        return _fake_chat_result()

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat)

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(inputs=_inputs(dataset, spec=_custom_spec()), dry_run=False, allow_live=True)
    result = JudgeNodeExecutor().run(ctx)

    assert result.status == "done"
    entry = result.outputs["judge_result"]["prj-x::0::peanut"]["cust"]
    # Template placeholder was filled from the sample.
    assert "do a thing" in captured["messages"][-1]["content"]
    # The result carries its alignment binding for the Eval node.
    assert entry["align"] == {"dimension": "story_flow_visuals", "score_path": "score_1_to_5"}
    assert entry["score"] == 4.0
    assert any(key.endswith("::prj-x::0::peanut::cust") for key in ctx.checkpoint.keys())


def test_calibration_input_injects_per_item_optimized_prompt(monkeypatch, make_ctx):
    captured = {}

    def fake_chat(**kwargs):
        captured.setdefault("system_by_call", []).append(
            next((m["content"] for m in kwargs["messages"] if m["role"] == "system"), None)
        )
        return _fake_chat_result()

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat)

    dataset = {
        "with::calib": _sample("with::calib"),
        "no::calib": _sample("no::calib"),
    }
    calibration = {
        "with::calib": {"optimized_prompt": "Calibration note: watch for X."},
        # "no::calib" intentionally absent — must fall back to the uncalibrated prompt.
    }
    inputs = _inputs(dataset)
    inputs["calibration"] = calibration
    ctx = make_ctx(inputs=inputs, dry_run=False, allow_live=True)

    result = JudgeNodeExecutor().run(ctx)

    assert result.status == "done"
    calibrated_entry = result.outputs["judge_result"]["with::calib"]["M1"]
    uncalibrated_entry = result.outputs["judge_result"]["no::calib"]["M1"]
    assert "Calibration note: watch for X." in (calibrated_entry["prompt_system"] or "")
    assert "Calibration note: watch for X." not in (uncalibrated_entry["prompt_system"] or "")


def test_general_calibration_is_applied_to_every_item(monkeypatch, make_ctx):
    captured = {}

    def fake_chat(**kwargs):
        captured.setdefault("systems", []).append(
            next((m["content"] for m in kwargs["messages"] if m["role"] == "system"), None)
        )
        return _fake_chat_result()

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat)

    dataset = {"a::x": _sample("a::x"), "b::x": _sample("b::x")}
    inputs = _inputs(dataset)
    inputs["general_calibration"] = "GENERAL NOTE: this judge under-scores."
    # A per-item note on just one item — to check the two get concatenated, not clobbered.
    inputs["calibration"] = {"a::x": {"optimized_prompt": "PER-ITEM NOTE for a."}}
    ctx = make_ctx(inputs=inputs, dry_run=False, allow_live=True)

    result = JudgeNodeExecutor().run(ctx)
    assert result.status == "done"
    ea = result.outputs["judge_result"]["a::x"]["M1"]
    eb = result.outputs["judge_result"]["b::x"]["M1"]
    # The general note reaches BOTH items...
    assert "GENERAL NOTE: this judge under-scores." in (ea["prompt_system"] or "")
    assert "GENERAL NOTE: this judge under-scores." in (eb["prompt_system"] or "")
    # ...and the item with a per-item note gets both (general first, then its own).
    assert "PER-ITEM NOTE for a." in (ea["prompt_system"] or "")
    assert "PER-ITEM NOTE for a." not in (eb["prompt_system"] or "")


def test_missing_calibration_input_is_a_silent_noop(monkeypatch, make_ctx):
    # "calibration" is optional — omitting it entirely must behave exactly like before.
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(inputs=_inputs(dataset), dry_run=False, allow_live=True)
    result = JudgeNodeExecutor().run(ctx)
    assert result.status == "done"


def test_video_spec_skips_items_with_no_video(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())
    dataset = {
        "with::vid": _sample("with::vid", video="/tmp/a.mp4"),
        "no::vid": _sample("no::vid", video=""),
    }
    ctx = make_ctx(inputs=_inputs(dataset, spec=builtin_spec("M5")), dry_run=False, allow_live=True)
    result = JudgeNodeExecutor().run(ctx)
    assert result.status == "done"
    assert result.outputs["judge_result"]["no::vid"]["M5"]["skipped"] is True
    assert result.outputs["judge_result"]["with::vid"]["M5"].get("skipped") is not True
