"""Instruction -> atomic checks -> fixture-specific deterministic decision."""

import json
from dataclasses import asdict

import pytest

from .hard_cases import HARD_ORIGINAL, HARD_SAMPLES, HARD_TARGETS, HARD_VALIDATION_SAMPLES, HARD_VALIDATION_TARGETS
from .test_harder_examples import mismatches
from .two_way import (
    CHECK_CONDITION, DECOMPOSE_INSTRUCTION, TwoWayExperiment, aggregate,
    instruction_text, parse_plan, reference_plan, reference_guards,
)


@pytest.mark.parametrize("edits,guards,expected", [
    (["satisfied"] * 3, ["satisfied"] * 3, "yes"),
    (["violated", "violated", "satisfied"], ["satisfied"] * 3, "partial"),
    (["unknown"] * 3, ["satisfied"] * 3, "no"),
    (["satisfied"] * 3, ["satisfied", "violated"], "no"),
    (["satisfied"] * 3, ["satisfied", "unknown"], "partial"),
    ([], ["satisfied"] * 3, "yes"),
    ([], ["unknown"], "partial"),
])
def test_fixture_reducer(edits, guards, expected):
    assert aggregate(edits, guards) == expected


def test_instruction_scope_and_permission_binding():
    sample = HARD_SAMPLES["h20"]
    plan = reference_plan(sample["instruction"])
    assert {c.key for c in reference_guards(plan)} == {"content_recognizable", "subject_identity"}
    scoped = reference_plan(HARD_SAMPLES["h14"]["instruction"])
    assert {c.key for c in scoped.edits} == {"color", "position"}
    request = TwoWayExperiment.request(scoped.edits[0], HARD_SAMPLES["h14"]["evidence"])
    assert set(json.loads(request)) == {"condition", "observed"}
    with pytest.raises(ValueError, match="Missing evidence"):
        TwoWayExperiment.request(scoped.edits[0], {})


@pytest.mark.parametrize("change", [
    {"allow_identity_change": "false"},
    {"edits": [{"key": "quality", "operator": "equals", "expected": "high"}]},
    {"edits": [{"key": "count", "operator": "equals", "expected": True}]},
    {"edits": [{"key": "color", "operator": "one_of", "expected": ["green", "blue", "red"]}]},
])
def test_invalid_instruction_plan_fails_closed(change):
    value = {"edits": [], "allow_identity_change": False, "allow_background_change": False, **change}
    with pytest.raises(ValueError):
        parse_plan(value)


def expected_atomic_status(request):
    """Independent exact predicates for this structured-evidence experiment."""
    data = json.loads(request)
    observed, condition = data["observed"], data["condition"]
    if observed is None or observed == "unknown":
        return "unknown"
    expected = condition["expected"]
    if condition["operator"] == "equals":
        satisfied = observed == expected
    elif condition["operator"] == "at_least":
        satisfied = observed >= expected
    else:
        satisfied = observed in expected
    return "satisfied" if satisfied else "violated"


def test_two_way_instruction_decomposition_and_individual_checks(hard_experiment):
    experiment = hard_experiment
    samples = {**HARD_SAMPLES, **HARD_VALIDATION_SAMPLES}
    targets = {**HARD_TARGETS, **HARD_VALIDATION_TARGETS}
    instructions = {key: instruction_text(sample["instruction"]) for key, sample in samples.items()}
    prototype = TwoWayExperiment(experiment)
    references = {key: reference_plan(sample["instruction"]) for key, sample in samples.items()}
    extracted = {key: prototype.decompose(text) for key, text in instructions.items()}
    # The original arm retains the preceding experiment's structured input.
    # The two-way arm separately parses natural language without seeing evidence.
    original = experiment.judge_many(HARD_ORIGINAL, samples)
    reference_predictions, reference_traces = prototype.evaluate_many(references, samples)
    extracted_predictions, extracted_traces = prototype.evaluate_many(extracted, samples)
    plan_errors = {
        key: {"instruction": instructions[key], "expected": asdict(references[key]), "actual": asdict(extracted[key])}
        for key in samples if references[key] != extracted[key]
    }
    atomic_errors = {
        request: {"expected": expected_atomic_status(request), "actual": result}
        for request, result in prototype.checks.items()
        if expected_atomic_status(request) != result["status"]
    }
    errors = {"original": mismatches(original, targets),
              "reference_plan": mismatches(reference_predictions, targets),
              "model_plan": mismatches(extracted_predictions, targets)}
    experiment.report(
        "two_way_decomposition", prompts={"Original rubric": HARD_ORIGINAL,
                                           "Instruction decomposition": DECOMPOSE_INSTRUCTION,
                                           "Individual condition checker": CHECK_CONDITION},
        samples=samples, targets=targets,
        comparisons={"Original": original, "Reference plan": reference_predictions,
                     "Model plan": extracted_predictions},
        instructions=instructions, plan_mismatches=plan_errors, atomic_mismatches=atomic_errors,
        mismatches=errors, reference_traces=reference_traces, extracted_traces=extracted_traces,
        unique_instructions=len(prototype.plans), unique_atomic_checks=len(prototype.checks),
        scores={arm: len(targets) - len(wrong) for arm, wrong in errors.items()},
        limitation="Test-only hand-specified harder-rubric reducer; no automatic learned-rubric compilation, merge, images, or production integration.",
    )
    # Baseline mistakes remain visible but do not prevent testing the prototype.
    assert not plan_errors, f"Instruction decomposition errors: {plan_errors}"
    assert not atomic_errors, f"Individual condition errors: {atomic_errors}"
    assert not errors["reference_plan"], f"Reference-plan errors: {errors['reference_plan']}"
    assert not errors["model_plan"], f"Two-way errors: {errors['model_plan']}"
