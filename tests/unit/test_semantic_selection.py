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
    assert selected["feature_set"] == "rubric_semantics"
    assert selected["meaningful_decision_tree"] is True
    assert selected["tree_depth"] == 2
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

    guarded, _ = select_semantic_tree_config(
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
        semantic_gain_threshold=10.0,
    )
    # A high materiality threshold now changes the evidence label, not the architecture:
    # score controls remain in leaves and the supported semantic decisions stay visible.
    assert guarded["feature_set"] == "rubric_semantics"
    assert guarded["selection_reason"] == "best_supported_semantic_structure"
    assert guarded["semantic_gain_is_material"] is False


def test_supported_shallow_semantic_rule_remains_a_semantic_decision():
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
    assert selected["feature_set"] == "rubric_semantics"
    assert selected["selection_reason"] == "best_supported_semantic_structure"
    assert selected["semantic_split_count"] == 1
    assert selected["raw_score_split_count"] == 0


def test_prompt_routing_selects_semantic_coverage_without_score_splits():
    items = [f"item-{index}" for index in range(8)]
    observation_ids = []
    observation_item = {}
    humans = {}
    features = {}
    weights = {}
    for index, item in enumerate(items):
        for metric_index, metric in enumerate(("M3", "M5")):
            obs = f"{item}::{metric}"
            decision = float((index + metric_index) % 2)
            observation_ids.append(obs)
            observation_item[obs] = item
            humans[obs] = 2.0 + 2.0 * decision
            features[obs] = [
                3.0, 1.0 if metric == "M3" else 0.0,
                1.0 if metric == "M5" else 0.0,
                decision if metric == "M3" else 0.0,
                decision if metric == "M5" else 0.0,
            ]
            weights[obs] = 0.5
    selected, _ = select_semantic_tree_config(
        observation_ids=observation_ids,
        observation_item=observation_item,
        humans=humans,
        features=features,
        weights=weights,
        feature_names=[
            "base_score", "prompt:M3", "prompt:M5",
            "rubric:M3:q1", "rubric:M5:q2",
        ],
        feature_weights={"rubric:M3:q1": 1.0, "rubric:M5:q2": 1.0},
        training_items=items,
        max_depth=2,
        min_leaf_floor=1,
        prompt_feature_names=["prompt:M3", "prompt:M5"],
        leaf_feature_names=["base_score"],
    )
    assert selected["semantic_prompt_coverage"] == 2
    assert set(selected["semantic_split_features"]) == {"rubric:M3:q1", "rubric:M5:q2"}
    assert selected["raw_score_split_count"] == 0


def test_exploratory_preference_selects_richer_tree_within_tolerance():
    items = [f"item-{index}" for index in range(12)]
    observation_ids = [f"{item}::M3" for item in items]
    observation_item = dict(zip(observation_ids, items))
    features = {}
    humans = {}
    for index, obs in enumerate(observation_ids):
        first = float(index % 2)
        second = float((index // 2) % 2)
        features[obs] = [3.0, 1.0, first, second]
        humans[obs] = 2.0 + first + 0.1 * second
    common = dict(
        observation_ids=observation_ids,
        observation_item=observation_item,
        humans=humans,
        features=features,
        weights={obs: 1.0 for obs in observation_ids},
        feature_names=["base_score", "prompt:M3", "rubric:M3:q1", "rubric:M3:q2"],
        feature_weights={"rubric:M3:q1": 1.0, "rubric:M3:q2": 1.0},
        training_items=items,
        max_depth=2,
        min_leaf_floor=1,
        prompt_feature_names=["prompt:M3"],
        leaf_feature_names=["base_score"],
        semantic_coverage_tolerance=0.2,
    )
    shallow, _ = select_semantic_tree_config(**common)
    deeper, _ = select_semantic_tree_config(
        **common, prefer_deeper_within_tolerance=True,
    )
    assert shallow["semantic_unique_split_count"] == 1
    assert deeper["semantic_unique_split_count"] == 2
    assert deeper["max_depth"] == 2
    assert deeper["prefer_deeper_within_tolerance"] is True
    assert deeper["raw_score_split_count"] == 0
