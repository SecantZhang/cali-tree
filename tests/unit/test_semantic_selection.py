from vejudge.core.calibration.debate.eval.semantic_selection import (
    select_semantic_tree_config,
)


def test_selection_is_grouped_and_never_reads_validation_rows():
    items = [f"train-{index}" for index in range(8)]
    observation_ids = [f"{item}::human::0" for item in items] + ["held::human::0"]
    observation_item = {
        obs: ("held" if obs.startswith("held") else obs.split("::", 1)[0])
        for obs in observation_ids
    }
    # Two semantic decisions are needed to isolate the high target quadrant. The held
    # target is deliberately extreme; changing it must not affect training-only selection.
    features = {}
    humans = {}
    for index, obs in enumerate(observation_ids[:-1]):
        a, b = index % 2, (index // 2) % 2
        features[obs] = [2.0, float(a), float(b)]
        humans[obs] = 5.0 if a and b else 2.0
    features["held::human::0"] = [2.0, 1.0, 1.0]
    humans["held::human::0"] = 1000.0
    weights = {obs: 1.0 for obs in observation_ids}

    selected, scores = select_semantic_tree_config(
        observation_ids=observation_ids,
        observation_item=observation_item,
        humans=humans,
        features=features,
        weights=weights,
        feature_names=["base_score", "rubric:a:q1", "rubric:b:q2"],
        feature_weights={"rubric:a:q1": 1.0, "rubric:b:q2": 1.0},
        training_items=items,
        max_depth=3,
        min_leaf_floor=1,
    )
    assert selected["feature_set"] in {"base_only", "rubric", "all"}
    assert scores

    humans["held::human::0"] = -1000.0
    selected_again, scores_again = select_semantic_tree_config(
        observation_ids=observation_ids,
        observation_item=observation_item,
        humans=humans,
        features=features,
        weights=weights,
        feature_names=["base_score", "rubric:a:q1", "rubric:b:q2"],
        feature_weights={"rubric:a:q1": 1.0, "rubric:b:q2": 1.0},
        training_items=items,
        max_depth=3,
        min_leaf_floor=1,
    )
    assert selected_again == selected
    assert scores_again == scores


def test_negligible_semantic_cv_gain_falls_back_to_base_only():
    items = [f"item-{index}" for index in range(6)]
    observation_ids = [f"{item}::human::0" for item in items]
    observation_item = dict(zip(observation_ids, items))
    humans = {obs: 2.0 + (index % 2) for index, obs in enumerate(observation_ids)}
    features = {
        obs: [2.0, float(index % 2)]
        for index, obs in enumerate(observation_ids)
    }
    selected, _ = select_semantic_tree_config(
        observation_ids=observation_ids,
        observation_item=observation_item,
        humans=humans,
        features=features,
        weights={obs: 1.0 for obs in observation_ids},
        feature_names=["base_score", "rubric:a:q1"],
        feature_weights={"rubric:a:q1": 1.0},
        training_items=items,
        max_depth=2,
        min_leaf_floor=1,
        semantic_gain_threshold=10.0,
    )
    assert selected["feature_set"] == "base_only"
    assert selected["selection_reason"] == "semantic_gain_below_threshold"
