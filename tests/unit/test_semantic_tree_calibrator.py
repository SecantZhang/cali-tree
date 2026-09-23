import pytest

from vejudge.core.calibration import (
    PromptRoutedSemanticTreeCalibrator,
    SemanticDecisionTreeCalibrator,
)
from vejudge.core.calibration.base import Calibrator


def test_is_a_calibrator():
    c = SemanticDecisionTreeCalibrator()
    assert isinstance(c, Calibrator)
    assert c.version == "semantic-tree-v5-semantic-model-leaves"


def test_predict_before_fit_raises():
    with pytest.raises(RuntimeError):
        SemanticDecisionTreeCalibrator().predict([[2.0, 1.0]])


def test_ontology_weight_breaks_a_variance_tie():
    # Two boolean features that separate y IDENTICALLY (equal variance reduction). The
    # ontology gives one a higher weight, so the tree must split on that one.
    X = [[2, 1, 1], [2, 1, 1], [2, 0, 0], [2, 0, 0], [2, 1, 1], [2, 0, 0]]
    y = [4, 4, 2, 2, 4, 2]
    names = ["base_score", "rule:audio_neglect", "rule:scale_drift"]
    c = SemanticDecisionTreeCalibrator(
        feature_weights={"rule:audio_neglect": 0.9, "rule:scale_drift": 0.2}
    ).fit(X, y, feature_names=names)
    assert c.metadata()["tree"]["feature"] == "rule:audio_neglect"
    # And it predicts the two groups' means.
    assert c.predict([[2, 1, 1], [2, 0, 0]]) == [4.0, 2.0]


def test_degenerate_fit_is_a_lone_leaf():
    c = SemanticDecisionTreeCalibrator().fit(
        [[2, 0], [2, 1], [1, 0]], [3, 3, 3], feature_names=["base_score", "rule:x"]
    )
    tree = c.metadata()["tree"]
    assert tree["leaf"] is True and tree["value"] == 3.0


def test_export_matches_the_decision_tree_view_contract():
    X = [[2, 1], [2, 1], [2, 0], [2, 0]]
    y = [4, 4, 2, 2]
    c = SemanticDecisionTreeCalibrator(min_samples_leaf=2).fit(
        X, y, feature_names=["base_score", "rule:audio_neglect"],
    )
    tree = c.metadata()["tree"]
    # Same keys the SVG DecisionTreeView reads.
    assert set(tree) >= {"leaf", "samples", "value", "feature", "threshold", "left", "right"}
    assert tree["left"]["leaf"] and tree["right"]["leaf"]
    # feature_importances mirrors the applied weights (base_score defaults to 1.0).
    assert c.metadata()["feature_importances"] == [1.0, 1.0]


def test_leaf_prediction_is_weighted_median_for_primary_mae_objective():
    c = SemanticDecisionTreeCalibrator(max_depth=1, min_samples_leaf=3).fit(
        [[2], [2], [2], [2]], [1, 4, 4, 5],
        feature_names=["base_score"], sample_weight=[1, 1, 1, 1],
    )
    assert c.predict([[2]]) == [4.0]


def test_unlisted_feature_weights_default_to_full():
    c = SemanticDecisionTreeCalibrator(feature_weights={"rule:x": 0.3})
    assert c._weight("base_score") == 1.0
    assert c._weight("rule:x") == 0.3


def test_allowed_features_can_prune_unstable_semantic_branches():
    c = SemanticDecisionTreeCalibrator(
        allowed_feature_names=["base_score"], max_depth=3, min_samples_leaf=1,
    ).fit(
        [[1, 0], [1, 1], [2, 0], [2, 1]], [2, 2, 4, 4],
        feature_names=["base_score", "rubric:flow:q1"],
    )
    assert c.metadata()["tree"]["feature"] == "base_score"
    assert c.metadata()["allowed_feature_names"] == ["base_score"]


def test_one_level_lookahead_learns_a_two_rule_interaction():
    X = []
    y = []
    for _repeat in range(3):
        for a, b in ((0, 0), (0, 1), (1, 0), (1, 1)):
            X.append([2.0, float(a), float(b)])
            y.append(5.0 if a and b else 2.0)
    greedy = SemanticDecisionTreeCalibrator(
        max_depth=2, min_samples_leaf=1, split_lookahead=0,
    ).fit(X, y, feature_names=["base_score", "rubric:a", "rubric:b"])
    assert greedy.metadata()["tree"]["leaf"] is True

    model = SemanticDecisionTreeCalibrator(
        max_depth=2, min_samples_leaf=1, split_lookahead=1,
    ).fit(X, y, feature_names=["base_score", "rubric:a", "rubric:b"])
    tree = model.metadata()["tree"]
    assert tree["leaf"] is False
    assert tree["lookahead_gain"] > 0
    assert set(model.predict(X)) == {2.0, 5.0}


def test_prompt_routed_tree_never_uses_score_controls_as_decisions():
    names = ["base_score", "score_std", "prompt:M3", "prompt:M5", "rubric:M3:q1", "rule:x:M5:q2"]
    X = [
        [1, 0.1, 1, 0, 0, 0], [2, 0.2, 1, 0, 0, 0],
        [4, 0.1, 1, 0, 1, 0], [5, 0.2, 1, 0, 1, 0],
        [1, 0.1, 0, 1, 0, 0], [2, 0.2, 0, 1, 0, 0],
        [4, 0.1, 0, 1, 0, 1], [5, 0.2, 0, 1, 0, 1],
    ]
    y = [1, 2, 5, 5, 1, 2, 5, 5]
    model = PromptRoutedSemanticTreeCalibrator(
        semantic_feature_names=["rubric:M3:q1", "rule:x:M5:q2"],
        prompt_feature_names=["prompt:M3", "prompt:M5"],
        leaf_feature_names=["base_score", "score_std"],
        max_depth=2,
        min_samples_leaf=1,
    ).fit(X, y, feature_names=names)
    meta = model.metadata()
    assert set(meta["semantic_split_features"]) == {"rubric:M3:q1", "rule:x:M5:q2"}
    assert meta["raw_score_split_count"] == 0
    assert meta["semantic_split_count"] == 2
    assert all(
        subtree["feature"] not in {"base_score", "score_std"}
        for subtree in meta["prompt_trees"].values()
    )
