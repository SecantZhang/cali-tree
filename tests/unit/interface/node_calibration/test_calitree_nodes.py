import json
import threading
import time
from types import SimpleNamespace

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
    _parse_judgment,
    _prompt,
    _select_consensus_calibrator,
    _semantic_edit_type,
)
from vejudge.interface.node_db.imagenhub_source_node import ImagenHubSourceNodeExecutor


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
