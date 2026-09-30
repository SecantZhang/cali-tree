"""Reference fixture oracles and a compatibility adapter over the core strategy."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

from critical.core.optimization.prompt.calitree.decomposition import (
    Condition, InstructionPlan, DecompositionTwoWay, ModelConditionEvaluator,
    parse_condition, parse_plan, load_templates,
)

_TEMPLATES = load_templates()
DECOMPOSE_INSTRUCTION = _TEMPLATES.decompose_instruction
CHECK_CONDITION = _TEMPLATES.check_condition


def reference_guards(plan):
    """Test-only harder-fixture oracle; core guards are generated from the rubric."""
    result = [Condition("content_recognizable", "equals", True)]
    if not plan.allow_identity_change:
        result.append(Condition("subject_identity", "equals", "preserved"))
    if not plan.allow_background_change:
        result.append(Condition("background", "equals", "preserved"))
    return tuple(result)


def reference_plan(instruction):
    edits = []
    for key in instruction["required_edits"]:
        expected = instruction[f"desired_{key}"]
        op = "equals"
        if key == "color" and instruction["allow_color_shades"]:
            op, expected = "one_of", [expected, f"light {expected}", f"dark {expected}"]
        elif key == "count" and instruction["count_rule"] == "at_least":
            op = "at_least"
        edits.append({"key": key, "operator": op, "expected": expected})
    return parse_plan({"edits": edits, "allow_identity_change": instruction["allow_identity_change"],
                       "allow_background_change": instruction["allow_background_change"]})


def instruction_text(instruction):
    """Natural-language rendering of fixture intent, without observations/labels."""
    parts = []
    for key in instruction["required_edits"]:
        if key == "color":
            parts.append(f"Make the objects {instruction['desired_color']}"
                         + (", allowing light or dark shades of that color" if instruction["allow_color_shades"]
                            else ", requiring that exact color"))
        elif key == "position":
            side = instruction["desired_position"].split("_")[0]
            parts.append(f"Place the objects to the {side} of the reference")
        else:
            quantifier = "exactly" if instruction["count_rule"] == "exactly" else "at least"
            parts.append(f"Show {quantifier} {instruction['desired_count']} objects")
    parts.append("Changes to subject identity are " + ("allowed" if instruction["allow_identity_change"] else "not allowed"))
    parts.append("Changes to the background are " + ("allowed" if instruction["allow_background_change"] else "not allowed"))
    return ". ".join(parts) + "."


def aggregate(edits, guards):
    """Harder-fixture policy: veto, success count, then uncertainty cap."""
    statuses = list(edits) + list(guards)
    if any(x not in {"satisfied", "violated", "unknown"} for x in statuses):
        raise ValueError("Invalid condition status")
    if "violated" in guards:
        return "no"
    if edits and "satisfied" not in edits:
        return "no"
    if "unknown" in guards or any(x != "satisfied" for x in edits):
        return "partial"
    return "yes"

class TwoWayExperiment:
    """Historical experiment API; generated-policy execution uses production code."""

    def __init__(self, experiment):
        self.engine = experiment.engine
        self.algorithm = DecompositionTwoWay(self.engine)
        self.plans = self.algorithm.instruction_compiler.plans
        self.checks = self.algorithm.condition_evaluator.checks
        self.decomposition_attempts = self.algorithm.instruction_compiler.attempts

    def decompose(self, instruction):
        return self.algorithm.decompose(instruction)

    request = staticmethod(ModelConditionEvaluator.request)

    def evaluate_many(self, plans, samples, policy=None):
        evidence = {key: samples[key]["evidence"] for key in plans}
        if policy is not None:
            results = self.algorithm.evaluate_many(policy, plans, evidence)
            return ({key: result.judgment() for key, result in results.items()},
                    {key: result.trace for key, result in results.items()})
        # Retain the hand-specified fixture reducer solely as an independent
        # reference arm. Production always executes a compiled policy.
        jobs = {}
        for key, plan in plans.items():
            for condition in (*plan.edits, *reference_guards(plan)):
                jobs.setdefault(self.request(condition, evidence[key]), (condition, evidence[key]))
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(lambda job: self.algorithm.condition_evaluator.evaluate(*job), jobs.values()))
        predictions, traces = {}, {}
        for key, plan in plans.items():
            def rows(conditions):
                return [{"condition": asdict(c), **self.checks[self.request(c, evidence[key])]} for c in conditions]
            edits, guards = rows(plan.edits), rows(reference_guards(plan))
            label = aggregate([r["status"] for r in edits], [r["status"] for r in guards])
            traces[key] = {"plan": asdict(plan), "edits": edits, "guards": guards, "label": label,
                           "decision": {"rule": "hand-specified reducer"}}
            predictions[key] = {"label": label, "rationale": json.dumps(traces[key], sort_keys=True)}
        return predictions, traces
