import pytest

from vejudge.database.dl_human_annotations.aggregate import AggregatedHumanRecord
from vejudge.interface.node_calibration import cl_adversarial_node
from vejudge.interface.node_calibration.cl_adversarial_node import ClAdversarialNodeExecutor
from vejudge.lm_engine import openai_compat
from vejudge.lm_engine.creds import PlutoCreds

# A superset response satisfying M3's schema, D1's schema, and D2's schema at once —
# validate_judge_output only checks for the presence of each schema's required keys, so
# one canned dict can drive the anchor judge call and every debate turn identically.
_CANNED = {
    "score_1_to_5": 3, "fully_complete": True, "missing_aspects": [],
    "revised": False, "evidence": [],
    "agrees_with_judge": True, "cited_failure_modes": [],
    "reasoning_lines": ["looks fine"],
}


def _sample(item_id):
    return {
        "item_id": item_id, "project": "prj-x", "prompt_idx": 0, "model": "peanut",
        "use_case": "visual montage", "input": {"user_prompt": "do a thing"},
        "algorithm": "peanut", "output": {"output_video_path": ""},
    }


def _fake_chat_result(payload=None):
    import json
    return openai_compat.ChatResult(
        content=json.dumps(payload or _CANNED),
        prompt_tokens=1, completion_tokens=1, total_tokens=2,
        endpoint_host="primary", latency_s=0.01, model="m",
    )


def _engine_config(**overrides):
    return {"engine_kind": "gpt", **overrides}


def _inputs(dataset, *, labels=None, **eng):
    inputs = {
        "samples": dataset,
        "judge_engine": _engine_config(**eng),
        "human_engine": _engine_config(),
    }
    if labels is not None:
        inputs["labels"] = labels
    return inputs


@pytest.fixture(autouse=True)
def fake_creds(monkeypatch):
    monkeypatch.setattr(
        cl_adversarial_node, "load_creds",
        lambda: PlutoCreds(token="sk-test", base_url="https://primary"),
    )


def test_dry_run_estimates_calls_without_gateway(monkeypatch, make_ctx):
    def boom(**kwargs):
        raise AssertionError("dry-run must not call the gateway")

    monkeypatch.setattr(openai_compat, "chat_completion", boom)

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(
        params={"metric_id": "M3", "max_rounds": 4},
        inputs=_inputs(dataset), dry_run=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)

    assert result.status == "done"
    assert result.meta["dry_run"] is True
    assert result.meta["n_items"] == 1
    # 1 anchor call + up to 4 rounds * 2 debate turns = 9
    assert result.meta["estimated_calls"] == {"max_calls": 9}
    assert result.outputs["calibration_results"] == {}


def test_live_call_rejected_without_allow_live(make_ctx):
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(
        params={"metric_id": "M3"}, inputs=_inputs(dataset), dry_run=False, allow_live=False,
    )
    result = ClAdversarialNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "--live" in result.error


def test_missing_samples_input_is_a_node_error(make_ctx):
    ctx = make_ctx(
        params={"metric_id": "M3"},
        inputs={"judge_engine": _engine_config(), "human_engine": _engine_config()},
        dry_run=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "samples" in result.error


def test_missing_judge_engine_input_is_a_node_error(make_ctx):
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(
        params={"metric_id": "M3"},
        inputs={"samples": dataset, "human_engine": _engine_config()}, dry_run=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "judge_engine" in result.error


def test_missing_human_engine_input_is_a_node_error(make_ctx):
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(
        params={"metric_id": "M3"},
        inputs={"samples": dataset, "judge_engine": _engine_config()}, dry_run=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "human_engine" in result.error


def test_full_run_produces_calibrated_result_per_item(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(
        params={"metric_id": "M3", "max_rounds": 2, "retrieval_enabled": False},
        inputs=_inputs(dataset), dry_run=False, allow_live=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)

    assert result.status == "done"
    r = result.outputs["calibration_results"]["prj-x::0::peanut"]
    assert r["item_id"] == "prj-x::0::peanut"
    assert r["metric_id"] == "M3"
    assert r["original_score"] == 3.0
    assert r["final_score"] == 3.0
    assert r["converged"] is True
    assert "optimized_prompt" in r and r["optimized_prompt"]
    assert "reasoning" in r and r["reasoning"]
    assert "transcript" in r and r["transcript"]["turns"]
    assert r["human_scores"] == {}  # no labels wired


def test_checkpoint_resume_skips_completed_items(monkeypatch, make_ctx):
    calls = {"n": 0}

    def fake_chat(**kwargs):
        calls["n"] += 1
        return _fake_chat_result()

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat)

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(
        params={"metric_id": "M3", "max_rounds": 1, "retrieval_enabled": False},
        inputs=_inputs(dataset), dry_run=False, allow_live=True,
    )

    result1 = ClAdversarialNodeExecutor().run(ctx)
    assert result1.status == "done"
    n_first = calls["n"]
    assert n_first > 0
    assert ctx.checkpoint.has("prj-x::0::peanut::calibration::M3")

    result2 = ClAdversarialNodeExecutor().run(ctx)
    assert result2.status == "done"
    assert calls["n"] == n_first  # unchanged — served from checkpoint


def test_labels_produce_human_scores_for_aligned_metric(monkeypatch, make_ctx):
    # M5 has several ALIGNMENT entries (story_flow_voiceover, story_flow_visuals, ...).
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    labels = {
        "prj-x::0::peanut": AggregatedHumanRecord(
            item_id="prj-x::0::peanut", project="prj-x", prompt_idx=0, model="peanut",
            scores={"story_flow_visuals": 4.0, "story_flow_voiceover": 3.5},
        )
    }
    ctx = make_ctx(
        params={"metric_id": "M5", "max_rounds": 1, "retrieval_enabled": False},
        inputs=_inputs(dataset, labels=labels), dry_run=False, allow_live=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)

    assert result.status == "done"
    r = result.outputs["calibration_results"]["prj-x::0::peanut"]
    assert r["human_scores"]["story_flow_visuals"] == 4.0
    assert r["human_scores"]["story_flow_voiceover"] == 3.5


def test_metric_without_alignment_entry_yields_empty_human_scores(monkeypatch, make_ctx):
    # M4 has no ALIGNMENT crosswalk entry at all.
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    labels = {
        "prj-x::0::peanut": AggregatedHumanRecord(
            item_id="prj-x::0::peanut", project="prj-x", prompt_idx=0, model="peanut",
            scores={"video_addresses_prompt": 5.0},
        )
    }
    ctx = make_ctx(
        params={"metric_id": "M4", "max_rounds": 1, "retrieval_enabled": False},
        inputs=_inputs(dataset, labels=labels), dry_run=False, allow_live=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)

    assert result.status == "done"
    r = result.outputs["calibration_results"]["prj-x::0::peanut"]
    assert r["human_scores"] == {}


def test_human_dimension_override_used_for_unaligned_metric(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    labels = {
        "prj-x::0::peanut": AggregatedHumanRecord(
            item_id="prj-x::0::peanut", project="prj-x", prompt_idx=0, model="peanut",
            scores={"video_addresses_prompt": 5.0},
        )
    }
    ctx = make_ctx(
        params={
            "metric_id": "M4", "max_rounds": 1, "retrieval_enabled": False,
            "human_dimension_override": "video_addresses_prompt",
        },
        inputs=_inputs(dataset, labels=labels), dry_run=False, allow_live=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)

    assert result.status == "done"
    r = result.outputs["calibration_results"]["prj-x::0::peanut"]
    assert r["human_scores"] == {"video_addresses_prompt": 5.0}


def test_progress_events_are_calibration_specific(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(
        params={"metric_id": "M3", "max_rounds": 1, "retrieval_enabled": False},
        inputs=_inputs(dataset), dry_run=False, allow_live=True,
    )
    events: list[tuple[str, dict]] = []
    ctx.progress_cb = lambda event, payload: events.append((event, payload))

    ClAdversarialNodeExecutor().run(ctx)

    names = {e for e, _ in events}
    assert "calibration_progress_init" in names
    assert "calibration_item_start" in names
    assert "calibration_item_done" in names


def test_all_turns_failed_item_is_not_checkpointed(monkeypatch, make_ctx):
    def boom(**kwargs):
        raise RuntimeError("gateway down")

    monkeypatch.setattr(openai_compat, "chat_completion", boom)

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(
        params={"metric_id": "M3", "max_rounds": 2, "retrieval_enabled": False},
        inputs=_inputs(dataset), dry_run=False, allow_live=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)

    assert result.status == "done"  # per-item failure doesn't abort the node
    r = result.outputs["calibration_results"]["prj-x::0::peanut"]
    assert r["final_score"] is None
    assert r["flags"] == ["all_turns_failed"]
    assert not ctx.checkpoint.has("prj-x::0::peanut::calibration::M3")
