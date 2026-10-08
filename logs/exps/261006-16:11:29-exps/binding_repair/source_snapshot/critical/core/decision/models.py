"""Data-only executable programs. Training metadata never belongs in these types."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

STATES = ("complete", "partial", "absent", "unknown")
OPERATIONS = ("attribute", "relation", "add", "remove", "count", "style", "action", "other")


@dataclass(frozen=True)
class PredicateSpec:
    id: str
    role: str
    applies_to: tuple[str, ...]
    dependencies: tuple[str, ...]
    binding: str
    question: str
    complete_when: str
    partial_when: str
    absent_when: str
    unknown_when: str
    provenance: str = "instruction"

    def to_dict(self):
        row = asdict(self)
        row["applies_to"], row["dependencies"] = list(self.applies_to), list(self.dependencies)
        return row

    @classmethod
    def from_dict(cls, row):
        row = dict(row)
        row["applies_to"], row["dependencies"] = tuple(row["applies_to"]), tuple(row["dependencies"])
        return cls(**row)


@dataclass(frozen=True)
class ProgramSpec:
    rubric: str
    predicates: tuple[PredicateSpec, ...]
    version: str = "decision-program-v1"
    aggregation: str = "requested-all-some-none-v1"
    checker_template: str = field(default_factory=lambda: (Path(__file__).parents[1] /
        "prompts/templates/decision_program_v1/check.txt").read_text())

    def to_dict(self):
        return {"version": self.version, "aggregation": self.aggregation,
                "rubric": self.rubric, "predicates": [p.to_dict() for p in self.predicates],
                "checker_template": self.checker_template}

    @classmethod
    def from_dict(cls, row):
        from .validation import validate_program
        if set(row) != {"rubric", "predicates", "version", "aggregation", "checker_template"}:
            raise ValueError("Invalid program fields")
        result = cls(row["rubric"], tuple(PredicateSpec.from_dict(p) for p in row["predicates"]),
                     row["version"], row["aggregation"], row["checker_template"])
        validate_program(result)
        return result


@dataclass(frozen=True)
class Outcome:
    id: str
    requirement: str
    source_phrase: str
    target: str
    reference: str
    operation: str


@dataclass(frozen=True)
class BoundPlan:
    instruction: str
    outcomes: tuple[Outcome, ...]

    def to_dict(self):
        return {"instruction": self.instruction, "outcomes": [asdict(o) for o in self.outcomes]}

    @classmethod
    def from_dict(cls, row):
        from .validation import validate_plan
        if set(row) != {"instruction", "outcomes"}:
            raise ValueError("Invalid plan fields")
        result = cls(row["instruction"], tuple(Outcome(**o) for o in row["outcomes"]))
        validate_plan(result)
        return result


@dataclass(frozen=True)
class Observation:
    outcome_id: str
    predicate_id: str
    status: str
    evidence: str
    execution_ref: str
    valid: bool = True
    completion_tokens: int = 0

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class DecisionResult:
    label: str | None
    reason: str
    observations: tuple[Observation, ...]
    program_ref: str
    plan: BoundPlan

    def to_dict(self):
        return {"label": self.label, "resolved": self.label is not None, "reason": self.reason,
                "observations": [o.to_dict() for o in self.observations],
                "program_ref": self.program_ref, "plan": self.plan.to_dict()}
