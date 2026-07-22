import pytest

from vejudge.core.calibration.debate.eval.joint_features import (
    build_joint_feature_rows,
    build_joint_observations,
    group_calibration_variants,
)


def _result(item, metric, score, temperature):
    return {
        "item_id": item,
        "metric_id": metric,
        "original_score": score,
        "transcript": {"turns": []},
        "judge_provenance": {"temperature": temperature},
    }


def test_temperature_variants_become_distribution_not_extra_observations():
    grouped = group_calibration_variants([
        {"video-a": _result("video-a", "M5", 2, 0.0)},
        {"video-a": _result("video-a", "M5", 4, 0.8)},
    ])
    task = grouped["video-a::metric::M5"]
    assert task["base"] == 3
    assert task["score_std"] == 1
    assert task["score_range"] == 2
    assert task["variant_count"] == 2
    assert task["temperatures"] == [0.0, 0.8]


def test_prompt_features_and_weights_keep_each_video_at_total_one():
    tasks = group_calibration_variants([
        {
            "video-a": _result("video-a", "M3", 2, 0.0),
            "video-b": _result("video-b", "M3", 4, 0.0),
        },
        {"video-a": _result("video-a", "M5", 3, 0.0)},
    ])
    tasks["video-a::metric::M3"]["humans"] = [1, 3]
    tasks["video-a::metric::M5"]["humans"] = [2]
    tasks["video-b::metric::M3"]["humans"] = [4, 5, 5]
    base_names, rows = build_joint_feature_rows(
        tasks, {key: [0.5] for key in tasks}, ["M3", "M5"],
    )
    assert base_names == ["base_score", "score_std", "score_range", "prompt:M3", "prompt:M5"]
    assert rows["video-a::metric::M3"][3:5] == [1.0, 0.0]
    assert rows["video-a::metric::M5"][3:5] == [0.0, 1.0]

    obs, groups, obs_tasks, _bases, _humans, _features, weights = build_joint_observations(
        tasks, rows,
    )
    assert len(obs) == 6
    assert sum(weight for oid, weight in weights.items() if groups[oid] == "video-a") == pytest.approx(1)
    assert sum(weight for oid, weight in weights.items() if groups[oid] == "video-b") == pytest.approx(1)
    assert {obs_tasks[oid] for oid in obs if groups[oid] == "video-a"} == {
        "video-a::metric::M3", "video-a::metric::M5",
    }
