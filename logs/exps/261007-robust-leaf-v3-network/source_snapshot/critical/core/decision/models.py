"""Portable executable leaf graphs; optimization labels never belong here."""
from dataclasses import asdict, dataclass

STATES = ('complete', 'partial', 'absent', 'unknown')
APPLICABILITY = ('applicable', 'not_applicable', 'unknown')
VERSION = 'decision-leaf-v2'

@dataclass(frozen=True)
class Requirement:
    id: str
    text: str
    source_phrase: str

@dataclass(frozen=True)
class Outcome:
    id: str
    requirement_ids: tuple[str, ...]
    description: str
    target: str
    reference: str = ''
    applicability: str = 'applicable'

@dataclass(frozen=True)
class Check:
    id: str
    outcome_id: str
    role: str
    question: str
    complete_when: str
    partial_when: str
    absent_when: str
    unknown_when: str
    dependencies: tuple[str, ...] = ()

@dataclass(frozen=True)
class ProgramSpec:
    instruction: str
    rubric: str
    requirements: tuple[Requirement, ...]
    outcomes: tuple[Outcome, ...]
    checks: tuple[Check, ...]
    checker_template: str
    version: str = VERSION
    aggregation: str = 'requested-all-some-none-v2'

    def to_dict(self):
        # JSON-normalize tuples for stable load/save parity.
        import json
        return json.loads(json.dumps(asdict(self)))

    @classmethod
    def from_dict(cls, row):
        row = dict(row)
        row['requirements'] = tuple(Requirement(**r) for r in row['requirements'])
        row['outcomes'] = tuple(Outcome(**{**r, 'requirement_ids': tuple(r['requirement_ids'])}) for r in row['outcomes'])
        row['checks'] = tuple(Check(**{**r, 'dependencies': tuple(r['dependencies'])}) for r in row['checks'])
        result = cls(**row)
        from .validation import validate_program
        validate_program(result)
        return result

@dataclass(frozen=True)
class Observation:
    check_id: str
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

    def to_dict(self):
        return {**asdict(self), 'observations': [o.to_dict() for o in self.observations], 'resolved': self.label is not None}
