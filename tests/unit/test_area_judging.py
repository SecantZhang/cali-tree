from vejudge.core.area.aggregate import aggregate_area_results
from vejudge.core.area.selection import select_units
from vejudge.core.calibration.unit_affine import (
    calibrate_area_result_units,
    fit_unit_calibrators,
)


def _unit(index, score=4, severity="none", unit_type="edit_boundary"):
    return {
        "item_id": "item",
        "unit_id": f"u{index}",
        "unit_type": unit_type,
        "start_seconds": float(index),
        "end_seconds": float(index + 1),
        "duration_seconds": 1.0,
        "confidence": 1.0,
        "applicable_rubrics": ["transition_smoothness"],
        "measurements": {"flicker_score": float(index)},
        "score": float(score),
        "severity": severity,
        "valid": True,
        "parsed": {"score_1_to_5": float(score)},
    }


def test_selection_is_deterministic_capped_and_reports_omissions():
    units = [_unit(index) for index in range(10)]
    first, report = select_units(
        units, rubric_id="transition_smoothness",
        unit_types=["edit_boundary"], caps={"edit_boundary": 4},
    )
    second, _ = select_units(
        units, rubric_id="transition_smoothness",
        unit_types=["edit_boundary"], caps={"edit_boundary": 4},
    )
    assert [unit["unit_id"] for unit in first] == [unit["unit_id"] for unit in second]
    assert report["selected"] == 4
    assert report["total"] == 10
    assert len(report["omitted_unit_ids"]) == 6
    assert "u9" in {unit["unit_id"] for unit in first}


def test_aggregation_applies_critical_cap_and_preserves_eval_alignment():
    bundle = {
        "item": {
            "rubric_id": "transition_smoothness",
            "evidence_hash": "e",
            "selection": {"selected": 2, "total": 2, "coverage": 1.0},
            "units": [_unit(0, score=5), _unit(1, score=1, severity="critical")],
        }
    }
    judges, features = aggregate_area_results([bundle])
    summary = features["item"]["rubric_summaries"]["transition_smoothness"]
    assert summary["weighted_mean_before_cap"] == 3.0
    assert summary["score_1_to_5"] == 2.0
    assert judges["item"]["area::story_flow_visuals"]["align"]["dimension"] == "story_flow_visuals"


def test_unit_calibrator_identity_then_activates_for_supported_rubric():
    result = {
        f"item{i}": {
            "rubric_id": "transition_smoothness",
            "units": [{**_unit(i), "item_id": f"item{i}", "score": float(1 + i % 4)}],
        }
        for i in range(5)
    }
    labels = [
        {
            "item_id": f"item{i}", "unit_id": f"u{i}",
            "rubric_id": "transition_smoothness", "rating": float(2 + i % 3),
        }
        for i in range(5)
    ]
    models = fit_unit_calibrators([result], labels)
    assert models["transition_smoothness"]["active"] is True
    calibrated = calibrate_area_result_units([result], models)
    assert "raw_score" in calibrated[0]["item0"]["units"][0]
