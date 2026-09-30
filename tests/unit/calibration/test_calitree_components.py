"""Component contracts and pre-refactor behavior fixtures (no model calls)."""

import json
from pathlib import Path

import pytest

from critical.core.optimization.prompt.calitree import (
    CaliTreeBuilder, CaliTreeNode, CaliTreeLeafNode, CaliTreeMergeNode,
    DefaultNodeFactory, FeedbackPromptOptimizer, LeafOptimizer,
    BehavioralCompleteLinkClustering, SemanticCompleteLinkClustering,
    MergeAlgorithm, MergeAcceptancePolicy, MergeProposal, MergeDecision,
    OptimizationResult, RootSelector, RootSelection, RoutingCalibrator, route_prompt,
)


SCENARIOS = (
    "accepted", "conflict", "low_accuracy", "partial", "regression",
    "budget", "behavioral", "transfer_rejected", "additive", "empty",
)


def run_scenario(scenario, **components):
    calls = []
    ids = [] if scenario == "empty" else ["a", "b", "c", "d"]
    samples = {key: {"item_id": key, "input": {"instruction": key}} for key in ids}
    targets = {key: "yes" for key in ids}

    def judge(prompt, sample):
        key = sample["item_id"]
        calls.append(["judge", prompt, key])
        label = "yes" if prompt != "initial" else "no"
        if scenario == "transfer_rejected" and prompt.startswith("leaf-"):
            label = "yes" if prompt == "leaf-" + key else "no"
        if prompt == "merged":
            if scenario in {"low_accuracy", "regression"}:
                label = "no"
            if scenario == "partial" and key == "b":
                label = "no"
        return {"label": label, "rationale": "fixture"}

    def optimize(prompt, feedback):
        calls.append(["optimize", prompt, feedback])
        if scenario == "transfer_rejected":
            return "leaf-" + feedback.split("Instruction: ", 1)[1].split("\n", 1)[0]
        return "good" if prompt == "initial" else prompt

    def extract(prompt):
        calls.append(["extract", prompt])
        return {"criteria": [prompt], "priorities": [], "constraints": []}

    def embed(texts):
        calls.append(["embed", texts])
        return [[1.0, 0.0] for _ in texts]

    def merge(left, right):
        calls.append(["merge", left, right])
        return {"prompt": "merged", "conflict": scenario == "conflict"}

    options = dict(max_steps=1, warm_start=scenario != "transfer_rejected")
    if scenario == "partial":
        options["merge_acceptance"] = 0.5
    if scenario == "regression":
        options.update(merge_objective="balanced", merge_generalization_floor=0.0)
    if scenario == "budget":
        options["max_merge_attempts"] = 1
    if scenario in {"behavioral", "transfer_rejected"}:
        options["clustering_algorithm"] = "behavioral_complete_link"
    if scenario == "additive":
        options["specialization_mode"] = "additive"
    builder = CaliTreeBuilder(
        judge=judge, optimize=optimize, extract_components=extract, embed=embed,
        merge_prompts=merge,
        progress=lambda kind, payload: calls.append(["progress", kind, payload]),
        **options, **components,
    )
    build_options = {}
    if scenario in {"regression", "additive"}:
        build_options = {
            "validation_samples": {"v": {"item_id": "v", "input": {"instruction": "v"}}},
            "validation_targets": {"v": "yes"},
            "validation_leaf_groups": {"v": "a"},
        }
    tree = builder.build(initial_prompt="initial", samples=samples, targets=targets,
                         **build_options)
    return {"tree": tree, "calls": calls, "route": route_prompt(tree, [1.0, 0.0])}


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_default_components_preserve_original_tree_and_call_order(scenario):
    fixture = Path(__file__).with_name("fixtures") / "calitree_components.json"
    expected = json.loads(fixture.read_text())[scenario]
    assert run_scenario(scenario) == expected


def test_node_factory_constructs_distinct_roles_with_shared_fields():
    from dataclasses import asdict, fields
    from critical.core.optimization.prompt.calitree.model import CaliTreeNode as LegacyNode
    from critical.core.calibration import CaliTreeNode as CalibrationNode

    assert LegacyNode is CalibrationNode is CaliTreeNode
    captured = []

    class RecordingFactory(DefaultNodeFactory):
        def leaf(self, **values):
            node = super().leaf(**values)
            captured.append(node)
            return node

        def merge(self, **values):
            node = super().merge(**values)
            captured.append(node)
            return node

        def promoted_leaf(self, **values):
            node = super().promoted_leaf(**values)
            captured.append(node)
            return node

        def global_node(self, **values):
            node = super().global_node(**values)
            captured.append(node)
            return node

    result = run_scenario("partial", node_factory=RecordingFactory())
    assert any(isinstance(node, CaliTreeMergeNode) for node in captured)
    assert any(isinstance(node, CaliTreeLeafNode) and node.status == "promoted" for node in captured)
    assert type(captured[-1]) is CaliTreeNode
    for node in captured:
        assert [field.name for field in fields(node)] == [field.name for field in fields(CaliTreeNode)]
        assert asdict(node) == result["tree"]["nodes"][node.id]


def test_custom_factory_can_create_new_node_subclasses():
    class ExtendedLeaf(CaliTreeLeafNode):
        pass

    class ExtendedFactory(DefaultNodeFactory):
        def leaf(self, **values):
            node = ExtendedLeaf(**values)
            node.prompt = "extended"
            return node

    result = run_scenario("conflict", node_factory=ExtendedFactory())
    assert result["tree"]["nodes"]["leaf:a"]["prompt"] == "extended"


def test_prompt_optimizer_is_shared_across_default_stages():
    case_sets = []

    class RecordingOptimizer(FeedbackPromptOptimizer):
        def optimize(self, prompt, ids, samples, targets, *, services, max_steps):
            case_sets.append((prompt, list(ids)))
            return super().optimize(prompt, ids, samples, targets,
                                    services=services, max_steps=max_steps)

    result = run_scenario("accepted", prompt_optimizer=RecordingOptimizer())
    assert case_sets[0] == ("initial", ["a", "b", "c", "d"])
    assert ("good", ["a"]) in case_sets
    assert ("merged", ["a", "b"]) in case_sets
    assert result == run_scenario("accepted")


def test_custom_leaf_optimizer_does_not_replace_warm_or_merge_optimization():
    seen = []

    class CustomLeafOptimizer(LeafOptimizer):
        def optimize(self, prompt, ids, context):
            seen.append((prompt, list(ids), context))
            prompt = "special-leaf"
            accuracy, correct, predictions = context.services.validate(
                prompt, ids, context.samples, context.targets,
            )
            return OptimizationResult(prompt, accuracy, correct, predictions, 0)

    result = run_scenario("accepted", leaf_optimizer=CustomLeafOptimizer())
    assert len(seen) == 4
    assert all(prompt == "good" and len(ids) == 1 for prompt, ids, _context in seen)
    assert result["tree"]["warm_start_prompt"] == "good"
    assert result["tree"]["nodes"]["leaf:a"]["prompt"] == "special-leaf"
    assert any(call[0] == "merge" and call[1:] == ["special-leaf", "special-leaf"]
               for call in result["calls"])


def test_clustering_injection_overrides_legacy_algorithm_selection():
    result = run_scenario("accepted", clustering=BehavioralCompleteLinkClustering())
    assert any(event["kind"] == "behavioral_clustering_probe" for event in result["tree"]["timeline"])
    assert all(node["behavior_profile"] for node in result["tree"]["nodes"].values()
               if node["status"] in {"leaf", "accepted"})


def test_clustering_can_replace_candidate_pairing():
    class NoPairs(SemanticCompleteLinkClustering):
        def pairs(self, nodes, threshold, *, level, blocked_pairs, context):
            return [], list(nodes)

    result = run_scenario("accepted", clustering=NoPairs())
    assert result["tree"]["stats"]["merge_attempts"] == 0
    assert not any(call[0] == "merge" for call in result["calls"])


def test_custom_synthesis_reuses_default_acceptance():
    class AlternateMerge(MergeAlgorithm):
        def propose(self, left, right, context):
            return MergeProposal("alternate")

    result = run_scenario("regression", merge_algorithm=AlternateMerge())
    assert result["tree"]["stats"]["accepted_merges"] > 0
    assert not any(call[0] == "merge" for call in result["calls"])
    assert any(node["prompt"] == "alternate" and node["status"] == "accepted"
               for node in result["tree"]["nodes"].values())


def test_acceptance_can_reject_independently_of_synthesis():
    class RejectAll(MergeAcceptancePolicy):
        def evaluate(self, optimization, covered_ids, context):
            return MergeDecision(False, "custom_rejection", diagnostics={"reason": "policy"})

    result = run_scenario("accepted", merge_acceptance_policy=RejectAll())
    assert result["tree"]["stats"]["accepted_merges"] == 0
    assert any(call[0] == "merge" for call in result["calls"])
    assert any(event["kind"] == "custom_rejection" and event["reason"] == "policy"
               for event in result["tree"]["timeline"])


def test_root_selection_is_independently_replaceable():
    class CustomRoot(RootSelector):
        def select(self, context, *, accepted_merges):
            assert accepted_merges > 0
            assert context.case_embeddings and context.nodes
            return RootSelection("custom-root", "custom", None, {"selected": "custom"})

    result = run_scenario("accepted", root_selector=CustomRoot())
    assert result["tree"]["roots"] == ["global:custom"]
    assert result["tree"]["nodes"]["global:custom"]["prompt"] == "custom-root"
    assert result["tree"]["stats"]["root_source"] == "custom"


def test_routing_calibrator_controls_inference_thresholds():
    class RootOnly(RoutingCalibrator):
        def calibrate(self, nodes, case_embeddings, *, margin):
            assert margin == 0.02
            assert case_embeddings
            for node in nodes.values():
                if node.status != "global":
                    node.routing_threshold = 1.1

    result = run_scenario("accepted", routing_calibrator=RootOnly())
    assert result["route"]["route_path"] == result["tree"]["roots"]


def test_shared_clustering_instance_uses_separate_build_contexts():
    contexts = []

    class RecordingClustering(BehavioralCompleteLinkClustering):
        def prepare(self, nodes, context):
            contexts.append(context)
            assert not context.rejected_static_generalization_prompts
            assert not context.behavioral_probe_ids
            return super().prepare(nodes, context)

    clustering = RecordingClustering()
    first = run_scenario("behavioral", clustering=clustering)
    second = run_scenario("behavioral", clustering=clustering)
    assert first == second
    assert contexts[0] is not contexts[1]
    assert contexts[0].nodes is not contexts[1].nodes


def test_batched_judging_and_custom_feedback_remain_available():
    batches, feedback_ids = [], []

    def judge_many(prompt, samples):
        batches.append((prompt, list(samples)))
        return {key: {"label": "yes" if prompt == "updated" else "no"} for key in samples}

    def feedback(ids, samples, targets, predictions):
        feedback_ids.append(list(ids))
        return "custom feedback"

    def update(prompt, feedback):
        assert feedback == "custom feedback"
        return "updated"

    builder = CaliTreeBuilder(
        judge=lambda *_args: pytest.fail("single-case judge should not run"),
        judge_many=judge_many, optimize=update, format_feedback=feedback,
        extract_components=lambda prompt: {"criteria": [prompt]},
        embed=lambda texts: [[1.0, 0.0] for _ in texts],
        merge_prompts=lambda *_args: {"conflict": True}, max_steps=1,
    )
    tree = builder.build(initial_prompt="initial", samples={"a": {}, "b": {}},
                         targets={"a": "yes", "b": "yes"})
    assert feedback_ids == [["a", "b"]]
    assert batches[:3] == [("initial", ["a", "b"]), ("initial", ["a", "b"]),
                           ("updated", ["a", "b"])]
    assert tree["warm_start_prompt"] == "updated"
