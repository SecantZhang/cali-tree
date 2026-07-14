import json

import pytest

from vejudge.database.dl_human_annotations.aggregate import AggregatedHumanRecord
from vejudge.interface.node_calibration import cl_adversarial_node
from vejudge.interface.node_calibration.cl_adversarial_node import (
    ClAdversarialNodeExecutor,
    _resolve_human_context,
)
from vejudge.lm_engine import openai_compat
from vejudge.lm_engine.creds import PlutoCreds

# A superset response satisfying D1's and D2's debate-turn schemas at once —
# validate_judge_output only checks for the presence of each schema's required keys.
_CANNED = {
    "score_1_to_5": 3, "revised": False, "evidence": [],
    "agrees_with_judge": True, "cited_failure_modes": [],
    "reasoning_lines": ["looks fine"],
}


def _sample(item_id):
    return {
        "item_id": item_id, "project": "prj-x", "prompt_idx": 0, "model": "peanut",
        "use_case": "visual montage", "input": {"user_prompt": "do a thing"},
        "algorithm": "peanut", "output": {"output_video_path": ""},
    }


def _judge_result(item_id, metric_id="M3", score=3.0, **overrides):
    entry = {
        "judge": metric_id, "metric_id": metric_id,
        "parsed": {"score_1_to_5": score, "reasoning_lines": ["baseline reasoning"]},
        "valid": True,
    }
    entry.update(overrides)
    return {item_id: {metric_id: entry}}


def _merge_judge_results(*results):
    merged: dict = {}
    for r in results:
        merged.update(r)
    return merged


def _fake_chat_result(payload=None):
    return openai_compat.ChatResult(
        content=json.dumps(payload or _CANNED),
        prompt_tokens=1, completion_tokens=1, total_tokens=2,
        endpoint_host="primary", latency_s=0.01, model="m",
    )


def _engine_config(**overrides):
    return {"engine_kind": "gpt", **overrides}


def _inputs(dataset, judge_result, *, labels=None, **eng):
    inputs = {
        "samples": dataset,
        "judge_result": judge_result,
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


def test_does_not_opt_into_streaming_batch_previews():
    # This node's run() drives a real, live, multi-round debate — the opposite of the
    # "cheap and safe to call repeatedly" contract supports_partial_input requires (see
    # NodeExecutor's docstring). Opting in here previously meant the graph executor
    # re-ran a full, real debate as a "preview" every time the upstream Judge node
    # finished one more item, burning real gateway calls and blocking the Judge node's
    # own run() from returning for the entire span it showed as "running" in the UI.
    assert ClAdversarialNodeExecutor.supports_partial_input is False


def test_dry_run_estimates_calls_without_gateway(monkeypatch, make_ctx):
    def boom(**kwargs):
        raise AssertionError("dry-run must not call the gateway")

    monkeypatch.setattr(openai_compat, "chat_completion", boom)

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    # Simulates the upstream Judge node's own dry-run output (always {}) — the
    # calibration node's dry-run estimate must not depend on real judge_result content.
    ctx = make_ctx(
        params={"max_rounds": 4},
        inputs=_inputs(dataset, judge_result={}), dry_run=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)

    assert result.status == "done"
    assert result.meta["dry_run"] is True
    assert result.meta["n_items"] == 1
    # up to 4 rounds * 2 debate turns = 8 — no anchor call anymore (that's upstream's cost).
    assert result.meta["estimated_calls"] == {"max_calls": 8}
    assert result.outputs["calibration_results"] == {}


def test_live_call_rejected_without_allow_live(make_ctx):
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(
        inputs=_inputs(dataset, judge_result={}), dry_run=False, allow_live=False,
    )
    result = ClAdversarialNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "--live" in result.error


def test_missing_samples_input_is_a_node_error(make_ctx):
    ctx = make_ctx(
        inputs={
            "judge_result": {}, "judge_engine": _engine_config(), "human_engine": _engine_config(),
        },
        dry_run=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "samples" in result.error


def test_missing_judge_result_input_is_a_node_error(make_ctx):
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(
        inputs={
            "samples": dataset, "judge_engine": _engine_config(), "human_engine": _engine_config(),
        },
        dry_run=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "judge_result" in result.error


def test_missing_judge_engine_input_is_a_node_error(make_ctx):
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(
        inputs={"samples": dataset, "judge_result": {}, "human_engine": _engine_config()},
        dry_run=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "judge_engine" in result.error


def test_missing_human_engine_input_is_a_node_error(make_ctx):
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    ctx = make_ctx(
        inputs={"samples": dataset, "judge_result": {}, "judge_engine": _engine_config()},
        dry_run=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "human_engine" in result.error


def test_full_run_produces_calibrated_result_per_item(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    judge_result = _judge_result("prj-x::0::peanut", metric_id="M3", score=3.0)
    ctx = make_ctx(
        params={"max_rounds": 2, "retrieval_enabled": False},
        inputs=_inputs(dataset, judge_result), dry_run=False, allow_live=True,
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
    assert r["human_gap"] == {}
    assert r["grounded"] is False
    assert result.meta["n_items_no_judge_result"] == 0
    assert result.meta["n_items_unusable_anchor"] == 0


def test_builtin_only_guard_rejects_custom_judge_result(monkeypatch, make_ctx):
    def boom(**kwargs):
        raise AssertionError("must fail before any gateway call")

    monkeypatch.setattr(openai_compat, "chat_completion", boom)

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    judge_result = {
        "prj-x::0::peanut": {
            "cust": {
                "judge": "cust", "metric_id": "cust", "spec_kind": "custom",
                "parsed": {"score_1_to_5": 3}, "valid": True,
                "align": {"dimension": "story_flow_visuals", "score_path": "score_1_to_5"},
            }
        }
    }
    ctx = make_ctx(
        inputs=_inputs(dataset, judge_result), dry_run=False, allow_live=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "cust" in result.error
    assert "builtin" in result.error.lower()


def test_binary_gate_metric_rejected_with_a_clear_error(monkeypatch, make_ctx):
    # M1 (Assembly Failure) is a real, live-observed case: a binary pass/fail gate whose
    # judge output has no score_1_to_5 at all (see m1_assembly_failure.py — its schema is
    # `failure`/`severity`, not a score). Every item's anchor would be excluded by
    # _usable_anchor for the same underlying reason, which used to surface as a generic
    # "no usable anchor" error blaming the (perfectly healthy) upstream Judge node. This
    # must instead name the real cause up front.
    def boom(**kwargs):
        raise AssertionError("must fail before any gateway call")

    monkeypatch.setattr(openai_compat, "chat_completion", boom)

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    judge_result = {
        "prj-x::0::peanut": {
            "M1": {
                "judge": "M1_assembly_failure", "metric_id": "M1",
                "parsed": {"failure": True, "severity": "major", "reasoning_lines": ["x"]},
                "valid": True,
            }
        }
    }
    ctx = make_ctx(
        inputs=_inputs(dataset, judge_result), dry_run=False, allow_live=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "M1" in result.error
    assert "score-based" in result.error.lower()
    assert "binary pass/fail gate" in result.error


def test_items_with_skipped_or_errored_anchor_are_excluded(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())

    dataset = {
        "prj-x::0::peanut": _sample("prj-x::0::peanut"),  # usable anchor
        "prj-x::1::peanut": _sample("prj-x::1::peanut"),  # skipped upstream (no video)
        "prj-x::2::peanut": _sample("prj-x::2::peanut"),  # errored upstream
    }
    judge_result = _merge_judge_results(
        _judge_result("prj-x::0::peanut", metric_id="M3", score=3.0),
        {"prj-x::1::peanut": {"M3": {"judge": "M3", "metric_id": "M3", "parsed": None, "skipped": True}}},
        {"prj-x::2::peanut": {"M3": {"judge": "M3", "metric_id": "M3", "parsed": None, "error": "boom"}}},
    )
    ctx = make_ctx(
        params={"max_rounds": 1, "retrieval_enabled": False},
        inputs=_inputs(dataset, judge_result), dry_run=False, allow_live=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)

    assert result.status == "done"
    assert set(result.outputs["calibration_results"]) == {"prj-x::0::peanut"}
    assert result.meta["n_items_no_judge_result"] == 0
    assert result.meta["n_items_unusable_anchor"] == 2


def test_anchor_with_parsed_dict_but_no_score_key_is_excluded(monkeypatch, make_ctx):
    # A `parsed` dict can be non-empty (schema-valid) yet still miss the actual score
    # field — previously `_usable_anchor` only checked `parsed` was truthy, letting this
    # through as "usable"; the debate would then crash formatting a None initial_score
    # (calibrated_result.render_optimized_prompt_addendum). It must be excluded here,
    # same as a skipped/errored anchor, not silently reach the debate.
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())

    dataset = {
        "prj-x::0::peanut": _sample("prj-x::0::peanut"),
        "prj-x::1::peanut": _sample("prj-x::1::peanut"),
    }
    judge_result = _merge_judge_results(
        _judge_result("prj-x::0::peanut", metric_id="M3", score=3.0),
        {
            "prj-x::1::peanut": {
                "M3": {
                    "judge": "M3", "metric_id": "M3",
                    "parsed": {"reasoning_lines": ["no score in here"]},
                    "valid": True,
                }
            }
        },
    )
    ctx = make_ctx(
        params={"max_rounds": 1, "retrieval_enabled": False},
        inputs=_inputs(dataset, judge_result), dry_run=False, allow_live=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)

    assert result.status == "done"
    assert set(result.outputs["calibration_results"]) == {"prj-x::0::peanut"}
    assert result.meta["n_items_unusable_anchor"] == 1


def test_items_missing_from_judge_result_entirely_are_excluded(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())

    dataset = {
        "prj-x::0::peanut": _sample("prj-x::0::peanut"),
        "prj-x::1::peanut": _sample("prj-x::1::peanut"),  # never judged upstream
    }
    judge_result = _judge_result("prj-x::0::peanut", metric_id="M3", score=3.0)
    ctx = make_ctx(
        params={"max_rounds": 1, "retrieval_enabled": False},
        inputs=_inputs(dataset, judge_result), dry_run=False, allow_live=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)

    assert result.status == "done"
    assert set(result.outputs["calibration_results"]) == {"prj-x::0::peanut"}
    assert result.meta["n_items_no_judge_result"] == 1
    assert result.meta["n_items_unusable_anchor"] == 0


def test_no_usable_anchor_at_all_is_a_node_error(make_ctx):
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    judge_result = {
        "prj-x::0::peanut": {"M3": {"judge": "M3", "metric_id": "M3", "parsed": None, "skipped": True}}
    }
    ctx = make_ctx(
        inputs=_inputs(dataset, judge_result), dry_run=False, allow_live=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "No usable" in result.error


def test_checkpoint_resume_skips_completed_items(monkeypatch, make_ctx):
    calls = {"n": 0}

    def fake_chat(**kwargs):
        calls["n"] += 1
        return _fake_chat_result()

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat)

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    judge_result = _judge_result("prj-x::0::peanut", metric_id="M3", score=3.0)
    ctx = make_ctx(
        params={"max_rounds": 1, "retrieval_enabled": False},
        inputs=_inputs(dataset, judge_result), dry_run=False, allow_live=True,
    )

    result1 = ClAdversarialNodeExecutor().run(ctx)
    assert result1.status == "done"
    n_first = calls["n"]
    assert n_first > 0
    assert ctx.checkpoint.has("prj-x::0::peanut::calibration::M3")

    result2 = ClAdversarialNodeExecutor().run(ctx)
    assert result2.status == "done"
    assert calls["n"] == n_first  # unchanged — served from checkpoint


def test_human_scores_and_gap_survive_a_disk_reload(monkeypatch, make_ctx):
    # Regression test for the checkpoint-ordering bug: human_scores/human_gap used to
    # be attached to each item's result dict in a post-loop AFTER _concurrent_debate.py
    # had already checkpointed that same dict to disk. In-memory it looked fine (same
    # dict object, mutated in place) — the bug only showed up once the checkpoint file
    # was reloaded fresh (a --continue resume, or a server restart). Using a BRAND-NEW
    # CheckpointStore pointed at the same file (not ctx.checkpoint, which shares the
    # live in-memory dict reference and would false-positive-pass even with the bug
    # present) is what actually proves the merge happens before the write.
    from vejudge.checkpoint import CheckpointStore

    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    judge_result = _judge_result("prj-x::0::peanut", metric_id="M3", score=3.0)
    labels = {
        "prj-x::0::peanut": AggregatedHumanRecord(
            item_id="prj-x::0::peanut", project="prj-x", prompt_idx=0, model="peanut",
            scores={"video_addresses_prompt": 4.0},
            score_counts={"video_addresses_prompt": 2},
        )
    }
    ctx = make_ctx(
        params={"max_rounds": 1, "retrieval_enabled": False},
        inputs=_inputs(dataset, judge_result, labels=labels), dry_run=False, allow_live=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)
    assert result.status == "done"

    reloaded = CheckpointStore(ctx.checkpoint.path)
    entry = reloaded.get("prj-x::0::peanut::calibration::M3")
    assert entry is not None
    assert entry["human_scores"] == {"video_addresses_prompt": {"score": 4.0, "n": 2}}
    assert entry["human_gap"]["video_addresses_prompt"] is not None
    assert entry["grounded"] is False


def test_resolve_human_context_anchor_is_rater_count_weighted():
    # 3.0 rated by 1 annotator, 4.5 rated by 3 — the well-supported dimension should
    # dominate: weighted (3.0*1 + 4.5*3)/(1+3) = 4.125, NOT the unweighted 3.75.
    agg = AggregatedHumanRecord(
        item_id="x", project="p", prompt_idx=0, model="peanut",
        scores={"story_flow_voiceover": 3.0, "story_flow_visuals": 4.5},
        score_counts={"story_flow_voiceover": 1, "story_flow_visuals": 3},
    )
    ctx = _resolve_human_context(agg, ["story_flow_voiceover", "story_flow_visuals"])
    assert ctx["anchor_score"] == pytest.approx(4.125)
    assert ctx["anchor_score"] != pytest.approx(3.75)  # not the unweighted mean
    # Per-dimension scores + rater counts are preserved separately, not collapsed.
    assert ctx["human_scores"]["story_flow_voiceover"] == {"score": 3.0, "n": 1}
    assert ctx["human_scores"]["story_flow_visuals"] == {"score": 4.5, "n": 3}


def test_resolve_human_context_skips_dimensions_without_data():
    # A dimension with no human score (n=0) contributes neither a weight nor a value.
    agg = AggregatedHumanRecord(
        item_id="x", project="p", prompt_idx=0, model="peanut",
        scores={"story_flow_voiceover": 4.0, "story_flow_visuals": None},
        score_counts={"story_flow_voiceover": 2, "story_flow_visuals": 0},
    )
    ctx = _resolve_human_context(agg, ["story_flow_voiceover", "story_flow_visuals"])
    assert ctx["anchor_score"] == pytest.approx(4.0)  # only the one with data


def test_resolve_human_context_none_when_no_usable_data():
    assert _resolve_human_context(None, ["story_flow_voiceover"])["anchor_score"] is None
    agg = AggregatedHumanRecord(
        item_id="x", project="p", prompt_idx=0, model="peanut",
        scores={"story_flow_voiceover": None}, score_counts={"story_flow_voiceover": 0},
    )
    assert _resolve_human_context(agg, ["story_flow_voiceover"])["anchor_score"] is None


def test_grounded_mode_end_to_end_with_a_real_usable_anchor(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    judge_result = _judge_result("prj-x::0::peanut", metric_id="M3", score=3.0)
    labels = {
        "prj-x::0::peanut": AggregatedHumanRecord(
            item_id="prj-x::0::peanut", project="prj-x", prompt_idx=0, model="peanut",
            scores={"video_addresses_prompt": 3.0},
            score_counts={"video_addresses_prompt": 4},
        )
    }
    ctx = make_ctx(
        params={"max_rounds": 1, "retrieval_enabled": False, "ground_in_human_labels": True},
        inputs=_inputs(dataset, judge_result, labels=labels), dry_run=False, allow_live=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)

    assert result.status == "done"
    r = result.outputs["calibration_results"]["prj-x::0::peanut"]
    # Anchor score (3.0) matches the human score (3.0) exactly, and the canned response
    # (_CANNED) also scores 3 -- closes the gap on round 1 via "epsilon_human".
    assert r["grounded"] is True
    assert r["converged"] is True
    assert "epsilon_human" in r["flags"]


def test_grounded_mode_per_item_fallback_when_one_item_has_no_human_anchor(monkeypatch, make_ctx):
    # Two items under ground_in_human_labels=True: one has a usable human anchor, the
    # other has none (0 raters for its mapped dimension) -- each item's fallback must
    # be independent, no all-or-nothing behavior for the whole run.
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())

    dataset = {
        "prj-x::0::peanut": _sample("prj-x::0::peanut"),
        "prj-x::1::peanut": _sample("prj-x::1::peanut"),
    }
    judge_result = _merge_judge_results(
        _judge_result("prj-x::0::peanut", metric_id="M3", score=3.0),
        _judge_result("prj-x::1::peanut", metric_id="M3", score=3.0),
    )
    labels = {
        "prj-x::0::peanut": AggregatedHumanRecord(
            item_id="prj-x::0::peanut", project="prj-x", prompt_idx=0, model="peanut",
            scores={"video_addresses_prompt": 3.0},
            score_counts={"video_addresses_prompt": 2},
        ),
        # No AggregatedHumanRecord at all for prj-x::1::peanut -- 0 raters, per the
        # reported prj-dog-owner-interview::0::peanut case.
    }
    ctx = make_ctx(
        params={"max_rounds": 1, "retrieval_enabled": False, "ground_in_human_labels": True},
        inputs=_inputs(dataset, judge_result, labels=labels), dry_run=False, allow_live=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)

    assert result.status == "done"
    by_id = result.outputs["calibration_results"]
    assert by_id["prj-x::0::peanut"]["grounded"] is True
    assert by_id["prj-x::1::peanut"]["grounded"] is False


def test_labels_produce_human_scores_for_aligned_metric(monkeypatch, make_ctx):
    # M5 has several ALIGNMENT entries (story_flow_voiceover, story_flow_visuals, ...).
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    judge_result = _judge_result("prj-x::0::peanut", metric_id="M5", score=3.0)
    labels = {
        "prj-x::0::peanut": AggregatedHumanRecord(
            item_id="prj-x::0::peanut", project="prj-x", prompt_idx=0, model="peanut",
            scores={"story_flow_visuals": 4.0, "story_flow_voiceover": 3.5},
            score_counts={"story_flow_visuals": 3, "story_flow_voiceover": 2},
        )
    }
    ctx = make_ctx(
        params={"max_rounds": 1, "retrieval_enabled": False},
        inputs=_inputs(dataset, judge_result, labels=labels), dry_run=False, allow_live=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)

    assert result.status == "done"
    r = result.outputs["calibration_results"]["prj-x::0::peanut"]
    assert r["human_scores"]["story_flow_visuals"] == {"score": 4.0, "n": 3}
    assert r["human_scores"]["story_flow_voiceover"] == {"score": 3.5, "n": 2}
    # final_score is 3.0 (canned response) — human_gap is the always-on passive signal,
    # computed regardless of ground_in_human_labels (unset here, defaults False).
    assert r["human_gap"]["story_flow_visuals"] == pytest.approx(1.0)
    assert r["human_gap"]["story_flow_voiceover"] == pytest.approx(0.5)
    assert r["grounded"] is False


def test_metric_without_alignment_entry_yields_empty_human_scores(monkeypatch, make_ctx):
    # M4 has no ALIGNMENT crosswalk entry at all.
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    judge_result = _judge_result("prj-x::0::peanut", metric_id="M4", score=4.0)
    labels = {
        "prj-x::0::peanut": AggregatedHumanRecord(
            item_id="prj-x::0::peanut", project="prj-x", prompt_idx=0, model="peanut",
            scores={"video_addresses_prompt": 5.0},
        )
    }
    ctx = make_ctx(
        params={"max_rounds": 1, "retrieval_enabled": False},
        inputs=_inputs(dataset, judge_result, labels=labels), dry_run=False, allow_live=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)

    assert result.status == "done"
    r = result.outputs["calibration_results"]["prj-x::0::peanut"]
    assert r["human_scores"] == {}
    assert r["human_gap"] == {}
    assert r["grounded"] is False


def test_human_dimension_override_used_for_unaligned_metric(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())

    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    judge_result = _judge_result("prj-x::0::peanut", metric_id="M4", score=4.0)
    labels = {
        "prj-x::0::peanut": AggregatedHumanRecord(
            item_id="prj-x::0::peanut", project="prj-x", prompt_idx=0, model="peanut",
            scores={"video_addresses_prompt": 5.0},
            score_counts={"video_addresses_prompt": 1},
        )
    }
    ctx = make_ctx(
        params={
            "max_rounds": 1, "retrieval_enabled": False,
            "human_dimension_override": "video_addresses_prompt",
        },
        inputs=_inputs(dataset, judge_result, labels=labels), dry_run=False, allow_live=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)

    assert result.status == "done"
    r = result.outputs["calibration_results"]["prj-x::0::peanut"]
    assert r["human_scores"] == {"video_addresses_prompt": {"score": 5.0, "n": 1}}


def test_progress_events_are_calibration_specific(monkeypatch, make_ctx):
    monkeypatch.setattr(openai_compat, "chat_completion", lambda **k: _fake_chat_result())
    dataset = {"prj-x::0::peanut": _sample("prj-x::0::peanut")}
    judge_result = _judge_result("prj-x::0::peanut", metric_id="M3", score=3.0)
    ctx = make_ctx(
        params={"max_rounds": 1, "retrieval_enabled": False},
        inputs=_inputs(dataset, judge_result), dry_run=False, allow_live=True,
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
    judge_result = _judge_result("prj-x::0::peanut", metric_id="M3", score=3.0)
    ctx = make_ctx(
        params={"max_rounds": 2, "retrieval_enabled": False},
        inputs=_inputs(dataset, judge_result), dry_run=False, allow_live=True,
    )
    result = ClAdversarialNodeExecutor().run(ctx)

    assert result.status == "done"  # per-item failure doesn't abort the node
    r = result.outputs["calibration_results"]["prj-x::0::peanut"]
    assert r["final_score"] is None
    assert r["flags"] == ["all_turns_failed"]
    assert not ctx.checkpoint.has("prj-x::0::peanut::calibration::M3")
