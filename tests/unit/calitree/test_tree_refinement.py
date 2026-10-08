"""Independent support, guarded corrections, real-valued features and selection."""
from copy import deepcopy
import json

import pytest

from critical.core.optimization.tree.regularized import (
    RegularizedSemanticTree, encode_fractions, fraction_feature_names,
)
from critical.core.optimization.tree.semantic import SharedDecisionTree, encode_conditions, feature_names
from run.calitree_shared_tree import file_hash
from run.calitree_tree_refinement import run_refinement
from tests.unit.calitree.test_shared_decision_tree import frozen_source


def features(states):
    conditions = [{"id": str(i), "requirement": "Change the requested object."} for i in range(len(states))]
    return encode_fractions(conditions, dict(zip((c["id"] for c in conditions), states)))


def case(identifier, states, label, *, repeats=5, group=None):
    return [{"case_id": identifier, "group": group or identifier, "target": label,
             "features": features(states)} for _ in range(repeats)]


def test_fractions_separate_severity_and_ignore_whole_set_duplication():
    a = features(["complete", "complete", "absent"])
    b = features(["complete", "absent", "absent"])
    assert a[:len(feature_names())] == b[:len(feature_names())]
    assert a != b
    assert a == features(["complete", "complete", "absent"] * 2)
    names = fraction_feature_names()
    assert a[names.index("preservation:not_applicable")] == 1
    assert a[names.index("preservation:complete_fraction")] == 0


def test_balanced_leaf_loss_recognizes_minority_without_inflating_support():
    rows = sum((case(f"no-{i}", ["absent"], "no") for i in range(20)), [])
    rows += sum((case(f"mixed-{i}", ["complete"], "no") for i in range(5)), [])
    rows += case("yes-a", ["complete"], "yes") + case("yes-b", ["complete"], "yes")
    rows += sum((case(f"partial-{i}", ["partial"], "partial") for i in range(3)), [])
    old_rows = [{**r, "features": r["features"][:len(feature_names())]} for r in rows]
    original = SharedDecisionTree(feature_names()).fit(old_rows)
    balanced = RegularizedSemanticTree(fraction_feature_names()).fit(rows)
    assert original.predict(features(["complete"])[:len(feature_names())]) == "no"
    decision = balanced.decision(features(["complete"]))
    assert decision["label"] == "yes"
    assert decision["case_support"] == 7
    assert decision["class_distribution"]["yes"] == pytest.approx(2 / 7)


def test_repeats_cannot_create_guarded_correction_evidence():
    rows = case("only-positive", ["partial"], "yes", repeats=200)
    guarded = RegularizedSemanticTree(fraction_feature_names(), guarded=True).fit(rows)
    assert guarded.predict(features(["partial"])) == "partial"
    assert guarded.tree["action"] == "fixed"
    assert guarded.tree["correction_group_support"]["yes"] == 1


def test_correction_requires_two_independent_source_groups():
    independent = case("a", ["absent"], "partial") + case("b", ["absent"], "partial")
    model = RegularizedSemanticTree(fraction_feature_names(), guarded=True).fit(independent)
    assert model.predict(features(["absent"])) == "partial"
    shared = [{**r, "group": "shared-task"} for r in independent]
    model.fit(shared)
    assert model.predict(features(["absent"])) == "no"


def test_balancing_does_not_allow_a_single_source_group_split():
    rows = case("a", ["absent"], "no", repeats=100)
    rows += case("b", ["complete"], "yes", repeats=100)
    model = RegularizedSemanticTree(fraction_feature_names(), min_cases_leaf=2).fit(rows)
    assert model.tree["leaf"]
    rows += case("c", ["absent"], "no", repeats=1) + case("d", ["complete"], "yes", repeats=1)
    model.fit(rows)
    assert not model.tree["leaf"]
    assert model.tree["left"]["case_mass"] == pytest.approx(2)
    assert model.tree["right"]["case_mass"] == pytest.approx(2)
    for r in rows:
        if r["target"] == "yes":
            r["group"] = "one-positive-source"
    model.fit(rows)
    assert model.tree["leaf"]


def test_fraction_threshold_roundtrip_and_rejected_unsupported_correction():
    rows = case("a", ["complete", "absent", "absent"], "no")
    rows += case("b", ["complete", "absent", "absent"], "no")
    rows += case("c", ["complete", "complete", "absent"], "partial")
    rows += case("d", ["complete", "complete", "absent"], "partial")
    model = RegularizedSemanticTree(fraction_feature_names(), guarded=True).fit(rows)
    assert not model.tree["leaf"]
    assert model.tree["feature"].endswith("_fraction")
    restored = RegularizedSemanticTree.from_dict(json.loads(json.dumps(model.to_dict())))
    assert [restored.predict(r["features"]) for r in rows] == [r["target"] for r in rows]
    assert "case_id" not in str(restored.to_dict())
    malformed = deepcopy(model.to_dict())
    malformed["tree"]["right"]["correction_group_support"]["partial"] = 1
    with pytest.raises(ValueError, match="Unsupported correction"):
        RegularizedSemanticTree.from_dict(malformed)


def test_unknown_not_applicable_and_invalid_features_stay_distinct():
    model = RegularizedSemanticTree(fraction_feature_names(), guarded=True).fit(case("a", ["complete"], "yes"))
    with pytest.raises(ValueError, match="unresolved"):
        model.predict(features(["unknown"]))
    bad = features(["complete"])
    bad[0] = .5
    with pytest.raises(ValueError, match="binary"):
        model.predict(bad)
    bad = features(["complete"])
    bad[-1] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        model.predict(bad)
    inconsistent = case("a", ["complete"], "yes", repeats=2)
    inconsistent[1]["group"] = "changed"
    with pytest.raises(ValueError, match="inconsistent source groups"):
        model.fit(inconsistent)


def test_refinement_selection_ignores_reused_evaluation_labels(frozen_source, tmp_path):
    first = run_refinement(frozen_source, tmp_path / "first")
    manifest_path = frozen_source / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    frozen = frozen_source.parent / "old/frozen_plans.json"
    cases = json.loads(frozen.read_text())
    for identifier in cases:
        if identifier.startswith("N"):
            cases[identifier]["human_label"] = "no"
            manifest["rows"][identifier]["human_label"] = "no"
    frozen.write_text(json.dumps(cases))
    manifest["source_files"][str(frozen)] = file_hash(frozen)
    manifest_path.write_text(json.dumps(manifest))
    second = run_refinement(frozen_source, tmp_path / "second")
    assert first["selected_on_training"] == second["selected_on_training"]
    assert first["selection"] == second["selection"]
    for name in first["models"]:
        assert first["models"][name]["program"] == second["models"][name]["program"]
    assert first["primary"]["fixed_reducer"] != second["primary"]["fixed_reducer"]
    assert first["primary"]["guarded_fractions"]["draw_coverage"] == .9
    assert first["evaluation_outcomes"] == {"unknown": 1, "incomplete": 1, "known": 18}
