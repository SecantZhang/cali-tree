"""Modular orchestration using the builder's shared strategies and node factory."""

from copy import deepcopy
from dataclasses import asdict, replace
from itertools import combinations
import math

from .context import BuildContext
from .decomposition.artifacts import ArtifactExecutor, TwoWayAdapter, prompt_hash
from .decomposition.decomposition_twoway import DecompositionTwoWay
from .evaluation import balanced_accuracy
from .geometry import centroid, cosine_similarity, similarity_threshold
from .merge.coordinator import MergeCoordinator
from .node.artifacts import VERSION, snapshot, validate_tree
from .node.leaf_controller import LeafController
from .optimization.composite import OptimizerPlan, SelectedPromptOptimizer
from .optimization.gepa import resolve_gepa_python


def build_modular(builder, *, initial_prompt, samples, targets, routing_texts=None,
                  validation_samples=None, validation_targets=None,
                  validation_routing_texts=None, validation_leaf_groups=None,
                  semantic_groups=None, leaf_groups=None):
    validation_samples, validation_targets = validation_samples or {}, validation_targets or {}
    if set(targets) - set(samples) or set(validation_targets) - set(validation_samples):
        raise ValueError("Targets refer to missing samples")
    if set(targets) & set(validation_targets):
        raise ValueError("Fit and reserved validation cases must be disjoint")
    if any(label not in {"no", "partial", "yes"} for label in
           [*targets.values(), *validation_targets.values()]):
        raise ValueError("Modular targets must use no/partial/yes")
    adapter = builder.decomposition
    if adapter is None:
        adapter = TwoWayAdapter(DecompositionTwoWay(builder.decomposition_engine))
    executor = ArtifactExecutor(adapter, builder.checkpoint)
    executor.preflight({**samples, **validation_samples})
    if not builder._custom_leaf_optimizer and ("gepa" in builder.optimizer_plan or builder.optimizer_plan == "best_of_both"):
        resolve_gepa_python(builder.gepa_python)
        if builder.reflect is None:
            raise ValueError("GEPA requires reflect=...")
    services = replace(builder._services(), judge=executor.judge, judge_many=executor.judge_many)
    # Reset per-build mutable state. Reusing a builder must not join timelines/caches.
    builder.timeline = []
    context = BuildContext(services, builder._settings(), None, initial_prompt,
                           samples, targets, validation_samples, validation_targets,
                           builder.timeline, executor=executor, checkpoint=builder.checkpoint)
    shared_optimizer = (builder.prompt_optimizer if builder._custom_prompt_optimizer else
                        SelectedPromptOptimizer(context.settings, executor, builder.checkpoint))
    optimization_reports = {}

    def optimize_cases(prompt, ids, case_samples, case_targets):
        result = shared_optimizer.optimize(prompt, ids, case_samples, case_targets,
                                          services=services, max_steps=builder.max_steps)
        optimization_reports[prompt_hash(result.prompt)] = result.report
        return result.as_tuple()

    context.optimize_cases = optimize_cases
    ids = context.item_ids
    route_text = routing_texts or {key: (samples[key].get("instruction") or
                                      (samples[key].get("input") or {}).get("instruction", "")) for key in ids}
    validation_route_text = validation_routing_texts or {
        key: (validation_samples[key].get("instruction") or
              (validation_samples[key].get("input") or {}).get("instruction", ""))
        for key in context.validation_ids}
    all_route_ids = ids + context.validation_ids
    texts = [route_text[key] for key in ids] + [validation_route_text[key] for key in context.validation_ids]
    context.case_embeddings = dict(zip(all_route_ids, services.embed(texts))) if texts else {}
    if len(context.case_embeddings) != len(all_route_ids):
        raise ValueError("Embedding callback returned the wrong number of vectors")
    context.warm_prompt = initial_prompt
    if ids:
        context.initial_accuracy, _, initial_results = services.validate(initial_prompt, ids, samples, targets)
        context.warm_accuracy, context.warm_results = context.initial_accuracy, initial_results
        if builder.warm_start:
            prompt, accuracy, _, results, steps = optimize_cases(initial_prompt, ids, samples, targets)
            context.warm_prompt, context.warm_accuracy, context.warm_results = prompt, accuracy, results
            context.timeline.append({"kind": "warm_start", "steps": steps, "accuracy": accuracy})
    else:
        executor.policy(initial_prompt)
    grouped = {}
    for key in ids:
        grouped.setdefault(str((leaf_groups or {}).get(key) or key), []).append(key)
    leaf_optimizer = builder.leaf_optimizer if builder._custom_leaf_optimizer else OptimizerPlan(
        builder.optimizer_plan, gepa_python=builder.gepa_python, seed=builder.optimizer_seed)
    controller = LeafController(leaf_optimizer, builder.node_factory)
    active, source_for_case = [], {}
    for group_id, group_ids in sorted(grouped.items()):
        result = controller.build(context.warm_prompt, group_ids, context,
                                  node_id=f"leaf:{group_id}", semantic_groups=semantic_groups)
        context.nodes[result.node.id], context.artifacts[result.node.id] = result.node, result.snapshot
        active.append(result.node)
        for key in group_ids:
            source_for_case[key] = result.node.id
        context.timeline.append({"kind": "leaf", "node_id": result.node.id,
                                 "accuracy": result.optimization.accuracy,
                                 "steps": result.optimization.steps, "cases": len(group_ids)})
        if builder.progress:
            builder.progress("calitree_leaf", {"completed": len(active), "total": len(grouped),
                                               "cases": len(group_ids)})
    builder.clustering.prepare(active, context)
    coordinator = MergeCoordinator(builder.merge_algorithm, builder.merge_acceptance_policy)
    blocked_pairs, blocked_groups = set(), set()
    attempted = accepted = rejected = promoted = 0
    max_levels = math.ceil((builder.similarity_start - builder.similarity_floor) / builder.similarity_decay) + 1
    for level in range(max_levels):
        threshold = similarity_threshold(level, start=builder.similarity_start,
                                         decay=builder.similarity_decay, floor=builder.similarity_floor)
        groups, remaining = builder.clustering.groups(active, threshold, level=level,
                            max_children=builder.max_merge_children, blocked_pairs=blocked_pairs,
                            blocked_groups=blocked_groups, context=context)
        for index, (children, similarity) in enumerate(groups):
            if attempted >= builder.max_merge_attempts:
                remaining.extend(node for pending, _ in groups[index:] for node in pending)
                break
            child_ids = [node.id for node in children]
            failing = []
            for left, right in combinations(children, 2):
                pair = builder.clustering.probe(left, right, context)
                similarity = min(similarity, pair.similarity)
                if pair.similarity < threshold:
                    failing.append(frozenset((left.id, right.id)))
            if failing:
                blocked_pairs.update(failing)
                remaining.extend(children)
                context.timeline.append({"kind": "rejected_transfer", "children": child_ids})
                continue
            attempted += 1
            merge_id = f"merge:{attempted}"
            result = coordinator.merge_many(children, context)
            context.timeline.append({"kind": result.decision.kind, "node_id": merge_id,
                                     "children": child_ids, "similarity": similarity,
                                     "reason": result.conflict_reason,
                                     **result.decision.diagnostics})
            if not result.decision.accepted:
                blocked_groups.add(frozenset(child_ids))
                remaining.extend(children)
                rejected += 1
                continue
            optimization = result.optimization
            components = services.extract_components(optimization.prompt)
            criteria = services.embed([builder.component_text(components)])[0]
            status = "accepted" if optimization.accuracy == 1 else "partial"
            parent = builder.node_factory.merge(id=merge_id, prompt=optimization.prompt,
                covered_ids=result.served_ids, children=child_ids,
                embedding=centroid(context.case_embeddings[key] for key in result.served_ids),
                components=components, level=1 + max(node.level for node in children), status=status,
                validation_accuracy=optimization.accuracy,
                criteria_embedding=criteria, member_embeddings=[embedding for node in children for embedding in node.member_embeddings],
                semantic_groups=sorted({g for node in children for g in node.semantic_groups}),
                generalization_accuracy=result.decision.generalization_accuracy, routing_eligible=False)
            context.nodes[parent.id] = parent
            context.artifacts[parent.id] = snapshot(parent, scope_ids=result.covered_ids,
                served_ids=result.served_ids,
                predictions={"accuracy": optimization.accuracy, "correct_ids": optimization.correct_ids,
                             "balanced_accuracy": balanced_accuracy(result.covered_ids, targets, optimization.predictions),
                             "predictions": optimization.predictions},
                strategy={"decomposition": adapter.name, "merge": type(builder.merge_algorithm).__name__,
                          "optimizer": "textgrad", "acceptance": type(builder.merge_acceptance_policy).__name__},
                provenance={"children": child_ids, "optimization": optimization_reports.get(prompt_hash(parent.prompt), {})})
            builder.clustering.refresh(parent, context)
            remaining.append(parent)
            accepted += 1
            residual = {key for node in children for key in context.artifacts[node.id]["served_ids"]} - set(result.served_ids)
            for key in sorted(residual):
                source = context.nodes[source_for_case[key]]
                accuracy, correct, predictions = services.validate(source.prompt, [key], samples, targets)
                promoted += 1
                fields = asdict(source)
                fields.update(id=f"promoted:{promoted}:{key}", children=[], covered_ids=[key],
                              level=parent.level, status="promoted", validation_accuracy=accuracy,
                              embedding=context.case_embeddings[key], routing_eligible=False)
                node = builder.node_factory.promoted_leaf(**fields)
                context.nodes[node.id] = node
                context.artifacts[node.id] = snapshot(node, scope_ids=[key], served_ids=[key],
                    predictions={"accuracy": accuracy, "correct_ids": correct, "predictions": predictions},
                    strategy=context.artifacts[source.id]["strategy_manifest"],
                    provenance={"source_leaf": source.id, "source_revision": 1})
                remaining.append(node)
            if builder.progress:
                builder.progress("calitree_merge", {"children": len(children), "accepted": accepted,
                                                    "attempts": attempted})
        active = sorted(remaining, key=lambda node: node.id)
        if attempted >= builder.max_merge_attempts or len(active) < 2:
            break
    selection = builder.root_selector.select(context, accepted_merges=accepted)
    components = services.extract_components(selection.prompt)
    global_id = f"global:{selection.source}"
    root = builder.node_factory.global_node(id=global_id, prompt=selection.prompt, covered_ids=ids,
        embedding=centroid(context.case_embeddings[key] for key in ids), components=components,
        level=1 + max((node.level for node in active), default=0), status="global",
        children=[node.id for node in active], routing_threshold=-1, routing_eligible=True)
    executor.policy(root.prompt)
    accuracy, correct, predictions = services.validate(root.prompt, ids, samples, targets) if ids else (0, [], {})
    root.validation_accuracy = accuracy
    context.nodes[root.id] = root
    context.artifacts[root.id] = snapshot(root, scope_ids=ids, served_ids=ids,
        predictions={"accuracy": accuracy, "correct_ids": correct, "predictions": predictions},
        strategy={"decomposition": adapter.name, "root": selection.source})
    # Calibrate routing using observable geometry, then compare each cohort with the fallback.
    builder.routing_calibrator.calibrate(context.nodes, context.case_embeddings, margin=builder.routing_margin)
    specialized = [node for node in context.nodes.values() if node.id != root.id]
    cohorts = {node.id: [] for node in specialized}
    for key in context.validation_ids:
        if specialized:
            best = max(specialized, key=lambda node: (cosine_similarity(node.embedding, context.case_embeddings[key]), node.id))
            if cosine_similarity(best.embedding, context.case_embeddings[key]) >= best.routing_threshold:
                cohorts[best.id].append(key)
    for node in specialized:
        cohort = cohorts[node.id]
        node.routing_validation_support = len(cohort)
        if cohort:
            raw, _, rows = services.validate(node.prompt, cohort, validation_samples, validation_targets)
            baseline, _, _ = services.validate(root.prompt, cohort, validation_samples, validation_targets)
            node.routing_validation_accuracy, node.routing_baseline_accuracy = raw, baseline
            context.artifacts[node.id]["validation"] = {"accuracy": raw, "baseline_accuracy": baseline,
                "support": len(cohort), "evaluation_refs": {key: row["evaluation_ref"] for key, row in rows.items()}}
            node.routing_eligible = len(cohort) >= builder.min_routing_support and raw > baseline + builder.global_min_validation_gain
    bundle = {"version": VERSION, "nodes": context.artifacts, "policies": deepcopy(executor.policies),
              "evaluations": deepcopy(executor.evaluations)}
    config = {"modular_mode": True, "decomposition_strategy": adapter.name,
              "optimizer_plan": builder.optimizer_plan, "optimizer_seed": builder.optimizer_seed,
              "optimizer_identity": deepcopy(services.optimizer_identity),
              "merge_strategy": type(builder.merge_algorithm).__name__, "max_merge_children": builder.max_merge_children,
              "min_routing_support": builder.min_routing_support,
              "singleton_exact_threshold": builder.singleton_exact_threshold,
              "max_steps": builder.max_steps, "merge_acceptance": builder.merge_acceptance,
              "settings": asdict(context.settings), "max_merge_attempts": builder.max_merge_attempts,
              "similarity_start": builder.similarity_start, "similarity_decay": builder.similarity_decay,
              "similarity_floor": builder.similarity_floor, "routing_margin": builder.routing_margin}
    tree = {"version": VERSION, "roots": [root.id], "nodes": {key: asdict(node) for key, node in context.nodes.items()},
            "artifacts": bundle, "config": config, "timeline": context.timeline,
            "warm_start_prompt": context.warm_prompt, "warm_start_accuracy": context.warm_accuracy,
            "warm_start_steps": sum(event.get("steps", 0) for event in context.timeline if event["kind"] == "warm_start"),
            "global_selection": selection.report,
            "stats": {"leaves": len(grouped), "accepted_merges": accepted, "rejected_merges": rejected,
                      "promoted": promoted, "roots": 1, "specialized_roots": len(active),
                      "merge_attempts": attempted, "merge_budget_exhausted": attempted >= builder.max_merge_attempts,
                      "root_source": selection.source}}
    validate_tree(tree, executor)
    return tree
