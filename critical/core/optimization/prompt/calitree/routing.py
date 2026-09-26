"""Route predictions through a trained CaliTree."""

from __future__ import annotations

from typing import Any, Optional

from .geometry import cosine_similarity

def route_prompt(
    tree: dict[str, Any],
    embedding: list[float],
    *,
    routing_keys: Optional[list[str]] = None,
) -> dict[str, Any]:
    nodes = tree.get("nodes") or {}
    roots = [node_id for node_id in tree.get("roots") or [] if node_id in nodes]
    if not roots:
        raise ValueError("Cali-Tree contains no routable roots")

    def similarity(node_id: str) -> float:
        return cosine_similarity(embedding, nodes[node_id].get("embedding") or [])

    current_id = max(roots, key=lambda node_id: (similarity(node_id), node_id))
    residual_router = tree.get("prediction_conditioned_router") or {}
    if residual_router:
        routes = residual_router.get("routes") or {}
        config = tree.get("config") or {}
        min_support = max(1, int(config.get("min_routing_support") or 1))
        for key in routing_keys or []:
            target_id = routes.get(key)
            target = nodes.get(target_id) or {}
            if (
                target_id in nodes
                and target.get("routing_eligible", False)
                and int(
                    target.get("routing_support")
                    or target.get("routing_validation_support")
                    or 0
                ) >= min_support
            ):
                selected = dict(target)
                selected["route_path"] = [current_id, target_id]
                selected["route_similarity"] = similarity(target_id)
                selected["route_basis"] = "top_prediction_context"
                selected["routing_key"] = key
                return selected
        # Prediction-conditioned trees never fall through to a semantically nearby leaf:
        # an unsupported or rejected correction must preserve the validated top prompt.
        selected = dict(nodes[current_id])
        selected["route_path"] = [current_id]
        selected["route_similarity"] = similarity(current_id)
        selected["route_basis"] = "top_prediction_fallback"
        selected["routing_key"] = None
        return selected
    path = [current_id]
    while True:
        current = nodes[current_id]
        children = [child for child in current.get("children") or [] if child in nodes]
        if not children:
            break
        config = tree.get("config") or {}
        min_support = max(1, int(config.get("min_routing_support") or 1))
        singleton_exact = float(config.get("singleton_exact_threshold") or 0.995)
        eligible = [
            child
            for child in children
            if nodes[child].get("routing_eligible", True)
            and (
                len(nodes[child].get("covered_ids") or []) >= min_support
                or similarity(child) >= singleton_exact
            )
        ]
        if not eligible:
            break
        candidate = max(eligible, key=lambda node_id: (similarity(node_id), node_id))
        # In additive mode the root already carries the accumulated deltas, so a case only
        # diverts to a specialized child on a near-exact match; otherwise the strong root
        # (which is validated >= the flat base) handles it, and routing cannot hurt.
        threshold = float(nodes[candidate].get("routing_threshold") or 0.70)
        if config.get("route_default_to_root"):
            threshold = max(threshold, singleton_exact)
        if similarity(candidate) < threshold:
            break
        current_id = candidate
        path.append(current_id)
    selected = dict(nodes[current_id])
    selected["route_path"] = path
    selected["route_similarity"] = similarity(current_id)
    return selected
