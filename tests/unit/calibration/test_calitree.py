import pytest

from vejudge.core.calibration.calitree import (
    CaliTreeBuilder,
    CaliTreeNode,
    classification_metrics,
    complete_link_similarity,
    greedy_pairs,
    route_prompt,
    similarity_threshold,
)


def _sample(item_id, *, editor="SDEdit"):
    return {
        "item_id": item_id,
        "editor": editor,
        "input": {"instruction": f"instruction {item_id}"},
    }


def _builder(judge, merge, *, max_steps=0):
    return CaliTreeBuilder(
        judge=judge,
        optimize=lambda prompt, _feedback: prompt,
        extract_components=lambda prompt: {
            "criteria": [prompt], "priorities": [], "constraints": ["json"]
        },
        embed=lambda texts: [[1.0, 0.0] for _ in texts],
        merge_prompts=merge,
        max_steps=max_steps,
    )


def test_similarity_decay_stops_at_floor():
    assert similarity_threshold(0) == 0.9
    assert similarity_threshold(2) == 0.8
    assert similarity_threshold(99) == 0.7


def test_greedy_clustering_is_deterministic_under_ties():
    nodes = [
        CaliTreeNode(str(index), "p", [str(index)], [1, 0], {})
        for index in range(4)
    ]
    pairs, remaining = greedy_pairs(nodes, 0.9)
    assert [(left.id, right.id) for left, right, _ in pairs] == [("0", "1"), ("2", "3")]
    assert remaining == []


def test_complete_link_rejects_a_centroid_shortcut_with_dissimilar_members():
    left = CaliTreeNode(
        "left", "p", ["a", "b"], [0.5, 0.5], {},
        member_embeddings=[[1, 0], [0, 1]],
    )
    right = CaliTreeNode(
        "right", "p", ["c"], [0.7, 0.7], {},
        member_embeddings=[[0.7, 0.7]],
    )
    assert complete_link_similarity(left, right) < 0.8
    pairs, remaining = greedy_pairs([left, right], 0.8)
    assert pairs == []
    assert remaining == [left, right]


def test_behavioral_clustering_prioritizes_cross_generalizing_leaf_pair():
    """A hierarchy can beat the plain judge when leaves transfer across a merge.

    The two leaves have only moderately similar prompt components, but each already predicts
    the other leaf's examples correctly.  Behavioral clustering therefore merges them and
    the root routes both classes through the validated merged prompt.
    """
    samples = {
        item_id: _sample(item_id)
        for item_id in ("a1", "a2", "b1", "b2")
    }
    targets = {item_id: "yes" for item_id in samples}

    def judge(prompt, sample):
        item_id = sample["item_id"]
        if prompt == "plain":
            return {"label": "no"}
        if prompt in {"leaf-a", "leaf-b", "merged"}:
            return {"label": "yes"}
        return {"label": "no"}

    def optimize(prompt, feedback):
        if prompt == "plain" and "instruction a" in feedback:
            return "leaf-a"
        if prompt == "plain" and "instruction b" in feedback:
            return "leaf-b"
        return prompt

    def embed(texts):
        vectors = {
            "leaf-a": [1.0, 0.0],
            "leaf-b": [0.8, 0.6],
            "merged": [0.9, 0.3],
            "instruction a1": [1.0, 0.0],
            "instruction a2": [1.0, 0.0],
            "instruction b1": [0.8, 0.6],
            "instruction b2": [0.8, 0.6],
        }
        return [vectors.get(text, [0.9, 0.3]) for text in texts]

    builder = CaliTreeBuilder(
        judge=judge,
        optimize=optimize,
        extract_components=lambda prompt: {
            "criteria": [prompt], "priorities": [], "constraints": [],
        },
        embed=embed,
        merge_prompts=lambda _left, _right: {
            "conflict": False, "prompt": "merged"
        },
        warm_start=False,
        max_steps=1,
        similarity_start=0.6,
        similarity_floor=0.6,
        similarity_decay=0.1,
        clustering_algorithm="behavioral_complete_link",
    )
    tree = builder.build(
        initial_prompt="plain",
        samples=samples,
        targets=targets,
        routing_texts={item_id: f"instruction {item_id}" for item_id in samples},
        leaf_groups={
            "a1": "a", "a2": "a", "b1": "b", "b2": "b",
        },
    )

    plain_accuracy = sum(
        judge("plain", sample)["label"] == targets[item_id]
        for item_id, sample in samples.items()
    ) / len(samples)
    routed_accuracy = sum(
        judge(route_prompt(tree, embed([f"instruction {item_id}"])[0])["prompt"], sample)["label"]
        == targets[item_id]
        for item_id, sample in samples.items()
    ) / len(samples)

    assert plain_accuracy == 0.0
    assert routed_accuracy == 1.0
    assert tree["stats"]["accepted_merges"] == 1
    assert tree["config"]["clustering_algorithm"] == "behavioral_complete_link"
    accepted = next(event for event in tree["timeline"] if event["kind"] == "accepted")
    assert accepted["cross_generalization"] == 1.0


def test_semantic_premerge_compatibility_groups_similar_operations_first():
    nodes = [
        CaliTreeNode(
            item_id,
            "p",
            [item_id],
            [1, 0],
            {},
            semantic_groups=[group],
        )
        for item_id, group in (
            ("add-a", "add"),
            ("remove-a", "remove"),
            ("add-b", "add"),
            ("remove-b", "remove"),
        )
    ]
    pairs, remaining = greedy_pairs(
        nodes,
        0.9,
        compatible=lambda left, right: bool(
            set(left.semantic_groups) & set(right.semantic_groups)
        ),
    )

    assert remaining == []
    assert {
        frozenset((left.id, right.id))
        for left, right, _score in pairs
    } == {
        frozenset(("add-a", "add-b")),
        frozenset(("remove-a", "remove-b")),
    }


def test_global_warm_start_initializes_every_leaf_from_balanced_feedback():
    samples = {item_id: _sample(item_id) for item_id in ("a", "b")}
    optimized = []

    def judge(prompt, sample):
        if prompt == "warm":
            return {"label": "yes" if sample["item_id"] == "a" else "no"}
        return {"label": "no"}

    builder = CaliTreeBuilder(
        judge=judge,
        optimize=lambda _prompt, feedback: optimized.append(feedback) or "warm",
        extract_components=lambda prompt: {
            "criteria": [prompt], "priorities": [], "constraints": [],
        },
        embed=lambda texts: [[1.0, 0.0] for _ in texts],
        merge_prompts=lambda _left, _right: {
            "conflict": True, "conflict_reason": "stop", "prompt": "",
        },
        max_steps=1,
    )
    tree = builder.build(
        initial_prompt="initial",
        samples=samples,
        targets={"a": "yes", "b": "no"},
    )

    assert tree["warm_start_prompt"] == "warm"
    assert tree["warm_start_accuracy"] == 1
    assert tree["warm_start_steps"] == 1
    assert optimized and "Target: yes" in optimized[0]
    assert tree["nodes"]["leaf:a"]["prompt"] == "warm"
    assert tree["nodes"]["leaf:b"]["prompt"] == "warm"


def test_global_prompt_selection_requires_balanced_validation_improvement():
    fit = {item_id: _sample(item_id) for item_id in ("a", "b")}
    validation = {item_id: _sample(item_id) for item_id in ("v-no", "v-yes")}
    targets = {"a": "yes", "b": "no"}
    validation_targets = {"v-no": "no", "v-yes": "yes"}

    def judge(prompt, sample):
        item_id = sample["item_id"]
        if prompt == "initial":
            return {"label": validation_targets.get(item_id, "no")}
        if item_id == "v-yes":
            return {"label": "partial"}
        return {"label": targets.get(item_id, validation_targets.get(item_id))}

    tree = CaliTreeBuilder(
        judge=judge,
        optimize=lambda _prompt, _feedback: "warm",
        extract_components=lambda prompt: {
            "criteria": [prompt], "priorities": [], "constraints": [],
        },
        embed=lambda texts: [[1.0, 0.0] for _ in texts],
        merge_prompts=lambda _left, _right: {
            "conflict": True, "conflict_reason": "stop", "prompt": "",
        },
        max_steps=1,
    ).build(
        initial_prompt="initial",
        samples=fit,
        targets=targets,
        validation_samples=validation,
        validation_targets=validation_targets,
    )

    assert tree["global_selection"]["selected"] == "initial"
    assert tree["roots"] == ["global:initial"]
    assert tree["nodes"]["global:initial"]["prompt"] == "initial"


def test_merge_generalization_guard_rejects_regression_on_other_training_cases():
    samples = {item_id: _sample(item_id) for item_id in ("a", "b", "c")}

    def judge(prompt, sample):
        if prompt == "regresses" and sample["item_id"] == "c":
            return {"label": "no"}
        return {"label": "yes"}

    tree = CaliTreeBuilder(
        judge=judge,
        optimize=lambda prompt, _feedback: prompt,
        extract_components=lambda prompt: {
            "criteria": [prompt], "priorities": [], "constraints": [],
        },
        embed=lambda texts: [[1.0, 0.0] for _ in texts],
        merge_prompts=lambda _left, _right: {
            "conflict": False, "prompt": "regresses",
        },
        max_steps=0,
        merge_validation_cap=3,
    ).build(
        initial_prompt="initial",
        samples=samples,
        targets={"a": "yes", "b": "yes", "c": "yes"},
    )

    assert any(
        event["kind"] == "rejected_generalization"
        for event in tree["timeline"]
    )
    assert all(node["prompt"] != "regresses" for node in tree["nodes"].values())


def test_merge_attempt_budget_preserves_unattempted_branches():
    samples = {
        item_id: _sample(item_id)
        for item_id in ("a", "b", "c", "d")
    }
    tree = CaliTreeBuilder(
        judge=lambda _prompt, _sample: {"label": "yes"},
        optimize=lambda prompt, _feedback: prompt,
        extract_components=lambda prompt: {
            "criteria": [prompt], "priorities": [], "constraints": [],
        },
        embed=lambda texts: [[1.0, 0.0] for _ in texts],
        merge_prompts=lambda _left, _right: {
            "conflict": False, "prompt": "merged",
        },
        max_steps=0,
        max_merge_attempts=1,
    ).build(
        initial_prompt="initial",
        samples=samples,
        targets={item_id: "yes" for item_id in samples},
    )

    global_root = tree["nodes"][tree["roots"][0]]
    assert tree["stats"]["merge_attempts"] == 1
    assert tree["stats"]["merge_budget_exhausted"] is True
    assert len(global_root["children"]) == 3
    assert any(
        event["kind"] == "merge_budget_exhausted"
        for event in tree["timeline"]
    )


def test_equivalent_static_generalization_failure_is_pruned():
    samples = {
        item_id: _sample(item_id)
        for item_id in ("a", "b", "c", "d")
    }
    validation = {
        item_id: _sample(item_id)
        for item_id in ("v-no", "v-yes")
    }
    targets = {item_id: "yes" for item_id in samples}
    validation_targets = {"v-no": "no", "v-yes": "yes"}
    merged_validation_calls = 0

    def judge(prompt, sample):
        nonlocal merged_validation_calls
        item_id = sample["item_id"]
        if prompt == "same bad merge":
            if item_id.startswith("v-"):
                merged_validation_calls += 1
                return {"label": "no"}
            return {"label": "yes"}
        if item_id.startswith("v-"):
            return {"label": validation_targets[item_id]}
        return {"label": targets[item_id]}

    tree = CaliTreeBuilder(
        judge=judge,
        optimize=lambda prompt, _feedback: prompt,
        extract_components=lambda prompt: {
            "criteria": [prompt], "priorities": [], "constraints": [],
        },
        embed=lambda texts: [[1.0, 0.0] for _ in texts],
        merge_prompts=lambda _left, _right: {
            "conflict": False, "prompt": "same bad merge",
        },
        max_steps=0,
    ).build(
        initial_prompt="initial",
        samples=samples,
        targets=targets,
        validation_samples=validation,
        validation_targets=validation_targets,
    )

    assert merged_validation_calls == len(validation)
    assert tree["stats"]["merge_attempts"] > 1
    assert tree["stats"]["rejected_merges"] == tree["stats"]["merge_attempts"]
    assert sum(
        event["kind"] == "rejected_generalization"
        for event in tree["timeline"]
    ) == 1
    assert sum(
        event["kind"] == "pruned_equivalent"
        for event in tree["timeline"]
    ) == tree["stats"]["merge_attempts"] - 1


def test_full_merge_is_accepted():
    samples = {item_id: _sample(item_id) for item_id in ("a", "b")}
    tree = _builder(
        lambda _prompt, _sample: {"label": "yes", "rationale": "ok"},
        lambda _left, _right: {"conflict": False, "prompt": "merged"},
    ).build(initial_prompt="initial", samples=samples, targets={"a": "yes", "b": "yes"})
    assert tree["stats"]["accepted_merges"] == 1
    assert tree["stats"]["roots"] == 1
    assert tree["nodes"][tree["roots"][0]]["status"] == "global"
    specialized = tree["nodes"][tree["roots"][0]]["children"]
    assert len(specialized) == 1
    assert tree["nodes"][specialized[0]]["status"] == "accepted"


def test_conflict_preserves_children_as_branches():
    samples = {item_id: _sample(item_id) for item_id in ("a", "b")}
    tree = _builder(
        lambda _prompt, _sample: {"label": "yes"},
        lambda _left, _right: {
            "conflict": True, "conflict_reason": "opposed priorities", "prompt": ""
        },
    ).build(initial_prompt="initial", samples=samples, targets={"a": "yes", "b": "yes"})
    assert tree["stats"]["roots"] == 1
    assert tree["stats"]["specialized_roots"] == 2
    assert any(event["kind"] == "branch" for event in tree["timeline"])


def test_low_accuracy_merge_is_rejected_without_replacing_children():
    samples = {item_id: _sample(item_id) for item_id in ("a", "b")}

    def judge(prompt, _sample):
        return {"label": "no" if prompt == "bad merge" else "yes"}

    tree = _builder(
        judge,
        lambda _left, _right: {"conflict": False, "prompt": "bad merge"},
    ).build(initial_prompt="initial", samples=samples, targets={"a": "yes", "b": "yes"})
    assert tree["stats"]["accepted_merges"] == 0
    assert tree["stats"]["rejected_merges"] == 1
    assert len([
        event for event in tree["timeline"] if event["kind"] == "rejected"
    ]) == 1
    global_root = tree["nodes"][tree["roots"][0]]
    assert set(global_root["children"]) == {"leaf:a", "leaf:b"}


def _additive_builder(judge, merge, *, max_steps=0):
    return CaliTreeBuilder(
        judge=judge,
        optimize=lambda prompt, _feedback: prompt,
        extract_components=lambda prompt: {
            "criteria": [prompt], "priorities": [], "constraints": ["json"]
        },
        embed=lambda texts: [[1.0, 0.0] for _ in texts],
        merge_prompts=merge,
        max_steps=max_steps,
        specialization_mode="additive",
    )


def test_additive_mode_sets_balanced_objective_and_validates_params():
    builder = _additive_builder(
        lambda _p, _s: {"label": "yes"},
        lambda _l, _r: {"conflict": False, "prompt": "m"},
    )
    # Additive mode implies the balanced, no-regression-vs-base objective.
    assert builder.merge_objective == "balanced"
    assert builder.require_ge_base is True
    with pytest.raises(ValueError):
        CaliTreeBuilder(
            judge=lambda _p, _s: {"label": "yes"},
            optimize=lambda p, _f: p,
            extract_components=lambda p: {"criteria": [p], "priorities": [], "constraints": []},
            embed=lambda texts: [[1.0, 0.0] for _ in texts],
            merge_prompts=lambda _l, _r: {"conflict": False, "prompt": "m"},
            specialization_mode="bogus",
        )


def test_root_objective_defaults_to_balanced_and_validates():
    builder = _additive_builder(
        lambda _p, _s: {"label": "yes"},
        lambda _l, _r: {"conflict": False, "prompt": "m"},
    )
    assert builder.root_objective == "balanced"
    with pytest.raises(ValueError):
        CaliTreeBuilder(
            judge=lambda _p, _s: {"label": "yes"},
            optimize=lambda p, _f: p,
            extract_components=lambda p: {"criteria": [p], "priorities": [], "constraints": []},
            embed=lambda texts: [[1.0, 0.0] for _ in texts],
            merge_prompts=lambda _l, _r: {"conflict": False, "prompt": "m"},
            root_objective="bogus",
        )


def test_additive_root_accumulates_widest_validated_merge():
    samples = {item_id: _sample(item_id) for item_id in ("a", "b")}
    tree = _additive_builder(
        lambda _prompt, _sample: {"label": "yes", "rationale": "ok"},
        lambda _left, _right: {"conflict": False, "prompt": "merged"},
    ).build(initial_prompt="base", samples=samples, targets={"a": "yes", "b": "yes"})
    assert tree["stats"]["accepted_merges"] == 1
    assert tree["stats"]["root_source"] == "accumulated"
    # The root prompt IS the accumulated merge, not a fallback.
    assert tree["nodes"][tree["roots"][0]]["prompt"] == "merged"
    assert tree["config"]["specialization_mode"] == "additive"
    assert tree["config"]["route_default_to_root"] is True


def test_additive_root_falls_back_to_base_when_no_merge_accepted():
    samples = {item_id: _sample(item_id) for item_id in ("a", "b")}
    tree = _additive_builder(
        lambda _prompt, _sample: {"label": "yes"},
        lambda _left, _right: {
            "conflict": True, "conflict_reason": "opposed", "prompt": ""
        },
    ).build(initial_prompt="base", samples=samples, targets={"a": "yes", "b": "yes"})
    assert tree["stats"]["accepted_merges"] == 0
    assert tree["stats"]["root_source"] == "base"
    # Root can never be worse than the flat base: it is the base rubric itself.
    assert tree["nodes"][tree["roots"][0]]["prompt"] == "base"


def test_additive_merge_rejected_when_it_regresses_minority_on_guard():
    samples = {
        "a": {**_sample("a"), "gold": "yes"},
        "b": {**_sample("b"), "gold": "yes"},
    }
    validation = {
        "v_no": {**_sample("v_no"), "gold": "no"},
        "v_yes": {**_sample("v_yes"), "gold": "yes"},
    }

    def judge(prompt, sample):
        # The merged delta over-predicts yes, regressing the `no` guard case.
        if "merged" in prompt:
            return {"label": "yes"}
        return {"label": sample["gold"]}

    tree = _additive_builder(
        judge,
        lambda _left, _right: {"conflict": False, "prompt": "merged"},
    ).build(
        initial_prompt="base",
        samples=samples,
        targets={"a": "yes", "b": "yes"},
        validation_samples=validation,
        validation_targets={"v_no": "no", "v_yes": "yes"},
    )
    assert tree["stats"]["accepted_merges"] == 0
    assert tree["stats"]["root_source"] == "base"
    assert any(
        event["kind"] == "rejected_generalization" for event in tree["timeline"]
    )


def test_additive_routing_defaults_to_root_below_near_exact_match():
    tree = {
        "roots": ["root"],
        "config": {
            "route_default_to_root": True,
            "singleton_exact_threshold": 0.995,
            "min_routing_support": 1,
        },
        "nodes": {
            "root": {
                "id": "root", "embedding": [1.0, 0.0], "children": ["child"],
                "covered_ids": ["a", "b"], "routing_threshold": -1.0, "prompt": "ROOT",
            },
            "child": {
                "id": "child", "embedding": [0.9, 0.1], "children": [],
                "covered_ids": ["a"], "routing_threshold": 0.5, "prompt": "CHILD",
            },
        },
    }
    # cos([0.8,0.2],[0.9,0.1]) ~= 0.991 < 0.995 -> stays at the strong root.
    stayed = route_prompt(tree, [0.8, 0.2])
    assert stayed["id"] == "root"
    # Without the flag the same case would divert (threshold 0.5).
    tree["config"]["route_default_to_root"] = False
    diverted = route_prompt(tree, [0.8, 0.2])
    assert diverted["id"] == "child"


def test_routing_ignores_leaf_that_failed_held_out_guard():
    tree = {
        "roots": ["root"],
        "config": {"min_routing_support": 1},
        "nodes": {
            "root": {
                "id": "root", "embedding": [0.0, 1.0], "children": ["leaf"],
                "covered_ids": ["a"], "routing_threshold": -1.0, "prompt": "ROOT",
            },
            "leaf": {
                "id": "leaf", "embedding": [1.0, 0.0], "children": [],
                "covered_ids": ["a"], "routing_threshold": 0.0, "prompt": "LEAF",
                "routing_eligible": False,
            },
        },
    }
    routed = route_prompt(tree, [1.0, 0.0])
    assert routed["id"] == "root"
    assert routed["route_path"] == ["root"]


def test_prediction_conditioned_routing_uses_supported_key_and_safe_fallback():
    tree = {
        "roots": ["root"],
        "config": {"min_routing_support": 2},
        "prediction_conditioned_router": {
            "routes": {"specific": "good", "rejected": "bad"},
        },
        "nodes": {
            "root": {
                "id": "root", "embedding": [0.0, 1.0], "children": ["good", "bad"],
                "covered_ids": ["a", "b"], "prompt": "ROOT",
            },
            "good": {
                "id": "good", "embedding": [0.0, 1.0], "children": [],
                "covered_ids": ["a", "b"], "prompt": "GOOD",
                "routing_eligible": True, "routing_validation_support": 2,
            },
            "bad": {
                "id": "bad", "embedding": [1.0, 0.0], "children": [],
                "covered_ids": ["c", "d"], "prompt": "BAD",
                "routing_eligible": False, "routing_validation_support": 2,
            },
        },
    }

    routed = route_prompt(
        tree, [1.0, 0.0], routing_keys=["specific", "prediction"]
    )
    assert routed["id"] == "good"
    assert routed["route_basis"] == "top_prediction_context"
    assert routed["routing_key"] == "specific"

    fallback = route_prompt(tree, [1.0, 0.0], routing_keys=["rejected"])
    assert fallback["id"] == "root"
    assert fallback["route_basis"] == "top_prediction_fallback"
    assert route_prompt(tree, [1.0, 0.0])["id"] == "root"


def test_partial_merge_promotes_incorrect_original_leaf():
    item_ids = tuple(str(index) for index in range(8))
    samples = {item_id: _sample(item_id) for item_id in item_ids}
    merge_calls = 0

    def merge(_left, _right):
        nonlocal merge_calls
        merge_calls += 1
        if merge_calls == 7:
            return {"conflict": False, "prompt": "partial-top"}
        if merge_calls > 7:
            return {"conflict": True, "conflict_reason": "stop", "prompt": ""}
        return {"conflict": False, "prompt": f"full-{merge_calls}"}

    def judge(prompt, sample):
        if prompt == "partial-top" and sample["item_id"] == "7":
            return {"label": "no"}
        return {"label": "yes"}

    tree = _builder(judge, merge).build(
        initial_prompt="initial",
        samples=samples,
        targets={item_id: "yes" for item_id in item_ids},
    )
    partials = [node for node in tree["nodes"].values() if node["status"] == "partial"]
    promoted = [node for node in tree["nodes"].values() if node["status"] == "promoted"]
    assert len(partials) == 1
    assert partials[0]["validation_accuracy"] == 7 / 8
    assert partials[0]["covered_ids"] == [str(index) for index in range(7)]
    assert [node["covered_ids"] for node in promoted] == [["7"]]


def test_routing_selects_deepest_valid_child_and_falls_back_to_root():
    tree = {
        "roots": ["root"],
        "nodes": {
            "root": {
                "id": "root", "prompt": "root prompt", "embedding": [0, 1],
                "children": ["child"], "routing_threshold": 0.7,
            },
            "child": {
                "id": "child", "prompt": "child prompt", "embedding": [1, 0],
                "children": [], "routing_threshold": 0.9,
            },
        },
    }
    assert route_prompt(tree, [1, 0])["id"] == "child"
    fallback = route_prompt(tree, [0, 1])
    assert fallback["id"] == "root"
    assert fallback["route_path"] == ["root"]


def test_builder_routes_with_case_centroids_not_generic_rubric_embeddings():
    samples = {item_id: _sample(item_id) for item_id in ("a", "b")}

    def embed(texts):
        mapping = {"route-a": [1.0, 0.0], "route-b": [0.0, 1.0]}
        return [mapping.get(text, [0.5, 0.5]) for text in texts]

    tree = CaliTreeBuilder(
        judge=lambda _prompt, _sample: {"label": "yes"},
        optimize=lambda prompt, _feedback: prompt,
        extract_components=lambda prompt: {
            "criteria": [prompt], "priorities": [], "constraints": [],
        },
        embed=embed,
        merge_prompts=lambda _left, _right: {
            "conflict": False, "prompt": "merged",
        },
        max_steps=0,
    ).build(
        initial_prompt="initial",
        samples=samples,
        targets={"a": "yes", "b": "yes"},
        routing_texts={"a": "route-a", "b": "route-b"},
    )

    assert route_prompt(tree, [1.0, 0.0])["id"] == "leaf:a"
    assert route_prompt(tree, [0.0, 1.0])["id"] == "leaf:b"


def test_unseen_case_falls_back_to_global_instead_of_singleton_leaf():
    samples = {item_id: _sample(item_id) for item_id in ("a", "b")}

    def embed(texts):
        mapping = {"route-a": [1.0, 0.0], "route-b": [0.0, 1.0]}
        return [mapping.get(text, [0.5, 0.5]) for text in texts]

    tree = CaliTreeBuilder(
        judge=lambda _prompt, _sample: {"label": "yes"},
        optimize=lambda prompt, _feedback: prompt,
        extract_components=lambda prompt: {
            "criteria": [prompt], "priorities": [], "constraints": [],
        },
        embed=embed,
        merge_prompts=lambda _left, _right: {
            "conflict": True, "conflict_reason": "keep leaves", "prompt": "",
        },
        max_steps=0,
        min_routing_support=2,
    ).build(
        initial_prompt="initial",
        samples=samples,
        targets={"a": "yes", "b": "yes"},
        routing_texts={"a": "route-a", "b": "route-b"},
    )

    assert route_prompt(tree, [1.0, 0.0])["id"] == "leaf:a"
    assert route_prompt(tree, [0.7, 0.7])["id"] == tree["roots"][0]


def test_task_grouped_leaves_jointly_optimize_editor_outputs():
    samples = {
        "task-a::SDEdit": _sample("task-a::SDEdit"),
        "task-a::DiffEdit": _sample(
            "task-a::DiffEdit", editor="DiffEdit"
        ),
        "task-b::SDEdit": _sample("task-b::SDEdit"),
    }
    optimized_case_sets = []

    def judge(_prompt, _sample):
        return {"label": "yes"}

    builder = CaliTreeBuilder(
        judge=judge,
        optimize=lambda prompt, _feedback: prompt,
        extract_components=lambda prompt: {
            "criteria": [prompt],
            "priorities": [],
            "constraints": [],
        },
        embed=lambda texts: [[1.0, 0.0] for _ in texts],
        merge_prompts=lambda _left, _right: {
            "conflict": True,
            "conflict_reason": "keep task branches",
            "prompt": "",
        },
        max_steps=0,
    )
    original = builder._optimize_for_cases

    def record(prompt, ids, case_samples, targets):
        optimized_case_sets.append(tuple(ids))
        return original(prompt, ids, case_samples, targets)

    builder._optimize_for_cases = record
    tree = builder.build(
        initial_prompt="initial",
        samples=samples,
        targets={item_id: "yes" for item_id in samples},
        leaf_groups={
            "task-a::SDEdit": "task-a",
            "task-a::DiffEdit": "task-a",
            "task-b::SDEdit": "task-b",
        },
    )

    assert tree["stats"]["leaves"] == 2
    assert tree["stats"]["leaf_cases"] == 3
    assert tree["nodes"]["leaf:task-a"]["covered_ids"] == [
        "task-a::DiffEdit",
        "task-a::SDEdit",
    ]
    assert (
        "task-a::DiffEdit", "task-a::SDEdit"
    ) in optimized_case_sets


def test_metrics_include_confusion_distribution_and_per_editor():
    samples = {"a": _sample("a"), "b": _sample("b", editor="DiffEdit")}
    report = classification_metrics(
        {"a": "yes", "b": "partial"}, {"a": "yes", "b": "no"}, samples
    )
    assert report["accuracy"] == 0.5
    assert report["balanced_accuracy"] == 0.5
    assert report["per_label_accuracy"] == {"no": None, "partial": 0.0, "yes": 1.0}
    assert report["per_label_precision"] == {"no": 0.0, "partial": None, "yes": 1.0}
    assert report["per_label_f1"] == {"no": None, "partial": None, "yes": 1.0}
    assert report["macro_f1"] == 1.0
    assert report["confusion"]["partial"]["no"] == 1
    assert report["prediction_distribution"] == {"no": 1, "partial": 0, "yes": 1}
    assert report["per_editor"]["SDEdit"]["accuracy"] == 1


def test_metrics_include_ordinal_mae():
    samples = {"a": _sample("a"), "b": _sample("b", editor="DiffEdit")}
    # a: yes->yes has ordinal error 0; b: partial->no has |0.5-0.0|=0.5.
    report = classification_metrics(
        {"a": "yes", "b": "partial"}, {"a": "yes", "b": "no"}, samples
    )
    assert report["ordinal_mae"] == 0.25
    assert report["per_editor"]["SDEdit"]["ordinal_mae"] == 0.0
    assert report["per_editor"]["DiffEdit"]["ordinal_mae"] == 0.5


def test_metrics_count_missing_predictions_as_invalid_errors():
    samples = {"a": _sample("a"), "b": _sample("b")}
    report = classification_metrics(
        {"a": "yes", "b": "no"}, {"a": "yes"}, samples
    )
    assert report["n"] == 2
    assert report["accuracy"] == 0.5
    assert report["per_label_accuracy"]["no"] == 0.0
    assert report["prediction_distribution"]["invalid"] == 1
    assert report["confusion"]["no"]["invalid"] == 1


def test_ordinal_mae_ignores_unknown_labels():
    from vejudge.core.calibration.calitree import ordinal_absolute_error

    assert ordinal_absolute_error("no", "yes") == 1.0
    assert ordinal_absolute_error("partial", "yes") == 0.5
    assert ordinal_absolute_error("yes", "needs_human") is None
    # An unrepresented prediction does not silently count toward MAE.
    report = classification_metrics(
        {"a": "yes"}, {"a": "needs_human"}, {"a": _sample("a")}
    )
    assert report["ordinal_mae"] is None
