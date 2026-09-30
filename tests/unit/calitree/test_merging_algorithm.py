"""Does actual model synthesis preserve both compatible requirements?"""

from dataclasses import asdict

from critical.core.optimization.prompt.calitree import (
    CallbackMergeAlgorithm, CaliTreeLeafNode, GuardedMergeAcceptance,
    MergeCoordinator, OptimizationResult,
)
from .cases import (
    COLOR_PROMPT, SHAPE_PROMPT, ORIGINAL_PROMPT, CONFLICT_PROMPT,
    SAMPLES, TARGETS, COLOR_TARGETS, SHAPE_TARGETS, VALIDATION_SAMPLES, VALIDATION_TARGETS,
)


def leaf(name, prompt, covered_ids):
    return CaliTreeLeafNode(name, prompt, covered_ids, [], {})


def test_merge_preserves_both_requirements(experiment):
    color = experiment.judge_many(COLOR_PROMPT, SAMPLES)
    shape = experiment.judge_many(SHAPE_PROMPT, SAMPLES)
    context = experiment.context(
        ORIGINAL_PROMPT, SAMPLES, TARGETS, VALIDATION_SAMPLES, VALIDATION_TARGETS,
    )
    result = MergeCoordinator(CallbackMergeAlgorithm(), GuardedMergeAcceptance()).merge(
        leaf("color", COLOR_PROMPT, ["c1", "c2"]),
        leaf("shape", SHAPE_PROMPT, ["c3", "c4"]), context,
    )
    merged_prompt = result.optimization.prompt if result.optimization else ""
    merged = result.optimization.predictions if result.optimization else {}
    experiment.report(
        "merging_algorithm", prompts={"Color rubric": COLOR_PROMPT, "Shape rubric": SHAPE_PROMPT,
                                      "Merged rubric": merged_prompt},
        samples=SAMPLES, targets=TARGETS,
        comparisons={"Color only": color, "Shape only": shape,
                     **({"Merged": merged} if merged else {})},
        merge_result=asdict(result),
    )
    assert experiment.labels(color) == COLOR_TARGETS
    assert experiment.labels(shape) == SHAPE_TARGETS
    assert result.decision.accepted, "Compatible merge failed synthesis or acceptance"
    assert experiment.labels(merged) == TARGETS, "Merged rubric dropped or changed a requirement"
    assert result.optimization.steps == 0, "Measure synthesis without optimizer repair"
    assert result.decision.generalization_accuracy == 1.0


def test_merge_reports_incompatible_requirements(experiment):
    context = experiment.context(ORIGINAL_PROMPT, SAMPLES, TARGETS, {}, {})
    result = MergeCoordinator(CallbackMergeAlgorithm(), GuardedMergeAcceptance()).merge(
        leaf("red", COLOR_PROMPT, ["c1"]), leaf("blue", CONFLICT_PROMPT, ["c4"]), context,
    )
    experiment.report(
        "merge_conflict", prompts={"Red requirement": COLOR_PROMPT, "Blue requirement": CONFLICT_PROMPT},
        merge_result=asdict(result),
    )
    assert not result.decision.accepted
    assert result.decision.kind == "branch"
    assert result.conflict_reason
    assert "invalid merge response" not in result.conflict_reason
    assert result.optimization is None


def test_guard_rejects_a_merge_that_drops_a_requirement(experiment):
    # Deliberately damaged candidate: it retained color but lost shape. All decisions
    # still come from the real model; this directly tests the production acceptance guard.
    fit_samples = {key: SAMPLES[key] for key in ("c1", "c4")}
    fit_targets = {key: TARGETS[key] for key in fit_samples}
    context = experiment.context(
        ORIGINAL_PROMPT, fit_samples, fit_targets, VALIDATION_SAMPLES, VALIDATION_TARGETS,
    )
    accuracy, correct, predictions = context.services.validate(
        COLOR_PROMPT, list(fit_samples), fit_samples, fit_targets,
    )
    optimization = OptimizationResult(COLOR_PROMPT, accuracy, correct, predictions, 0)
    decision = GuardedMergeAcceptance().evaluate(optimization, list(fit_samples), context)
    heldout = experiment.judge_many(COLOR_PROMPT, VALIDATION_SAMPLES)
    baseline = experiment.judge_many(ORIGINAL_PROMPT, VALIDATION_SAMPLES)
    experiment.report(
        "merge_dropped_requirement", prompts={"Complete baseline": ORIGINAL_PROMPT,
                                              "Damaged merge": COLOR_PROMPT},
        samples=VALIDATION_SAMPLES, targets=VALIDATION_TARGETS,
        comparisons={"Baseline": baseline, "Damaged merge": heldout},
        fit_accuracy=accuracy, decision=asdict(decision),
    )
    assert accuracy == 1.0, "Damaged merge should fit the two easy cases"
    assert experiment.labels(baseline) == VALIDATION_TARGETS
    assert not decision.accepted, "A fit-perfect merge must still pass the generalization guard"
    assert decision.kind == "rejected_generalization"
    assert decision.generalization_accuracy < 0.8
