"""Local fitting inputs and immutable structural transactions."""
from dataclasses import asdict, dataclass, field
from critical.core.decision.models import Requirement, Outcome, Check

@dataclass(frozen=True)
class Case:
    id: str
    instruction: str
    evidence: dict
    group: str = ''

@dataclass(frozen=True)
class Edit:
    operator: str
    target: str = ''
    outcomes: tuple[Outcome, ...] = ()
    checks: tuple[Check, ...] = ()

@dataclass(frozen=True)
class Transaction:
    edits: tuple[Edit, ...]
    reason: str
    requirements: tuple[Requirement, ...] = ()
    def to_dict(self):
        return asdict(self)
    @classmethod
    def from_dict(cls, row):
        return cls(tuple(Edit(e['operator'], e['target'],
                   tuple(Outcome(**{**o, 'requirement_ids': tuple(o['requirement_ids'])}) for o in e['outcomes']),
                   tuple(Check(**{**c, 'dependencies': tuple(c['dependencies'])}) for c in e['checks'])) for e in row['edits']),
                   row['reason'], tuple(Requirement(**r) for r in row['requirements']))

@dataclass
class LeafResult:
    case_id: str
    seed: dict | None = None
    selected: dict | None = None
    candidates: dict = field(default_factory=dict)
    lineage: list = field(default_factory=list)
    status: str = 'unresolved'
    stop_reason: str = ''
    usage: dict = field(default_factory=dict)
    def to_dict(self):
        return asdict(self)
