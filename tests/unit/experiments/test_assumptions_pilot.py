"""Check statistical units and label isolation in the retrospective pilot."""
from copy import deepcopy

import pytest

from run.assumptions_pilot import FEATURES, distribution, fit_trees, mode


def toy_data():
    labels = ["no"] * 3 + ["partial"] * 4 + ["yes"] * 3
    cases = [{"target_label": label, "task": f"category-{i // 2}"}
             for i, label in enumerate(labels)]
    names = set().union(*FEATURES.values())
    # Identical measurements with conflicting human labels: no deterministic
    # function of the features can achieve more than the majority frequency.
    rows = [{name: 0.0 for name in names} for _ in range(100)]
    return cases, rows


def test_disagreement_counts_distinct_pairs_and_does_not_resolve_ties():
    d = distribution(["no"] * 6 + ["yes"] * 4)
    assert d["pairwise_disagreement"] == pytest.approx(48 / 90)
    assert not d["stable"]
    assert mode(["no"] * 5 + ["yes"] * 5) == "tie"


def test_exact_feature_collisions_bound_empirical_accuracy(tmp_path):
    cases, rows = toy_data()
    result = fit_trees(cases, rows, tmp_path)
    for schema in FEATURES:
        assert result[schema]["observed_deterministic_mapping_accuracy_ceiling"] == 0.4
        assert len(result[schema]["feature_collisions"]) == 1


def test_held_out_label_cannot_change_its_fold_prediction(tmp_path):
    cases, rows = toy_data()
    original = fit_trees(cases, rows, tmp_path)
    changed_cases = deepcopy(cases)
    changed_cases[0]["target_label"] = "yes"
    changed = fit_trees(changed_cases, rows, tmp_path)
    for schema in FEATURES:
        old_cv = original[schema]["leave_task_out"]
        new_cv = changed[schema]["leave_task_out"]
        assert old_cv["cases"][0]["counts"] == new_cv["cases"][0]["counts"]
        fold = old_cv["folds"][0]
        assert fold["test_case_indices"] == [0]
        assert 0 not in fold["train_case_indices"]
        for category_fold in original[schema]["leave_category_out"]["folds"]:
            assert not set(category_fold["train_case_indices"]) & set(category_fold["test_case_indices"])
