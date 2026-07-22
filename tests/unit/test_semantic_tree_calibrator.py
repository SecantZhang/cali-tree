import pytest

from vejudge.core.calibration import SemanticDecisionTreeCalibrator
from vejudge.core.calibration.base import Calibrator


def test_is_a_calibrator():
    c = SemanticDecisionTreeCalibrator()
    assert isinstance(c, Calibrator)
    assert c.version == "semantic-tree-v3-graded-mae"


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
