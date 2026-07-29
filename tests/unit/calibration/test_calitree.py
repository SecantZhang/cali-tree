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
