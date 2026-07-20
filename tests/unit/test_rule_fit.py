"""fit_and_evaluate: the four-comparator default, and the extra_calibrators hook the
Semantic Tree node uses to report a fifth `semantic` column on the same features."""

from vejudge.core.calibration import SemanticDecisionTreeCalibrator
from vejudge.core.calibration.debate.eval.rule_fit import fit_and_evaluate

_IDS = [f"i{k}" for k in range(6)]
_BASES = {i: 2.0 for i in _IDS}
_HUMANS = dict(zip(_IDS, [4.0, 4.0, 2.0, 2.0, 4.0, 2.0]))
_FEATS = {_IDS[k]: v for k, v in enumerate([[2, 1], [2, 1], [2, 0], [2, 0], [2, 1], [2, 0]])}
_NAMES = ["base_score", "rule:audio_neglect"]


def _report(extra=None):
    return fit_and_evaluate(
        item_ids=_IDS, bases=_BASES, humans=_HUMANS, feats_full=_FEATS,
        feature_names=_NAMES, extra_calibrators=extra,
    )


def test_default_reports_the_four_comparators():
    rep = _report()
    assert set(rep["insample_mae"]) == {"base", "bias", "linear", "tree"}
    assert set(rep["loo_mae"]) == {"base", "bias", "linear", "tree"}


def test_extra_calibrator_adds_a_named_column_in_and_out_of_sample():
    rep = _report({"semantic": lambda: SemanticDecisionTreeCalibrator(
        feature_weights={"rule:audio_neglect": 0.9})})
    assert "semantic" in rep["insample_mae"] and "semantic" in rep["loo_mae"]
    # The rule cleanly separates y, so the semantic tree nails it here.
    assert rep["loo_mae"]["semantic"] == 0.0
