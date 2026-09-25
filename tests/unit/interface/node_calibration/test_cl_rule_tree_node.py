import json

import pytest

from vejudge.database.dl_human_annotations.aggregate import AggregatedHumanRecord
from vejudge.interface.node_calibration import cl_rule_tree_node
from vejudge.interface.node_calibration.cl_rule_tree_node import ClRuleTreeNodeExecutor
from vejudge.interface.node_calibration.evaluation_support import stable_holdout_split
from vejudge.lm_engine.creds import PlutoCreds


class _ScriptedCritic:
    """Routes canned JSON by which pipeline stage's system prompt it sees."""

    def generate(self, prompt, media_inputs=None, schema=None, *, system=None, model=None):
        s = system or ""
        if "extract reusable evaluation rules" in s:
            payload = {"questions": [
                {"question": "Does the judge penalize user-requested repetition?", "raises_score_when": "no"}]}
        elif "consolidate a list of candidate" in s:
            payload = {"questions": [
                {"question": "Does the judge penalize user-requested repetition?", "raises_score_when": "no"},
                {"question": "Does the judge penalize an unstated constraint?", "raises_score_when": "no"}]}
        elif "independent semantic reviewer" in s:
            payload = {"decision_answers": {
                "q1": "a::0::peanut" not in prompt,
                "q2": "c::0::peanut" not in prompt,
            }}
        else:
            payload = {}
        return {"content": json.dumps(payload), "model": "m",
                "promptTokens": 1, "completionTokens": 1, "totalTokens": 2}


def _sample(item_id):
    return {"item_id": item_id, "project": "prj-x", "prompt_idx": 0, "model": "peanut",
            "input": {"user_prompt": "do a thing"}, "output": {"assembly_json": {"clips": [item_id]}}}


def _calib(item_id, *, base, metric_id="M5"):
    return {
        "item_id": item_id, "metric_id": metric_id, "original_score": base,
        "final_score": base, "score_delta": 0.0, "reasoning": "Original judge rationale: x",
        "semantic_summary": {
            "principle": f"Judge requested repetition consistently for {item_id}.",
            "applies_when": "The edit intentionally repeats material.",
            "evidence_to_check": ["Check the request and repeated clips."],
            "scoring_guidance": "Do not penalize requested repetition.",
        },
        "transcript": {
            "item_id": item_id, "metric_id": metric_id, "turns": [],
            "initial_judge_result": {"parsed": {"reasoning_lines": ["the judge said it was too repetitive"]}},
        },
    }


def _label(item_id, **dim_scores):
    return AggregatedHumanRecord(
        item_id=item_id, project="prj-x", prompt_idx=0, model="peanut",
        scores=dict(dim_scores), score_counts={d: 3 for d in dim_scores},
    )


# M5-aligned dims (postprocessing.align): story_flow_* / section_placement_*.
def _m5_label(item_id, score):
    return _label(item_id, story_flow_visuals=score, story_flow_voiceover=score)


def _inputs(items):
    samples = {it: _sample(it) for it in items}
    calibration_results = {it: _calib(it, base=b) for it, b in items.items()}
    labels = {it: _m5_label(it, h) for it, h in {
        "a::0::peanut": 3.5, "b::0::peanut": 4.0, "c::0::peanut": 3.0}.items() if it in items}
    return {"samples": samples, "calibration_results": calibration_results,
            "labels": labels, "critic_engine": {"engine_kind": "gpt"}}


@pytest.fixture(autouse=True)
def _fake_engine(monkeypatch):
    monkeypatch.setattr(cl_rule_tree_node, "load_creds",
                        lambda **kwargs: PlutoCreds(token="sk-test", base_url="https://x"))
    monkeypatch.setattr(cl_rule_tree_node, "get_engine", lambda *a, **k: _ScriptedCritic())


def test_missing_inputs_error(make_ctx):
    ctx = make_ctx(inputs={"samples": {}, "labels": {}, "critic_engine": {}}, dry_run=True)
    result = ClRuleTreeNodeExecutor().run(ctx)
    assert result.status == "error" and "calibration_results" in result.error


def test_dry_run_estimates_without_calls(make_ctx):
    items = {"a::0::peanut": 2.0, "b::0::peanut": 1.0}
    ctx = make_ctx(inputs=_inputs(items), dry_run=True)
    result = ClRuleTreeNodeExecutor().run(ctx)
    assert result.status == "done"
    assert result.outputs["judge_rule"] == {}
    assert result.meta["estimated_calls"] == {
        "rule_extraction_calls": 2, "bank_calls": 1, "critic_calls": 2,
    }


def test_unaggregated_labels_become_raw_fit_observations(make_ctx):
    items = {"a::0::peanut": 2.0, "b::0::peanut": 1.0}
    inputs = _inputs(items)
    for rec in inputs["labels"].values():
        rec.aggregation = "none"
        rec.scores = {d: None for d in rec.scores}
        rec.raw_scores = {
            "story_flow_visuals": [2.0, 4.0],
            "story_flow_voiceover": [3.0],
        }
    ctx = make_ctx(inputs=inputs, dry_run=False, allow_live=True)
    result = ClRuleTreeNodeExecutor().run(ctx)
    assert result.status == "done"
    report = result.outputs["judge_rule"]
    assert report["n_items"] == 2
    assert report["n_observations"] == 6
    assert report["per_item"]["a::0::peanut"]["human"] == [3.0, 2.0, 4.0]


def test_full_run_mines_bank_and_reports_mae(make_ctx):
    items = {"a::0::peanut": 2.0, "b::0::peanut": 1.0, "c::0::peanut": 2.0}
    ctx = make_ctx(inputs=_inputs(items), dry_run=False, allow_live=True)
    result = ClRuleTreeNodeExecutor().run(ctx)

    assert result.status == "done"
    jr = result.outputs["judge_rule"]
    assert jr["n_items"] == 3
    assert len(jr["bank"]) == 2  # canonicalized from the mined candidates
    assert jr["feature_names"] == ["base_score", "q1", "q2"]
    # Score-only and rule-feature comparators computed, in-sample + LOO.
    for split in ("insample_mae", "loo_mae"):
        assert set(jr[split]) == {"base", "bias", "score_linear", "linear", "tree"}
        assert jr[split]["base"] is not None
    # Baseline MAE = mean|base - human| — judge under-scores here, so it's clearly > 0.
    assert jr["insample_mae"]["base"] > 0.5
    assert "tree_rule" in jr and jr["per_item"]["a::0::peanut"]["booleans"] == [1, 0]


def test_frozen_holdout_mines_only_training_semantic_summaries(make_ctx, monkeypatch):
    class RecordingCritic(_ScriptedCritic):
        def __init__(self):
            self.extraction_prompts = []

        def generate(self, prompt, *args, system=None, **kwargs):
            if "extract reusable evaluation rules" in (system or ""):
                self.extraction_prompts.append(prompt)
            return super().generate(prompt, *args, system=system, **kwargs)

    critic = RecordingCritic()
    monkeypatch.setattr(cl_rule_tree_node, "get_engine", lambda *a, **k: critic)
    items = {"a::0::peanut": 2.0, "b::0::peanut": 1.0, "c::0::peanut": 2.0}
    training, validation = stable_holdout_split(list(items), validation_fraction=0.2, split_seed=0)
    ctx = make_ctx(
        inputs=_inputs(items), dry_run=False, allow_live=True,
        params={"evaluation_mode": "frozen_holdout", "validation_fraction": 0.2, "split_seed": 0},
    )
    report = ClRuleTreeNodeExecutor().run(ctx).outputs["judge_rule"]
    combined = "\n".join(critic.extraction_prompts)
    assert report["train_item_ids"] == training
    assert report["validation_item_ids"] == validation
    assert len(critic.extraction_prompts) == len(training)
    assert all(item in combined for item in training)
    assert all(item not in combined for item in validation)


def test_no_human_anchor_is_an_error(make_ctx):
    # Labels present but with no M5-aligned dimensions -> no usable anchor.
    inp = _inputs({"a::0::peanut": 2.0})
    inp["labels"] = {"a::0::peanut": _label("a::0::peanut", video_addresses_prompt=4.0)}
    ctx = make_ctx(inputs=inp, dry_run=False, allow_live=True)
    result = ClRuleTreeNodeExecutor().run(ctx)
    assert result.status == "error" and "human targets" in result.error


def test_preflight_reports_metric_aligned_label_skips_and_constant_raw_scores(make_ctx):
    items = {"a::0::peanut": 2.0, "b::0::peanut": 2.0}
    inputs = _inputs(items)
    inputs["labels"]["b::0::peanut"] = _label(
        "b::0::peanut", video_addresses_prompt=4.0,
    )
    report = ClRuleTreeNodeExecutor().run(
        make_ctx(inputs=inputs, dry_run=False, allow_live=True),
    ).outputs["judge_rule"]
    assert report["diagnostics"]["skipped_items"] == {
        "b::0::peanut": "no_usable_metric_aligned_human_target",
    }
    assert report["diagnostics"]["score_source"]["parsed_field"] == "score_1_to_5"
    assert any("constant" in warning for warning in report["warnings"])
