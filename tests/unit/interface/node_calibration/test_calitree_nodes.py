import json
import math
import threading
import time
from types import SimpleNamespace

import pytest

from vejudge.interface.node_calibration.calitree_nodes import (
    CaliTreeEvalNodeExecutor,
    CaliTreeJudgeNodeExecutor,
    CaliTreeTrainNodeExecutor,
    _CaliTreeRuntime,
    _apply_consensus_calibrator,
    _calibration_split,
    _conflict_action,
    _consensus_result,
    _editor_prior_action,
    _fit_editor_prior,
    _fit_conflict_policy,
    _fit_selective_policy,
    _hash,
    _human_agreement_bucket,
    _human_label_reliability,
    _parse_judgment,
    _prompt,
    _select_consensus_calibrator,
    _semantic_edit_type,
)
from vejudge.interface.node_db.imagenhub_source_node import ImagenHubSourceNodeExecutor
from vejudge.interface.node_db.editinspector_source_node import (
    EditInspectorSourceNodeExecutor,
)
from vejudge.interface.node_calibration.rubric_lite_nodes import (
    RubricLiteApplyNodeExecutor,
    RubricLiteBoundaryNodeExecutor,
    RubricLiteFitNodeExecutor,
    RubricLiteFrozenNodeExecutor,
    RubricLiteTrainNodeExecutor,
)


def _sample(item_id, split="train"):
    return {
        "item_id": item_id,
        "editor": "SDEdit",
        "split": split,
        "input": {
            "instruction": "make it blue",
            "source_image_path": "/tmp/source.jpg",
        },
        "output": {"edited_image_path": "/tmp/edited.jpg"},
    }


def test_imagenhub_source_dry_run_needs_no_dataset_or_download(
    make_ctx, monkeypatch
):
    monkeypatch.setattr(
        "vejudge.interface.node_db.imagenhub_source_node.ImagenHubLoader.load_all",
        lambda _self: (_ for _ in ()).throw(FileNotFoundError("not installed")),
    )
    result = ImagenHubSourceNodeExecutor().run(make_ctx(params={"editors": ["SDEdit"]}))
    assert result.status == "done"
    assert result.outputs == {"raw_dataset": {}, "raw_labels": {}}
    assert result.meta["downloads"] == 0
    assert result.meta["expected_train"] == 29
    assert result.meta["expected_test"] == 150
    assert result.meta["local_data_available"] is False


def test_imagenhub_source_dry_run_uses_local_records_for_exact_planning(
    make_ctx, monkeypatch
):
    samples = {
        "task::SDEdit": _sample("task::SDEdit"),
        "heldout::SDEdit": _sample("heldout::SDEdit", "test"),
    }
    labels = {
        item_id: {"target_label": "yes"}
        for item_id in samples
    }
    monkeypatch.setattr(
        "vejudge.interface.node_db.imagenhub_source_node.ImagenHubLoader.load_all",
        lambda _self: (samples, labels),
    )
    result = ImagenHubSourceNodeExecutor().run(
        make_ctx(params={"editors": ["SDEdit"]})
    )
    assert result.outputs["raw_dataset"] == samples
    assert result.meta["split_counts"] == {"train": 1, "test": 1}
    assert result.meta["downloads"] == 0
    assert result.meta["local_data_available"] is True


def test_editinspector_source_filters_frozen_confirmation_partition(
    make_ctx, monkeypatch
):
    samples = {
        "dev": {**_sample("dev", "test"), "external_partition": "development"},
        "confirm": {
            **_sample("confirm", "test"),
            "external_partition": "confirmation",
        },
    }
    labels = {
        item_id: {"target_label": "yes"}
        for item_id in samples
    }
    monkeypatch.setattr(
        "vejudge.interface.node_db.editinspector_source_node.EditInspectorLoader.load_all",
        lambda _self: (samples, labels),
    )

    result = EditInspectorSourceNodeExecutor().run(
        make_ctx(params={"partition": "confirmation"})
    )

    assert set(result.outputs["raw_dataset"]) == {"confirm"}
    assert set(result.outputs["raw_labels"]) == {"confirm"}
    assert result.meta["partition"] == "confirmation"
    assert result.meta["n_items"] == 1

    calibration = EditInspectorSourceNodeExecutor().run(
        make_ctx(params={"partition": "calibration"})
    )
    assert set(calibration.outputs["raw_dataset"]) == {
        "dev", "confirm",
    }


def test_calitree_train_dry_run_reports_calls_and_equal_token_cap(make_ctx):
    samples = {
        "train::SDEdit": _sample("train::SDEdit"),
        "test::SDEdit": _sample("test::SDEdit", "test"),
    }
    labels = {
        "train::SDEdit": {"target_label": "yes"},
        "test::SDEdit": {"target_label": "partial"},
    }
    ctx = make_ctx(
        params={"embedding_model": "embed", "max_steps": 3},
        inputs={
            "samples": samples,
            "labels": labels,
            "judge_engine": {"model": "judge"},
            "optimizer_engine": {"model": "optimizer", "max_tokens": 100},
        },
    )
    result = CaliTreeTrainNodeExecutor().run(ctx)
    assert result.status == "done"
    assert result.meta["n_train"] == result.meta["n_test"] == 1
    assert result.meta["optimizer_completion_token_budget"] == 300
    assert result.meta["n_fit_tasks"] == 1
    assert result.meta["estimated_calls"]["task_leaf_optimizer_max"] == 3


def test_rubric_lite_dry_run_has_no_tree_embedding_or_critic_calls(make_ctx):
    samples = {
        "train::SDEdit": _sample("train::SDEdit"),
        "test::SDEdit": _sample("test::SDEdit", "test"),
    }
    labels = {
        "train::SDEdit": {
            "target_label": "partial",
            "ratings": [{"sc": 0.5}, {"sc": 0.5}, {"sc": 0.5}],
        },
        "test::SDEdit": {"target_label": "yes"},
    }
    result = RubricLiteTrainNodeExecutor().run(make_ctx(
        params={"max_steps": 3},
        inputs={
            "samples": samples,
            "labels": labels,
            "judge_engine": {"model": "judge"},
            "optimizer_engine": {"model": "optimizer", "max_tokens": 100},
        },
    ))

    assert result.status == "done"
    assert result.meta["architecture"] == "rubric_lite"
    assert result.meta["optimizer_completion_token_budget"] == 300
    assert result.meta["estimated_calls"]["embedding"] == 0
    assert result.meta["estimated_calls"]["critic"] == 0
    assert result.meta["estimated_calls"]["optimizer_max"] == 3


def test_frozen_rubric_lite_loads_versioned_prompt_and_cutpoints(make_ctx):
    result = RubricLiteFrozenNodeExecutor().run(make_ctx(
        params={"model_version": "rubric_lite_v4_imagenhub"},
        inputs={},
    ))

    assert result.status == "done"
    tree = result.outputs["prompt_tree"]
    assert tree["architecture"] == "rubric_lite"
    assert tree["prediction_cache"] == {}
    assert tree["ordinal_thresholds"] == {
        "no_partial": 75.000001,
        "partial_yes": 89.000001,
    }
    assert tree["training_provenance"]["train_tasks"] == 29
    assert tree["selective_policy"]["minimum_ordinal_score"] == 100
    assert "change_evidence" in tree["nodes"]["rubric:global"]["prompt"]
    assert result.meta["model_calls"] == 0


def test_frozen_rubric_lite_loads_external_two_cutpoint_calibrator(
    make_ctx,
):
    result = RubricLiteFrozenNodeExecutor().run(make_ctx(
        params={
            "model_version":
                "rubric_lite_v4_editinspector_cutpoints_v1"
        },
        inputs={},
    ))

    assert result.status == "done"
    tree = result.outputs["prompt_tree"]
    assert tree["ordinal_thresholds"] == {
        "no_partial": 25.000001,
        "partial_yes": 75.000001,
    }
    assert tree["training_provenance"]["calibration_cases"] == 392
    assert tree["training_provenance"]["final_partition_used"] is False
    assert result.meta["model_calls"] == 0


def test_frozen_rubric_lite_loads_core_completion_rubric(make_ctx):
    result = RubricLiteFrozenNodeExecutor().run(make_ctx(
        params={
            "model_version":
                "rubric_lite_v5_core_completion_experimental"
        },
        inputs={},
    ))

    assert result.status == "done"
    tree = result.outputs["prompt_tree"]
    assert tree["prompt_version"] == "rubric_lite_v5"
    assert tree["ordinal_thresholds"] == {
        "no_partial": 25.0,
        "partial_yes": 75.0,
    }
    prompt = tree["nodes"]["rubric:global"]["prompt"]
    assert "CORE visibly testable requirements" in prompt
    assert "GENERATION QUALITY" in prompt
    assert result.meta["model_calls"] == 0


def test_frozen_rubric_lite_loads_evidence_ledger_rubric(make_ctx):
    result = RubricLiteFrozenNodeExecutor().run(make_ctx(
        params={
            "model_version":
                "rubric_lite_v6_evidence_ledger_experimental"
        },
        inputs={},
    ))

    assert result.status == "done"
    tree = result.outputs["prompt_tree"]
    assert tree["prompt_version"] == "rubric_lite_v6"
    assert tree["ordinal_thresholds"] == {
        "no_partial": 25.0,
        "partial_yes": 75.0,
    }
    prompt = tree["nodes"]["rubric:global"]["prompt"]
    assert "EVIDENCE LEDGER" in prompt
    assert "semantic_completion" in prompt
    assert result.meta["model_calls"] == 0


def test_rubric_lite_fit_learns_only_two_cutpoints_with_oof_report(
    make_ctx,
):
    item_ids = [
        f"{label}-{index}"
        for label in ("no", "partial", "yes")
        for index in range(5)
    ]
    targets = {
        item_id: item_id.split("-", 1)[0]
        for item_id in item_ids
    }
    scores = {
        "no": [0, 0, 10, 20, 20],
        "partial": [40, 40, 50, 60, 60],
        "yes": [90, 90, 95, 100, 100],
    }
    samples = {
        item_id: _sample(item_id, "test")
        for item_id in item_ids
    }
    labels = {
        item_id: {"target_label": targets[item_id]}
        for item_id in item_ids
    }
    judge_result = {
        item_id: {
            "calitree": {
                "label": "partial",
                "ordinal_score": scores[targets[item_id]][
                    int(item_id.rsplit("-", 1)[1])
                ],
            },
        }
        for item_id in item_ids
    }

    result = RubricLiteFitNodeExecutor().run(make_ctx(
        dry_run=False,
        inputs={
            "samples": samples,
            "labels": labels,
            "judge_result": judge_result,
        },
        params={
            "selection_objective": "macro_f1",
            "cv_folds": 5,
            "cv_seed": 44,
        },
    ))

    assert result.status == "done"
    calibrator = result.outputs["rubric_calibrator"]
    report = result.outputs["calitree_report"]
    assert calibrator["fitted"] is True
    assert set(calibrator["thresholds"]) == {
        "no_partial", "partial_yes",
    }
    assert calibrator["uses_editor_identity"] is False
    assert calibrator["uses_instruction_features"] is False
    assert report["out_of_fold"]["metrics"]["accuracy"] == 1
    assert report["deployment"]["metrics"]["per_label_f1"][
        "partial"
    ] == 1
    assert result.meta["model_calls"] == 0


def test_rubric_lite_fit_dry_run_emits_placeholder_without_scores(
    make_ctx,
):
    result = RubricLiteFitNodeExecutor().run(make_ctx(
        inputs={
            "samples": {"case": _sample("case")},
            "labels": {"case": {"target_label": "partial"}},
            "judge_result": {},
        },
    ))

    assert result.status == "done"
    assert result.outputs["rubric_calibrator"]["fitted"] is False
    assert result.meta["n_expected"] == 1
    assert result.meta["model_calls"] == 0


def test_rubric_lite_apply_relabels_scores_without_model_calls(
    make_ctx,
):
    judge_result = {
        "low": {
            "calitree": {
                "label": "partial",
                "ordinal_score": 10,
                "parsed": {"label": "partial"},
            },
        },
        "middle": {
            "calitree": {
                "label": "no",
                "ordinal_score": 50,
                "parsed": {"label": "no"},
            },
        },
        "high": {
            "calitree": {
                "label": "partial",
                "ordinal_score": 90,
                "parsed": {"label": "partial"},
            },
        },
    }
    result = RubricLiteApplyNodeExecutor().run(make_ctx(inputs={
        "judge_result": judge_result,
        "rubric_calibrator": {
            "version": "rubric-lite-cutpoints-v1",
            "selection_objective": "macro_f1",
            "thresholds": {
                "no_partial": 25.000001,
                "partial_yes": 75.000001,
            },
        },
    }))

    assert result.status == "done"
    rows = {
        item_id: value["calitree"]
        for item_id, value in result.outputs["judge_result"].items()
    }
    assert {
        item_id: row["label"] for item_id, row in rows.items()
    } == {"low": "no", "middle": "partial", "high": "yes"}
    assert rows["middle"]["pre_calibration_label"] == "no"
    assert rows["high"]["parsed"]["label"] == "yes"
    assert result.meta["n_changed"] == 3
    assert result.meta["model_calls"] == 0


def test_rubric_lite_boundary_dry_run_counts_only_score_band(make_ctx):
    samples = {
        "low": _sample("low", "test"),
        "high": _sample("high", "test"),
        "train": _sample("train", "train"),
    }
    judge_result = {
        "low": {"calitree": {"label": "no", "ordinal_score": 25}},
        "high": {"calitree": {"label": "no", "ordinal_score": 75}},
        "train": {"calitree": {"label": "partial", "ordinal_score": 75}},
    }

    result = RubricLiteBoundaryNodeExecutor().run(make_ctx(
        params={
            "verifier_version": "rubric_lite_v1",
            "minimum_ordinal_score": 50,
            "eligible_base_labels": ["no", "partial", "yes"],
            "decision_policy": "partial_only",
            "apply_split": "test",
        },
        inputs={
            "samples": samples,
            "judge_result": judge_result,
            "judge_engine": {"model": "judge"},
        },
    ))

    assert result.status == "done"
    assert result.meta["n_split_eligible"] == 2
    assert result.meta["n_score_eligible"] == 1
    assert result.meta["estimated_calls"] == 1
    assert result.outputs["judge_result"] is judge_result


def test_rubric_lite_boundary_dry_run_reports_max_when_upstream_is_placeholder(
    make_ctx,
):
    samples = {
        "test-a": _sample("test-a", "test"),
        "test-b": _sample("test-b", "test"),
        "train": _sample("train", "train"),
    }

    result = RubricLiteBoundaryNodeExecutor().run(make_ctx(
        params={"apply_split": "test"},
        inputs={
            "samples": samples,
            "judge_result": {},
            "judge_engine": {"model": "judge"},
        },
    ))

    assert result.status == "done"
    assert result.meta["estimated_calls"] == 0
    assert result.meta["estimated_calls_max"] == 2
    assert result.meta["n_split_eligible"] == 2


def test_rubric_lite_boundary_can_be_disabled_without_calls(make_ctx):
    judge_result = {
        "case": {"calitree": {"label": "yes", "ordinal_score": 100}},
    }
    result = RubricLiteBoundaryNodeExecutor().run(make_ctx(
        dry_run=False,
        allow_live=True,
        params={"enabled": False},
        inputs={
            "samples": {"case": _sample("case", "test")},
            "judge_result": judge_result,
            "judge_engine": {"model": "judge"},
        },
    ))

    assert result.status == "done"
    assert result.outputs["judge_result"] is judge_result
    assert result.meta["enabled"] is False
    assert result.meta["estimated_calls"] == 0


@pytest.mark.parametrize(
    ("conditions", "delta", "subject", "scene", "expected"),
    [
        ([{"evidence": "none"}], "absent", "correct", "same", "no"),
        (
            [{"evidence": "full"}, {"evidence": "none"}],
            "recognizable",
            "correct",
            "same",
            "partial",
        ),
        (
            [{"evidence": "partial"}],
            "recognizable",
            "correct",
            "same",
            "partial",
        ),
        (
            [{"evidence": "full"}, {"evidence": "full"}],
            "recognizable",
            "correct",
            "same",
            "yes",
        ),
        ([{"evidence": "full"}], "recognizable", "wrong", "same", "no"),
        ([{"evidence": "full"}], "recognizable", "correct", "replaced", "no"),
    ],
)
def test_partial_progress_rubric_maps_structured_evidence_deterministically(
    conditions, delta, subject, scene, expected
):
    parsed = _parse_judgment(json.dumps({
        "rubric_version": "rubric-lite-partial-v2",
        "conditions": conditions,
        "requested_delta": delta,
        "intended_subject": subject,
        "scene": scene,
        "label": "yes",
        "rationale": "visible comparison",
    }))

    assert parsed["valid"] is True
    assert parsed["label"] == expected


def test_calitree_dry_run_allows_unset_models_but_live_requires_embedding(
    make_ctx,
):
    planning = CaliTreeTrainNodeExecutor().run(make_ctx(inputs={
        "samples": {}, "labels": {}, "judge_engine": {}, "optimizer_engine": {},
    }))
    assert planning.status == "done"
    live = CaliTreeTrainNodeExecutor().run(make_ctx(
        dry_run=False,
        allow_live=True,
        inputs={
            "samples": {},
            "labels": {},
            "judge_engine": {},
            "optimizer_engine": {},
        },
    ))
    assert live.status == "error"
    assert "embedding_model" in live.error


def test_calitree_rejects_unknown_calibration_agreement_filter(make_ctx):
    result = CaliTreeTrainNodeExecutor().run(make_ctx(
        params={"calibration_agreement_filter": "mostly"},
        inputs={
            "samples": {},
            "labels": {},
            "judge_engine": {},
            "optimizer_engine": {},
        },
    ))
    assert result.status == "error"
    assert "calibration_agreement_filter" in result.error


def test_internal_calibration_split_is_deterministic_and_label_stratified():
    labels = {
        f"{label}-{index}": {"target_label": label}
        for label in ("no", "partial", "yes")
        for index in range(4)
    }
    ids = sorted(labels)
    first = _calibration_split(ids, labels, validation_fraction=0.25, seed=44)
    second = _calibration_split(ids, labels, validation_fraction=0.25, seed=44)

    assert first == second
    fit, validation = first
    assert len(fit) == 9
    assert len(validation) == 3
    assert {_target["target_label"] for item_id, _target in labels.items() if item_id in validation} == {
        "no", "partial", "yes",
    }


def test_internal_calibration_split_has_zero_task_leakage():
    labels = {}
    for task_index in range(8):
        task_uid = f"task-{task_index}"
        for editor_index, target in enumerate(("no", "partial", "yes")):
            item_id = f"{task_uid}::editor-{editor_index}"
            labels[item_id] = {
                "task_uid": task_uid,
                "target_label": target,
            }

    fit, validation = _calibration_split(
        sorted(labels),
        labels,
        validation_fraction=0.25,
        seed=44,
    )
    fit_tasks = {labels[item_id]["task_uid"] for item_id in fit}
    validation_tasks = {
        labels[item_id]["task_uid"] for item_id in validation
    }

    assert len(validation_tasks) == 2
    assert fit_tasks.isdisjoint(validation_tasks)
    assert len(validation) == 6


def test_conflict_tree_branches_by_editor_and_prunes_non_improving_rules():
    samples = {
        "a1": {**_sample("a1"), "editor": "A"},
        "a2": {**_sample("a2"), "editor": "A"},
        "b1": {**_sample("b1"), "editor": "B"},
        "b2": {**_sample("b2"), "editor": "B"},
    }
    base = {item_id: {"label": "partial"} for item_id in samples}
    critic = {item_id: {"label": "no"} for item_id in samples}
    targets = {"a1": "no", "a2": "no", "b1": "partial", "b2": "partial"}

    policy = _fit_conflict_policy(
        base, critic, samples, targets, sorted(samples), min_support=2, min_gain=0
    )

    assert policy["rules"]["A::partial"]["action"] == "critic"
    assert "B::partial" not in policy["rules"]
    assert policy["rules"]["*::*"]["action"] == "base"
    assert _conflict_action(policy, samples["a1"], "partial") == (
        "critic", "A::partial"
    )
    assert _conflict_action(policy, samples["b1"], "partial") == (
        "base", "*::*"
    )


def test_three_way_consensus_uses_majority_and_partial_for_total_disagreement():
    fallback = {"label": "no", "rationale": "fallback"}
    majority = _consensus_result(
        {
            "initial": {"label": "yes", "rationale": "initial"},
            "textgrad": {"label": "yes", "rationale": "textgrad"},
            "critic": {"label": "no", "rationale": "critic"},
        },
        fallback=fallback,
    )
    assert majority["label"] == "yes"
    assert majority["consensus_support"] == 2
    assert majority["consensus_tie"] is False
    assert majority["candidate_labels"] == {
        "initial": "yes", "textgrad": "yes", "critic": "no",
    }

    tie = _consensus_result(
        {
            "initial": {"label": "yes", "rationale": "initial"},
            "textgrad": {"label": "partial", "rationale": "uncertain"},
            "critic": {"label": "no", "rationale": "critic"},
        },
        fallback=fallback,
    )
    assert tie["label"] == "partial"
    assert tie["rationale"] == "uncertain"
    assert tie["consensus_support"] == 1
    assert tie["consensus_tie"] is True


def test_hierarchical_consensus_capacity_is_selected_on_validation_gain():
    ids = [f"case-{index}" for index in range(12)]
    samples = {item_id: _sample(item_id) for item_id in ids}
    targets = {item_id: "yes" for item_id in ids}
    candidates = {
        item_id: {
            "initial": {"label": "no", "rationale": "initial"},
            "textgrad": {"label": "no", "rationale": "textgrad"},
            "critic": {"label": "partial", "rationale": "critic"},
        }
        for item_id in ids
    }

    policy = _select_consensus_calibrator(
        fit_ids=ids[:8],
        validation_ids=ids[8:],
        train_ids=ids,
        candidates=candidates,
        samples=samples,
        targets=targets,
    )
    calibrated = _apply_consensus_calibrator(
        policy,
        sample=samples[ids[0]],
        candidates=candidates[ids[0]],
        fallback=candidates[ids[0]]["initial"],
    )

    assert policy["selection"]["baseline_accuracy"] == 0
    assert policy["selection"]["selected_accuracy"] == 1
    assert policy["selection"]["selected_levels"]
    assert calibrated["label"] == "yes"
    assert calibrated["calibration_action"] == "override"
    assert calibrated["calibration_rule_support"] == 12


def test_semantic_edit_preprocessing_is_target_blind_and_deterministic():
    sample = _sample("x")
    sample["input"]["instruction"] = "Remove the vase from the table"
    assert _semantic_edit_type(sample) == "remove"
    sample["input"]["instruction"] = "Make the car bright blue"
    assert _semantic_edit_type(sample) == "color"
    sample["input"]["instruction"] = "Change the car to blue"
    assert _semantic_edit_type(sample) == "color"
    sample["input"]["instruction"] = "Put the dog behind the chair"
    assert _semantic_edit_type(sample) == "spatial"


def test_human_agreement_filter_distinguishes_rating_noise():
    assert _human_agreement_bucket({
        "ratings": [{"sc": 0}, {"sc": 0}, {"sc": 0}],
    }) == "unanimous"
    assert _human_agreement_bucket({
        "ratings": [{"sc": 0}, {"sc": 0.5}, {"sc": 0.5}],
    }) == "disputed"
    assert _human_agreement_bucket({}) == "unknown"


def test_human_label_reliability_quantifies_partial_ambiguity():
    targets = {"no": "no", "partial": "partial", "yes": "yes"}
    predictions = {"no": "no", "partial": "partial", "yes": "partial"}
    labels = {
        "no": {"ratings": [{"sc": 0}, {"sc": 0}, {"sc": 0}]},
        "partial": {"ratings": [{"sc": 0}, {"sc": 0.5}, {"sc": 1}]},
        "yes": {"ratings": [{"sc": 1}, {"sc": 1}, {"sc": 0.5}]},
    }

    report = _human_label_reliability(targets, predictions, labels)

    assert report["n"] == 3
    assert report["mean_raters"] == 3
    assert report["unanimous_fraction"] == pytest.approx(1 / 3)
    assert report["target_majority_support_fraction"] == pytest.approx(2 / 3)
    assert report["target_matches_rating_median_fraction"] == 1
    assert report["modal_rater_agreement_ceiling"] == pytest.approx(2 / 3)
    assert report["prediction_expected_rater_agreement"] == pytest.approx(5 / 9)
    assert report["per_target"]["partial"]["unanimous_fraction"] == 0
    assert report["per_target"]["partial"][
        "target_majority_support_fraction"
    ] == 0
    assert report["per_target"]["partial"][
        "mean_label_entropy_bits"
    ] == pytest.approx(math.log2(3))


def test_selective_policy_is_fit_only_from_supported_training_editors():
    rows = {
        "a1": {"label": "no", "consensus_support": 3},
        "a2": {"label": "no", "consensus_support": 3},
        "b1": {"label": "yes", "consensus_support": 3},
        "b2": {"label": "yes", "consensus_support": 2},
    }
    samples = {
        "a1": {"editor": "stable"},
        "a2": {"editor": "stable"},
        "b1": {"editor": "noisy"},
        "b2": {"editor": "noisy"},
    }
    targets = {"a1": "no", "a2": "no", "b1": "no", "b2": "yes"}
    policy = _fit_selective_policy(
        rows,
        samples,
        targets,
        list(rows),
        minimum_consensus_support=3,
        editor_min_support=2,
        editor_accuracy_threshold=0.85,
    )
    assert policy["active_editors"] == ["stable"]
    assert policy["editors"]["stable"]["accuracy"] == 1
    assert policy["editors"]["noisy"]["n"] == 1
    assert policy["editors"]["noisy"]["active"] is False


def test_editor_prior_uses_only_official_train_and_prunes_uncertain_editors():
    labels = {
        **{
            f"stable-{index}": {
                "split": "train", "editor": "Stable", "target_label": "no"
            }
            for index in range(20)
        },
        "stable-test": {
            "split": "test", "editor": "Stable", "target_label": "yes"
        },
        "mixed-no": {
            "split": "train", "editor": "Mixed", "target_label": "no"
        },
        "mixed-yes": {
            "split": "train", "editor": "Mixed", "target_label": "yes"
        },
    }

    policy = _fit_editor_prior(labels, threshold=0.98, min_support=20)

    assert policy["branches"]["Stable"]["counts"] == {
        "no": 20, "partial": 0, "yes": 0,
    }
    assert policy["branches"]["Stable"]["active"] is True
    assert _editor_prior_action(policy, {"editor": "Stable"}) == (
        "no", "editor_prior:Stable"
    )
    assert policy["branches"]["Mixed"]["active"] is False
    assert _editor_prior_action(policy, {"editor": "Mixed"}) == (
        None, "editor_prior:pruned"
    )


def test_conflict_tree_keeps_globally_better_critic_when_subgroups_are_tiny():
    samples = {str(i): {**_sample(str(i)), "editor": f"E{i}"} for i in range(4)}
    base = {str(i): {"label": "partial"} for i in range(4)}
    critic = {
        "0": {"label": "no"},
        "1": {"label": "no"},
        "2": {"label": "yes"},
        "3": {"label": "yes"},
    }
    targets = {"0": "no", "1": "no", "2": "yes", "3": "partial"}

    policy = _fit_conflict_policy(
        base, critic, samples, targets, sorted(samples), min_support=2, min_gain=0
    )

    assert policy["rules"]["*::*"]["action"] == "critic"
    assert _conflict_action(policy, samples["0"], "partial") == (
        "critic", "*::*"
    )


def test_optimizer_prompt_templates_preserve_literal_json_when_formatted():
    extracted = _prompt("extract_components.txt").format(rubric="judge rubric")
    merged = _prompt("merge_prompts.txt").format(left="left rubric", right="right rubric")

    assert '{"criteria":["..."]' in extracted
    assert "judge rubric" in extracted
    assert '{"conflict":false' in merged
    assert "left rubric" in merged
    assert "right rubric" in merged


def test_v2_rubric_targets_semantic_consistency_not_standalone_quality():
    rubric = _prompt("initial_rubric.txt", "calitree_v2")
    assert "Semantic Consistency" in rubric
    assert "Minor visual artifacts alone do not reduce SC" in rubric
    assert "no versus partial" in rubric
    assert "partial versus yes" in rubric


def test_v3_decomposed_rubric_resolves_conflicting_model_label():
    result = _parse_judgment(json.dumps({
        "rubric_version": "sc-v3",
        "rubric_scores": {
            "requested_change": "none",
            "subject_identity": "correct",
            "spatial_relation": "not_applicable",
            "scene_continuity": "preserved",
        },
        "label": "partial",
        "rationale": "The requested object is absent.",
    }))

    assert result["label"] == "no"
    assert result["model_label"] == "partial"
    assert result["conflict_resolved"] is True
    assert "no visible evidence" in result["conflict_reason"]


def test_v3_decomposed_rubric_does_not_penalize_noncatastrophic_degradation():
    result = _parse_judgment(json.dumps({
        "rubric_version": "sc-v3",
        "rubric_scores": {
            "requested_change": "full",
            "subject_identity": "correct",
            "spatial_relation": "not_applicable",
            "scene_continuity": "degraded",
        },
        "label": "partial",
        "rationale": "The edit is complete but blurry.",
    }))

    assert result["label"] == "yes"
    assert result["conflict_resolved"] is True


def test_v4_fulfillment_field_has_a_deterministic_label_mapping():
    result = _parse_judgment(json.dumps({
        "fulfillment": "none",
        "label": "partial",
        "rationale": "The requested object is absent.",
    }))

    assert result["label"] == "no"
    assert result["model_label"] == "partial"
    assert result["conflict_resolved"] is True
    assert "fulfillment=none" in result["conflict_reason"]


def test_rubric_lite_condition_evidence_deterministically_maps_partial():
    result = _parse_judgment(json.dumps({
        "conditions": [
            {"condition": "make shirt blue", "evidence": "full"},
            {"condition": "add a logo", "evidence": "partial"},
        ],
        "scene": "same",
        "label": "yes",
        "rationale": "The logo is incomplete.",
    }))

    assert result["label"] == "partial"
    assert result["model_label"] == "yes"
    assert result["conflict_resolved"] is True
    assert "partial evidence" in result["conflict_reason"]


def test_rubric_lite_three_view_vote_overrides_inconsistent_model_label():
    result = _parse_judgment(json.dumps({
        "rubric_votes": {
            "evidence_gate": {"label": "partial", "evidence": "incomplete"},
            "completion_gate": {"label": "partial", "evidence": "ambiguous"},
            "locality_gate": {"label": "no", "evidence": "drift"},
        },
        "label": "yes",
        "rationale": "The model emitted an inconsistent label.",
    }))

    assert result["label"] == "partial"
    assert result["model_label"] == "yes"
    assert result["conflict_resolved"] is True
    assert "majority" in result["conflict_reason"]


def test_rubric_lite_ordinal_score_uses_weakest_visible_evidence():
    result = _parse_judgment(json.dumps({
        "rubric_version": "rubric-lite-ordinal-v3",
        "ordinal_scores": {
            "change_evidence": 95,
            "specification_fidelity": 68,
            "source_preservation": 90,
        },
        "label": "yes",
        "rationale": "The requested count is incomplete.",
    }))

    assert result["ordinal_score"] == 68
    assert result["ordinal_scores"]["specification_fidelity"] == 68
    assert result["label"] == "partial"
    assert result["model_label"] == "yes"
    assert result["conflict_resolved"] is True
    assert "minimum visible-evidence score 68" in result["conflict_reason"]


def test_rubric_lite_v5_core_completion_uses_fixed_ordinal_score():
    result = _parse_judgment(json.dumps({
        "rubric_version": "rubric-lite-core-completion-v5",
        "ordinal_scores": {
            "change_evidence": 100,
            "specification_fidelity": 50,
            "source_preservation": 100,
        },
        "label": "yes",
        "rationale": "One core requirement remains incomplete.",
    }))

    assert result["ordinal_score"] == 50
    assert result["label"] == "partial"
    assert result["model_label"] == "yes"
    assert result["conflict_resolved"] is True


def test_rubric_lite_v6_uses_semantic_completion_score():
    result = _parse_judgment(json.dumps({
        "rubric_version": "rubric-lite-evidence-ledger-v6",
        "conditions": [
            {"condition": "replace the television", "status": "mostly"},
            {"condition": "with a gaming PC", "status": "emerging"},
        ],
        "achieved_evidence": "Computer components appear in the screen.",
        "missing_evidence": "The television itself remains.",
        "residual_type": "residual_old_content",
        "semantic_completion": 58,
        "scene_validity": "same",
        "label": "yes",
        "rationale": "The requested identity is only partly achieved.",
    }))

    assert result["ordinal_score"] == 58
    assert result["ordinal_scores"] == {
        "semantic_completion": 58,
        "scene_validity_score": 100,
    }
    assert result["label"] == "partial"
    assert result["model_label"] == "yes"
    assert result["conflict_resolved"] is True
    assert "semantic completion score 58" in result["conflict_reason"]


def test_rubric_lite_v6_scene_replacement_forces_zero():
    result = _parse_judgment(json.dumps({
        "rubric_version": "rubric-lite-evidence-ledger-v6",
        "conditions": [
            {"condition": "make the door red", "status": "complete"},
        ],
        "achieved_evidence": "A red door is visible.",
        "missing_evidence": "The original scene is gone.",
        "residual_type": "scene_replacement",
        "semantic_completion": 90,
        "scene_validity": "replaced",
        "label": "yes",
        "rationale": "The output is a different scene.",
    }))

    assert result["ordinal_score"] == 0
    assert result["label"] == "no"
    assert result["valid"] is True


def test_rubric_lite_v6_rejects_invalid_ledger_schema():
    result = _parse_judgment(json.dumps({
        "rubric_version": "rubric-lite-evidence-ledger-v6",
        "conditions": [],
        "achieved_evidence": "",
        "missing_evidence": "",
        "residual_type": "unknown",
        "semantic_completion": 50,
        "scene_validity": "same",
        "label": "partial",
        "rationale": "Missing the required evidence ledger.",
    }))

    assert result["ordinal_score"] is None
    assert result["ordinal_scores"] is None
    assert result["label"] == ""
    assert result["valid"] is False


def test_rubric_lite_ordinal_score_rejects_out_of_range_fields():
    result = _parse_judgment(json.dumps({
        "rubric_version": "rubric-lite-ordinal-v3",
        "ordinal_scores": {
            "change_evidence": 101,
            "specification_fidelity": 80,
            "source_preservation": 90,
        },
        "label": "yes",
        "rationale": "Invalid score.",
    }))

    assert result["ordinal_score"] is None
    assert result["ordinal_scores"] is None
    assert result["label"] == "yes"


def test_valid_judgments_resume_from_checkpoint_without_a_second_call(make_ctx):
    class Engine:
        model = "judge"
        creds = SimpleNamespace(endpoints=["https://mock"], token="token")

        def __init__(self):
            self.calls = 0

        def generate(self, *_args, **_kwargs):
            self.calls += 1
            return {
                "content": json.dumps({"label": "yes", "rationale": "correct"}),
                "promptTokens": 2, "completionTokens": 3, "totalTokens": 5,
            }

    ctx = make_ctx(dry_run=False, allow_live=True)
    engine = Engine()
    runtime = _CaliTreeRuntime(
        ctx, judge_engine=engine, optimizer_engine=engine,
        embedding_model="embed", optimizer_budget=100,
    )
    sample = _sample("case")
    assert runtime.judge("rubric", sample)["label"] == "yes"
    assert runtime.judge("rubric", sample)["label"] == "yes"
    assert engine.calls == 1
    assert len(ctx.checkpoint) == 1


def test_judge_many_uses_configured_concurrency_and_checkpoints_results(make_ctx):
    class Engine:
        model = "judge"
        creds = SimpleNamespace(endpoints=["https://mock"], token="token")

        def __init__(self):
            self.active = 0
            self.max_active = 0
            self.lock = threading.Lock()

        def generate(self, *_args, **_kwargs):
            with self.lock:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
            time.sleep(0.02)
            with self.lock:
                self.active -= 1
            return {
                "content": json.dumps({"label": "yes", "rationale": "correct"}),
                "promptTokens": 2, "completionTokens": 3, "totalTokens": 5,
            }

    ctx = make_ctx(dry_run=False, allow_live=True)
    engine = Engine()
    runtime = _CaliTreeRuntime(
        ctx, judge_engine=engine, optimizer_engine=engine,
        embedding_model="embed", optimizer_budget=100, concurrency=4,
    )
    samples = {str(index): _sample(str(index)) for index in range(4)}
    results = runtime.judge_many("rubric", samples)

    assert set(results) == set(samples)
    assert engine.max_active > 1
    assert runtime.usage["judge_calls"] == 4
    assert len(ctx.checkpoint) == 4


def test_routed_judge_reuses_matching_training_prediction_cache(make_ctx, monkeypatch):
    prompt = "cached rubric"
    cached = {"label": "yes", "rationale": "already judged", "valid": True}
    tree = {
        "embedding_model": "embed",
        "prompt_version": "calitree_v2",
        "roots": ["root"],
        "nodes": {
            "root": {
                "id": "root",
                "prompt": prompt,
                "embedding": [1.0, 0.0],
                "children": [],
            },
        },
        "prediction_cache": {
            "case": {
                "prompt_hash": _hash("calitree_prediction", prompt),
                "result": cached,
            },
        },
    }
    monkeypatch.setattr(
        "vejudge.interface.node_calibration.calitree_nodes._engine_from",
        lambda _config, _ctx: object(),
    )
    monkeypatch.setattr(
        _CaliTreeRuntime,
        "embed",
        lambda _runtime, texts: [[1.0, 0.0] for _ in texts],
    )
    monkeypatch.setattr(
        _CaliTreeRuntime,
        "judge_many",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("cache hit must not call the judge")
        ),
    )

    result = CaliTreeJudgeNodeExecutor().run(make_ctx(
        dry_run=False,
        allow_live=True,
        inputs={
            "samples": {"case": _sample("case")},
            "prompt_tree": tree,
            "judge_engine": {"model": "judge"},
        },
    ))

    assert result.status == "done"
    assert result.outputs["judge_result"]["case"]["calitree"]["label"] == "yes"
    assert result.meta["cache_hits"] == 1
    assert result.meta["judge_calls"] == 0


def test_rubric_lite_judge_routes_single_root_without_embedding(make_ctx, monkeypatch):
    prompt = "one global rubric"
    cached = {"label": "partial", "rationale": "boundary", "valid": True}
    tree = {
        "architecture": "rubric_lite",
        "prompt_version": "rubric_lite_v1",
        "roots": ["rubric:global"],
        "nodes": {
            "rubric:global": {
                "id": "rubric:global",
                "prompt": prompt,
                "embedding": [],
                "children": [],
            },
        },
        "prediction_cache": {
            "case": {
                "prompt_hash": _hash("calitree_prediction", prompt),
                "result": cached,
            },
        },
    }
    monkeypatch.setattr(
        "vejudge.interface.node_calibration.calitree_nodes._engine_from",
        lambda _config, _ctx: object(),
    )
    monkeypatch.setattr(
        _CaliTreeRuntime,
        "embed",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("Rubric-Lite must not embed or route")
        ),
    )

    result = CaliTreeJudgeNodeExecutor().run(make_ctx(
        dry_run=False,
        allow_live=True,
        inputs={
            "samples": {"case": _sample("case")},
            "prompt_tree": tree,
            "judge_engine": {"model": "judge"},
        },
    ))

    assert result.status == "done"
    row = result.outputs["judge_result"]["case"]["calitree"]
    assert row["label"] == "partial"
    assert row["routed_node"] == "rubric:global"
    assert result.meta["judge_calls"] == 0


def test_rubric_lite_judge_applies_global_ordinal_cutpoints(
    make_ctx, monkeypatch
):
    prompt = "one scored global rubric"
    tree = {
        "architecture": "rubric_lite",
        "prompt_version": "rubric_lite_v3",
        "ordinal_thresholds": {
            "no_partial": 35,
            "partial_yes": 90,
        },
        "roots": ["rubric:global"],
        "nodes": {
            "rubric:global": {
                "id": "rubric:global",
                "prompt": prompt,
                "embedding": [],
                "children": [],
            },
        },
    }
    monkeypatch.setattr(
        "vejudge.interface.node_calibration.calitree_nodes._engine_from",
        lambda _config, _ctx: object(),
    )
    monkeypatch.setattr(
        _CaliTreeRuntime,
        "judge_many",
        lambda _runtime, _prompt, _samples: {
            "case": {
                "label": "yes",
                "ordinal_score": 70,
                "rationale": "Recognizable but incomplete.",
                "valid": True,
            },
        },
    )

    result = CaliTreeJudgeNodeExecutor().run(make_ctx(
        dry_run=False,
        allow_live=True,
        inputs={
            "samples": {"case": _sample("case")},
            "prompt_tree": tree,
            "judge_engine": {"model": "judge"},
        },
    ))

    assert result.status == "done"
    row = result.outputs["judge_result"]["case"]["calitree"]
    assert row["label"] == "partial"
    assert row["uncalibrated_label"] == "yes"
    assert row["ordinal_thresholds"] == {
        "no_partial": 35.0,
        "partial_yes": 90.0,
    }


def test_rubric_lite_judge_persists_perfect_evidence_selection(
    make_ctx, monkeypatch
):
    prompt = "one scored global rubric"
    tree = {
        "architecture": "rubric_lite",
        "prompt_version": "rubric_lite_v4",
        "ordinal_thresholds": {
            "no_partial": 75.000001,
            "partial_yes": 89.000001,
        },
        "selective_policy": {
            "version": "rubric-lite-perfect-evidence-v1",
            "signal": "ordinal_score",
            "minimum_ordinal_score": 100,
            "allowed_labels": ["yes"],
        },
        "roots": ["rubric:global"],
        "nodes": {
            "rubric:global": {
                "id": "rubric:global",
                "prompt": prompt,
                "embedding": [],
                "children": [],
            },
        },
    }
    monkeypatch.setattr(
        "vejudge.interface.node_calibration.calitree_nodes._engine_from",
        lambda _config, _ctx: object(),
    )
    monkeypatch.setattr(
        _CaliTreeRuntime,
        "judge_many",
        lambda _runtime, _prompt, _samples: {
            "perfect": {
                "label": "yes", "ordinal_score": 100,
                "rationale": "exact", "valid": True,
            },
            "near": {
                "label": "partial", "ordinal_score": 89,
                "rationale": "near", "valid": True,
            },
        },
    )

    result = CaliTreeJudgeNodeExecutor().run(make_ctx(
        dry_run=False,
        allow_live=True,
        inputs={
            "samples": {
                "perfect": _sample("perfect"),
                "near": _sample("near"),
            },
            "prompt_tree": tree,
            "judge_engine": {"model": "judge"},
        },
    ))

    rows = {
        item_id: value["calitree"]
        for item_id, value in result.outputs["judge_result"].items()
    }
    assert rows["perfect"]["selective_accepted"] is True
    assert rows["near"]["selective_accepted"] is False
    assert rows["perfect"]["selective_policy_version"] == (
        "rubric-lite-perfect-evidence-v1"
    )


def test_rubric_lite_boundary_overrides_only_partial_verifier_label(
    make_ctx, monkeypatch
):
    samples = {
        "partial": _sample("partial", "test"),
        "yes": _sample("yes", "test"),
        "low": _sample("low", "test"),
    }
    judge_result = {
        item_id: {
            "calitree": {
                "label": "no",
                "ordinal_score": score,
                "rationale": "base",
                "parsed": {"label": "no", "rationale": "base"},
            },
        }
        for item_id, score in (
            ("partial", 50), ("yes", 75), ("low", 25)
        )
    }
    monkeypatch.setattr(
        "vejudge.interface.node_calibration.rubric_lite_nodes._engine_from",
        lambda _config, _ctx: object(),
    )
    monkeypatch.setattr(
        _CaliTreeRuntime,
        "judge_many",
        lambda _runtime, _prompt, selected: {
            item_id: {
                "label": "partial" if item_id == "partial" else "yes",
                "rationale": f"verifier {item_id}",
                "valid": True,
            }
            for item_id in selected
        },
    )

    result = RubricLiteBoundaryNodeExecutor().run(make_ctx(
        dry_run=False,
        allow_live=True,
        params={
            "verifier_version": "rubric_lite_v1",
            "minimum_ordinal_score": 50,
            "eligible_base_labels": ["no", "partial", "yes"],
            "decision_policy": "partial_only",
            "apply_split": "test",
        },
        inputs={
            "samples": samples,
            "judge_result": judge_result,
            "judge_engine": {"model": "judge"},
        },
    ))

    assert result.status == "done"
    rows = {
        item_id: value["calitree"]
        for item_id, value in result.outputs["judge_result"].items()
    }
    assert rows["partial"]["label"] == "partial"
    assert rows["partial"]["pre_boundary_label"] == "no"
    assert rows["partial"]["boundary_action"] == "override_partial"
    assert rows["yes"]["label"] == "no"
    assert rows["yes"]["boundary_action"] == "retain_base"
    assert rows["low"]["label"] == "no"
    assert rows["low"]["boundary_action"] == "not_score_eligible"
    assert result.meta["n_score_eligible"] == 2
    assert result.meta["n_partial_overrides"] == 1


def test_rubric_lite_boundary_can_replace_only_selected_base_label(
    make_ctx, monkeypatch
):
    samples = {
        "no": _sample("no", "test"),
        "yes": _sample("yes", "test"),
    }
    judge_result = {
        "no": {
            "calitree": {
                "label": "no",
                "ordinal_score": 75,
                "rationale": "base no",
            },
        },
        "yes": {
            "calitree": {
                "label": "yes",
                "ordinal_score": 95,
                "rationale": "base yes",
            },
        },
    }
    monkeypatch.setattr(
        "vejudge.interface.node_calibration.rubric_lite_nodes._engine_from",
        lambda _config, _ctx: object(),
    )
    monkeypatch.setattr(
        _CaliTreeRuntime,
        "judge_many",
        lambda _runtime, _prompt, selected: {
            item_id: {
                "label": "partial",
                "rationale": "recognizable incomplete progress",
                "valid": True,
            }
            for item_id in selected
        },
    )

    result = RubricLiteBoundaryNodeExecutor().run(make_ctx(
        dry_run=False,
        allow_live=True,
        params={
            "verifier_version": "rubric_lite_partial_v2",
            "minimum_ordinal_score": 0,
            "eligible_base_labels": ["yes"],
            "decision_policy": "replace",
            "apply_split": "test",
        },
        inputs={
            "samples": samples,
            "judge_result": judge_result,
            "judge_engine": {"model": "judge"},
        },
    ))

    assert result.status == "done"
    rows = {
        item_id: value["calitree"]
        for item_id, value in result.outputs["judge_result"].items()
    }
    assert rows["no"]["label"] == "no"
    assert rows["no"]["boundary_action"] == "not_score_eligible"
    assert rows["yes"]["label"] == "partial"
    assert rows["yes"]["pre_boundary_label"] == "yes"
    assert rows["yes"]["boundary_action"] == "replace_eligible"
    assert result.meta["n_score_eligible"] == 1
    assert result.meta["n_partial_overrides"] == 1


def test_eval_reports_overall_splits_editors_and_confusion(make_ctx):
    samples = {
        "train": _sample("train", "train"),
        "test": _sample("test", "test"),
    }
    result = CaliTreeEvalNodeExecutor().run(make_ctx(inputs={
        "samples": samples,
        "labels": {
            "train": {"target_label": "yes"},
            "test": {"target_label": "partial"},
        },
        "judge_result": {
            "train": {
                "calitree": {
                    "label": "yes", "consensus_support": 2,
                    "selective_accepted": True,
                }
            },
            "test": {
                "calitree": {
                    "label": "no", "consensus_support": 3,
                    "selective_accepted": False,
                }
            },
        },
    }))
    report = result.outputs["metrics_report"]
    assert report["overall"]["accuracy"] == 0.5
    assert report["train"]["accuracy"] == 1
    assert report["test"]["confusion"]["partial"]["no"] == 1
    assert report["overall"]["per_editor"]["SDEdit"]["n"] == 2
    assert report["selective"]["overall"]["coverage"] == 0.5
    assert report["selective"]["overall"]["n_accepted"] == 1
    assert report["selective"]["overall"]["accepted"]["accuracy"] == 1
    assert report["selective"]["overall"]["confidence_signal"] == (
        "persisted_training_selective_policy"
    )
    assert report["selective"]["test"]["n_abstained"] == 1


def test_eval_separates_unanimous_and_disputed_human_labels(make_ctx):
    samples = {
        "unanimous": _sample("unanimous", "test"),
        "disputed": _sample("disputed", "test"),
    }
    result = CaliTreeEvalNodeExecutor().run(make_ctx(inputs={
        "samples": samples,
        "labels": {
            "unanimous": {
                "target_label": "no",
                "ratings": [{"sc": 0}, {"sc": 0}, {"sc": 0}],
            },
            "disputed": {
                "target_label": "partial",
                "ratings": [{"sc": 0}, {"sc": 0.5}, {"sc": 0.5}],
            },
        },
        "judge_result": {
            "unanimous": {"calitree": {"label": "no"}},
            "disputed": {"calitree": {"label": "no"}},
        },
    }))

    agreement = result.outputs["metrics_report"]["test"]["human_agreement"]
    assert agreement["unanimous"]["accuracy"] == 1
    assert agreement["disputed"]["accuracy"] == 0
    interval = result.outputs["metrics_report"]["test"]["grouped_bootstrap_95_ci"]
    assert interval["unit"] == "task_uid"
    assert interval["repeats"] == 1000
    assert len(interval["accuracy"]) == 2
