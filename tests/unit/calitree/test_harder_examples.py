"""Real-model semantic preservation under interacting rules and exceptions."""

from dataclasses import asdict

from critical.core.optimization.prompt.calitree import (
    CallbackMergeAlgorithm, CaliTreeLeafNode, GuardedMergeAcceptance, MergeCoordinator,
)
from .hard_cases import (
    HARD_ORIGINAL, HARD_COLOR_POSITION, HARD_COUNT, HARD_SAMPLES, HARD_TARGETS,
    HARD_COLOR_POSITION_TARGETS, HARD_COUNT_TARGETS, HARD_PURPOSES,
    HARD_VALIDATION_SAMPLES, HARD_VALIDATION_TARGETS,
)


def recompose(components):
    return "\n\n".join(
        heading + ":\n" + "\n".join(components[kind])
        for kind, heading in (
            ("criteria", "Requirements"), ("priorities", "Decision priorities"),
            ("constraints", "Output constraints"),
        )
    )


def mismatches(predictions, targets):
    return {
        key: {"expected": targets[key], "actual": predictions[key]["label"],
              "rationale": predictions[key]["rationale"]}
        for key in targets if predictions[key]["label"] != targets[key]
    }


def test_harder_decomposition_preserves_priorities_and_exceptions(hard_experiment):
    experiment = hard_experiment
    components = experiment.runtime.extract(HARD_ORIGINAL)
    reconstructed = recompose(components)
    # Combine the 21 main and 8 changed-target cases to test decomposition's
    # scope as well as the original rubric. No targets or purposes reach the model.
    samples = {**HARD_SAMPLES, **HARD_VALIDATION_SAMPLES}
    targets = {**HARD_TARGETS, **HARD_VALIDATION_TARGETS}
    original = experiment.judge_many(HARD_ORIGINAL, samples)
    decomposed = experiment.judge_many(reconstructed, samples)
    errors = {
        "original": mismatches(original, targets),
        "decomposed": mismatches(decomposed, targets),
    }
    experiment.report(
        "harder_decomposition", prompts={"Original rubric": HARD_ORIGINAL,
                                         "Recomposed decision components": reconstructed},
        samples=samples, targets=targets,
        comparisons={"Original": original, "Decomposed": decomposed},
        components=components, case_purposes=HARD_PURPOSES, mismatches=errors,
    )
    assert all(components[kind] for kind in ("criteria", "priorities", "constraints"))
    assert not errors["original"], f"Baseline rubric errors: {errors['original']}"
    assert not errors["decomposed"], f"Decomposition changed decisions: {errors['decomposed']}"


def test_harder_merge_preserves_scope_vetoes_and_exceptions(hard_experiment):
    experiment = hard_experiment
    color_position = experiment.judge_many(HARD_COLOR_POSITION, HARD_SAMPLES)
    count = experiment.judge_many(HARD_COUNT, HARD_SAMPLES)
    context = experiment.context(
        HARD_ORIGINAL, HARD_SAMPLES, HARD_TARGETS,
        HARD_VALIDATION_SAMPLES, HARD_VALIDATION_TARGETS,
    )
    ids = list(HARD_SAMPLES)
    result = MergeCoordinator(CallbackMergeAlgorithm(), GuardedMergeAcceptance()).merge(
        CaliTreeLeafNode("color-position", HARD_COLOR_POSITION, ids[:9], [], {}),
        CaliTreeLeafNode("count", HARD_COUNT, ids[9:], [], {}), context,
    )
    merged_prompt = result.optimization.prompt if result.optimization else ""
    fit_predictions = result.optimization.predictions if result.optimization else {}
    validation_predictions = (
        experiment.judge_many(merged_prompt, HARD_VALIDATION_SAMPLES) if merged_prompt else {}
    )
    errors = {
        "color_position": mismatches(color_position, HARD_COLOR_POSITION_TARGETS),
        "count": mismatches(count, HARD_COUNT_TARGETS),
        "merged_fit": (mismatches(fit_predictions, HARD_TARGETS)
                       if fit_predictions else {"missing": "No refined merge proposal"}),
        "merged_validation": (mismatches(validation_predictions, HARD_VALIDATION_TARGETS)
                              if validation_predictions else {"missing": "No merge to validate"}),
    }
    experiment.report(
        "harder_merging", prompts={"Color and position rubric": HARD_COLOR_POSITION,
                                   "Count rubric": HARD_COUNT, "Merged rubric": merged_prompt},
        samples=HARD_SAMPLES, targets=HARD_TARGETS,
        comparisons={"Color/position": color_position, "Count": count,
                     **({"Merged": fit_predictions} if fit_predictions else {})},
        case_purposes=HARD_PURPOSES, merge_result=asdict(result), mismatches=errors,
    )
    if validation_predictions:
        experiment.report(
            "harder_merge_validation", prompts={"Merged rubric": merged_prompt},
            samples=HARD_VALIDATION_SAMPLES, targets=HARD_VALIDATION_TARGETS,
            comparisons={"Merged": validation_predictions}, mismatches=errors["merged_validation"],
        )
    assert not errors["color_position"], f"Color/position source errors: {errors['color_position']}"
    assert not errors["count"], f"Count source errors: {errors['count']}"
    assert result.decision.accepted, f"Merge rejected: {asdict(result.decision)}"
    assert not errors["merged_fit"], f"Merged rubric errors: {errors['merged_fit']}"
    assert not errors["merged_validation"], f"Merged held-out errors: {errors['merged_validation']}"
    assert result.optimization.steps == 0
    assert result.decision.generalization_accuracy == 1.0
