"""Blind stress test: twenty new cases, frozen and newly compiled policies."""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from .generated_policy import COMPILE_POLICY, RubricCompiler, parse_policy
from .hard_cases import HARD_ORIGINAL
from .stress_cases import STRESS_CASES
from .test_harder_examples import mismatches
from .test_two_way_decomposition import expected_atomic_status
from .two_way import TwoWayExperiment, aggregate, reference_plan, reference_guards


FROZEN_PATH = Path(__file__).parent / "fixtures" / "frozen_generated_policy.json"


def frozen_policy():
    value = json.loads(FROZEN_PATH.read_text())
    assert value["rubric"] == HARD_ORIGINAL
    assert value["rubric_sha256"] == hashlib.sha256(HARD_ORIGINAL.encode()).hexdigest()
    return parse_policy(value["policy"], HARD_ORIGINAL)


def test_twenty_cases_have_consistent_independent_targets():
    assert len(STRESS_CASES) == 20
    assert len({case.instruction for case in STRESS_CASES.values()}) == 20
    for key, case in STRESS_CASES.items():
        plan = reference_plan(case.sample["instruction"])
        def statuses(conditions):
            return [expected_atomic_status(TwoWayExperiment.request(c, case.sample["evidence"])) for c in conditions]
        # Validate hand-authored target consistency using the original reference
        # reducer, never the generated policies whose quality is being measured.
        assert aggregate(statuses(plan.edits), statuses(reference_guards(plan))) == case.expected, key


def test_saved_policy_is_valid_and_bound_to_the_original_rubric():
    frozen_policy()


def test_twenty_hard_cases_with_real_models(hard_experiment):
    experiment = hard_experiment
    samples = {key: case.sample for key, case in STRESS_CASES.items()}
    targets = {key: case.expected for key, case in STRESS_CASES.items()}
    purposes = {key: case.purpose for key, case in STRESS_CASES.items()}
    instructions = {key: case.instruction for key, case in STRESS_CASES.items()}
    policies = {"Frozen policy": frozen_policy()}
    compiler = RubricCompiler(experiment.engine)
    compilation_error = None
    try:
        # Compile before any observations/instructions reach the model. No
        # decision-error repair or changes to the policy during scoring.
        policies["Fresh policy"] = compiler.compile(HARD_ORIGINAL)
    except ValueError as error:
        compilation_error = str(error)
    prototype = TwoWayExperiment(experiment)
    plans, plan_failures = {}, {}
    for key, instruction in instructions.items():
        try:
            plans[key] = prototype.decompose(instruction)
        except ValueError as error:
            plan_failures[key] = str(error)
    references = {key: reference_plan(sample["instruction"]) for key, sample in samples.items()}
    plan_errors = {key: {"expected": asdict(references[key]), "actual": asdict(plans[key])}
                   for key in plans if references[key] != plans[key]}
    predictions = {"Original overall judge": experiment.judge_many(HARD_ORIGINAL, samples)}
    traces = {}
    for name, policy in policies.items():
        judgments, traces[name] = prototype.evaluate_many(plans, samples, policy=policy)
        predictions[name] = {
            key: judgments.get(key, {"label": "error", "rationale": plan_failures.get(key, "Missing plan")})
            for key in samples
        }
    if compilation_error:
        predictions["Fresh policy"] = {key: {"label": "error", "rationale": compilation_error} for key in samples}
    errors = {name: mismatches(values, targets) for name, values in predictions.items()}
    atomic_errors = {request: {"expected": expected_atomic_status(request), "actual": result}
                     for request, result in prototype.checks.items()
                     if expected_atomic_status(request) != result["status"]}
    scores = {name: len(samples) - len(wrong) for name, wrong in errors.items()}
    per_label = {name: {
        label: {"correct": sum(values[key]["label"] == label for key in targets if targets[key] == label),
                "total": sum(target == label for target in targets.values())}
        for label in ("no", "partial", "yes")
    } for name, values in predictions.items()}
    experiment.report(
        "twenty_hard_cases", prompts={"Rubric": HARD_ORIGINAL, "Rubric compiler": COMPILE_POLICY},
        samples=samples, targets=targets, comparisons=predictions, instructions=instructions,
        case_purposes=purposes, generated_policies={name: p.specification for name, p in policies.items()},
        frozen_policy_provenance=json.loads(FROZEN_PATH.read_text())["provenance"],
        compilation_attempts=compiler.attempts.get(HARD_ORIGINAL, []), compilation_error=compilation_error,
        plan_mismatches=plan_errors, plan_failures=plan_failures, atomic_mismatches=atomic_errors,
        decomposition_attempts=prototype.decomposition_attempts,
        mismatches=errors, scores=scores, per_label=per_label, decision_traces=traces,
        unique_instructions=len(prototype.plans), unique_atomic_checks=len(prototype.checks),
        limitation="Twenty deliberately selected text-evidence holdouts, not a random benchmark or image test. Original overall judging uses structured instructions; two-way judging parses the authored natural-language instructions. No quality-based retries or target feedback to generation.",
    )
    # A short, readable result is preserved even when the strict quality check fails.
    lines = ["# Twenty hard CaliTree cases", "", f"Model: {experiment.engine.model}", "",
             "Policies were fixed during scoring. Expected labels were authored before generation.", "",
             "| Case | Stress condition | Expected | Overall judge | Frozen policy | Fresh policy |",
             "| --- | --- | --- | --- | --- | --- |"]
    for key in samples:
        lines.append("| " + " | ".join([key, purposes[key], targets[key], *[
            predictions[name][key]["label"] for name in ("Original overall judge", "Frozen policy", "Fresh policy")
        ]]) + " |")
    lines += ["", "## Scores", ""]
    lines += [f"- {name}: {score}/20" for name, score in scores.items()]
    lines += ["", f"Instruction plan mismatches: {len(plan_errors)}; parse failures: {len(plan_failures)}.",
              f"Atomic check mismatches: {len(atomic_errors)} across {len(prototype.checks)} distinct checks.",
              f"Model calls: {len(experiment.calls)}.", "", "## Interpretation", "",
              "The cases concentrate on zero successful edits combined with uncertain preservation, scoped permissions, empty requested sets, count-zero boundaries, shade matching, and untrusted metadata. This is a targeted stress test of previously untested interactions.",
              "Failures are retained; the policies and expected labels were not repaired after scoring. The detailed report separates instruction parsing, individual checks, and rule execution.", "",
              "Text evidence and a predefined condition vocabulary are used. These results do not measure image judging or unrestricted rubric compilation.", "",
              "[Full instructions, evidence, rationales, and matching-rule traces](twenty_hard_cases.md)",
              "[Machine-readable report and model calls](twenty_hard_cases.json)", ""]
    (experiment.report_dir / "summary.md").write_text("\n".join(lines))
    assert compilation_error is None, f"Fresh rubric compilation failed: {compilation_error}"
    assert not plan_failures, f"Instruction parsing failed: {plan_failures}"
    assert not plan_errors, f"Instruction decomposition errors: {plan_errors}"
    assert not atomic_errors, f"Atomic checker errors: {atomic_errors}"
    # The immutable flat policy is a historical control, not the current staged
    # algorithm. Keep its errors visible; gate the current freshly compiled policy.
    assert not errors["Fresh policy"], f"Fresh-policy failures: {list(errors['Fresh policy'])}"
