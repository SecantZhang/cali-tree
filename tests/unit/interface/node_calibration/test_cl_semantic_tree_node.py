import json

import pytest

from vejudge.database.dl_human_annotations.aggregate import AggregatedHumanRecord
from vejudge.interface.node_calibration import cl_semantic_tree_node
from vejudge.interface.node_calibration.cl_semantic_tree_node import ClSemanticTreeNodeExecutor
from vejudge.lm_engine.creds import PlutoCreds


class _ScriptedCritic:
    """Routes canned JSON by which pipeline stage's system prompt it sees — now including
    the concept-tagging stage that the semantic node adds."""

    def generate(self, prompt, media_inputs=None, schema=None, *, system=None, model=None):
        s = system or ""
        if "extract reusable evaluation rules" in s:
            payload = {"questions": [
                {"question": "Does the judge penalize user-requested repetition?", "raises_score_when": "no"}]}
        elif "consolidate a list of candidate" in s:
            payload = {"questions": [
                {"question": "Does the judge penalize user-requested repetition?", "raises_score_when": "no"},
                {"question": "Does the judge over-penalize by edit category?", "raises_score_when": "no"}]}
        elif "map each evaluation question to the ONE" in s:  # concept tagging
            payload = {"concepts": [
                {"index": 1, "key": "category_imbalance"}, {"index": 2, "key": None}]}
        elif "auditing an AI judge" in s:
            payload = {"decision_answers": {"q1": False, "q2": True}}
        else:
            payload = {}
        return {"content": json.dumps(payload), "model": "m",
                "promptTokens": 1, "completionTokens": 1, "totalTokens": 2}


def _sample(item_id):
    return {"item_id": item_id, "project": "prj-x", "prompt_idx": 0, "model": "peanut",
            "input": {"user_prompt": "do a thing"}, "output": {"assembly_json": {"clips": [item_id]}}}


def _calib(item_id, *, base, fms):
    return {
        "item_id": item_id, "metric_id": "M5", "original_score": base, "final_score": base,
        "score_delta": 0.0, "reasoning": "x", "failure_mode_summary": dict(fms),
        "transcript": {
            "item_id": item_id, "metric_id": "M5", "turns": [],
            "initial_judge_result": {"parsed": {"reasoning_lines": ["too repetitive"]}},
        },
    }


def _m5_label(item_id, score):
    return AggregatedHumanRecord(
        item_id=item_id, project="prj-x", prompt_idx=0, model="peanut",
        scores={"story_flow_visuals": score, "story_flow_voiceover": score},
        score_counts={"story_flow_visuals": 3, "story_flow_voiceover": 3},
    )


def _inputs(items, fms_by_item):
    return {
        "samples": {it: _sample(it) for it in items},
        "calibration_results": {it: _calib(it, base=b, fms=fms_by_item.get(it, {})) for it, b in items.items()},
        "labels": {it: _m5_label(it, h) for it, h in
                   {"a::0::peanut": 3.5, "b::0::peanut": 4.0, "c::0::peanut": 3.0}.items() if it in items},
        "critic_engine": {"engine_kind": "gpt"},
    }


@pytest.fixture(autouse=True)
def _fake_engine(monkeypatch):
    monkeypatch.setattr(cl_semantic_tree_node, "load_creds",
                        lambda: PlutoCreds(token="sk-test", base_url="https://x"))
    monkeypatch.setattr(cl_semantic_tree_node, "get_engine", lambda *a, **k: _ScriptedCritic())


def test_dry_run_estimates_critic_and_tagging_calls(make_ctx):
    items = {"a::0::peanut": 2.0, "b::0::peanut": 1.0}
    ctx = make_ctx(inputs=_inputs(items, {}), dry_run=True)
    result = ClSemanticTreeNodeExecutor().run(ctx)
    assert result.status == "done"
    assert result.meta["estimated_calls"] == {"critic_calls": 2, "tagging_calls": 1}


def test_full_run_builds_concept_features_and_a_semantic_comparator(make_ctx):
    items = {"a::0::peanut": 2.0, "b::0::peanut": 1.0, "c::0::peanut": 2.0}
    fms = {"a::0::peanut": {"audio_neglect": 2}, "b::0::peanut": {"audio_neglect": 1}}
    ctx = make_ctx(inputs=_inputs(items, fms), dry_run=False, allow_live=True)
    result = ClSemanticTreeNodeExecutor().run(ctx)

    assert result.status == "done"
    jr = result.outputs["judge_rule"]
    assert jr["n_items"] == 3
    names = jr["feature_names"]
    assert names[0] == "base_score"
    # Ontology-native fm count feature (audio_neglect was cited) + a concept-tagged rule
    # feature (q1 -> category_imbalance); q2 was untagged and dropped.
    assert "fm:audio_neglect" in names
    assert "rule:category_imbalance" in names
    assert "rule:" + "category_imbalance" in names and not any(n.startswith("q") for n in names)
    # The report carries the semantic comparator alongside base/bias/linear/tree.
    for split in ("insample_mae", "loo_mae"):
        assert "semantic" in jr[split] and "tree" in jr[split]
    # The exported tree + labels are self-contained for the UI.
    assert jr["tree"] is not None
    assert jr["feature_labels"]["base_score"]
    assert jr["concept_tags"] == ["category_imbalance", None]


def test_no_human_anchor_is_an_error(make_ctx):
    inp = _inputs({"a::0::peanut": 2.0}, {})
    inp["labels"] = {"a::0::peanut": AggregatedHumanRecord(
        item_id="a::0::peanut", project="prj-x", prompt_idx=0, model="peanut",
        scores={"video_addresses_prompt": 4.0}, score_counts={"video_addresses_prompt": 3})}
    ctx = make_ctx(inputs=inp, dry_run=False, allow_live=True)
    result = ClSemanticTreeNodeExecutor().run(ctx)
    assert result.status == "error" and "human anchor" in result.error
