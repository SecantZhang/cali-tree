"""fit_and_evaluate comparator coverage and the semantic-calibrator extension hook."""

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


def test_default_reports_score_only_and_rule_comparators():
    rep = _report()
    expected = {"base", "bias", "score_linear", "linear", "tree"}
    assert set(rep["insample_mae"]) == expected
    assert set(rep["loo_mae"]) == expected


def test_extra_calibrator_adds_a_named_column_in_and_out_of_sample():
    rep = _report({"semantic": lambda: SemanticDecisionTreeCalibrator(
        feature_weights={"rule:audio_neglect": 0.9})})
    assert "semantic" in rep["insample_mae"] and "semantic" in rep["loo_mae"]
    # The rule cleanly separates y, so the semantic tree nails it here.
    assert rep["loo_mae"]["semantic"] == 0.0


def test_joint_evaluation_adds_prompt_specific_control_models():
    strata = {item: "M3" if index < 3 else "M5" for index, item in enumerate(_IDS)}
    names = ["base_score", "score_std", "prompt:M3", "prompt:M5", "rule:x"]
    features = {
        item: [2.0, 0.0, 1.0 if strata[item] == "M3" else 0.0,
               1.0 if strata[item] == "M5" else 0.0, _FEATS[item][1]]
        for item in _IDS
    }
    report = fit_and_evaluate(
        item_ids=_IDS, bases=_BASES, humans=_HUMANS, feats_full=features,
        feature_names=names, strata=strata,
        reference_feature_names=names[:4],
    )
    assert "prompt_bias" in report["loo_mae"]
    assert "prompt_linear" in report["loo_mae"]
