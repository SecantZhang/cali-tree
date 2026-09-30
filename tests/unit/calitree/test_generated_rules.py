"""Automatically compile rubric rules, then verify execution and rubric changes."""

from copy import deepcopy
from dataclasses import asdict

import pytest

from .generated_policy import COMPILE_POLICY, parse_policy, RubricCompiler
from .hard_cases import (
    HARD_ORIGINAL, HARD_COLOR_POSITION, HARD_SAMPLES, HARD_TARGETS,
    HARD_COLOR_POSITION_TARGETS, HARD_VALIDATION_SAMPLES, HARD_VALIDATION_TARGETS,
)
from .test_harder_examples import mismatches
from .test_two_way_decomposition import expected_atomic_status
from .two_way import TwoWayExperiment, instruction_text, reference_plan

STRICT_RUBRIC = HARD_ORIGINAL.replace(
    "If at least one requested supported check is satisfied but another is failed or unknown, return partial.",
    "If any requested supported check is failed or unknown, return no, even if another check is satisfied.",
)
# Independent expected labels for the changed rule, not generated-policy outputs.
STRICT_NO_CASES = {"h02", "h09", "h10", "h15", "h18", "v02", "v06"}
SCOPED_VALIDATION_TARGETS = {
    "v01": "yes", "v02": "partial", "v03": "no", "v04": "no",
    "v05": "yes", "v06": "yes", "v07": "partial", "v08": "yes",
}


def minimal_policy():
    return {
        "supported_edits": ["color"], "guards": [],
        "rules": [{"when": {"fact": "violated_count", "operator": "gt", "value": 0},
                   "label": "no", "source": 1}],
        "default": {"label": "yes", "source": 2},
    }


def test_rule_order_labels_and_fallback_are_policy_data():
    plan = reference_plan(HARD_SAMPLES["h01"]["instruction"])
    rows = [{"condition": asdict(next(c for c in plan.edits if c.key == "color")), "status": "violated"}]
    value = minimal_policy()
    assert parse_policy(value, "failure\nsuccess").decide(rows, [], plan)[0] == "no"
    # Interpreter must obey a changed policy rather than a fixed edit reducer.
    value["rules"][0]["label"] = "partial"
    assert parse_policy(value, "failure\nsuccess").decide(rows, [], plan)[0] == "partial"
    rows[0]["status"] = "satisfied"
    assert parse_policy(value, "failure\nsuccess").decide(rows, [], plan)[0] == "yes"
    with pytest.raises(ValueError, match="exactly the applicable"):
        parse_policy(value, "failure\nsuccess").decide([], [], plan)


@pytest.mark.parametrize("change", [
    {"supported_edits": ["caption"]},
    {"guards": [{"key": "subject_identity", "expected": "preserved", "unless_permission": "allow_background_change"}]},
    {"rules": [{"when": {"fact": "target_label", "operator": "eq", "value": "yes"}, "label": "yes", "source": 2}]},
    {"rules": [{"when": {"fact": "edit_count", "operator": "gt", "value": True}, "label": "yes", "source": 2}]},
    {"rules": [{"when": {"fact": "edit_count", "operator": "eq", "value": {"fact": "guard.background"}}, "label": "yes", "source": 2}]},
    {"rules": [{"when": {"all": []}, "label": "yes", "source": 2}]},
    {"default": {"label": "yes", "source": 999}},
    {"default": {"label": "maybe", "source": 2}},
    {"guards": [{"key": "background", "expected": "preserved", "unless_permission": None}],
     "rules": [{"when": {"fact": "guard.background", "operator": "ne", "value": "satisfied"},
                "label": "no", "source": 1}]},
])
def test_invalid_generated_policy_fails_closed(change):
    value = {**deepcopy(minimal_policy()), **change}
    with pytest.raises(ValueError):
        parse_policy(value, "failure\nsuccess")


def test_guard_permission_and_unknown_are_separate_policy_facts():
    value = minimal_policy()
    value["guards"] = [{"key": "subject_identity", "expected": "preserved",
                        "unless_permission": "allow_identity_change"}]
    value["rules"] = [{"when": {"fact": "guard.subject_identity", "operator": "eq", "value": "unknown"},
                       "label": "partial", "source": 1}]
    policy = parse_policy(value, "failure\nsuccess")
    plan = reference_plan(HARD_SAMPLES["h17"]["instruction"])
    edits = [{"condition": asdict(c), "status": "satisfied"} for c in policy.edits(plan)]
    guards = [{"condition": asdict(c), "status": "unknown"} for c in policy.guards(plan)]
    assert policy.decide(edits, guards, plan)[0] == "partial"
    allowed = reference_plan(HARD_SAMPLES["h06"]["instruction"])
    label, trace = policy.decide(edits, [], allowed)
    assert label == "yes"
    assert trace["facts"]["guard.subject_identity"] == "satisfied"
    assert trace["exempt_guards"] == ["subject_identity"]


def test_exemption_does_not_turn_an_uncertainty_cap_into_a_match():
    value = minimal_policy()
    value["guards"] = [{"key": "subject_identity", "expected": "preserved",
                        "unless_permission": "allow_identity_change"}]
    value["rules"] = [{"when": {"all": [
        {"fact": "satisfied_count", "operator": "gt", "value": 0},
        {"fact": "guard.subject_identity", "operator": "eq", "value": "unknown"},
    ]}, "label": "partial", "source": 1}]
    policy = parse_policy(value, "failure\nsuccess")
    plan = reference_plan(HARD_SAMPLES["h06"]["instruction"])
    edits = [{"condition": asdict(c), "status": "satisfied"} for c in policy.edits(plan)]
    label, trace = policy.decide(edits, [], plan)
    assert label == "yes"
    assert trace["exempt_guards"] == ["subject_identity"]


def test_automatically_generated_rules_follow_rubric_changes(hard_experiment):
    experiment = hard_experiment
    samples = {**HARD_SAMPLES, **HARD_VALIDATION_SAMPLES}
    original_targets = {**HARD_TARGETS, **HARD_VALIDATION_TARGETS}
    strict_targets = {key: "no" if key in STRICT_NO_CASES else value for key, value in original_targets.items()}
    scoped_targets = {**HARD_COLOR_POSITION_TARGETS, **SCOPED_VALIDATION_TARGETS}
    rubrics = {"Original": HARD_ORIGINAL, "Strict all-edits": STRICT_RUBRIC, "Color/position only": HARD_COLOR_POSITION}
    targets = {"Original": original_targets, "Strict all-edits": strict_targets, "Color/position only": scoped_targets}
    compiler = RubricCompiler(experiment.engine)
    # Compiler sees only each rubric. Targets never enter either compiler.
    policies = {name: compiler.compile(rubric) for name, rubric in rubrics.items()}
    prototype = TwoWayExperiment(experiment)
    instructions = {key: instruction_text(sample["instruction"]) for key, sample in samples.items()}
    plans = {key: prototype.decompose(text) for key, text in instructions.items()}
    references = {key: reference_plan(sample["instruction"]) for key, sample in samples.items()}
    predictions, traces = {}, {}
    for name, policy in policies.items():
        predictions[name], traces[name] = prototype.evaluate_many(plans, samples, policy=policy)
    errors = {name: mismatches(predictions[name], targets[name]) for name in rubrics}
    plan_errors = {key: {"expected": asdict(references[key]), "actual": asdict(plans[key])}
                   for key in samples if references[key] != plans[key]}
    atomic_errors = {request: {"expected": expected_atomic_status(request), "actual": result}
                     for request, result in prototype.checks.items()
                     if expected_atomic_status(request) != result["status"]}
    # Compare each arm against its own policy targets, since variants deliberately
    # change labels. The Markdown table's Expected column is the original policy.
    experiment.report(
        "generated_rules", prompts={**rubrics, "Rubric compiler": COMPILE_POLICY},
        samples=samples, targets=original_targets, comparisons=predictions,
        generated_policies={name: policy.specification for name, policy in policies.items()},
        compilation_attempts={name: compiler.attempts[rubric] for name, rubric in rubrics.items()},
        targets_by_policy=targets, mismatches=errors, plan_mismatches=plan_errors,
        atomic_mismatches=atomic_errors, decision_traces=traces, instructions=instructions,
        scores={name: len(samples) - len(wrong) for name, wrong in errors.items()},
        unique_instructions=len(prototype.plans), unique_atomic_checks=len(prototype.checks),
        limitation="Test-only compiler for supported edit types and a bounded decision-rule language; no production integration or image evaluation. Quoted sources do not prove semantic correctness; independent targets validate these examples.",
    )
    assert not plan_errors, f"Instruction plan errors: {plan_errors}"
    assert not atomic_errors, f"Atomic check errors: {atomic_errors}"
    assert all(not wrong for wrong in errors.values()), f"Generated policy errors: {errors}"
    # Behavioral assertions ensure scope and aggregation really are generated.
    assert predictions["Original"]["h02"]["label"] == "partial"
    assert predictions["Strict all-edits"]["h02"]["label"] == "no"
    assert predictions["Original"]["h15"]["label"] == "partial"
    assert predictions["Color/position only"]["h15"]["label"] == "yes"
