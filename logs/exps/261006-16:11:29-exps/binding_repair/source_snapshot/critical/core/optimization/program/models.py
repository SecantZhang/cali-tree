"""Training-only search records, separate from executable specifications."""
from dataclasses import dataclass, field

from critical.core.decision.models import ProgramSpec, PredicateSpec, BoundPlan


@dataclass(frozen=True)
class ProgramEdit:
    operator: str
    target: str
    replacements: tuple[PredicateSpec, ...]
    reason: str

    def to_dict(self):
        return {"operator": self.operator, "target": self.target,
                "replacements": [p.to_dict() for p in self.replacements], "reason": self.reason}


@dataclass(frozen=True)
class Case:
    id: str
    group: str
    plan: BoundPlan
    evidence: dict
    target: str


@dataclass(frozen=True)
class ProgramSearchContext:
    fit: tuple[Case, ...]
    selection: tuple[Case, ...] = ()
    namespace: str = "search"


@dataclass
class ProgramOptimizationResult:
    program: ProgramSpec
    fit: dict
    selection: dict | None
    lineage: list[dict] = field(default_factory=list)
    stop_reason: str = "round_limit"
    support_status: str = "locally_fitted"

    def to_dict(self):
        from critical.core.decision.artifacts import export_program
        return {**export_program(self.program), "fit": self.fit, "selection": self.selection,
                "lineage": self.lineage, "stop_reason": self.stop_reason,
                "support_status": self.support_status}
