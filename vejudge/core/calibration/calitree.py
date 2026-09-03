"""Paper-derived Cali-Tree hierarchy construction and semantic routing.

Model calls are injected as callbacks, keeping the hierarchy deterministic and unit-testable
while the interface node owns gateway gating, logging, and checkpoints.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Iterable, Optional

LABELS = ("no", "partial", "yes")
ORDINAL_VALUE = {"no": 0.0, "partial": 0.5, "yes": 1.0}


def ordinal_absolute_error(target: str, prediction: str) -> Optional[float]:
    """Absolute error on the ``no=0, partial=0.5, yes=1`` ordinal scale.

    Returns ``None`` when either label is outside the ordinal vocabulary so unknown
    predictions do not silently count as a perfect or worst-case distance.
    """
    if target not in ORDINAL_VALUE or prediction not in ORDINAL_VALUE:
        return None
    return abs(ORDINAL_VALUE[target] - ORDINAL_VALUE[prediction])


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    a, b = list(left), list(right)
    if len(a) != len(b) or not a:
        return 0.0
    numerator = sum(x * y for x, y in zip(a, b))
    denominator = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return 0.0 if denominator == 0 else numerator / denominator


def centroid(vectors: Iterable[Iterable[float]]) -> list[float]:
    rows = [list(row) for row in vectors]
    if not rows:
        return []
    width = len(rows[0])
    if width == 0 or any(len(row) != width for row in rows):
        return []
    return [sum(row[index] for row in rows) / len(rows) for index in range(width)]


def similarity_threshold(
    level: int, *, start: float = 0.90, decay: float = 0.05, floor: float = 0.70
) -> float:
    return max(floor, start - decay * level)


@dataclass
class CaliTreeNode:
    id: str
    prompt: str
    covered_ids: list[str]
    embedding: list[float]
    components: dict[str, list[str]]
    level: int = 0
    status: str = "leaf"
    children: list[str] = field(default_factory=list)
    validation_accuracy: float = 0.0
    routing_threshold: float = 0.70
    conflict_reason: str = ""
    criteria_embedding: list[float] = field(default_factory=list)
    member_embeddings: list[list[float]] = field(default_factory=list)
    generalization_accuracy: Optional[float] = None
    semantic_groups: list[str] = field(default_factory=list)
    # Specialized routing is opt-in when a held-out leaf cohort exists. A leaf that does
    # not match or beat the root on enough validation cases remains useful for clustering
    # but cannot intercept unseen cases.
    routing_eligible: bool = True
    routing_validation_support: int = 0
    routing_validation_accuracy: Optional[float] = None
    routing_baseline_accuracy: Optional[float] = None
    # A normalized no/partial/yes confusion profile measured after leaf optimization.
    # It is deliberately derived from predictions, not prompt wording, so clustering can
    # discover leaves with compatible decision boundaries.
    behavior_profile: list[float] = field(default_factory=list)


def complete_link_similarity(left: CaliTreeNode, right: CaliTreeNode) -> float:
    left_members = left.member_embeddings or [
        left.criteria_embedding or left.embedding
    ]
    right_members = right.member_embeddings or [
        right.criteria_embedding or right.embedding
    ]
    scores = [
        cosine_similarity(left_embedding, right_embedding)
        for left_embedding in left_members
        for right_embedding in right_members
    ]
    return min(scores) if scores else 0.0


def _pair_candidates(
    nodes: list[CaliTreeNode],
    threshold: float,
    blocked_pairs: Optional[set[frozenset[str]]] = None,
    compatible: Optional[
        Callable[[CaliTreeNode, CaliTreeNode], bool]
    ] = None,
    pair_score: Optional[Callable[[CaliTreeNode, CaliTreeNode], float]] = None,
) -> list[tuple[int, int, float]]:
    candidates: list[tuple[int, int, float]] = []
    for i, left in enumerate(nodes):
        for j in range(i + 1, len(nodes)):
            if (
                blocked_pairs is not None
                and frozenset((left.id, nodes[j].id)) in blocked_pairs
            ):
                continue
            if compatible is not None and not compatible(left, nodes[j]):
                continue
            score = (
                pair_score(left, nodes[j])
                if pair_score is not None
                else complete_link_similarity(left, nodes[j])
            )
            if score >= threshold:
                candidates.append((i, j, score))
    return sorted(candidates, key=lambda row: (-row[2], nodes[row[0]].id, nodes[row[1]].id))


def greedy_pairs(
    nodes: list[CaliTreeNode],
    threshold: float,
    blocked_pairs: Optional[set[frozenset[str]]] = None,
    compatible: Optional[
        Callable[[CaliTreeNode, CaliTreeNode], bool]
    ] = None,
    pair_score: Optional[Callable[[CaliTreeNode, CaliTreeNode], float]] = None,
) -> tuple[list[tuple[CaliTreeNode, CaliTreeNode, float]], list[CaliTreeNode]]:
    used: set[int] = set()
    pairs: list[tuple[CaliTreeNode, CaliTreeNode, float]] = []
    for i, j, score in _pair_candidates(
        nodes, threshold, blocked_pairs, compatible, pair_score
    ):
        if i not in used and j not in used:
            used.update((i, j))
            pairs.append((nodes[i], nodes[j], score))
    return pairs, [node for idx, node in enumerate(nodes) if idx not in used]


def classification_metrics(
    targets: dict[str, str], predictions: dict[str, str], samples: dict[str, Any]
) -> dict[str, Any]:
    ids = sorted(targets)
    normalized_predictions = {
        item_id: (
            predictions.get(item_id)
            if predictions.get(item_id) in LABELS
            else "invalid"
        )
        for item_id in ids
    }
    correct = sum(
        targets[item_id] == normalized_predictions[item_id] for item_id in ids
    )
    confusion = {
        label: {pred: 0 for pred in (*LABELS, "invalid")} for label in LABELS
    }
    by_editor: dict[str, dict[str, float]] = {}
    distribution = {label: 0 for label in LABELS}
    abs_errors: list[float] = []
    for item_id in ids:
        target, prediction = targets[item_id], normalized_predictions[item_id]
        if target in confusion and prediction in confusion[target]:
            confusion[target][prediction] += 1
        if prediction in distribution:
            distribution[prediction] += 1
        else:
            distribution["invalid"] = distribution.get("invalid", 0) + 1
        editor = str(samples[item_id].get("editor") or samples[item_id].get("model") or "unknown")
        row = by_editor.setdefault(editor, {"correct": 0, "n": 0, "abs_error_sum": 0.0, "n_ordinal": 0})
        row["n"] += 1
        row["correct"] += int(target == prediction)
        abs_error = ordinal_absolute_error(target, prediction)
        if abs_error is not None:
            abs_errors.append(abs_error)
            row["abs_error_sum"] += abs_error
            row["n_ordinal"] += 1
    per_label_accuracy = {
        label: (
            confusion[label][label] / sum(confusion[label].values())
            if sum(confusion[label].values())
            else None
        )
        for label in LABELS
    }
    per_label_precision = {
        label: (
            confusion[label][label]
            / sum(confusion[target][label] for target in LABELS)
            if sum(confusion[target][label] for target in LABELS)
            else None
        )
        for label in LABELS
    }
    per_label_f1 = {
        label: (
            2 * per_label_precision[label] * per_label_accuracy[label]
            / (per_label_precision[label] + per_label_accuracy[label])
            if per_label_precision[label] is not None
            and per_label_accuracy[label] is not None
            and per_label_precision[label] + per_label_accuracy[label] > 0
            else 0.0
            if per_label_precision[label] is not None
            and per_label_accuracy[label] is not None
            else None
        )
        for label in LABELS
    }
    supported = [value for value in per_label_accuracy.values() if value is not None]
    supported_f1 = [value for value in per_label_f1.values() if value is not None]
    return {
        "n": len(ids),
        "accuracy": correct / len(ids) if ids else None,
        "balanced_accuracy": sum(supported) / len(supported) if supported else None,
        "per_label_accuracy": per_label_accuracy,
        "per_label_precision": per_label_precision,
        "per_label_f1": per_label_f1,
        "macro_f1": sum(supported_f1) / len(supported_f1) if supported_f1 else None,
        "ordinal_mae": (sum(abs_errors) / len(abs_errors) if abs_errors else None),
        "confusion": confusion,
        "prediction_distribution": distribution,
        "per_editor": {
            editor: {
                "n": int(row["n"]),
                "accuracy": row["correct"] / row["n"],
                "ordinal_mae": (
                    row["abs_error_sum"] / row["n_ordinal"]
                    if row["n_ordinal"]
                    else None
                ),
            }
            for editor, row in sorted(by_editor.items())
        },
    }


class CaliTreeBuilder:
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

    def _validate(
        self, prompt: str, ids: list[str], samples: dict[str, Any], targets: dict[str, str]
    ) -> tuple[float, list[str], dict[str, dict[str, Any]]]:
        selected = {item_id: samples[item_id] for item_id in ids}
        results = (
            self.judge_many(prompt, selected)
            if self.judge_many is not None
            else {item_id: self.judge(prompt, sample) for item_id, sample in selected.items()}
        )
        correct = [
            item_id for item_id, result in results.items()
            if result.get("label") == targets[item_id]
        ]
        return (len(correct) / len(ids) if ids else 0.0), correct, results

    def _optimize_for_cases(
        self,
        prompt: str,
        ids: list[str],
        samples: dict[str, Any],
        targets: dict[str, str],
    ) -> tuple[str, float, list[str], dict[str, dict[str, Any]], int]:
        accuracy, correct, results = self._validate(prompt, ids, samples, targets)
        steps = 0
        while accuracy < 1.0 and steps < self.max_steps:
            mistakes = [item_id for item_id in ids if item_id not in correct]
            if self.format_feedback is not None:
                feedback = self.format_feedback(mistakes, samples, targets, results)
            else:
                feedback = "\n\n".join(
                    f"Instruction: {(samples[item_id].get('input') or {}).get('instruction', '')}\n"
                    f"Predicted: {results[item_id].get('label')}\n"
                    f"Target: {targets[item_id]}\n"
                    f"Rationale: {results[item_id].get('rationale', '')}"
                    for item_id in mistakes
                )
            prompt = self.optimize(prompt, feedback)
            steps += 1
            accuracy, correct, results = self._validate(prompt, ids, samples, targets)
        return prompt, accuracy, correct, results, steps

    @staticmethod
    def _balanced_case_subset(
        ids: list[str], targets: dict[str, str], limit: int
    ) -> list[str]:
        if limit <= 0 or len(ids) <= limit:
            return sorted(ids)
        groups: dict[str, list[str]] = {}
        for item_id in sorted(ids):
            groups.setdefault(targets[item_id], []).append(item_id)
        selected: list[str] = []
        offsets = {label: 0 for label in groups}
        labels = sorted(groups)
        while len(selected) < limit:
            progressed = False
            for label in labels:
                offset = offsets[label]
                if offset >= len(groups[label]):
                    continue
                selected.append(groups[label][offset])
                offsets[label] += 1
                progressed = True
                if len(selected) == limit:
                    break
            if not progressed:
                break
        return sorted(selected)

    @staticmethod
    def _balanced_accuracy(
        ids: list[str],
        targets: dict[str, str],
        results: dict[str, dict[str, Any]],
    ) -> float:
        scores: list[float] = []
        for label in LABELS:
            label_ids = [item_id for item_id in ids if targets[item_id] == label]
            if label_ids:
                scores.append(
                    sum(results[item_id].get("label") == label for item_id in label_ids)
                    / len(label_ids)
                )
        return sum(scores) / len(scores) if scores else 0.0

    @staticmethod
    def _behavior_profile(
        ids: list[str],
        targets: dict[str, str],
        results: dict[str, dict[str, Any]],
    ) -> list[float]:
        """Return a label-confusion fingerprint for a prompt on a fixed probe set.

        A profile has one coordinate per target/prediction pair.  Comparing profiles on
        the same examples makes leaves with the same *decision behavior* close even when
        their generated prompt text happens to look unrelated.
        """
        profile = [0.0] * (len(LABELS) * len(LABELS))
        label_index = {label: index for index, label in enumerate(LABELS)}
        for item_id in ids:
            target = targets.get(item_id)
            prediction = (results.get(item_id) or {}).get("label")
            if target in label_index and prediction in label_index:
                profile[
                    label_index[target] * len(LABELS) + label_index[prediction]
                ] += 1.0
        total = sum(profile)
        return [value / total for value in profile] if total else profile

    def _behavioral_pair_score(
        self,
        left: CaliTreeNode,
        right: CaliTreeNode,
        cross_generalization: Optional[float] = None,
    ) -> tuple[float, dict[str, float]]:
        """Score a candidate merge by semantic affinity and bidirectional transfer.

        Cross-generalization is measured lazily for proposed pairs before prompting the merge:
        a leaf must already classify the other leaf's cases reasonably well. This avoids a
        quadratic all-leaf evaluation while still preventing embedding-only merges.
        """
        semantic = complete_link_similarity(left, right)
        behavior = cosine_similarity(left.behavior_profile, right.behavior_profile)
        # Before the exact transfer probe, use the normalized semantic/behavioral portion to
        # rank candidates.  The transfer weight enters only once a pair is proposed.
        active_weights = self.semantic_similarity_weight + self.behavior_similarity_weight
        if cross_generalization is not None:
            active_weights += self.cross_generalization_weight
        if active_weights == 0:
            active_weights = 1.0
        score = (
            self.semantic_similarity_weight * semantic
            + self.behavior_similarity_weight * behavior
            + (
                self.cross_generalization_weight * cross_generalization
                if cross_generalization is not None else 0.0
            )
        ) / active_weights
        diagnostics: dict[str, float] = {
            "semantic_similarity": semantic,
            "behavior_similarity": behavior,
        }
        if cross_generalization is not None:
            diagnostics["cross_generalization"] = cross_generalization
        return score, diagnostics

    def _calibrate_routing_thresholds(
        self,
        nodes: dict[str, CaliTreeNode],
        case_embeddings: dict[str, list[float]],
    ) -> None:
        """Calibrate every parent→child edge from training instruction geometry."""
        for parent in nodes.values():
            children = [nodes[node_id] for node_id in parent.children if node_id in nodes]
            for child in children:
                positives = [
                    cosine_similarity(case_embeddings[item_id], child.embedding)
                    for item_id in child.covered_ids
                    if item_id in case_embeddings
                ]
                negative_ids = {
                    item_id
                    for sibling in children
                    if sibling.id != child.id
                    for item_id in sibling.covered_ids
                }
                negatives = [
                    cosine_similarity(case_embeddings[item_id], child.embedding)
                    for item_id in sorted(negative_ids)
                    if item_id in case_embeddings
                ]
                if not positives:
                    child.routing_threshold = 1.0
                    continue
                positive_floor = min(positives)
                if negatives:
                    negative_ceiling = max(negatives)
                    if positive_floor > negative_ceiling:
                        threshold = (positive_floor + negative_ceiling) / 2
                    else:
                        threshold = (
                            sum(positives) / len(positives)
                            + sum(negatives) / len(negatives)
                        ) / 2
                    threshold += self.routing_margin
                else:
                    threshold = positive_floor - self.routing_margin
                child.routing_threshold = max(-1.0, min(1.0, threshold))

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
    ) -> dict[str, Any]:
        nodes: dict[str, CaliTreeNode] = {}
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

        for index, (group_id, group_ids) in enumerate(
            sorted(grouped_ids.items())
        ):
            prompt, accuracy, _correct, _results, steps = self._optimize_for_cases(
                warm_prompt, group_ids, samples, targets
            )
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
            nodes[node_id] = CaliTreeNode(
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
        # Prompt-text embeddings alone are a poor proxy for whether two judges can be
        # compressed.  In behavioral mode, run every optimized leaf over a common probe set
        # once and retain both its confusion fingerprint and its transfer predictions.  The
        # probe is training-only here; actual merge acceptance remains held-out below.
        behavioral_probe_ids = self._balanced_case_subset(
            item_ids, targets, self.behavioral_probe_cap
        )
        if self.clustering_algorithm == "behavioral_complete_link" and item_ids:
            for leaf in active:
                _score, _correct, results = self._validate(
                    leaf.prompt, behavioral_probe_ids, samples, targets
                )
                leaf.behavior_profile = self._behavior_profile(
                    behavioral_probe_ids, targets, results
                )
            self.timeline.append({
                "kind": "behavioral_clustering_probe",
                "node_id": "behavioral_clustering",
                "leaves": len(active),
                "probe_cases": len(behavioral_probe_ids),
            })

        def pair_score(left: CaliTreeNode, right: CaliTreeNode) -> float:
            if self.clustering_algorithm != "behavioral_complete_link":
                return complete_link_similarity(left, right)
            return self._behavioral_pair_score(left, right)[0]

        def pair_diagnostics(
            left: CaliTreeNode, right: CaliTreeNode
        ) -> dict[str, float]:
            if self.clustering_algorithm != "behavioral_complete_link":
                return {"semantic_similarity": complete_link_similarity(left, right)}
            return self._behavioral_pair_score(left, right)[1]

        promoted_count = accepted_merges = rejected_merges = 0
        blocked_pairs: set[frozenset[str]] = set()
        rejected_static_generalization_prompts: set[str] = set()
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
            compatible = None
            if level < self.semantic_premerge_levels:
                compatible = lambda left, right: bool(
                    set(left.semantic_groups)
                    & set(right.semantic_groups)
                )
            pairs, unpaired = greedy_pairs(
                active,
                threshold,
                blocked_pairs,
                compatible,
                pair_score,
            )
            if not pairs:
                if threshold <= self.similarity_floor:
                    break
                continue
            next_active = list(unpaired)
            level_success = 0
            for pair_index, (left, right, similarity) in enumerate(pairs):
                diagnostics = pair_diagnostics(left, right)
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
                if self.clustering_algorithm == "behavioral_complete_link":
                    # Probe transfer only for a candidate that survived the cheap
                    # semantic/behavior ranking. This is the actual pairwise criterion:
                    # both leaves must generalize to the other's examples before a parent is
                    # synthesized or optimized.
                    left_probe_ids = self._balanced_case_subset(
                        right.covered_ids, targets, self.cross_generalization_cap
                    )
                    right_probe_ids = self._balanced_case_subset(
                        left.covered_ids, targets, self.cross_generalization_cap
                    )
                    _left_raw, _left_correct, left_probe_results = self._validate(
                        left.prompt, left_probe_ids, samples, targets
                    )
                    _right_raw, _right_correct, right_probe_results = self._validate(
                        right.prompt, right_probe_ids, samples, targets
                    )
                    left_on_right = self._balanced_accuracy(
                        left_probe_ids, targets, left_probe_results
                    )
                    right_on_left = self._balanced_accuracy(
                        right_probe_ids, targets, right_probe_results
                    )
                    transfer = (left_on_right + right_on_left) / 2
                    similarity, diagnostics = self._behavioral_pair_score(
                        left, right, transfer
                    )
                    diagnostics.update({
                        "left_on_right": left_on_right,
                        "right_on_left": right_on_left,
                    })
                    if similarity < threshold:
                        blocked_pairs.add(frozenset((left.id, right.id)))
                        next_active.extend((left, right))
                        rejected_merges += 1
                        self.timeline.append({
                            "kind": "rejected_transfer",
                            "node_id": f"merge:{level + 1}:{pair_index}:{left.id}:{right.id}",
                            "level": level + 1,
                            "similarity": similarity,
                            "threshold": threshold,
                            **diagnostics,
                        })
                        continue
                merged = self.merge_prompts(left.prompt, right.prompt)
                merge_id = f"merge:{level + 1}:{pair_index}:{left.id}:{right.id}"
                if merged.get("conflict") or not str(merged.get("prompt") or "").strip():
                    blocked_pairs.add(frozenset((left.id, right.id)))
                    left.conflict_reason = right.conflict_reason = str(
                        merged.get("conflict_reason") or "incompatible criteria"
                    )
                    next_active.extend((left, right))
                    rejected_merges += 1
                    self.timeline.append({
                        "kind": "branch", "node_id": merge_id, "level": level + 1,
                        "similarity": similarity, "reason": left.conflict_reason,
                        **diagnostics,
                    })
                    continue
                raw_merge_prompt = str(merged["prompt"])
                normalized_raw_merge = " ".join(raw_merge_prompt.lower().split())
                if normalized_raw_merge in rejected_static_generalization_prompts:
                    blocked_pairs.add(frozenset((left.id, right.id)))
                    next_active.extend((left, right))
                    rejected_merges += 1
                    self.timeline.append({
                        "kind": "pruned_equivalent",
                        "node_id": merge_id,
                        "level": level + 1,
                        "similarity": similarity,
                        **diagnostics,
                        "reason": "identical unoptimized prompt already failed the shared guard",
                    })
                    continue
                covered = sorted(set(left.covered_ids + right.covered_ids))
                prompt, accuracy, correct, _results, steps = self._optimize_for_cases(
                    raw_merge_prompt, covered, samples, targets
                )
                # In additive/balanced mode the merged prompt is base + a compacted union of
                # deltas, so it fits its own cluster by construction; acceptance is decided by
                # the no-regression-vs-base generalization guard below, not a covered-accuracy
                # floor. Replace mode keeps the original covered-accuracy gate.
                if self.merge_objective == "covered_accuracy" and accuracy < self.merge_acceptance:
                    blocked_pairs.add(frozenset((left.id, right.id)))
                    next_active.extend((left, right))
                    rejected_merges += 1
                    self.timeline.append({
                        "kind": "rejected", "node_id": merge_id, "level": level + 1,
                        "accuracy": accuracy, "similarity": similarity, "steps": steps,
                        **diagnostics,
                    })
                    continue
                if external_validation_ids:
                    guard_ids = self._balanced_case_subset(
                        external_validation_ids,
                        external_validation_targets,
                        self.merge_validation_cap,
                    )
                    guard_samples = external_validation_samples
                    guard_targets = external_validation_targets
                else:
                    guard_ids = self._balanced_case_subset(
                        [item_id for item_id in item_ids if item_id not in covered],
                        targets,
                        self.merge_validation_cap,
                    )
                    guard_samples = samples
                    guard_targets = targets
                generalization_accuracy: Optional[float] = None
                if guard_ids:
                    _guard_accuracy, _guard_correct, guard_results = self._validate(
                        prompt, guard_ids, guard_samples, guard_targets
                    )
                    generalization_accuracy = self._balanced_accuracy(
                        guard_ids, guard_targets, guard_results
                    )
                    if external_validation_ids:
                        _warm_guard_raw, _warm_guard_correct, warm_guard_results = self._validate(
                            warm_prompt, guard_ids, guard_samples, guard_targets
                        )
                    else:
                        warm_guard_results = warm_results
                    if warm_guard_results:
                        warm_guard_accuracy = self._balanced_accuracy(
                            guard_ids, guard_targets, warm_guard_results
                        )
                        # The absolute balanced floor is calibrated for replace mode; in
                        # additive/balanced mode a typical balanced accuracy (~0.6) is well
                        # below 0.80, so only the no-regression-vs-base condition applies —
                        # that is what keeps delta accumulation monotone.
                        floor_violated = (
                            self.merge_objective == "covered_accuracy"
                            and generalization_accuracy < self.merge_generalization_floor
                        )
                        if (
                            floor_violated
                            or
                            generalization_accuracy + self.merge_regression_tolerance
                            < warm_guard_accuracy
                        ):
                            if steps == 0:
                                rejected_static_generalization_prompts.add(
                                    normalized_raw_merge
                                )
                            blocked_pairs.add(frozenset((left.id, right.id)))
                            next_active.extend((left, right))
                            rejected_merges += 1
                            self.timeline.append({
                                "kind": "rejected_generalization",
                                "node_id": merge_id,
                                "level": level + 1,
                                "accuracy": accuracy,
                                "generalization_accuracy": generalization_accuracy,
                                "baseline_generalization_accuracy": warm_guard_accuracy,
                                "generalization_floor": self.merge_generalization_floor,
                                "similarity": similarity,
                                "steps": steps,
                                **diagnostics,
                            })
                            continue
                components = self.extract_components(prompt)
                criteria_embedding = self.embed([self.component_text(components)])[0]
                status = "accepted" if accuracy == 1.0 else "partial"
                parent_behavior_results: dict[str, dict[str, Any]] = {}
                if self.clustering_algorithm == "behavioral_complete_link":
                    # This is deliberately a fresh evaluation of the optimized parent on
                    # the common probe set.  Reusing child behavior here would turn the next
                    # level back into text/centroid clustering instead of measuring the merge.
                    _probe_score, _probe_correct, parent_behavior_results = self._validate(
                        prompt, behavioral_probe_ids, samples, targets
                    )
                parent = CaliTreeNode(
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
                    behavior_profile=(
                        self._behavior_profile(
                            behavioral_probe_ids,
                            targets,
                            parent_behavior_results,
                        )
                        if self.clustering_algorithm == "behavioral_complete_link"
                        else []
                    ),
                )
                nodes[parent.id] = parent
                next_active.append(parent)
                accepted_merges += 1
                level_success += 1
                if status == "partial":
                    for item_id in sorted(set(covered) - set(correct)):
                        source = nodes[leaf_for_case[item_id]]
                        promoted_count += 1
                        promoted = CaliTreeNode(
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
        global_prompt = warm_prompt
        global_source = "textgrad"
        global_selection: dict[str, Any] = {
            "selected": global_source,
            "criterion": "fit_accuracy_no_internal_validation",
            "initial_fit_accuracy": initial_accuracy,
            "textgrad_fit_accuracy": warm_accuracy,
        }
        if external_validation_ids:
            initial_validation_accuracy, _correct, initial_validation_results = self._validate(
                initial_prompt,
                external_validation_ids,
                external_validation_samples,
                external_validation_targets,
            )
            warm_validation_accuracy, _correct, warm_validation_results = self._validate(
                warm_prompt,
                external_validation_ids,
                external_validation_samples,
                external_validation_targets,
            )
            initial_validation_balanced = self._balanced_accuracy(
                external_validation_ids,
                external_validation_targets,
                initial_validation_results,
            )
            warm_validation_balanced = self._balanced_accuracy(
                external_validation_ids,
                external_validation_targets,
                warm_validation_results,
            )
            # A rewritten prompt must demonstrate balanced validation improvement.
            # Exact ties keep the fixed rubric, preventing fit-only gains from silently
            # trading away minority-label recall on unseen cases.
            if (
                warm_validation_balanced
                > initial_validation_balanced + self.global_min_validation_gain
            ):
                global_prompt = warm_prompt
                global_source = "textgrad"
            else:
                global_prompt = initial_prompt
                global_source = "initial"
            global_selection = {
                "selected": global_source,
                "criterion": "internal_balanced_accuracy",
                "minimum_gain": self.global_min_validation_gain,
                "initial_fit_accuracy": initial_accuracy,
                "textgrad_fit_accuracy": warm_accuracy,
                "initial_validation_accuracy": initial_validation_accuracy,
                "textgrad_validation_accuracy": warm_validation_accuracy,
                "initial_validation_balanced_accuracy": initial_validation_balanced,
                "textgrad_validation_balanced_accuracy": warm_validation_balanced,
            }
            self.timeline.append({
                "kind": "global_selection",
                "node_id": f"global:{global_source}",
                **global_selection,
            })
        accumulated_root_id: Optional[str] = None
        if self.specialization_mode == "additive":
            # The root is the accumulation of validated deltas — the widest-coverage accepted
            # merge. Every accepted merge already cleared the no-regression-vs-base guard, so
            # this node is validated >= the flat base on its guard set. With no accepted merge
            # the root falls back to the base rubric, so the root is never worse than flat.
            accepted_parents = [
                node for node in nodes.values()
                if node.status in {"accepted", "partial"}
            ]
            if external_validation_ids:
                baseline_validation_accuracy = (
                    warm_validation_accuracy
                    if global_source == "textgrad"
                    else initial_validation_accuracy
                )
                baseline_validation_balanced = (
                    warm_validation_balanced
                    if global_source == "textgrad"
                    else initial_validation_balanced
                )
                root_candidates: list[CaliTreeNode] = []
                for node in accepted_parents:
                    candidate_accuracy, _correct, candidate_results = self._validate(
                        node.prompt,
                        external_validation_ids,
                        external_validation_samples,
                        external_validation_targets,
                    )
                    candidate_balanced = self._balanced_accuracy(
                        external_validation_ids,
                        external_validation_targets,
                        candidate_results,
                    )
                    node.generalization_accuracy = candidate_balanced
                    node.routing_eligible = bool(
                        candidate_accuracy >= baseline_validation_accuracy
                        and candidate_balanced
                        > baseline_validation_balanced + self.global_min_validation_gain
                    )
                    self.timeline.append({
                        "kind": "accumulated_root_validation",
                        "node_id": node.id,
                        "accuracy": candidate_accuracy,
                        "balanced_accuracy": candidate_balanced,
                        "baseline_accuracy": baseline_validation_accuracy,
                        "baseline_balanced_accuracy": baseline_validation_balanced,
                        "routing_eligible": node.routing_eligible,
                    })
                    if node.routing_eligible:
                        root_candidates.append(node)
                accepted_parents = root_candidates
            if accepted_parents:
                if self.root_objective == "balanced":
                    # Prefer the accumulated node with the best held-out balanced accuracy
                    # (each merge's generalization guard already measured it), so the root
                    # cannot trade the minority `partial` class for a wider `no`-heavy merge.
                    best = max(
                        accepted_parents,
                        key=lambda node: (
                            node.generalization_accuracy
                            if node.generalization_accuracy is not None
                            else -1.0,
                            len(node.covered_ids),
                            node.validation_accuracy,
                            node.id,
                        ),
                    )
                else:
                    best = max(
                        accepted_parents,
                        key=lambda node: (
                            len(node.covered_ids), node.validation_accuracy, node.id
                        ),
                    )
                global_prompt = best.prompt
                global_source = "accumulated"
                accumulated_root_id = best.id
            else:
                # Keep the flat prompt already selected on the full validation split. A
                # locally accepted merge remains useful evidence, but cannot become the
                # root (or intercept a route) until it improves the complete held-out set.
                accumulated_root_id = None
                flat_prompt_source = global_source
                global_source = "base"
                global_selection["base_prompt_source"] = flat_prompt_source
                if external_validation_ids:
                    global_selection["base_validation_accuracy"] = (
                        warm_validation_accuracy
                        if flat_prompt_source == "textgrad"
                        else initial_validation_accuracy
                    )
                else:
                    global_selection["base_fit_accuracy"] = warm_accuracy
            global_selection = {
                **global_selection,
                "selected": global_source,
                "criterion": "widest_validated_delta_accumulation",
                "accumulated_node": accumulated_root_id,
                "accepted_merges": accepted_merges,
            }
            self.timeline.append({
                "kind": "additive_root",
                "node_id": f"global:{global_source}",
                "selected": global_source,
                "accumulated_node": accumulated_root_id,
            })
        global_components = self.extract_components(global_prompt)
        global_criteria_embedding = self.embed(
            [self.component_text(global_components)]
        )[0]
        global_id = f"global:{global_source}"
        global_node = CaliTreeNode(
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
