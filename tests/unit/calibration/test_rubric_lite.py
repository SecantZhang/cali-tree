from vejudge.core.calibration.rubric_lite import (
    RubricLiteLearner,
    apply_ordinal_thresholds,
    fit_ordinal_thresholds,
    ordinal_label,
    select_boundary_cases,
)


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
