"""Training-only grouped selection for semantic-first model trees."""

from __future__ import annotations

from statistics import mean
from typing import Any, Optional

from ...semantic_tree import (
    PromptRoutedSemanticTreeCalibrator,
    SemanticDecisionTreeCalibrator,
)


def _tree_shape(tree: Optional[dict[str, Any]]) -> tuple[int, list[str]]:
    if not tree or tree.get("leaf"):
        return 0, []
    left_depth, left_features = _tree_shape(tree.get("left"))
    right_depth, right_features = _tree_shape(tree.get("right"))
    return (
        1 + max(left_depth, right_depth),
        [str(tree.get("feature")), *left_features, *right_features],
    )


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
    prompt_feature_names: Optional[list[str]] = None,
    leaf_feature_names: Optional[list[str]] = None,
    semantic_coverage_tolerance: float = 0.01,
    prefer_deeper_within_tolerance: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Select semantic capacity with item-grouped LOO inside training only.

    Unlike the legacy selector, raw-score and prompt-control fields cannot compete for a
    learned branch. Prompt indicators form a fixed context router; the fitted decisions
    below it are ontology-backed rubric/debate questions. Score controls are restricted to
    regularized leaf models. The best supported semantic structure is retained even when
    its CV gain is small or negative, while that trade-off is reported honestly.
    """
    train_set = set(training_items)
    train_obs = [obs for obs in observation_ids if observation_item[obs] in train_set]
    prompts = list(prompt_feature_names or [])
    leaf_features = list(leaf_feature_names or [])
    rubric_features = [name for name in feature_names if name.startswith("rubric:")]
    debate_features = [name for name in feature_names if name.startswith("rule:")]
    feature_sets = {
        "rubric_semantics": rubric_features,
        "debate_semantics": debate_features,
        "all_semantics": [*rubric_features, *debate_features],
    }
    feature_sets = {name: values for name, values in feature_sets.items() if values}
    max_leaf = max(min_leaf_floor, min(5, max(1, len(training_items) // 4)))
    configs = [
        {
            "feature_set": feature_set,
            "semantic_feature_names": allowed,
            "max_depth": depth,
            "min_samples_leaf": leaf,
        }
        for feature_set, allowed in feature_sets.items()
        for depth in range(1, max(1, max_depth) + 1)
        for leaf in range(max(1, min_leaf_floor), max_leaf + 1)
    ]

    def factory(config: dict[str, Any], *, semantic: bool = True):
        allowed = config["semantic_feature_names"] if semantic else []
        if prompts:
            return PromptRoutedSemanticTreeCalibrator(
                feature_weights=feature_weights,
                semantic_feature_names=allowed,
                prompt_feature_names=prompts,
                leaf_feature_names=leaf_features,
                max_depth=config["max_depth"] if semantic else 0,
                min_samples_leaf=config["min_samples_leaf"],
            )
        return SemanticDecisionTreeCalibrator(
            feature_weights=feature_weights,
            allowed_feature_names=allowed,
            leaf_feature_names=leaf_features,
            max_depth=config["max_depth"] if semantic else 0,
            min_samples_leaf=config["min_samples_leaf"],
        )

    def grouped_loo(config: dict[str, Any], *, semantic: bool = True) -> Optional[float]:
        held_errors: list[float] = []
        for held_item in training_items:
            fit_ids = [obs for obs in train_obs if observation_item[obs] != held_item]
            query_ids = [obs for obs in train_obs if observation_item[obs] == held_item]
            if not fit_ids or not query_ids:
                continue
            model = factory(config, semantic=semantic).fit(
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
        return mean(held_errors) if held_errors else None

    scores: list[dict[str, Any]] = []
    for config in configs:
        loo_mae = grouped_loo(config)
        full_model = factory(config).fit(
            [features[obs] for obs in train_obs],
            [humans[obs] for obs in train_obs],
            feature_names=feature_names,
            sample_weight=[weights[obs] for obs in train_obs],
        )
        metadata = full_model.metadata()
        tree_depth, split_features = _tree_shape(metadata.get("tree"))
        semantic_splits = metadata.get("semantic_split_features") or [
            name for name in split_features if name.startswith(("rubric:", "rule:"))
        ]
        scores.append({
            **config,
            "grouped_loo_mae": loo_mae,
            "tree_depth": tree_depth,
            "split_features": split_features,
            "semantic_split_features": semantic_splits,
            "semantic_split_count": len(semantic_splits),
            "semantic_unique_split_count": len(set(semantic_splits)),
            "semantic_prompt_coverage": len({
                prompt.split(":", 1)[1]
                for prompt in prompts
                if any(f":{prompt.split(':', 1)[1]}:" in name for name in semantic_splits)
            }),
            "raw_score_split_count": sum(
                name in {"base_score", "score_std", "score_range"}
                for name in split_features
            ),
            "meaningful_decision_tree": bool(semantic_splits),
        })

    eligible = [
        entry for entry in scores
        if entry["grouped_loo_mae"] is not None and entry["meaningful_decision_tree"]
    ]
    if not configs:
        return {
            "feature_set": "no_semantic_features",
            "semantic_feature_names": [],
            "allowed_feature_names": [],
            "max_depth": 0,
            "min_samples_leaf": max(1, min_leaf_floor),
            "selection_reason": "no_semantic_features",
            "meaningful_decision_tree": False,
            "semantic_split_features": [],
            "semantic_split_count": 0,
            "raw_score_split_count": 0,
        }, scores

    baseline_config = configs[0]
    controls_loo = grouped_loo(baseline_config, semantic=False)
    if not eligible:
        selected = min(
            (entry for entry in scores if entry["grouped_loo_mae"] is not None),
            key=lambda entry: (entry["grouped_loo_mae"], entry["max_depth"]),
            default=scores[0],
        )
        reason = "no_supported_semantic_split"
    else:
        feature_set_order = {
            "rubric_semantics": 0, "debate_semantics": 1, "all_semantics": 2,
        }
        best_error = min(entry["grouped_loo_mae"] for entry in eligible)
        competitive = [
            entry for entry in eligible
            if entry["grouped_loo_mae"] <= best_error + semantic_coverage_tolerance
        ]
        if prefer_deeper_within_tolerance:
            selected = min(
                competitive,
                key=lambda entry: (
                    -entry["semantic_prompt_coverage"],
                    -entry["semantic_unique_split_count"],
                    -entry["semantic_split_count"],
                    entry["grouped_loo_mae"],
                    feature_set_order[entry["feature_set"]],
                ),
            )
        else:
            selected = min(
                competitive,
                key=lambda entry: (
                    -entry["semantic_prompt_coverage"],
                    entry["max_depth"],
                    -entry["min_samples_leaf"],
                    feature_set_order[entry["feature_set"]],
                    entry["grouped_loo_mae"],
                ),
            )
        reason = (
            "deeper_semantics_within_cv_tolerance"
            if prefer_deeper_within_tolerance else
            "semantic_coverage_within_cv_tolerance"
            if selected["grouped_loo_mae"] > best_error
            else "best_supported_semantic_structure"
        )
    semantic_gain = (
        controls_loo - selected["grouped_loo_mae"]
        if controls_loo is not None and selected["grouped_loo_mae"] is not None else None
    )
    return {
        "feature_set": selected["feature_set"],
        "semantic_feature_names": selected["semantic_feature_names"],
        # Compatibility for stored reports and older UI code.
        "allowed_feature_names": selected["semantic_feature_names"],
        "leaf_feature_names": leaf_features,
        "prompt_feature_names": prompts,
        "max_depth": selected["max_depth"],
        "min_samples_leaf": selected["min_samples_leaf"],
        "selection_reason": reason,
        "semantic_gain_threshold": semantic_gain_threshold,
        "best_semantic_gain_over_base": semantic_gain,
        "reference_feature_set": "score_controls_in_leaves_only",
        "tree_depth": selected["tree_depth"],
        "semantic_or_prompt_splits": selected["semantic_split_features"],
        "semantic_split_features": selected["semantic_split_features"],
        "semantic_split_count": selected["semantic_split_count"],
        "semantic_unique_split_count": selected["semantic_unique_split_count"],
        "semantic_prompt_coverage": selected["semantic_prompt_coverage"],
        "raw_score_split_count": selected["raw_score_split_count"],
        "meaningful_decision_tree": selected["meaningful_decision_tree"],
        "controls_only_grouped_loo_mae": controls_loo,
        "semantic_coverage_tolerance": semantic_coverage_tolerance,
        "prefer_deeper_within_tolerance": prefer_deeper_within_tolerance,
        "selected_cv_penalty_for_coverage": (
            selected["grouped_loo_mae"]
            - min(entry["grouped_loo_mae"] for entry in eligible)
            if eligible else None
        ),
        "semantic_gain_is_material": (
            semantic_gain is not None and semantic_gain >= semantic_gain_threshold
        ),
    }, scores
