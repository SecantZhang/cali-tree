"""Training-only grouped model selection for the semantic decision tree."""

from __future__ import annotations

from statistics import mean
from typing import Any, Optional

from ...semantic_tree import SemanticDecisionTreeCalibrator


def _tree_shape(tree: Optional[dict[str, Any]]) -> tuple[int, list[str]]:
    if not tree or tree.get("leaf"):
        return 0, []
    left_depth, left_features = _tree_shape(tree.get("left"))
    right_depth, right_features = _tree_shape(tree.get("right"))
    return 1 + max(left_depth, right_depth), [str(tree.get("feature")), *left_features, *right_features]


def select_semantic_tree_config(
    *,
    observation_ids: list[str],
    observation_item: dict[str, str],
    humans: dict[str, float],
    features: dict[str, list[float]],
    weights: dict[str, float],
    feature_names: list[str],
    feature_weights: dict[str, float],
    training_items: list[str],
    max_depth: int,
    min_leaf_floor: int = 2,
    semantic_gain_threshold: float = 0.01,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Select depth/leaf mass by grouped LOO entirely inside the training partition.

    Raw-rating rows from the held video always move together. Ties prefer fewer nodes via
    shallower depth and larger leaves, preventing capacity from increasing without evidence.
    """
    train_set = set(training_items)
    train_obs = [obs for obs in observation_ids if observation_item[obs] in train_set]
    max_leaf = max(min_leaf_floor, min(5, max(2, len(training_items) // 4)))
    score_features = [
        name for name in feature_names
        if name == "base_score" or name in {"score_std", "score_range"}
    ]
    prompt_features = [name for name in feature_names if name.startswith("prompt:")]
    feature_sets = {
        "base_only": [name for name in feature_names if name == "base_score"],
        "score_distribution": score_features,
        "prompt_score": [*score_features, *prompt_features],
        "rubric": [
            name for name in feature_names
            if name in score_features or name in prompt_features or name.startswith("rubric:")
        ],
        "debate": [
            name for name in feature_names
            if name in score_features or name in prompt_features or name.startswith("rule:")
        ],
        "all": list(feature_names),
    }
    configs = [
        {
            "feature_set": feature_set,
            "allowed_feature_names": allowed,
            "max_depth": depth,
            "min_samples_leaf": leaf,
        }
        for feature_set, allowed in feature_sets.items()
        for depth in range(1, max(1, max_depth) + 1)
        for leaf in range(max(1, min_leaf_floor), max_leaf + 1)
    ]
    scores: list[dict[str, Any]] = []
    for config in configs:
        held_errors: list[float] = []
        for held_item in training_items:
            fit_ids = [obs for obs in train_obs if observation_item[obs] != held_item]
            query_ids = [obs for obs in train_obs if observation_item[obs] == held_item]
            if not fit_ids or not query_ids:
                continue
            model = SemanticDecisionTreeCalibrator(
                feature_weights=feature_weights,
                allowed_feature_names=config["allowed_feature_names"],
                max_depth=config["max_depth"],
                min_samples_leaf=config["min_samples_leaf"],
            ).fit(
                [features[obs] for obs in fit_ids],
                [humans[obs] for obs in fit_ids],
                feature_names=feature_names,
                sample_weight=[weights[obs] for obs in fit_ids],
            )
            predictions = model.predict([features[obs] for obs in query_ids])
            total_weight = sum(weights[obs] for obs in query_ids)
            held_errors.append(
                sum(
                    weights[obs] * abs(prediction - humans[obs])
                    for obs, prediction in zip(query_ids, predictions)
                ) / total_weight
            )
        full_model = SemanticDecisionTreeCalibrator(
            feature_weights=feature_weights,
            allowed_feature_names=config["allowed_feature_names"],
            max_depth=config["max_depth"],
            min_samples_leaf=config["min_samples_leaf"],
        ).fit(
            [features[obs] for obs in train_obs],
            [humans[obs] for obs in train_obs],
            feature_names=feature_names,
            sample_weight=[weights[obs] for obs in train_obs],
        )
        tree_depth, split_features = _tree_shape(full_model.metadata().get("tree"))
        decision_splits = [
            name for name in split_features
            if name.startswith(("prompt:", "rubric:", "rule:"))
        ]
        scores.append({
            "feature_set": config["feature_set"],
            "allowed_feature_names": config["allowed_feature_names"],
            "max_depth": config["max_depth"],
            "min_samples_leaf": config["min_samples_leaf"],
            "grouped_loo_mae": mean(held_errors) if held_errors else None,
            "tree_depth": tree_depth,
            "split_features": split_features,
            "semantic_or_prompt_splits": decision_splits,
            "meaningful_decision_tree": tree_depth >= 2 and bool(decision_splits),
        })

    eligible = [entry for entry in scores if entry["grouped_loo_mae"] is not None]
    if not eligible:
        return {
            "feature_set": "base_only",
            "allowed_feature_names": ["base_score"],
            "max_depth": 1,
            "min_samples_leaf": max(1, min_leaf_floor),
        }, scores
    feature_set_order = {
        "base_only": 0, "score_distribution": 1, "prompt_score": 2,
        "rubric": 3, "debate": 4, "all": 5,
    }
    reference = min(
        (entry for entry in eligible if entry["feature_set"] in {
            "base_only", "score_distribution", "prompt_score",
        }),
        key=lambda entry: (
            entry["grouped_loo_mae"],
            feature_set_order[entry["feature_set"]],
            entry["max_depth"],
            -entry["min_samples_leaf"],
        ),
    )
    semantic_candidates = [
        entry for entry in eligible
        if entry["feature_set"] in {"rubric", "debate", "all"}
        and entry["meaningful_decision_tree"]
    ]
    best_semantic = min(
        semantic_candidates,
        key=lambda entry: (
            entry["grouped_loo_mae"], feature_set_order[entry["feature_set"]],
            entry["max_depth"],
            -entry["min_samples_leaf"],
        ),
        default=None,
    )
    # Do not spend semantic capacity for a negligible training-CV fluctuation. This guard
    # is determined entirely inside the training partition and prevents a larger bank from
    # winning by a few thousandths merely because more split candidates were available.
    selected = reference
    selection_reason = "best_nonsemantic_reference"
    semantic_gain = None
    if best_semantic is not None:
        semantic_gain = reference["grouped_loo_mae"] - best_semantic["grouped_loo_mae"]
        if semantic_gain >= semantic_gain_threshold:
            selected = best_semantic
            selection_reason = "meaningful_semantic_gain"
        else:
            selection_reason = "semantic_gain_below_threshold"
    else:
        selection_reason = "no_supported_deep_semantic_tree"
    return {
        "feature_set": selected["feature_set"],
        "allowed_feature_names": selected["allowed_feature_names"],
        "max_depth": selected["max_depth"],
        "min_samples_leaf": selected["min_samples_leaf"],
        "selection_reason": selection_reason,
        "semantic_gain_threshold": semantic_gain_threshold,
        "best_semantic_gain_over_base": semantic_gain,
        "reference_feature_set": reference["feature_set"],
        "tree_depth": selected["tree_depth"],
        "semantic_or_prompt_splits": selected["semantic_or_prompt_splits"],
        "meaningful_decision_tree": selected["meaningful_decision_tree"],
    }, scores
