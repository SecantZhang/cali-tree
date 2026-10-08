"""CaliTree prompt hierarchy builder."""

from __future__ import annotations

from dataclasses import asdict, fields
from typing import Any, Callable, Optional

from .geometry import centroid, similarity_threshold
from .node import CaliTreeNode, NodeFactory, DefaultNodeFactory
from .context import BuildContext, CaliTreeServices, CaliTreeSettings
from .evaluation import balanced_accuracy, balanced_case_subset, behavior_profile
from .optimization import (
    PromptOptimizer, FeedbackPromptOptimizer, LeafOptimizer, DefaultLeafOptimizer,
)
from .clustering import (
    ClusteringAlgorithm, SemanticCompleteLinkClustering, BehavioralCompleteLinkClustering,
)
from .merge import (
    MergeAlgorithm, CallbackMergeAlgorithm, MergeAcceptancePolicy, GuardedMergeAcceptance,
    MergeCoordinator,
)
from .root import RootSelector, ValidatedRootSelector
from .routing_calibration import RoutingCalibrator, GeometryRoutingCalibrator


class CaliTreeBuilder:
    @staticmethod
    def build_program_leaves(cases, *, reference_labels, optimizer_factory, seeds=None):
        """Fit one independently executable program per case; no shared leaf selection."""
        from .node.program_leaf import ProgramLeafController
        return ProgramLeafController(optimizer_factory).build(tuple(cases), reference_labels, seeds=seeds)

    def __init__(
        self,
        *,
        judge: Callable[[str, dict[str, Any]], dict[str, Any]],
        judge_many: Optional[
            Callable[[str, dict[str, dict[str, Any]]], dict[str, dict[str, Any]]]
        ] = None,
        optimize: Callable[[str, str], str],
        extract_components: Callable[[str], dict[str, list[str]]],
        embed: Callable[[list[str]], list[list[float]]],
        merge_prompts: Callable[[str, str], dict[str, Any]],
        format_feedback: Optional[
            Callable[[list[str], dict[str, Any], dict[str, str], dict[str, dict[str, Any]]], str]
        ] = None,
        max_steps: int = 3,
        merge_acceptance: float = 0.80,
        specialization_mode: str = "replace",
        merge_objective: str = "covered_accuracy",
        require_ge_base: bool = False,
        root_objective: str = "balanced",
        similarity_start: float = 0.90,
        similarity_decay: float = 0.05,
        similarity_floor: float = 0.70,
        warm_start: bool = True,
        merge_validation_cap: int = 6,
        merge_regression_tolerance: float = 0.05,
        merge_generalization_floor: float = 0.80,
        routing_margin: float = 0.02,
        min_routing_support: int = 2,
        singleton_exact_threshold: float = 0.995,
        global_min_validation_gain: float = 0.0,
        max_merge_attempts: int = 20,
        semantic_premerge_levels: int = 2,
        clustering_algorithm: str = "semantic_complete_link",
        semantic_similarity_weight: float = 0.35,
        behavior_similarity_weight: float = 0.25,
        cross_generalization_weight: float = 0.40,
        behavioral_probe_cap: int = 48,
        cross_generalization_cap: int = 6,
        progress: Optional[Callable[[str, dict[str, Any]], None]] = None,
        node_factory: Optional[NodeFactory] = None,
        prompt_optimizer: Optional[PromptOptimizer] = None,
        leaf_optimizer: Optional[LeafOptimizer] = None,
        clustering: Optional[ClusteringAlgorithm] = None,
        merge_algorithm: Optional[MergeAlgorithm] = None,
        merge_acceptance_policy: Optional[MergeAcceptancePolicy] = None,
        root_selector: Optional[RootSelector] = None,
        routing_calibrator: Optional[RoutingCalibrator] = None,
        modular_mode: bool = False,
        decomposition: Any = None,
        decomposition_engine: Any = None,
        optimizer_plan: str = "textgrad",
        optimizer_seed: int = 44,
        gepa_python: Optional[str] = None,
        max_merge_children: int = 2,
        merge_many_prompts: Optional[Callable] = None,
        reflect: Optional[Callable] = None,
        budget_available: Optional[Callable] = None,
        optimizer_identity: Optional[dict[str, Any]] = None,
        optimizer_usage: Optional[Callable] = None,
        checkpoint: Any = None,
    ) -> None:
        self.judge = judge
        self.judge_many = judge_many
        self.optimize = optimize
        self.extract_components = extract_components
        self.embed = embed
        self.merge_prompts = merge_prompts
        self.format_feedback = format_feedback
        self.max_steps = max_steps
        self.merge_acceptance = merge_acceptance
        if specialization_mode not in {"replace", "additive"}:
            raise ValueError(f"Unknown specialization_mode {specialization_mode!r}")
        if merge_objective not in {"covered_accuracy", "balanced"}:
            raise ValueError(f"Unknown merge_objective {merge_objective!r}")
        self.specialization_mode = specialization_mode
        # Additive specialization accumulates validated deltas into the root; the natural
        # acceptance objective there is balanced accuracy against the base, and the root must
        # never regress below the flat base rubric.
        self.merge_objective = (
            "balanced" if specialization_mode == "additive" and
            merge_objective == "covered_accuracy" else merge_objective
        )
        self.require_ge_base = bool(require_ge_base or specialization_mode == "additive")
        if root_objective not in {"balanced", "coverage"}:
            raise ValueError(f"Unknown root_objective {root_objective!r}")
        self.root_objective = root_objective
        self.similarity_start = similarity_start
        self.similarity_decay = similarity_decay
        self.similarity_floor = similarity_floor
        self.warm_start = warm_start
        self.merge_validation_cap = max(0, merge_validation_cap)
        self.merge_regression_tolerance = max(0.0, merge_regression_tolerance)
        self.merge_generalization_floor = max(0.0, merge_generalization_floor)
        self.routing_margin = max(0.0, routing_margin)
        self.min_routing_support = max(1, int(min_routing_support))
        self.singleton_exact_threshold = max(-1.0, min(1.0, singleton_exact_threshold))
        self.global_min_validation_gain = max(0.0, global_min_validation_gain)
        self.max_merge_attempts = max(0, int(max_merge_attempts))
        self.semantic_premerge_levels = max(
            0, int(semantic_premerge_levels)
        )
        if clustering_algorithm not in {
            "semantic_complete_link", "behavioral_complete_link"
        }:
            raise ValueError(f"Unknown clustering_algorithm {clustering_algorithm!r}")
        self.clustering_algorithm = clustering_algorithm
        weights = (
            max(0.0, float(semantic_similarity_weight)),
            max(0.0, float(behavior_similarity_weight)),
            max(0.0, float(cross_generalization_weight)),
        )
        if clustering_algorithm == "behavioral_complete_link" and not any(weights):
            raise ValueError("behavioral clustering requires at least one positive weight")
        total_weight = sum(weights) or 1.0
        self.semantic_similarity_weight = weights[0] / total_weight
        self.behavior_similarity_weight = weights[1] / total_weight
        self.cross_generalization_weight = weights[2] / total_weight
        self.behavioral_probe_cap = max(1, int(behavioral_probe_cap))
        self.cross_generalization_cap = max(1, int(cross_generalization_cap))
        self.progress = progress
        self.timeline: list[dict[str, Any]] = []
        self.node_factory = node_factory if node_factory is not None else DefaultNodeFactory()
        self.prompt_optimizer = prompt_optimizer if prompt_optimizer is not None else FeedbackPromptOptimizer()
        self.leaf_optimizer = leaf_optimizer if leaf_optimizer is not None else DefaultLeafOptimizer()
        self.clustering = clustering if clustering is not None else (
            BehavioralCompleteLinkClustering()
            if clustering_algorithm == "behavioral_complete_link"
            else SemanticCompleteLinkClustering()
        )
        self.merge_algorithm = merge_algorithm if merge_algorithm is not None else CallbackMergeAlgorithm()
        self.merge_acceptance_policy = (
            merge_acceptance_policy if merge_acceptance_policy is not None else GuardedMergeAcceptance()
        )
        self.root_selector = root_selector if root_selector is not None else ValidatedRootSelector()
        self.routing_calibrator = (
            routing_calibrator if routing_calibrator is not None else GeometryRoutingCalibrator()
        )
        self.modular_mode = modular_mode
        self.decomposition, self.decomposition_engine = decomposition, decomposition_engine
        self.optimizer_plan, self.optimizer_seed, self.gepa_python = optimizer_plan, optimizer_seed, gepa_python
        self.max_merge_children, self.merge_many_prompts = max_merge_children, merge_many_prompts
        self.reflect, self.budget_available, self.checkpoint = reflect, budget_available, checkpoint
        self.optimizer_identity, self.optimizer_usage = optimizer_identity or {}, optimizer_usage
        self._custom_leaf_optimizer = leaf_optimizer is not None
        self._custom_prompt_optimizer = prompt_optimizer is not None
        if type(max_merge_children) is not int or max_merge_children < 2:
            raise ValueError("max_merge_children must be an integer >= 2")
        if not modular_mode and max_merge_children != 2:
            raise ValueError("Multi-child merging requires modular_mode=True")
        if modular_mode:
            from .optimization.composite import PLANS
            from .merge.callback import CallbackMultiMergeAlgorithm
            from .merge.base import MultiMergeAlgorithm
            if specialization_mode != "replace":
                raise ValueError("Modular mode supports replacement specialization only")
            if optimizer_plan not in PLANS:
                raise ValueError(f"Unknown optimizer plan {optimizer_plan!r}")
            if type(max_steps) is not int or max_steps < 0:
                raise ValueError("max_steps must be a nonnegative integer")
            if optimizer_plan in {"textgrad_then_gepa", "gepa_then_textgrad", "best_of_both"} and max_steps < 2:
                raise ValueError("Combined optimizer plans require max_steps >= 2")
            if not 0 <= similarity_floor <= similarity_start <= 1 or similarity_decay <= 0:
                raise ValueError("Invalid modular similarity schedule")
            if merge_algorithm is None and merge_many_prompts is not None:
                self.merge_algorithm = CallbackMultiMergeAlgorithm()
            if max_merge_children > 2 and not isinstance(self.merge_algorithm, MultiMergeAlgorithm):
                raise ValueError("Selected merge algorithm supports only two children")

    @staticmethod
    def component_text(components: dict[str, list[str]]) -> str:
        def normalized(value: str) -> str:
            return " ".join(str(value).strip().lower().split())

        return "\n".join(
            f"{kind}: {normalized(value)}"
            for kind in ("criteria", "priorities", "constraints")
            for value in components.get(kind, [])
            if normalized(value)
        )

    def _services(self) -> CaliTreeServices:
        return CaliTreeServices(
            judge=self.judge, judge_many=self.judge_many, optimize=self.optimize,
            extract_components=self.extract_components, embed=self.embed,
            merge_prompts=self.merge_prompts, format_feedback=self.format_feedback,
            merge_many_prompts=self.merge_many_prompts, reflect=self.reflect,
            budget_available=self.budget_available,
            optimizer_identity=self.optimizer_identity, optimizer_usage=self.optimizer_usage,
        )

    def _settings(self) -> CaliTreeSettings:
        return CaliTreeSettings(**{
            field.name: getattr(self, field.name) for field in fields(CaliTreeSettings)
        })

    def _validate(
        self, prompt: str, ids: list[str], samples: dict[str, Any], targets: dict[str, str],
    ) -> tuple[float, list[str], dict[str, dict[str, Any]]]:
        return self._services().validate(prompt, ids, samples, targets)

    def _optimize_for_cases(
        self, prompt: str, ids: list[str], samples: dict[str, Any], targets: dict[str, str],
    ) -> tuple[str, float, list[str], dict[str, dict[str, Any]], int]:
        # Preserve this delegation hook for callers that instrument optimization calls.
        return self.prompt_optimizer.optimize(
            prompt, ids, samples, targets, services=self._services(), max_steps=self.max_steps,
        ).as_tuple()

    _balanced_case_subset = staticmethod(balanced_case_subset)
    _balanced_accuracy = staticmethod(balanced_accuracy)
    _behavior_profile = staticmethod(behavior_profile)

    def _behavioral_pair_score(
        self, left: CaliTreeNode, right: CaliTreeNode,
        cross_generalization: Optional[float] = None,
    ) -> tuple[float, dict[str, float]]:
        result = BehavioralCompleteLinkClustering.weighted_score(
            left, right, self._settings(), cross_generalization,
        )
        return result.similarity, result.diagnostics

    def _calibrate_routing_thresholds(
        self, nodes: dict[str, CaliTreeNode], case_embeddings: dict[str, list[float]],
    ) -> None:
        self.routing_calibrator.calibrate(nodes, case_embeddings, margin=self.routing_margin)

    def build(
        self,
        *,
        initial_prompt: str,
        samples: dict[str, Any],
        targets: dict[str, str],
        routing_texts: Optional[dict[str, str]] = None,
        validation_samples: Optional[dict[str, Any]] = None,
        validation_targets: Optional[dict[str, str]] = None,
        validation_routing_texts: Optional[dict[str, str]] = None,
        validation_leaf_groups: Optional[dict[str, str]] = None,
        semantic_groups: Optional[dict[str, str]] = None,
        leaf_groups: Optional[dict[str, str]] = None,
        annotation_reviews: Optional[dict[str, dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        uncertain_targets = sorted(key for key, value in {**targets, **(validation_targets or {})}.items()
                                   if value == "uncertain")
        if uncertain_targets:
            raise ValueError("Uncertain annotations are not fitting targets: " + ", ".join(uncertain_targets))
        if annotation_reviews:
            from .annotation_quality import partition_annotations
            _, quarantined = partition_annotations({key: {"annotation_review": review}
                                                    for key, review in annotation_reviews.items()})
            excluded = sorted((set(targets) | set(validation_targets or {})) & set(quarantined))
            if excluded:
                raise ValueError("Uncertain annotations cannot enter fitting or validation: " + ", ".join(excluded))
        if self.modular_mode:
            from .modular import build_modular
            return build_modular(self, initial_prompt=initial_prompt, samples=samples, targets=targets,
                routing_texts=routing_texts, validation_samples=validation_samples,
                validation_targets=validation_targets, validation_routing_texts=validation_routing_texts,
                validation_leaf_groups=validation_leaf_groups, semantic_groups=semantic_groups,
                leaf_groups=leaf_groups)
        context = BuildContext(
            services=self._services(), settings=self._settings(),
            optimize_cases=self._optimize_for_cases,
            initial_prompt=initial_prompt, samples=samples, targets=targets,
            validation_samples=validation_samples or {},
            validation_targets=validation_targets or {}, timeline=self.timeline,
            warm_prompt=initial_prompt,
        )
        nodes = context.nodes
        merge_coordinator = MergeCoordinator(self.merge_algorithm, self.merge_acceptance_policy)
        leaf_components: list[dict[str, list[str]]] = []
        leaf_payloads: list[
            tuple[str, list[str], str, float, int]
        ] = []
        item_ids = sorted(targets)
        grouped_ids: dict[str, list[str]] = {}
        for item_id in item_ids:
            group_id = str((leaf_groups or {}).get(item_id) or item_id)
            grouped_ids.setdefault(group_id, []).append(item_id)
        for group_ids in grouped_ids.values():
            group_ids.sort()
        warm_prompt = initial_prompt
        initial_accuracy = 0.0
        warm_accuracy = 0.0
        warm_steps = 0
        warm_results: dict[str, dict[str, Any]] = {}
        if item_ids:
            initial_accuracy, _initial_correct, _initial_results = self._validate(
                initial_prompt, item_ids, samples, targets
            )
        if self.warm_start and item_ids:
            warm_prompt, warm_accuracy, _correct, warm_results, warm_steps = (
                self._optimize_for_cases(initial_prompt, item_ids, samples, targets)
            )
            self.timeline.append({
                "kind": "warm_start",
                "node_id": "warm_start",
                "accuracy": warm_accuracy,
                "steps": warm_steps,
            })

        context.warm_prompt = warm_prompt
        context.initial_accuracy = initial_accuracy
        context.warm_accuracy = warm_accuracy
        context.warm_results = warm_results

        for index, (group_id, group_ids) in enumerate(
            sorted(grouped_ids.items())
        ):
            prompt, accuracy, _correct, _results, steps = self.leaf_optimizer.optimize(
                warm_prompt, group_ids, context,
            ).as_tuple()
            components = self.extract_components(prompt)
            leaf_components.append(components)
            leaf_payloads.append(
                (group_id, group_ids, prompt, accuracy, steps)
            )
            if self.progress:
                self.progress(
                    "calitree_leaf",
                    {
                        "completed": index + 1,
                        "total": len(grouped_ids),
                        "cases": len(group_ids),
                    },
                )
        criteria_embeddings = self.embed(
            [self.component_text(components) for components in leaf_components]
        )
        route_text = routing_texts or {
            item_id: str((samples[item_id].get("input") or {}).get("instruction") or "")
            for item_id in item_ids
        }
        route_embeddings = self.embed([route_text[item_id] for item_id in item_ids])
        case_embeddings = dict(zip(item_ids, route_embeddings))
        context.case_embeddings = case_embeddings
        external_validation_samples = validation_samples or {}
        external_validation_targets = validation_targets or {}
        external_validation_ids = sorted(
            set(external_validation_samples) & set(external_validation_targets)
        )
        if external_validation_ids:
            external_route_text = validation_routing_texts or {
                item_id: str(
                    (external_validation_samples[item_id].get("input") or {}).get(
                        "instruction"
                    ) or ""
                )
                for item_id in external_validation_ids
            }
            validation_embeddings = self.embed(
                [external_route_text[item_id] for item_id in external_validation_ids]
            )
            case_embeddings.update(zip(external_validation_ids, validation_embeddings))
        leaf_for_case: dict[str, str] = {}
        for (
            group_id,
            group_ids,
            prompt,
            accuracy,
            steps,
        ), components, criteria_embedding in zip(
            leaf_payloads, leaf_components, criteria_embeddings
        ):
            node_id = f"leaf:{group_id}"
            for item_id in group_ids:
                leaf_for_case[item_id] = node_id
            nodes[node_id] = self.node_factory.leaf(
                id=node_id,
                prompt=prompt,
                covered_ids=list(group_ids),
                embedding=centroid(
                    case_embeddings[item_id] for item_id in group_ids
                ),
                components=components,
                validation_accuracy=accuracy,
                criteria_embedding=criteria_embedding,
                member_embeddings=[criteria_embedding],
                semantic_groups=sorted({
                    str(
                        (semantic_groups or {}).get(item_id)
                        or "unknown"
                    )
                    for item_id in group_ids
                }),
            )
            self.timeline.append({
                "kind": "leaf",
                "node_id": node_id,
                "steps": steps,
                "cases": len(group_ids),
            })

        active = [
            nodes[f"leaf:{group_id}"]
            for group_id in sorted(grouped_ids)
        ]
        if validation_leaf_groups is not None:
            for group_id in sorted(grouped_ids):
                leaf = nodes[f"leaf:{group_id}"]
                leaf_validation_ids = [
                    item_id for item_id in external_validation_ids
                    if validation_leaf_groups.get(item_id) == group_id
                ]
                leaf.routing_validation_support = len(leaf_validation_ids)
                if leaf_validation_ids:
                    leaf_accuracy, _correct, _results = self._validate(
                        leaf.prompt,
                        leaf_validation_ids,
                        external_validation_samples,
                        external_validation_targets,
                    )
                    warm_baseline_accuracy, _base_correct, _base_results = self._validate(
                        warm_prompt,
                        leaf_validation_ids,
                        external_validation_samples,
                        external_validation_targets,
                    )
                    initial_baseline_accuracy, _initial_correct, _initial_results = self._validate(
                        initial_prompt,
                        leaf_validation_ids,
                        external_validation_samples,
                        external_validation_targets,
                    )
                    leaf.routing_validation_accuracy = leaf_accuracy
                    leaf.routing_baseline_accuracy = max(
                        warm_baseline_accuracy, initial_baseline_accuracy
                    )
                leaf.routing_eligible = bool(
                    len(leaf_validation_ids) >= self.min_routing_support
                    and leaf.routing_validation_accuracy is not None
                    and leaf.routing_baseline_accuracy is not None
                    and leaf.routing_validation_accuracy
                    > leaf.routing_baseline_accuracy
                    + self.global_min_validation_gain
                )
                self.timeline.append({
                    "kind": "leaf_routing_validation",
                    "node_id": leaf.id,
                    "support": leaf.routing_validation_support,
                    "leaf_accuracy": leaf.routing_validation_accuracy,
                    "baseline_accuracy": leaf.routing_baseline_accuracy,
                    "routing_eligible": leaf.routing_eligible,
                })
        self.clustering.prepare(active, context)

        promoted_count = accepted_merges = rejected_merges = 0
        blocked_pairs: set[frozenset[str]] = set()
        merge_attempts = 0
        merge_budget_exhausted = False
        semantic_group_counts: dict[str, int] = {}
        for item_id in item_ids:
            group = str(
                (semantic_groups or {}).get(item_id) or "unknown"
            )
            semantic_group_counts[group] = (
                semantic_group_counts.get(group, 0) + 1
            )
        self.timeline.append({
            "kind": "semantic_premerge",
            "node_id": "semantic_premerge",
            "levels": self.semantic_premerge_levels,
            "groups": semantic_group_counts,
        })
        max_levels = (
            int(round((self.similarity_start - self.similarity_floor)
                      / self.similarity_decay)) + 1
        )
        for level in range(max_levels):
            threshold = similarity_threshold(
                level, start=self.similarity_start, decay=self.similarity_decay,
                floor=self.similarity_floor,
            )
            pairs, unpaired = self.clustering.pairs(
                active, threshold, level=level, blocked_pairs=blocked_pairs, context=context,
            )
            if not pairs:
                if threshold <= self.similarity_floor:
                    break
                continue
            next_active = list(unpaired)
            level_success = 0
            for pair_index, (left, right, similarity) in enumerate(pairs):
                if merge_attempts >= self.max_merge_attempts:
                    for pending_left, pending_right, _score in pairs[pair_index:]:
                        next_active.extend((pending_left, pending_right))
                    merge_budget_exhausted = True
                    self.timeline.append({
                        "kind": "merge_budget_exhausted",
                        "node_id": "merge_budget",
                        "level": level + 1,
                        "attempts": merge_attempts,
                        "limit": self.max_merge_attempts,
                    })
                    break
                merge_attempts += 1
                pair_result = self.clustering.probe(left, right, context)
                similarity, diagnostics = pair_result.similarity, pair_result.diagnostics
                merge_id = f"merge:{level + 1}:{pair_index}:{left.id}:{right.id}"
                if similarity < threshold:
                    blocked_pairs.add(frozenset((left.id, right.id)))
                    next_active.extend((left, right))
                    rejected_merges += 1
                    self.timeline.append({
                        "kind": "rejected_transfer", "node_id": merge_id, "level": level + 1,
                        "similarity": similarity, "threshold": threshold, **diagnostics,
                    })
                    continue
                result = merge_coordinator.merge(left, right, context)
                if not result.decision.accepted:
                    blocked_pairs.add(frozenset((left.id, right.id)))
                    next_active.extend((left, right))
                    rejected_merges += 1
                    if result.conflict_reason:
                        left.conflict_reason = right.conflict_reason = result.conflict_reason
                    event = {
                        "kind": result.decision.kind, "node_id": merge_id, "level": level + 1,
                        "similarity": similarity, **diagnostics, **result.decision.diagnostics,
                    }
                    if result.optimization is not None:
                        event.update(accuracy=result.optimization.accuracy, steps=result.optimization.steps)
                    self.timeline.append(event)
                    continue
                if result.optimization is None:
                    raise RuntimeError("Accepted merge must include an optimization result")
                covered = result.covered_ids
                prompt, accuracy, correct, _results, steps = result.optimization.as_tuple()
                generalization_accuracy = result.decision.generalization_accuracy
                components = self.extract_components(prompt)
                criteria_embedding = self.embed([self.component_text(components)])[0]
                status = "accepted" if accuracy == 1.0 else "partial"
                parent = self.node_factory.merge(
                    id=merge_id,
                    prompt=prompt,
                    covered_ids=correct,
                    embedding=centroid(case_embeddings[item_id] for item_id in correct),
                    components=components,
                    level=level + 1,
                    status=status,
                    children=[left.id, right.id],
                    validation_accuracy=accuracy,
                    routing_threshold=threshold,
                    criteria_embedding=criteria_embedding,
                    member_embeddings=(
                        list(left.member_embeddings) + list(right.member_embeddings)
                    ),
                    generalization_accuracy=generalization_accuracy,
                    semantic_groups=sorted(set(
                        left.semantic_groups + right.semantic_groups
                    )),
                )
                self.clustering.refresh(parent, context)
                nodes[parent.id] = parent
                next_active.append(parent)
                accepted_merges += 1
                level_success += 1
                if status == "partial":
                    for item_id in sorted(set(covered) - set(correct)):
                        source = nodes[leaf_for_case[item_id]]
                        promoted_count += 1
                        promoted = self.node_factory.promoted_leaf(
                            id=f"promoted:{promoted_count}:{item_id}",
                            prompt=source.prompt,
                            covered_ids=[item_id],
                            embedding=list(source.embedding),
                            components=dict(source.components),
                            level=level + 1,
                            status="promoted",
                            validation_accuracy=1.0,
                            criteria_embedding=list(source.criteria_embedding),
                            member_embeddings=[list(row) for row in source.member_embeddings],
                            semantic_groups=list(source.semantic_groups),
                            routing_eligible=source.routing_eligible,
                            routing_validation_support=source.routing_validation_support,
                            routing_validation_accuracy=source.routing_validation_accuracy,
                            routing_baseline_accuracy=source.routing_baseline_accuracy,
                        )
                        nodes[promoted.id] = promoted
                        next_active.append(promoted)
                self.timeline.append({
                    "kind": status, "node_id": parent.id, "level": level + 1,
                    "accuracy": accuracy, "similarity": similarity, "steps": steps,
                    **diagnostics,
                })
                if self.progress:
                    self.progress("calitree_merge", {
                        "level": level + 1, "accepted": accepted_merges,
                        "rejected": rejected_merges,
                    })
            active = sorted(next_active, key=lambda node: node.id)
            if merge_budget_exhausted:
                break
            if level_success == 0 and threshold <= self.similarity_floor:
                break
        # A universal, target-blind fallback prevents unrelated unseen instructions from
        # being forced into an arbitrary specialized root. Specialized singleton leaves
        # remain useful for exact training-case diagnostics but require near-exact routing.
        all_routing_ids = item_ids + external_validation_ids
        selection = self.root_selector.select(context, accepted_merges=accepted_merges)
        global_prompt = selection.prompt
        global_source = selection.source
        accumulated_root_id = selection.accumulated_node_id
        global_selection = selection.report
        global_components = self.extract_components(global_prompt)
        global_criteria_embedding = self.embed(
            [self.component_text(global_components)]
        )[0]
        global_id = f"global:{global_source}"
        global_node = self.node_factory.global_node(
            id=global_id,
            prompt=global_prompt,
            covered_ids=all_routing_ids,
            embedding=centroid(
                case_embeddings[item_id]
                for item_id in all_routing_ids
                if item_id in case_embeddings
            ),
            components=global_components,
            level=(max((node.level for node in active), default=0) + 1),
            status="global",
            children=[node.id for node in active],
            validation_accuracy=float(
                (
                    global_selection.get(f"{global_source}_validation_accuracy")
                    if external_validation_ids
                    else global_selection.get(f"{global_source}_fit_accuracy")
                )
                or (nodes[accumulated_root_id].validation_accuracy
                    if accumulated_root_id else warm_accuracy)
            ),
            routing_threshold=-1.0,
            criteria_embedding=global_criteria_embedding,
            member_embeddings=[global_criteria_embedding],
        )
        nodes[global_id] = global_node
        self._calibrate_routing_thresholds(nodes, case_embeddings)
        return {
            "version": "calitree-v2",
            "roots": [global_id],
            "nodes": {node_id: asdict(node) for node_id, node in nodes.items()},
            "timeline": self.timeline,
            "warm_start_prompt": warm_prompt,
            "warm_start_accuracy": warm_accuracy,
            "warm_start_steps": warm_steps,
            "global_selection": global_selection,
            "config": {
                "max_steps": self.max_steps,
                "merge_acceptance": self.merge_acceptance,
                "similarity_start": self.similarity_start,
                "similarity_decay": self.similarity_decay,
                "similarity_floor": self.similarity_floor,
                "warm_start": self.warm_start,
                "merge_validation_cap": self.merge_validation_cap,
                "merge_regression_tolerance": self.merge_regression_tolerance,
                "merge_generalization_floor": self.merge_generalization_floor,
                "routing_margin": self.routing_margin,
                "min_routing_support": self.min_routing_support,
                "singleton_exact_threshold": self.singleton_exact_threshold,
                "global_min_validation_gain": self.global_min_validation_gain,
                "max_merge_attempts": self.max_merge_attempts,
                "semantic_premerge_levels": self.semantic_premerge_levels,
                "clustering_algorithm": self.clustering_algorithm,
                "semantic_similarity_weight": self.semantic_similarity_weight,
                "behavior_similarity_weight": self.behavior_similarity_weight,
                "cross_generalization_weight": self.cross_generalization_weight,
                "leaf_grouping": (
                    "configured" if leaf_groups else "per_case"
                ),
                "specialization_mode": self.specialization_mode,
                "merge_objective": self.merge_objective,
                "require_ge_base": self.require_ge_base,
                "root_objective": self.root_objective,
                # Additive roots already contain the accumulated deltas, so routing biases to
                # the root and diverts to a leaf only on a near-exact match.
                "route_default_to_root": self.specialization_mode == "additive",
            },
            "stats": {
                "leaves": len(grouped_ids),
                "leaf_cases": len(item_ids),
                "accepted_merges": accepted_merges,
                "rejected_merges": rejected_merges,
                "promoted": promoted_count,
                "roots": 1,
                "specialized_roots": len(active),
                "merge_attempts": merge_attempts,
                "merge_budget_exhausted": merge_budget_exhausted,
                "specialization_mode": self.specialization_mode,
                "root_source": global_source,
                "accumulated_root": accumulated_root_id,
            },
        }
