import pytest

from vejudge.core.calibration import DecisionTreeCalibrator
from vejudge.core.calibration.base import Calibrator


def test_is_a_calibrator_with_fit_predict_metadata():
    c = DecisionTreeCalibrator()
    assert isinstance(c, Calibrator)
    assert c.version == "decision-tree-v2-weighted"


def test_predict_before_fit_raises():
    with pytest.raises(RuntimeError):
        DecisionTreeCalibrator().predict([[2.0, 1.0]])


def test_fit_predict_shape_and_a_learnable_split():
    # A boolean that cleanly separates high- from low-human items: the tree must use it.
    X = [[2.0, 1], [2.0, 1], [2.0, 0], [2.0, 0], [1.0, 1], [1.0, 0]]
    y = [4.0, 4.0, 2.0, 2.0, 4.0, 2.0]
    c = DecisionTreeCalibrator().fit(X, y, feature_names=["base", "b1"])
    preds = c.predict(X)
    assert len(preds) == len(X)
    # b1=1 rows should predict clearly higher than b1=0 rows.
    hi = [p for p, x in zip(preds, X) if x[1] == 1]
    lo = [p for p, x in zip(preds, X) if x[1] == 0]
    assert min(hi) > max(lo)


def test_metadata_exposes_auditable_rule_text_and_respects_depth():
    c = DecisionTreeCalibrator(max_depth=2, min_samples_leaf=2)
    c.fit([[2.0, 1], [2.0, 0], [1.0, 1], [1.0, 0], [2.0, 1], [1.0, 0]],
          [4.0, 2.0, 4.0, 2.0, 4.0, 2.0], feature_names=["base", "b1"])
    meta = c.metadata()
    assert meta["max_depth"] == 2 and meta["min_samples_leaf"] == 2
    assert "b1" in meta["rule_text"]  # feature names surfaced in the rule
    assert len(meta["feature_importances"]) == 2


def test_metadata_exposes_a_structured_tree_for_a_ui_to_draw():
    # The clean b1 split from above → a structured node/edge tree, not just text.
    c = DecisionTreeCalibrator(max_depth=2, min_samples_leaf=2)
    c.fit([[2.0, 1], [2.0, 0], [1.0, 1], [1.0, 0], [2.0, 1], [1.0, 0]],
          [4.0, 2.0, 4.0, 2.0, 4.0, 2.0], feature_names=["base", "b1"])
    tree = c.metadata()["tree"]
    # Root is a split on b1 (the separating feature), with both children present.
    assert tree["leaf"] is False
    assert tree["feature"] == "b1"
    assert tree["threshold"] == 0.5  # boolean split midpoint
    assert tree["samples"] == 6
    # left = condition TRUE (b1 <= 0.5, i.e. b1==0) → the low (2.0) group; right → high (4.0).
    assert tree["left"]["leaf"] is True and tree["left"]["value"] == 2.0
    assert tree["right"]["leaf"] is True and tree["right"]["value"] == 4.0


def test_structured_tree_absent_before_fit():
    assert "tree" not in DecisionTreeCalibrator().metadata()
