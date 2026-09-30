"""Versioned snapshots alongside the unchanged legacy node dataclasses."""

from copy import deepcopy

from ..decomposition.artifacts import prompt_hash

VERSION = "calitree-modular-v1"


def snapshot(node, *, scope_ids, served_ids, predictions, strategy, provenance=None):
    return {"id": node.id, "kind": "global" if node.status == "global" else
            ("merge" if node.children else "leaf"), "revision": 1,
            "prompt_sha256": prompt_hash(node.prompt), "policy_ref": prompt_hash(node.prompt),
            "children": list(node.children), "scope_ids": sorted(set(scope_ids)),
            "served_ids": sorted(set(served_ids)),
            "correct_ids": sorted(k for k in scope_ids if k in predictions.get("correct_ids", [])),
            "evaluation_refs": {k: v["evaluation_ref"] for k, v in
                                predictions.get("predictions", {}).items()},
            "fit": {k: deepcopy(v) for k, v in predictions.items() if k != "predictions"},
            "strategy_manifest": deepcopy(strategy), "provenance": deepcopy(provenance or {})}


def validate_tree(tree, executor):
    if tree.get("version") != VERSION:
        raise ValueError("Unsupported modular tree version")
    bundle = tree.get("artifacts") or {}
    if bundle.get("version") != VERSION:
        raise ValueError("Missing modular artifact bundle")
    executor.load_policies(bundle.get("policies", {}), strategy=tree["config"]["decomposition_strategy"])
    nodes, snapshots = tree.get("nodes", {}), bundle.get("nodes", {})
    if set(nodes) != set(snapshots) or not tree.get("roots"):
        raise ValueError("Incomplete node artifact bundle")
    for root in tree["roots"]:
        if root not in nodes:
            raise ValueError("Missing root")
    visited, visiting = set(), set()

    def visit(key):
        if key in visiting:
            raise ValueError("Cycle in modular tree")
        if key in visited:
            return
        if key not in nodes:
            raise ValueError("Missing child node")
        node, snap = nodes[key], snapshots[key]
        policy_ref = snap.get("policy_ref")
        if (node["id"] != key or snap.get("id") != key or
                snap.get("prompt_sha256") != prompt_hash(node["prompt"]) or
                policy_ref != snap["prompt_sha256"] or policy_ref not in executor.policies):
            raise ValueError("Node/policy binding mismatch")
        children = node.get("children", [])
        if children != snap.get("children") or len(set(children)) != len(children):
            raise ValueError("Invalid node children")
        if not set(snap["served_ids"]) <= set(snap["scope_ids"]):
            raise ValueError("Served cases are outside node scope")
        if not set(snap.get("correct_ids", [])) <= set(snap["scope_ids"]):
            raise ValueError("Correct cases are outside node scope")
        if any(ref not in bundle.get("evaluations", {}) for ref in snap.get("evaluation_refs", {}).values()):
            raise ValueError("Unresolved evaluation reference")
        visiting.add(key)
        for child in children:
            visit(child)
        if snap.get("kind") == "merge":
            if len(children) < 2:
                raise ValueError("A merge artifact requires at least two children")
            child_scope = {case for child in children for case in snapshots[child]["scope_ids"]}
            if set(snap["scope_ids"]) != child_scope:
                raise ValueError("Parent scope differs from descendant scope union")
            if node["level"] != 1 + max(nodes[child]["level"] for child in children):
                raise ValueError("Parent depth differs from child depths")
        visiting.remove(key)
        visited.add(key)

    for key in nodes:
        visit(key)
    return tree
