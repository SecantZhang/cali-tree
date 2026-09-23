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
    _evidence_referral,
    _evidence_signals,
    _failure_mode_groups,
    _failure_mode_signature,
    _fit_evidence_referral_policy,
    _human_agreement_bucket,
    _human_label_reliability,
    _is_referred,
    _parse_judgment,
    _prompt,
    _referral_quality_metrics,
    _fit_residual_context_partition,
    _fit_pareto_prompt_cascade,
    _residual_context_keys,
    _route_metrics,
    _select_consensus_calibrator,
    _semantic_edit_type,
    _tree_metrics,
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
    assert tree["selective_policy"] == {}
    assert "change_evidence" in tree["nodes"]["rubric:global"]["prompt"]
    assert result.meta["model_calls"] == 0


def test_frozen_rubric_lite_scopes_external_selective_policy(
    make_ctx,
):
    result = RubricLiteFrozenNodeExecutor().run(make_ctx(
        params={
            "model_version":
                "rubric_lite_v4_editinspector_selective_v1"
        },
        inputs={},
    ))

    assert result.status == "done"
    tree = result.outputs["prompt_tree"]
    assert tree["selective_policy"]["minimum_ordinal_score"] == 100
    assert tree["selective_policy"]["allowed_labels"] == ["yes"]
    assert tree["training_provenance"]["scope"] == (
        "EditInspector selective deployment only"
    )


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


def test_referral_quality_separates_consensus_from_model_error():
    # Four cases: two referred, two accepted; disputed/unanimous mix.
    targets = {"d1": "partial", "d2": "no", "u1": "yes", "u2": "no"}
    predictions = {"d1": "no", "d2": "no", "u1": "yes", "u2": "yes"}
    samples = {
        "d1": _sample("d1"),
        "d2": _sample("d2"),
        "u1": _sample("u1"),
        "u2": _sample("u2"),
    }
    labels = {
        # d1 disputed + referred + model-wrong; d2 disputed + accepted + correct.
        "d1": {"ratings": [{"sc": 0}, {"sc": 0.5}, {"sc": 1}]},
        "d2": {"ratings": [{"sc": 0}, {"sc": 0.5}, {"sc": 0}]},
        # u1 unanimous + accepted + correct; u2 unanimous + referred + model-wrong.
        "u1": {"ratings": [{"sc": 1}, {"sc": 1}, {"sc": 1}]},
        "u2": {"ratings": [{"sc": 0}, {"sc": 0}, {"sc": 0}]},
    }
    rows = {
        "d1": {"needs_human": True},
        "d2": {"needs_human": False},
        "u1": {"needs_human": False},
        "u2": {"needs_human": True},
    }

    report = _referral_quality_metrics(targets, predictions, samples, labels, rows)

    assert report["n"] == 4
    assert report["n_referred"] == 2
    assert report["review_rate"] == 0.5
    assert report["n_disputed"] == 2
    # Referred: {d1 disputed, u2 unanimous} -> precision 1/2.
    assert report["consensus_referral_precision"] == 0.5
    # Disputed: {d1, d2}; only d1 referred -> recall 1/2.
    assert report["consensus_referral_recall"] == 0.5
    assert report["consensus_referral_f1"] == pytest.approx(0.5)
    # Model errors: {d1, u2}; both referred -> full capture.
    assert report["error_capture_recall"] == 1.0
    assert report["error_prevalence_in_referrals"] == 1.0
    # One true partial (d1), referred.
    assert report["fraction_true_partial_referred"] == 1.0
    assert "by_editor" in report and "by_operation_family" in report


def test_is_referred_reads_flag_then_decision_label():
    assert _is_referred({"needs_human": True}) is True
    assert _is_referred({"needs_human": False}) is False
    assert _is_referred({"decision_label": "needs_human"}) is True
    assert _is_referred({"decision_label": "partial"}) is False
    assert _is_referred({}) is False


def test_tree_metrics_report_compression_and_root_coverage():
    tree = {
        "roots": ["root"],
        "nodes": {
            "root": {
                "status": "global",
                "level": 2,
                "covered_ids": ["a", "b", "c"],
                "validation_accuracy": 0.8,
                "children": ["leaf_a", "leaf_b"],
            },
            "leaf_a": {
                "status": "leaf",
                "level": 0,
                "covered_ids": ["a"],
                "validation_accuracy": 1.0,
                "children": [],
            },
            "leaf_b": {
                "status": "leaf",
                "level": 0,
                "covered_ids": ["b"],
                "validation_accuracy": 1.0,
                "children": [],
            },
        },
        "timeline": [
            {"kind": "accepted", "node_id": "root"},
            {"kind": "branch", "node_id": "x"},
        ],
        "stats": {
            "leaves": 2,
            "leaf_cases": 3,
            "accepted_merges": 1,
            "rejected_merges": 0,
            "promoted": 0,
            "specialized_roots": 1,
            "merge_attempts": 2,
            "merge_budget_exhausted": False,
        },
        "usage": {"judge_calls": 10},
    }

    report = _tree_metrics(tree)

    assert report["n_leaves"] == 2
    assert report["n_final_nodes"] == 3
    assert report["compression_ratio"] == pytest.approx(2 / 3)
    assert report["n_full_merges"] == 1
    assert report["n_branch_merges"] == 1
    assert report["root_coverage"] == 1.0
    assert report["root_accuracy"] == 0.8
    # Mean child accuracy 1.0 minus parent 0.8 -> 0.2 accuracy loss.
    assert report["accuracy_loss_child_to_parent"] == pytest.approx(0.2)
    assert report["by_depth"]["0"]["n_nodes"] == 2
    assert report["token_usage"] == {"judge_calls": 10}


def test_route_metrics_report_depth_and_fallback():
    rows = {
        "deep": {"calitree": {"route_path": ["root", "mid", "leaf"], "routed_node": "leaf"}},
        "shallow": {"calitree": {"route_path": ["root"], "routed_node": "root"}},
    }
    report = _route_metrics(rows)
    assert report["n_routed"] == 2
    assert report["mean_route_depth"] == pytest.approx(1.0)
    assert report["fallback_to_root_rate"] == 0.5


def test_failure_mode_grouping_is_deterministic_and_signature_based():
    samples = {
        "a": _sample("a"),  # instruction "make it blue" -> family "color"
        "b": _sample("b"),
        "c": _sample("c"),
    }
    base_results = {
        "a": {"label": "no"},
        "b": {"label": "no"},
        "c": {"label": "yes"},
    }
    targets = {"a": "partial", "b": "partial", "c": "partial"}
    groups = _failure_mode_groups(base_results, samples, targets, ["a", "b", "c"])
    # a and b share the same (base=no -> target=partial) failure mode; c differs.
    assert groups["a"] == groups["b"]
    assert groups["a"] != groups["c"]
    assert groups["a"].endswith("no->partial")
    # Deterministic re-run.
    assert _failure_mode_groups(base_results, samples, targets, ["a", "b", "c"]) == groups
    # An invalid base label is bucketed, not crashed on.
    assert _failure_mode_signature("garbage", "no", "color").endswith("invalid->no")


def test_residual_context_partition_backs_off_by_support_without_targets():
    samples = {
        "a1": {**_sample("a1"), "editor": "EditorA"},
        "a2": {**_sample("a2"), "editor": "EditorA"},
        "b1": {
            **_sample("b1"),
            "editor": "EditorB",
            "input": {**_sample("b1")["input"], "instruction": "remove the cup"},
        },
        "b2": {
            **_sample("b2"),
            "editor": "EditorB",
            "input": {**_sample("b2")["input"], "instruction": "remove the cup"},
        },
        "c1": {
            **_sample("c1"),
            "editor": "EditorC",
            "input": {**_sample("c1")["input"], "instruction": "move it left"},
        },
        "va": {**_sample("va"), "editor": "EditorA"},
        "vb": {
            **_sample("vb"),
            "editor": "EditorB",
            "input": {**_sample("vb")["input"], "instruction": "remove the cup"},
        },
        "vc": {
            **_sample("vc"),
            "editor": "EditorC",
            "input": {**_sample("vc")["input"], "instruction": "move it left"},
        },
    }
    fit_ids = ["a1", "a2", "b1", "b2", "c1"]
    validation_ids = ["va", "vb", "vc"]
    fit_base = {item_id: {"label": "no"} for item_id in fit_ids}
    validation_base = {item_id: {"label": "no"} for item_id in validation_ids}

    fit, validation, policy = _fit_residual_context_partition(
        fit_base_results=fit_base,
        validation_base_results=validation_base,
        samples=samples,
        fit_ids=fit_ids,
        validation_ids=validation_ids,
        min_fit_support=2,
        min_validation_support=1,
    )

    assert fit["a1"] == fit["a2"]
    assert fit["a1"].startswith("editor_operation_prediction:")
    assert fit["b1"] == fit["b2"]
    assert fit["b1"].startswith("editor_operation_prediction:")
    assert fit["c1"].startswith("prediction:")
    assert validation["va"] == fit["a1"]
    assert validation["vb"] == fit["b1"]
    assert validation["vc"] == fit["c1"]
    assert policy["target_blind"] is True
    assert policy["fit_support"][fit["c1"]] == 1


def test_residual_context_keys_are_ordered_specific_to_prediction_backoff():
    keys = _residual_context_keys(_sample("case"), "partial")
    assert [key.split(":", 1)[0] for key in keys] == [
        "editor_operation_prediction",
        "editor_prediction",
        "operation_prediction",
        "prediction",
    ]
    assert all("partial" in key for key in keys)


def test_pareto_prompt_cascade_accepts_only_non_regressing_correction():
    ids = ["fix", "same1", "same2", "same3", "regress", "validation"]
    samples = {item_id: _sample(item_id) for item_id in ids}
    initial = {
        "fix": {"label": "yes"},
        "same1": {"label": "yes"},
        "same2": {"label": "yes"},
        "same3": {"label": "yes"},
        "regress": {"label": "no"},
        "validation": {"label": "no"},
    }
    optimized = {
        "fix": {"label": "partial"},
        "same1": {"label": "yes"},
        "same2": {"label": "yes"},
        "same3": {"label": "yes"},
        "regress": {"label": "partial"},
        "validation": {"label": "no"},
    }
    targets = {
        "fix": "partial",
        "same1": "yes",
        "same2": "yes",
        "same3": "yes",
        "regress": "no",
        "validation": "no",
    }

    policy = _fit_pareto_prompt_cascade(
        initial_results=initial,
        optimized_results=optimized,
        samples=samples,
        targets=targets,
        fit_ids=["fix", "same1", "same2", "same3", "regress"],
        validation_ids=["validation"],
        min_fit_support=4,
    )

    yes_key = _residual_context_keys(samples["fix"], "yes")[-1]
    no_key = _residual_context_keys(samples["regress"], "no")[-1]
    assert list(policy["rules"]) == [yes_key]
    assert policy["rules"][yes_key]["fit_improvements"] == 1
    assert policy["rules"][yes_key]["fit_regressions"] == 0
    assert policy["rules"][yes_key]["validation_support"] == 0
    assert no_key not in policy["rules"]


def test_evidence_referral_distinguishes_partial_from_needs_human():
    node = {"routing_threshold": 0.5, "covered_ids": ["a", "b", "c"]}
    # Total three-way disagreement is indeterminate -> needs_human.
    disagreeing = _evidence_signals(
        {"consensus_tie": True}, node, 0.9, min_route_support=2
    )
    refer, reason = _evidence_referral(disagreeing, {"rule": "disagreement"})
    assert refer is True
    assert "total_disagreement" in reason
    # A confident consensus (no tie, strong route) is kept, even when it is partial.
    agreeing = _evidence_signals(
        {"consensus_tie": False}, node, 0.9, min_route_support=2
    )
    refer, reason = _evidence_referral(agreeing, {"rule": "disagreement"})
    assert refer is False
    assert reason == "evidence_accepted"


def test_evidence_referral_routing_rule_fires_on_weak_route():
    node = {"routing_threshold": 0.8, "covered_ids": ["only"]}
    signals = _evidence_signals(
        {"consensus_tie": False}, node, 0.6, min_route_support=2
    )
    # Below-threshold similarity and unsupported one-case leaf both fire.
    assert signals["low_route_similarity"] is True
    assert signals["unsupported_route"] is True
    assert _evidence_referral(signals, {"rule": "routing"})[0] is True
    # The disagreement-only rule ignores routing weakness.
    assert _evidence_referral(signals, {"rule": "disagreement"})[0] is False


def test_fit_evidence_referral_policy_uses_only_training_labels():
    tree = {"nodes": {"root": {"routing_threshold": 0.5, "covered_ids": ["a", "b", "c"]}}}
    tree_results = {
        "t_disp": {
            "label": "no", "consensus_tie": True,
            "routed_node": "root", "route_similarity": 0.9,
        },
        "t_unan": {
            "label": "yes", "consensus_tie": False,
            "routed_node": "root", "route_similarity": 0.9,
        },
        # A disputed test case that must not influence the fitted policy.
        "x_test": {
            "label": "no", "consensus_tie": True,
            "routed_node": "root", "route_similarity": 0.9,
        },
    }
    labels = {
        "t_disp": {"ratings": [{"sc": 0}, {"sc": 0.5}, {"sc": 1}]},
        "t_unan": {"ratings": [{"sc": 1}, {"sc": 1}, {"sc": 1}]},
        "x_test": {"ratings": [{"sc": 0}, {"sc": 0.5}, {"sc": 1}]},
    }
    targets = {"t_disp": "no", "t_unan": "yes", "x_test": "no"}

    policy = _fit_evidence_referral_policy(
        tree_results,
        tree,
        targets,
        labels,
        ["t_disp", "t_unan"],
        coverage_floor=0.0,
    )

    assert policy["version"] == "evidence-referral-v1"
    assert policy["rule"] == "disagreement"
    # Only the one disputed training case is referred; the test-set disputed case is
    # excluded, so recall is 1/1 rather than 1/2.
    assert policy["train_metrics"]["referral_recall"] == 1.0
    assert policy["train_metrics"]["referral_precision"] == 1.0
    assert policy["train_metrics"]["coverage"] == 0.5


def test_calitree_evidence_policy_requires_a_persisted_policy_before_calls(
    make_ctx, monkeypatch
):
    tree = {
        "architecture": "rubric_lite",
        "roots": ["rubric:global"],
        "nodes": {
            "rubric:global": {
                "id": "rubric:global", "prompt": "rubric",
                "embedding": [], "children": [],
            },
        },
    }
    engine_calls = 0

    def engine_from(_config, _ctx):
        nonlocal engine_calls
        engine_calls += 1
        return object()

    monkeypatch.setattr(
        "vejudge.interface.node_calibration.calitree_nodes._engine_from",
        engine_from,
    )
    result = CaliTreeJudgeNodeExecutor().run(make_ctx(
        dry_run=False,
        allow_live=True,
        params={"human_review_mode": "evidence_policy"},
        inputs={
            "samples": {"case": _sample("case")},
            "prompt_tree": tree,
            "judge_engine": {"model": "judge"},
        },
    ))

    assert result.status == "error"
    assert "persisted evidence_referral_policy" in str(result.error)
    assert engine_calls == 0


def test_calitree_evidence_policy_refers_only_indeterminate_cases(
    make_ctx, monkeypatch
):
    tree = {
        "architecture": "rubric_lite",
        "roots": ["rubric:global"],
        "nodes": {
            "rubric:global": {
                "id": "rubric:global", "prompt": "rubric",
                "embedding": [], "children": [],
                "routing_threshold": 0.0, "covered_ids": ["a", "b"],
            },
        },
        "evidence_referral_policy": {
            "version": "evidence-referral-v1",
            "rule": "disagreement",
            "min_route_support": 1,
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
            "indeterminate": {
                "label": "partial", "consensus_tie": True,
                "rationale": "split", "valid": True,
            },
            "confident": {
                "label": "partial", "consensus_tie": False,
                "rationale": "clear partial", "valid": True,
            },
        },
    )

    result = CaliTreeJudgeNodeExecutor().run(make_ctx(
        dry_run=False,
        allow_live=True,
        params={"human_review_mode": "evidence_policy"},
        inputs={
            "samples": {
                "indeterminate": _sample("indeterminate"),
                "confident": _sample("confident"),
            },
            "prompt_tree": tree,
            "judge_engine": {"model": "judge"},
        },
    ))

    rows = {
        item_id: value["calitree"]
        for item_id, value in result.outputs["judge_result"].items()
    }
    # Indeterminate: underlying label preserved, but referred.
    assert rows["indeterminate"]["label"] == "partial"
    assert rows["indeterminate"]["needs_human"] is True
    assert rows["indeterminate"]["decision_label"] == "needs_human"
    assert "total_disagreement" in rows["indeterminate"]["review_reason"]
    # Confident partial stays partial, not referred.
    assert rows["confident"]["label"] == "partial"
    assert rows["confident"]["needs_human"] is False
    assert rows["confident"]["decision_label"] == "partial"
    assert rows["confident"]["evidence_referral_policy_version"] == (
        "evidence-referral-v1"
    )


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


def test_parser_recovers_an_explicit_gpt4o_prose_final_label():
    result = _parse_judgment(
        "The requested object is present but its color is wrong.\n\n"
        "**Final assessment: Partial** — the edit is incomplete."
    )

    assert result["valid"] is True
    assert result["label"] == "partial"
    assert result["parser_mode"] == "explicit_prose_final_label"


def test_parser_does_not_infer_label_from_unmarked_prose():
    result = _parse_judgment("The edit is partial in one region but yes in another.")

    assert result["valid"] is False


def test_parser_recovers_explicit_presence_phrase_from_gpt4o_prose():
    result = _parse_judgment(
        "### Final Decision:\nThe requested edit is **partly present**."
    )

    assert result["valid"] is True
    assert result["label"] == "partial"
    assert result["parser_mode"] == "explicit_prose_presence_label"


def test_parser_scene_failure_overrides_fully_present_phrase():
    result = _parse_judgment(
        "Scene Continuity:\n- Label: No\n\n"
        "### Final Decision:\nThe requested edit is **fully present**."
    )

    assert result["valid"] is True
    assert result["label"] == "no"


def test_parser_recovers_explicit_final_scorecard():
    result = _parse_judgment(
        "### Final Assessment:\n- **Requested Change**: Partial\n"
        "- **Scene Continuity**: Yes"
    )

    assert result["valid"] is True
    assert result["label"] == "partial"
    assert result["parser_mode"] == "explicit_prose_scorecard"


def test_parser_normalizes_nested_gpt4o_rubric_scores_without_top_level_label():
    result = _parse_judgment(json.dumps({"rubric_scores": {
        "requested_change": {"label": "partial", "rationale": "change incomplete"},
        "scene_continuity": {"label": "yes", "rationale": "scene preserved"},
    }}))

    assert result["valid"] is True
    assert result["label"] == "partial"
    assert result["parser_mode"] == "nested_rubric_scores"


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


def test_routed_judge_predicts_context_then_runs_supported_leaf(make_ctx, monkeypatch):
    sample = _sample("case")
    routing_key = _residual_context_keys(sample, "no")[0]
    tree = {
        "embedding_model": "embed",
        "prompt_version": "calitree_v2",
        "roots": ["root"],
        "config": {"min_routing_support": 2},
        "prediction_conditioned_router": {
            "router_prompt": "TOP",
            "routes": {routing_key: "leaf"},
        },
        "nodes": {
            "root": {
                "id": "root", "prompt": "ROOT", "embedding": [0.0, 1.0],
                "children": ["leaf"],
            },
            "leaf": {
                "id": "leaf", "prompt": "LEAF", "embedding": [1.0, 0.0],
                "children": [], "covered_ids": ["a", "b"],
                "routing_eligible": True, "routing_validation_support": 2,
            },
        },
        "prediction_cache": {},
    }
    calls = []

    monkeypatch.setattr(
        "vejudge.interface.node_calibration.calitree_nodes._engine_from",
        lambda _config, _ctx: object(),
    )
    monkeypatch.setattr(
        _CaliTreeRuntime,
        "embed",
        lambda _runtime, texts: [[1.0, 0.0] for _ in texts],
    )

    def judge_many(_runtime, prompt, prompt_samples):
        calls.append((prompt, sorted(prompt_samples)))
        label = "no" if prompt == "TOP" else "yes"
        return {
            item_id: {"label": label, "rationale": prompt, "valid": True}
            for item_id in prompt_samples
        }

    monkeypatch.setattr(_CaliTreeRuntime, "judge_many", judge_many)

    result = CaliTreeJudgeNodeExecutor().run(make_ctx(
        dry_run=False,
        allow_live=True,
        inputs={
            "samples": {"case": sample},
            "prompt_tree": tree,
            "judge_engine": {"model": "judge"},
        },
    ))

    assert result.status == "done"
    row = result.outputs["judge_result"]["case"]["calitree"]
    assert row["label"] == "yes"
    assert row["routed_node"] == "leaf"
    assert calls == [("TOP", ["case"]), ("LEAF", ["case"])]


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
        params={"human_review_mode": "selective_policy"},
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
    assert rows["perfect"]["label"] == "yes"
    assert rows["perfect"]["decision_label"] == "yes"
    assert rows["perfect"]["needs_human"] is False
    assert rows["near"]["label"] == "partial"
    assert rows["near"]["decision_label"] == "needs_human"
    assert rows["near"]["needs_human"] is True
    assert rows["near"]["review_reason"] == "selective_policy_rejected"
    assert rows["perfect"]["selective_policy_version"] == (
        "rubric-lite-perfect-evidence-v1"
    )


def test_human_review_mode_requires_a_persisted_policy_before_calls(
    make_ctx, monkeypatch
):
    tree = {
        "architecture": "rubric_lite",
        "roots": ["rubric:global"],
        "nodes": {
            "rubric:global": {
                "id": "rubric:global",
                "prompt": "rubric",
                "embedding": [],
                "children": [],
            },
        },
    }
    engine_calls = 0

    def engine_from(_config, _ctx):
        nonlocal engine_calls
        engine_calls += 1
        return object()

    monkeypatch.setattr(
        "vejudge.interface.node_calibration.calitree_nodes._engine_from",
        engine_from,
    )
    result = CaliTreeJudgeNodeExecutor().run(make_ctx(
        dry_run=False,
        allow_live=True,
        params={"human_review_mode": "selective_policy"},
        inputs={
            "samples": {"case": _sample("case")},
            "prompt_tree": tree,
            "judge_engine": {"model": "judge"},
        },
    ))

    assert result.status == "error"
    assert "persisted selective_policy" in str(result.error)
    assert engine_calls == 0


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
                    "human_review_mode": "selective_policy",
                }
            },
            "test": {
                "calitree": {
                    "label": "no", "consensus_support": 3,
                    "selective_accepted": False,
                    "human_review_mode": "selective_policy",
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
    assert report["selective"]["overall"]["n_needs_human"] == 1
    assert report["selective"]["overall"]["needs_human_outcome_enabled"] is True
    assert report["selective"]["overall"]["review_rate"] == 0.5
    assert report["selective"]["overall"]["error_capture_rate"] == 1
    assert report["selective"]["overall"]["partial_review_rate"] == 1
    assert (
        report["selective"]["overall"][
            "system_accuracy_with_perfect_human_review"
        ]
        == 1
    )
    assert report["selective"]["overall"]["decision_distribution"] == {
        "no": 0,
        "partial": 0,
        "yes": 1,
        "needs_human": 1,
    }
    assert report["selective"]["overall"]["target_coverage"]["partial"] == {
        "n": 1,
        "n_accepted": 0,
        "n_needs_human": 1,
        "coverage": 0,
    }
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
