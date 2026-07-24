from vejudge.interface.node_calibration import edit_aware_calibration_node
from vejudge.interface.node_calibration.edit_aware_calibration_node import (
    EditAwareCalibrationNodeExecutor,
)


def _fixture(n=10):
    samples = {}
    judges = {}
    labels = {}
    features = {}
    for index in range(n):
        item = f"item-{index}"
        score = float(1 + index % 5)
        samples[item] = {"item_id": item, "use_case": "a" if index % 2 else "b"}
        judges[item] = {
            "area::story_flow_visuals": {
                "parsed": {"score_1_to_5": score},
                "align": {
                    "dimension": "story_flow_visuals",
                    "score_path": "score_1_to_5",
                },
            }
        }
        labels[item] = {
            "scores": {"story_flow_visuals": min(5.0, score + 0.5)},
            "raw_scores": {"story_flow_visuals": [score, min(5.0, score + 1)]},
        }
        features[item] = {
            "features": {
                "area:transition_smoothness:p20": score - 0.25,
                "area:transition_smoothness:variance": index / 10,
            }
        }
    return samples, judges, labels, features


def test_edit_aware_calibration_emits_heldout_predictions_registry_and_queue(
    tmp_path, make_ctx, monkeypatch,
):
    monkeypatch.setattr(edit_aware_calibration_node.config, "EVIDENCE_ROOT", tmp_path)
    samples, judges, labels, features = _fixture()
    result = EditAwareCalibrationNodeExecutor().run(make_ctx(
        inputs={
            "samples": samples,
            "judge_result": [judges],
            "labels": labels,
            "decomposition_features": features,
            "unit_labels": [],
        },
        params={"validation_fraction": 0.2, "split_seed": 7, "bootstrap_repeats": 20},
        dry_run=False,
    ))
    assert result.status == "done"
    assert len(result.outputs["judge_result"]) == 2
    report = result.outputs["judge_rule"]
    assert report["models"]["story_flow_visuals"]["validation_ids"]
    assert report["registry_version"].startswith("edit-cal-")
    assert result.outputs["active_labeling_report"]["items"][0]["priority"] >= 0


def test_edit_aware_calibration_dry_run_does_not_fit_or_publish(tmp_path, make_ctx, monkeypatch):
    monkeypatch.setattr(edit_aware_calibration_node.config, "EVIDENCE_ROOT", tmp_path)
    samples, judges, labels, features = _fixture()
    result = EditAwareCalibrationNodeExecutor().run(make_ctx(
        inputs={
            "samples": samples, "judge_result": judges, "labels": labels,
            "decomposition_features": features,
        },
        dry_run=True,
    ))
    assert result.meta["dry_run"] is True
    assert not (tmp_path / "calibration_registry").exists()
