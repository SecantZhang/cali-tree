"""Explicit callback services, validated settings, and per-build component state."""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .node.base import CaliTreeNode

Predictions = dict[str, dict[str, Any]]
Validation = tuple[float, list[str], Predictions]
Optimization = tuple[str, float, list[str], Predictions, int]
OptimizeCases = Callable[[str, list[str], dict[str, Any], dict[str, str]], Optimization]


@dataclass(frozen=True)
class CaliTreeServices:
    judge: Callable[[str, dict[str, Any]], dict[str, Any]]
    optimize: Callable[[str, str], str]
    extract_components: Callable[[str], dict[str, list[str]]]
    embed: Callable[[list[str]], list[list[float]]]
    merge_prompts: Callable[[str, str], dict[str, Any]]
    judge_many: Optional[Callable[[str, dict[str, dict[str, Any]]], Predictions]] = None
    format_feedback: Optional[
        Callable[[list[str], dict[str, Any], dict[str, str], Predictions], str]
    ] = None
    merge_many_prompts: Optional[Callable[[list[dict[str, Any]]], dict[str, Any]]] = None
    reflect: Optional[Callable[[Any], str]] = None
    budget_available: Optional[Callable[[], bool]] = None
    optimizer_identity: dict[str, Any] = field(default_factory=dict)
    optimizer_usage: Optional[Callable[[], dict[str, int]]] = None

    on_candidate: Optional[Callable[[dict[str, Any]], None]] = None

    def validate(
        self, prompt: str, ids: list[str], samples: dict[str, Any], targets: dict[str, str],
    ) -> Validation:
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


@dataclass(frozen=True)
class CaliTreeSettings:
    """Snapshot of the builder's already validated component settings."""

    max_steps: int
    merge_acceptance: float
    merge_objective: str
    merge_validation_cap: int
    merge_regression_tolerance: float
    merge_generalization_floor: float
    semantic_premerge_levels: int
    semantic_similarity_weight: float
    behavior_similarity_weight: float
    cross_generalization_weight: float
    behavioral_probe_cap: int
    cross_generalization_cap: int
    global_min_validation_gain: float
    specialization_mode: str
    root_objective: str


@dataclass
class OptimizationResult:
    prompt: str
    accuracy: float
    correct_ids: list[str]
    predictions: Predictions
    steps: int
    report: dict[str, Any] = field(default_factory=dict)

    def as_tuple(self) -> Optimization:
        return self.prompt, self.accuracy, self.correct_ids, self.predictions, self.steps


@dataclass
class PairScore:
    similarity: float
    diagnostics: dict[str, float]


@dataclass
class RootSelection:
    prompt: str
    source: str
    accumulated_node_id: Optional[str]
    report: dict[str, Any]


@dataclass
class BuildContext:
    services: CaliTreeServices
    settings: CaliTreeSettings
    optimize_cases: OptimizeCases
    initial_prompt: str
    samples: dict[str, Any]
    targets: dict[str, str]
    validation_samples: dict[str, Any]
    validation_targets: dict[str, str]
    timeline: list[dict[str, Any]]
    nodes: dict[str, CaliTreeNode] = field(default_factory=dict)
    case_embeddings: dict[str, list[float]] = field(default_factory=dict)
    warm_prompt: str = ""
    initial_accuracy: float = 0.0
    warm_accuracy: float = 0.0
    warm_results: Predictions = field(default_factory=dict)
    behavioral_probe_ids: list[str] = field(default_factory=list)
    rejected_static_generalization_prompts: set[str] = field(default_factory=set)
    artifacts: dict[str, Any] = field(default_factory=dict)
    executor: Any = None
    checkpoint: Any = None

    @property
    def item_ids(self) -> list[str]:
        return sorted(self.targets)

    @property
    def validation_ids(self) -> list[str]:
        return sorted(set(self.validation_samples) & set(self.validation_targets))
