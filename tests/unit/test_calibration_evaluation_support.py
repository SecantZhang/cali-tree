import pytest

from vejudge.core.calibration.debate.eval.rule_fit import fit_and_evaluate
from vejudge.interface.node_calibration.evaluation_support import (
    build_observations,
    filter_constant_questions,
    impute_missing_semantic_values,
    semantic_summary_text,
    stable_holdout_split,
)


def test_raw_ratings_sum_to_one_weight_per_video_and_drive_weighted_fit():
    anchored = {
        "a": {"base": 0.0, "humans": [1.0] * 10},
        "b": {"base": 0.0, "humans": [4.0]},
        "c": {"base": 0.0, "humans": [5.0]},
    }
    ids, groups, bases, humans, feats, weights = build_observations(
        anchored, {item: [] for item in anchored},
    )
    assert sum(weights[obs] for obs in ids if groups[obs] == "a") == pytest.approx(1.0)
    assert sum(weights[obs] for obs in ids if groups[obs] == "b") == pytest.approx(1.0)
    report = fit_and_evaluate(
        item_ids=ids, bases=bases, humans=humans, feats_full=feats,
        feature_names=["base_score"], loo_groups=groups,
        observation_weights=weights, train_groups=["a", "b", "c"], validation_groups=[],
    )
    # Equal-video bias predicts the mean of item means: (1+4+5)/3, not the
    # annotation-count-weighted mean (10+4+5)/12.
    assert report["insample_mae"]["bias"] == pytest.approx(1.5555555555555554)
    assert report["insample_weighted_mae"]["bias"] == pytest.approx(
        report["insample_mae"]["bias"],
    )


def test_frozen_split_is_stable_and_disjoint():
    items = [f"item-{index}" for index in range(20)]
    train1, validation1 = stable_holdout_split(items, validation_fraction=0.2, split_seed=7)
    train2, validation2 = stable_holdout_split(list(reversed(items)), validation_fraction=0.2, split_seed=7)
    assert (train1, validation1) == (train2, validation2)
    assert len(validation1) == 4
    assert set(train1).isdisjoint(validation1)


def test_constant_questions_are_dropped_using_training_items_only():
    bank = [{"question": "constant"}, {"question": "varies"}]
    booleans = {"train-a": [0, 0], "train-b": [0, 1], "held": [1, 1]}
    kept, filtered, prevalence, dropped = filter_constant_questions(
        bank, booleans, ["train-a", "train-b"],
    )
    assert kept == [{"question": "varies"}]
    assert filtered["held"] == [1]
    assert prevalence[0]["positive_rate"] == 0
    assert dropped[0]["reason"] == "constant_on_training"


def test_missing_semantics_use_training_medians_not_validation_or_zero():
    values = {
        "train-a": [-1.0, 0.5],
        "train-b": [1.0, 1.0],
        "held": [0.0, 99.0],
    }
    missing = {"train-a": [], "train-b": [], "held": ["q1", "q2"]}
    imputed, diagnostics = impute_missing_semantic_values(
        values, missing, ["train-a", "train-b"],
    )
    # The held-out 99 never participates in either training-derived fill value.
    assert imputed["held"] == [0.0, 0.75]
    assert diagnostics[1]["n_training_observed"] == 2


def test_rule_mining_rejects_unsafe_stored_semantics_instead_of_using_transcript():
    result = {
        "semantic_summary": {
            "principle": "Match the human score of 5.",
            "applies_when": "always",
            "evidence_to_check": ["observable edit"],
            "scoring_guidance": "copy it",
        },
        "transcript": {"turns": [{"reasoning_lines": ["human ratings were [2, 5]"]}]},
    }
    assert semantic_summary_text(result) == ""
