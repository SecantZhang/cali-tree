"""Semantic feature, repeat isolation, support, and portable execution contracts."""
from copy import deepcopy
import json

import pytest

from critical.core.optimization.tree.semantic import (
    SharedDecisionTree, case_weights, condition_role, encode_conditions,
    feature_names, fixed_prediction,
)
from run.calitree_shared_tree import (
    bootstrap_delta, collisions, digest, file_hash, grouped_folds,
    load_observations, metrics, run_experiment,
)


def condition(identifier, requirement):
    return {"id": identifier, "requirement": requirement}


def test_parameterized_roles_ignore_entities_and_local_ids():
    a = [condition("remove_shark", "Remove the shark from the source image."),
         condition("preserve_a", "Preserve the rest of the scene.")]
    b = [condition("c1", "Remove the green block from the source image."),
         condition("c2", "The overall scene must remain the same.")]
    assert encode_conditions(a, {"remove_shark": "partial", "preserve_a": "complete"}) == encode_conditions(
        b, {"c1": "partial", "c2": "complete"})


def test_unknown_absent_and_not_applicable_remain_distinct():
    conditions = [condition("c1", "Remove the block.")]
    unknown = encode_conditions(conditions, {"c1": "unknown"})
    absent = encode_conditions(conditions, {"c1": "absent"})
    names = feature_names()
    assert unknown != absent
    assert unknown[names.index("preservation:not_applicable")] == 1
    assert unknown[names.index("requested_change:unknown")] == 1
    assert unknown[names.index("requested_change:absent")] == 0
    assert fixed_prediction(["unknown", "absent"]) == "unresolved"


def test_preserved_target_attributes_are_not_global_preservation():
    assert condition_role("The cylinder is present, with identifying attributes preserved except color.") == "requested_change"
    assert condition_role("The overall scene and background remain the same.") == "preservation"
    assert condition_role("Identify the catcher in the source image.") == "target_binding"


def test_missing_observations_cannot_be_imputed_as_absent():
    with pytest.raises(ValueError, match="exactly one"):
        encode_conditions([condition("c1", "Remove the block.")], {})
    with pytest.raises(ValueError, match="Invalid observation"):
        encode_conditions([condition("c1", "Remove the block.")], {"c1": "transport_error"})


def records(case, state, target, count=5, category="a"):
    return [{"case_id": case, "group": case, "category": category,
             "features": [state], "target": target} for _ in range(count)]


def test_each_case_has_equal_training_and_metric_weight():
    rows = records("a", 0, "no", 5) + records("b", 1, "yes", 1)
    assert sum(case_weights(rows)[:5]) == pytest.approx(1)
    assert sum(case_weights(rows)[5:]) == pytest.approx(1)
    measured = metrics(rows, ["no"] * 6)
    assert measured["case_macro_accuracy"] == .5


def test_repeats_and_shared_source_instruction_groups_never_cross_folds():
    rows = sum((records(str(i), i % 2, "no") for i in range(8)), [])
    # Multiple editor outputs of one task must remain together as well.
    for row in rows:
        if row["case_id"] == "1":
            row["group"] = "0"
    for train, test in grouped_folds(rows):
        assert {rows[i]["group"] for i in train}.isdisjoint({rows[i]["group"] for i in test})
        assert {rows[i]["case_id"] for i in train}.isdisjoint({rows[i]["case_id"] for i in test})


def test_minimum_case_support_cannot_be_satisfied_by_repeats():
    rows = records("a", 0, "no", 100) + records("b", 1, "yes", 100)
    model = SharedDecisionTree(["semantic"], min_cases_leaf=2).fit(rows)
    assert model.tree["leaf"]  # Two cases cannot create two leaves of two cases.
    rows += records("c", 0, "no", 1) + records("d", 1, "yes", 1)
    model.fit(rows)
    assert not model.tree["leaf"]
    assert model.tree["left"]["case_support"] == 2
    assert model.tree["right"]["case_support"] == 2


def test_portable_program_and_trace_use_only_features():
    rows = records("a", 0, "no") + records("b", 0, "no") + records("c", 1, "yes") + records("d", 1, "yes")
    program = SharedDecisionTree(["requested_change:complete"]).fit(rows)
    restored = SharedDecisionTree.from_dict(program.to_dict())
    assert [restored.predict([v]) for v in (0, 1)] == ["no", "yes"]
    assert restored.decision([1])["path"][0]["feature"] == "requested_change:complete"
    assert "case_id" not in str(restored.to_dict())
    assert restored.to_dict()["probabilities_calibrated"] is False
    broken = deepcopy(program.to_dict())
    broken["tree"]["feature"] = "human_label"
    with pytest.raises(ValueError, match="Invalid split"):
        SharedDecisionTree.from_dict(broken)


def test_collision_bound_and_case_bootstrap_do_not_count_repeats_as_cases():
    rows = records("a", 0, "no", 5) + records("b", 0, "yes", 1)
    diagnostic = collisions(rows)
    assert diagnostic["observed_lookup_accuracy_bound"] == pytest.approx(.5)
    assert len(diagnostic["conflicting_vectors"]) == 1
    delta = bootstrap_delta(rows, ["no"] * 6, ["yes"] * 6, repeats=100)
    assert delta["cases"] == 2
    assert delta["difference"] == 0


def test_constant_prediction_stability_does_not_imply_alignment():
    rows = records("a", 0, "yes") + records("b", 0, "partial")
    measured = metrics(rows, ["no"] * 10)
    assert measured["conditional_pairwise_disagreement"] == 0
    assert measured["case_macro_accuracy"] == 0


@pytest.fixture
def frozen_source(tmp_path):
    """Synthetic bound five-repeat records, including unknown and failed draws."""
    old, source = tmp_path / "old", tmp_path / "five"
    for directory in (old, source):
        (directory / "jobs").mkdir(parents=True)
    rows = {}
    for cohort in ("J", "N"):
        for i, target in enumerate(("no", "no", "partial", "yes"), 1):
            case = f"{cohort}{i:02}"
            criteria = {"conditions": [condition("c1", "Remove the block.")]}
            rows[case] = {"instruction": f"Unique instruction {case}", "human_label": target,
                          "task": str(i), "plan": criteria, "feedback_used": False,
                          "images": [{"sha256": f"source-{case}"}, {"sha256": f"edit-{case}"}]}
            for rep in range(5):
                job = f"check/{rep}/{case}/c1"
                status = {"no": "absent", "partial": "partial", "yes": "complete"}[target]
                if case == "N01" and rep == 0:
                    status = "unknown"
                record = {"job_id": job, "outcome": "completed",
                          "full_plan_sha256": digest(criteria),
                          "check": {"condition_id": "c1", "status": status},
                          "calls": [{"input": {"instruction": rows[case]["instruction"],
                                               "condition": criteria["conditions"][0]},
                                     "image_sha256": [f"source-{case}", f"edit-{case}"]}]}
                if case == "N01" and rep == 1:
                    record = {"job_id": job, "outcome": "transport_error"}
                directory = old if rep < 2 else source
                (directory / "jobs" / f"{case}-{rep}.json").write_text(json.dumps(record))
    frozen = old / "frozen_plans.json"
    frozen.write_text(json.dumps(rows))
    manifest = {"repeats": 5, "source": str(old), "rows": rows,
                "source_files": {str(frozen): file_hash(frozen)}}
    (source / "manifest.json").write_text(json.dumps(manifest))
    return source


def test_bound_loader_preserves_failures_and_rejects_checker_label_leakage(frozen_source):
    rows, draws, _ = load_observations(frozen_source)
    assert len(rows) == 8 and len(draws) == 40
    assert {d["repeat"]: d["gate"] for d in draws if d["case_id"] == "N01"} == {
        0: "unknown", 1: "incomplete", 2: "known", 3: "known", 4: "known"}
    path = frozen_source / "jobs/N02-2.json"
    value = json.loads(path.read_text())
    value["calls"][0]["input"]["human_label"] = "no"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="checker inputs"):
        load_observations(frozen_source)


def test_bound_loader_rejects_missing_slots_and_changed_original(frozen_source):
    path = frozen_source / "jobs/N02-2.json"
    original = path.read_text()
    path.unlink()
    with pytest.raises(ValueError, match="observation slots"):
        load_observations(frozen_source)
    path.write_text(original)
    frozen = frozen_source.parent / "old/frozen_plans.json"
    frozen.write_text(frozen.read_text() + " ")
    with pytest.raises(ValueError, match="Changed original artifact"):
        load_observations(frozen_source)


def test_offline_pipeline_test_targets_cannot_change_primary_selected_rules(frozen_source, tmp_path):
    first = run_experiment(frozen_source, tmp_path / "run-one")
    assert first["evaluation_outcomes"] == {"unknown": 1, "incomplete": 1, "known": 18}
    assert first["primary"]["roles_tree"]["resolved_draw_coverage"] == .9
    # Change evaluation labels in both bound snapshots; observations stay fixed.
    # Primary selection must remain independent even though test metrics change.
    path = frozen_source / "manifest.json"
    manifest = json.loads(path.read_text())
    frozen = frozen_source.parent / "old/frozen_plans.json"
    rows = json.loads(frozen.read_text())
    for case in rows:
        if case.startswith("N"):
            rows[case]["human_label"] = "partial"
            manifest["rows"][case]["human_label"] = "partial"
    frozen.write_text(json.dumps(rows))
    manifest["source_files"][str(frozen)] = file_hash(frozen)
    path.write_text(json.dumps(manifest))
    second = run_experiment(frozen_source, tmp_path / "run-two")
    assert first["selection"] == second["selection"]
    for name in first["models"]:
        assert first["models"][name]["program"] == second["models"][name]["program"]
        assert first["models"][name]["decisions"] == second["models"][name]["decisions"]
    assert first["primary"]["fixed_reducer"] != second["primary"]["fixed_reducer"]
    assert (tmp_path / "run-two/llm-histories.log").read_text().startswith("No model calls")
