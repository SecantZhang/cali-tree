"""Offline example: three leaves → joint parent → JSON reload → policy execution.

Run: .venv/bin/python -m run.calitree_modular_demo
No models, credentials, image downloads, or paid calls are used.
"""

import json

from critical.core.optimization.prompt.calitree import (
    ArtifactExecutor, CaliTreeBuilder, DecompositionTwoWay, TwoWayAdapter,
    route_prompt, validate_tree,
)
from critical.core.optimization.prompt.calitree.decomposition import (
    RubricCompiler, InstructionCompiler, ConditionEvaluator, Condition,
    ConditionResult, InstructionPlan, parse_policy,
)

RUBRIC = "No successful requested edits means no.\nAll requested edits succeed means yes.\nOtherwise return partial."


class DemoRubricCompiler(RubricCompiler):
    def compile(self, rubric):
        # Deliberately limited deterministic compiler for this example only.
        def when(fact, value):
            return {"fact": fact, "operator": "eq", "value": value}
        rules = [{"when": when("satisfied_count", 0), "label": "no", "source": 1},
                 {"when": when("satisfied_count", {"fact": "edit_count"}), "label": "yes", "source": 2}]
        if rubric.startswith("Always no"):
            rules = []
        return parse_policy({"supported_edits": ["color"], "criteria": [], "guards": [],
                             "veto_rules": [], "decision_rules": rules, "caps": [],
                             "default": {"label": "no" if not rules else "partial", "source": 3}}, rubric)


class DemoInstructionCompiler(InstructionCompiler):
    def decompose(self, instruction):
        if instruction not in {"Make it red", "Make it blue"}:
            raise ValueError("Demo supports only red/blue instructions")
        return InstructionPlan((Condition("color", "equals", instruction.split()[-1]),))


class DemoConditionEvaluator(ConditionEvaluator):
    def evaluate(self, condition, evidence):
        value = evidence.get(condition.key)
        return ConditionResult("unknown" if value is None else
                               "satisfied" if value == condition.expected else "violated", "demo observation")


def demo_adapter():
    return TwoWayAdapter(DecompositionTwoWay(rubric_compiler=DemoRubricCompiler(),
        instruction_compiler=DemoInstructionCompiler(), condition_evaluator=DemoConditionEvaluator()))


def demo_sample(color="red", instruction="Make it red"):
    return {"input": {"instruction": instruction}, "evidence": {"color": color}}


def demo_builder(**overrides):
    options = dict(judge=lambda *_: {}, optimize=lambda prompt, _: prompt,
        extract_components=lambda prompt: {"criteria": [prompt], "priorities": [], "constraints": []},
        embed=lambda texts: [[1.0, 0.0] for _ in texts], merge_prompts=lambda *_: {"prompt": RUBRIC},
        merge_many_prompts=lambda _: {"prompt": RUBRIC}, modular_mode=True,
        decomposition=demo_adapter(), max_steps=0, warm_start=False, max_merge_children=3,
        semantic_premerge_levels=0, merge_generalization_floor=0.0)
    options.update(overrides)
    return CaliTreeBuilder(**options)


def main():
    tree = demo_builder().build(initial_prompt=RUBRIC,
        samples={key: demo_sample() for key in ("a", "b", "c")},
        targets={key: "yes" for key in ("a", "b", "c")},
        validation_samples={"v": demo_sample()}, validation_targets={"v": "yes"})
    restored = json.loads(json.dumps(tree))
    executor = ArtifactExecutor(demo_adapter())
    validate_tree(restored, executor)
    routed = route_prompt(restored, [1, 0])
    result = executor.judge(routed["prompt"], demo_sample())
    parent = next(node for node in tree["nodes"].values() if node["id"].startswith("merge:"))
    print(json.dumps({"version": tree["version"], "merged_children": parent["children"],
                      "routed_node": routed["id"], "label": result["label"]}, indent=2))


if __name__ == "__main__":
    main()
