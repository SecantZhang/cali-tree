from vejudge.core.calibration.rubric_lite import (
    RubricLiteLearner,
    apply_ordinal_thresholds,
    apply_two_gate,
    cross_validate_ordinal_thresholds,
    cross_validate_two_gate,
    fit_ordinal_thresholds,
    fit_two_gate_thresholds,
    ordinal_label,
    select_boundary_cases,
    two_gate_label,
)


def _scored(change_evidence, specification_fidelity, source_preservation=100):
    """A judge row carrying the two evidence axes the two-gate reads."""
    return {
        "ordinal_scores": {
            "change_evidence": change_evidence,
            "specification_fidelity": specification_fidelity,
            "source_preservation": source_preservation,
        },
        "ordinal_score": min(change_evidence, specification_fidelity, source_preservation),
        "label": "no",
    }


def test_two_gate_label_truth_table():
    # No requested change present -> no, regardless of completeness.
    assert two_gate_label(10, 100, presence_cut=50, completeness_cut=90) == "no"
    # Present and complete -> yes.
    assert two_gate_label(80, 95, presence_cut=50, completeness_cut=90) == "yes"
    # Present but not complete -> partial (the boundary min() hides).
    assert two_gate_label(80, 60, presence_cut=50, completeness_cut=90) == "partial"


def test_two_gate_recovers_partial_that_min_scalar_collapses():
    # A partial case with high change_evidence but low specification_fidelity has the SAME
    # min-score (30) as a `no` case with low change_evidence — the collision the audit found.
    samples = {i: _sample(i, i) for i in ("p", "n", "y")}
    results = {
        "p": _scored(90, 30),  # present, incomplete -> partial ; min=30
        "n": _scored(30, 95),  # absent            -> no      ; min=30 (same scalar!)
        "y": _scored(95, 95),  # present, complete -> yes
    }
    targets = {"p": "partial", "n": "no", "y": "yes"}
    fit = fit_two_gate_thresholds(
        results=results, targets=targets, samples=samples,
        ids=list(samples), minimum_class_recall=0.0, selection_objective="macro_f1",
    )
    calibrated = apply_two_gate(results, fit["thresholds"])
    preds = {i: calibrated[i]["label"] for i in samples}
    # Two independent cutpoints separate all three where a single min-scalar cannot.
    assert preds == {"p": "partial", "n": "no", "y": "yes"}
    assert set(fit["thresholds"]) == {"presence_cut", "completeness_cut"}
    assert fit["selection_objective"] == "macro_f1"


def test_two_gate_apply_preserves_uncalibrated_label():
    results = {"p": _scored(90, 30)}
    calibrated = apply_two_gate(results, {"presence_cut": 50, "completeness_cut": 90})
    assert calibrated["p"]["label"] == "partial"
    assert calibrated["p"]["uncalibrated_label"] == "no"
    assert calibrated["p"]["threshold_calibrated"] is True


def test_two_gate_cross_validation_is_deterministic():
    samples = {f"t{i}::e": _sample(f"t{i}::e", f"t{i}") for i in range(6)}
    results, targets = {}, {}
    for i in range(6):
        item = f"t{i}::e"
        if i % 3 == 0:
            results[item], targets[item] = _scored(20, 95), "no"
        elif i % 3 == 1:
            results[item], targets[item] = _scored(90, 30), "partial"
        else:
            results[item], targets[item] = _scored(95, 95), "yes"
    first = cross_validate_two_gate(
        results=results, targets=targets, samples=samples, ids=list(samples),
        folds=3, seed=44, minimum_class_recall=0.0,
    )
    second = cross_validate_two_gate(
        results=results, targets=targets, samples=samples, ids=list(samples),
        folds=3, seed=44, minimum_class_recall=0.0,
    )
    assert first["metrics"] == second["metrics"]
    assert first["folds"] >= 2


def _sample(item_id, task=None):
    return {
        "item_id": item_id,
        "task_uid": task or item_id,
        "editor": "editor",
        "input": {"instruction": f"edit {item_id}"},
    }


def test_boundary_selection_balances_partial_errors_and_task_diversity():
    ids = ["a::e1", "a::e2", "b::e1", "c::e1", "d::e1"]
    samples = {
        item_id: _sample(item_id, item_id.split("::")[0])
        for item_id in ids
    }
    targets = {
        "a::e1": "partial",
        "a::e2": "partial",
        "b::e1": "no",
        "c::e1": "partial",
        "d::e1": "yes",
    }
    results = {
        "a::e1": {"label": "no"},
        "a::e2": {"label": "yes"},
        "b::e1": {"label": "partial"},
        "c::e1": {"label": "partial"},
        "d::e1": {"label": "yes"},
    }

    selected = select_boundary_cases(
        ids=ids,
        samples=samples,
        targets=targets,
        results=results,
        per_bucket=1,
    )

    assert "a::e1" in selected
    assert "a::e2" not in selected
    assert "b::e1" in selected
    assert "c::e1" in selected
    assert "d::e1" in selected


def test_rubric_lite_selects_partial_improvement_within_accuracy_guard():
    ids = ["fit-no", "fit-partial", "v-no", "v-partial", "v-yes"]
    samples = {item_id: _sample(item_id) for item_id in ids}
    targets = {
        "fit-no": "no",
        "fit-partial": "partial",
        "v-no": "no",
        "v-partial": "partial",
        "v-yes": "yes",
    }

    def judge_many(prompt, selected):
        initial = {
            "fit-no": "no", "fit-partial": "no",
            "v-no": "no", "v-partial": "no", "v-yes": "yes",
        }
        improved = {
            "fit-no": "no", "fit-partial": "partial",
            "v-no": "no", "v-partial": "partial", "v-yes": "yes",
        }
        labels = improved if prompt == "learned" else initial
        return {
            item_id: {"label": labels[item_id], "rationale": "evidence"}
            for item_id in selected
        }

    result = RubricLiteLearner(
        judge_many=judge_many,
        optimize=lambda _prompt, _feedback: "learned",
        format_feedback=lambda ids, *_args: "\n".join(ids),
        max_steps=1,
    ).fit(
        initial_prompt="initial",
        samples=samples,
        targets=targets,
        fit_ids=["fit-no", "fit-partial"],
        validation_ids=["v-no", "v-partial", "v-yes"],
    )

    assert result.prompt == "learned"
    assert result.report["selection"]["selected_validation_partial_f1"] == 1
    tree = result.prompt_tree()
    assert tree["architecture"] == "rubric_lite"
    assert tree["roots"] == ["rubric:global"]
    assert tree["stats"]["leaves"] == 0
    assert tree["nodes"]["rubric:global"]["children"] == []


def test_rubric_lite_rejects_partial_gain_that_breaks_accuracy_guard():
    ids = ["fit", "v-no-1", "v-no-2", "v-partial"]
    samples = {item_id: _sample(item_id) for item_id in ids}
    targets = {
        "fit": "partial",
        "v-no-1": "no",
        "v-no-2": "no",
        "v-partial": "partial",
    }

    def judge_many(prompt, selected):
        if prompt == "overpartial":
            labels = {item_id: "partial" for item_id in selected}
        else:
            labels = {
                item_id: ("no" if item_id != "fit" else "no")
                for item_id in selected
            }
        return {
            item_id: {"label": labels[item_id], "rationale": "evidence"}
            for item_id in selected
        }

    result = RubricLiteLearner(
        judge_many=judge_many,
        optimize=lambda _prompt, _feedback: "overpartial",
        format_feedback=lambda *_args: "feedback",
        max_steps=1,
        max_validation_accuracy_drop=0.01,
    ).fit(
        initial_prompt="initial",
        samples=samples,
        targets=targets,
        fit_ids=["fit"],
        validation_ids=["v-no-1", "v-no-2", "v-partial"],
    )

    assert result.prompt == "initial"
    assert result.report["selection"]["selected_step"] == 0


def test_global_ordinal_cutpoints_fit_ordered_classes_without_metadata():
    ids = [
        "no-0", "no-1", "no-2",
        "partial-0", "partial-1",
        "yes-0", "yes-1",
    ]
    scores = [0, 10, 20, 50, 60, 95, 100]
    targets = {
        item_id: item_id.split("-", 1)[0]
        for item_id in ids
    }
    samples = {
        item_id: {
            **_sample(item_id),
            "editor": f"ignored-editor-{index}",
        }
        for index, item_id in enumerate(ids)
    }
    results = {
        item_id: {"label": "no", "ordinal_score": score}
        for item_id, score in zip(ids, scores)
    }

    fitted = fit_ordinal_thresholds(
        results=results,
        targets=targets,
        samples=samples,
        ids=ids,
        accuracy_tolerance=0,
    )
    calibrated = apply_ordinal_thresholds(
        results, fitted["thresholds"]
    )

    assert fitted["version"] == "global-ordinal-cutpoints-v1"
    assert fitted["metrics"]["accuracy"] == 1
    assert fitted["metrics"]["per_label_f1"]["partial"] == 1
    assert fitted["thresholds"]["no_partial"] < fitted["thresholds"]["partial_yes"]
    assert {
        item_id: calibrated[item_id]["label"] for item_id in ids
    } == targets
    assert calibrated["yes-0"]["uncalibrated_label"] == "no"
    assert calibrated["yes-0"]["threshold_calibrated"] is True


def test_ordinal_threshold_selection_respects_accuracy_tolerance():
    ids = [f"case-{index}" for index in range(8)]
    samples = {item_id: _sample(item_id) for item_id in ids}
    targets = {
        **{item_id: "no" for item_id in ids[:6]},
        ids[6]: "partial",
        ids[7]: "yes",
    }
    results = {
        item_id: {"label": "no", "ordinal_score": score}
        for item_id, score in zip(ids, [0, 5, 10, 15, 20, 90, 90, 100])
    }

    fitted = fit_ordinal_thresholds(
        results=results,
        targets=targets,
        samples=samples,
        ids=ids,
        accuracy_tolerance=0.05,
    )

    assert (
        fitted["metrics"]["accuracy"] + 0.05 + 1e-12
        >= fitted["max_accuracy"]
    )
    assert fitted["class_preserving_candidate_count"] > 0
    assert all(
        (recall or 0) >= 0.1
        for recall in fitted["metrics"]["per_label_accuracy"].values()
    )
    assert ordinal_label(0, fitted["thresholds"]) in {
        "no", "partial", "yes"
    }


def test_macro_f1_threshold_objective_prefers_partial_recovery():
    ids = [f"case-{index}" for index in range(12)]
    samples = {item_id: _sample(item_id) for item_id in ids}
    targets = {
        **{item_id: "no" for item_id in ids[:3]},
        **{item_id: "partial" for item_id in ids[3:6]},
        **{item_id: "yes" for item_id in ids[6:]},
    }
    results = {
        item_id: {"label": "yes", "ordinal_score": score}
        for item_id, score in zip(
            ids,
            [0, 0, 25, 25, 50, 50, 75, 75, 100, 100, 100, 100],
        )
    }

    fitted = fit_ordinal_thresholds(
        results=results,
        targets=targets,
        samples=samples,
        ids=ids,
        minimum_class_recall=0.1,
        selection_objective="macro_f1",
    )

    assert fitted["selection_objective"] == "macro_f1"
    assert fitted["thresholds"] == {
        "no_partial": 0.000001,
        "partial_yes": 50.000001,
    }
    assert fitted["metrics"]["per_label_accuracy"]["partial"] > 0


def test_ordinal_cross_validation_holds_out_every_labelled_item():
    ids = [
        f"{label}-{index}"
        for label in ("no", "partial", "yes")
        for index in range(5)
    ]
    samples = {item_id: _sample(item_id) for item_id in ids}
    targets = {
        item_id: item_id.split("-", 1)[0]
        for item_id in ids
    }
    scores = {
        "no": [0, 0, 10, 20, 20],
        "partial": [40, 40, 50, 60, 60],
        "yes": [90, 90, 95, 100, 100],
    }
    results = {
        item_id: {
            "label": "partial",
            "ordinal_score": scores[targets[item_id]][
                int(item_id.rsplit("-", 1)[1])
            ],
        }
        for item_id in ids
    }

    report = cross_validate_ordinal_thresholds(
        results=results,
        targets=targets,
        samples=samples,
        ids=ids,
        folds=5,
        seed=44,
    )

    assert report["n"] == 15
    assert report["folds"] == 5
    assert sum(
        row["n_validation"] for row in report["fold_reports"]
    ) == 15
    assert all(
        row["n_fit"] == 12 for row in report["fold_reports"]
    )
    assert report["metrics"]["accuracy"] == 1


def test_grouped_ordinal_cross_validation_never_splits_a_task():
    ids = [
        f"task-{task_index}::{editor}"
        for task_index in range(6)
        for editor in ("a", "b")
    ]
    samples = {
        item_id: _sample(item_id, item_id.split("::", 1)[0])
        for item_id in ids
    }
    label_by_task = {
        0: "no", 1: "no",
        2: "partial", 3: "partial",
        4: "yes", 5: "yes",
    }
    score_by_label = {"no": 10, "partial": 50, "yes": 90}
    targets = {
        item_id: label_by_task[
            int(item_id.split("::", 1)[0].split("-")[1])
        ]
        for item_id in ids
    }
    results = {
        item_id: {"ordinal_score": score_by_label[targets[item_id]]}
        for item_id in ids
    }

    report = cross_validate_ordinal_thresholds(
        results=results,
        targets=targets,
        samples=samples,
        ids=ids,
        folds=3,
        seed=44,
        group_by_task=True,
    )

    validation_tasks = [
        task_uid
        for fold in report["fold_reports"]
        for task_uid in fold["validation_task_uids"]
    ]
    assert report["group_by_task"] is True
    assert sorted(validation_tasks) == [
        f"task-{index}" for index in range(6)
    ]
    assert all(
        fold["n_validation"] > 0
        for fold in report["fold_reports"]
    )
    assert all(
        fold["n_validation"] % 2 == 0
        for fold in report["fold_reports"]
    )
