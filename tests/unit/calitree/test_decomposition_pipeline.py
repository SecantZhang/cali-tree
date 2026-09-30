"""Current generated-policy pipeline must match every existing ground truth."""

from dataclasses import asdict
from itertools import combinations, product

import pytest

from .cases import ORIGINAL_PROMPT, SAMPLES, TARGETS, VALIDATION_SAMPLES, VALIDATION_TARGETS
from .generated_policy import COMPILE_POLICY, RubricCompiler
from .hard_cases import HARD_ORIGINAL, HARD_SAMPLES, HARD_TARGETS, HARD_VALIDATION_SAMPLES, HARD_VALIDATION_TARGETS
from .stress_cases import STRESS_CASES
from .test_harder_examples import mismatches
from .test_two_way_decomposition import expected_atomic_status
from .two_way import DECOMPOSE_INSTRUCTION, TwoWayExperiment, aggregate, instruction_text, parse_plan, reference_plan, reference_guards


def exhaustive_hard_policy_errors(policy):
    """Target-free compiler test inputs; an independent rubric oracle scores them.

    All requested subsets, edit statuses, definite recognizability states,
    identity/background statuses, and permission combinations are included.
    Results are never sent back to the compiler.
    """
    base = HARD_SAMPLES["h01"]["instruction"]
    errors, total = [], 0
    for size in range(4):
        for subset in combinations(("color", "position", "count"), size):
            for allow_identity, allow_background in product((False, True), repeat=2):
                plan = reference_plan({**base, "required_edits": list(subset),
                                       "allow_identity_change": allow_identity,
                                       "allow_background_change": allow_background})
                actual_edits, actual_guards = policy.edits(plan), policy.guards(plan)
                if actual_edits != plan.edits or actual_guards != reference_guards(plan):
                    errors.append({"kind": "applicability", "plan": asdict(plan)})
                    continue
                guard_domains = [("satisfied", "violated") if c.key == "content_recognizable"
                                 else ("satisfied", "violated", "unknown") for c in actual_guards]
                for edit_statuses in product(("satisfied", "violated", "unknown"), repeat=size):
                    for guard_statuses in product(*guard_domains):
                        total += 1
                        rows = lambda cs, ss: [{"condition": asdict(c), "status": s} for c, s in zip(cs, ss)]
                        actual, trace = policy.decide(rows(actual_edits, edit_statuses), rows(actual_guards, guard_statuses), plan)
                        expected = aggregate(edit_statuses, guard_statuses)
                        if actual != expected:
                            errors.append({"expected": expected, "actual": actual, "plan": asdict(plan),
                                           "edits": edit_statuses, "guards": guard_statuses, "trace": trace})
    return total, errors


def dataset(name):
    if name == "simple":
        records = {**SAMPLES, **VALIDATION_SAMPLES}
        samples = {key: {"evidence": evidence} for key, evidence in records.items()}
        targets = {**TARGETS, **VALIDATION_TARGETS}
        instruction = "Require the object's color to be red and its shape to be circular."
        instructions = dict.fromkeys(samples, instruction)
        plan = parse_plan({"edits": [{"key": "color", "operator": "equals", "expected": "red"},
                                     {"key": "shape", "operator": "equals", "expected": "circular"}],
                           "allow_identity_change": False, "allow_background_change": False})
        return ORIGINAL_PROMPT, samples, targets, instructions, dict.fromkeys(samples, plan)
    if name == "harder":
        samples = {**HARD_SAMPLES, **HARD_VALIDATION_SAMPLES}
        targets = {**HARD_TARGETS, **HARD_VALIDATION_TARGETS}
        instructions = {key: instruction_text(sample["instruction"]) for key, sample in samples.items()}
    else:
        samples = {key: case.sample for key, case in STRESS_CASES.items()}
        targets = {key: case.expected for key, case in STRESS_CASES.items()}
        instructions = {key: case.instruction for key, case in STRESS_CASES.items()}
    references = {key: reference_plan(sample["instruction"]) for key, sample in samples.items()}
    return HARD_ORIGINAL, samples, targets, instructions, references


@pytest.mark.parametrize("name", ["simple", "harder", "stress"])
def test_current_pipeline_matches_all_ground_truths(name, hard_experiment):
    experiment = hard_experiment
    rubric, samples, targets, instructions, references = dataset(name)
    compiler = RubricCompiler(experiment.engine)
    policy = compiler.compile(rubric)
    prototype = TwoWayExperiment(experiment)
    plans = {key: prototype.decompose(text) for key, text in instructions.items()}
    predictions, traces = prototype.evaluate_many(plans, samples, policy=policy)
    plan_errors = {key: {"expected": asdict(references[key]), "actual": asdict(plans[key])}
                   for key in samples if plans[key] != references[key]}
    atomic_errors = {request: {"expected": expected_atomic_status(request), "actual": result}
                     for request, result in prototype.checks.items()
                     if expected_atomic_status(request) != result["status"]}
    errors = mismatches(predictions, targets)
    state_count, state_errors = exhaustive_hard_policy_errors(policy) if name != "simple" else (0, [])
    experiment.report(
        f"pipeline_{name}", prompts={"Rubric": rubric, "Policy compiler": COMPILE_POLICY,
                                     "Instruction compiler": DECOMPOSE_INSTRUCTION},
        samples=samples, targets=targets, comparisons={"Current pipeline": predictions},
        generated_policy=policy.specification, compilation_attempts=compiler.attempts[rubric],
        decomposition_attempts=prototype.decomposition_attempts, instructions=instructions,
        plan_mismatches=plan_errors, atomic_mismatches=atomic_errors, mismatches=errors,
        decision_traces=traces, correct=len(samples) - len(errors), total=len(samples),
        exhaustive_states=state_count, exhaustive_errors=state_errors,
        limitation="Real-model text-evidence prototype. No target feedback into generation; original ground truths unchanged. Exhaustive checks cover the fixture's finite predicate/status vocabulary, not arbitrary rubrics or images.",
    )
    assert not plan_errors, f"Instruction errors: {plan_errors}"
    assert not atomic_errors, f"Atomic errors: {atomic_errors}"
    assert not errors, f"Decision errors: {errors}"
    assert not state_errors, f"Compiled policy differs from rubric in {len(state_errors)} states; first: {state_errors[:1]}"
    if name != "simple":
        assert state_count == 2048
