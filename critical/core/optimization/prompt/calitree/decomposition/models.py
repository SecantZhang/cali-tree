"""Typed, serializable decomposition inputs and decisions.

The first strategy supports a finite structured-evidence vocabulary. Unknown
requirements are rejected instead of silently approximated.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any


EDIT_KEYS = {"color", "shape", "position", "count"}
STATUSES = {"satisfied", "violated", "unknown"}


@dataclass(frozen=True)
class Condition:
    key: str
    operator: str
    expected: Any

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InstructionPlan:
    edits: tuple[Condition, ...]
    allow_identity_change: bool = False
    allow_background_change: bool = False

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["edits"] = [condition.to_dict() for condition in self.edits]
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> InstructionPlan:
        return parse_plan(value)


@dataclass(frozen=True)
class ConditionResult:
    status: str
    rationale: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, str) or self.status not in STATUSES:
            raise ValueError("Invalid atomic status")
        if not isinstance(self.rationale, str):
            raise ValueError("Atomic rationale must be text")

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> ConditionResult:
        if not isinstance(value, dict) or set(value) != {"status", "rationale"}:
            raise ValueError("Invalid atomic check response")
        return cls(value["status"], value["rationale"])


@dataclass(frozen=True)
class DecompositionResult:
    label: str
    rationale: str
    trace: dict[str, Any]

    def judgment(self) -> dict[str, str]:
        """The judge callback contract accepted by CaliTreeServices."""
        return {"label": self.label, "rationale": self.rationale}


def parse_condition(edit: Any) -> Condition:
    if not isinstance(edit, dict) or set(edit) != {"key", "operator", "expected"}:
        raise ValueError("Malformed condition")
    key, op, expected = edit["key"], edit["operator"], edit["expected"]
    if not isinstance(key, str) or key not in EDIT_KEYS:
        raise ValueError("Unsupported requested check; each key must name one check")
    if not isinstance(op, str):
        raise ValueError("Condition operator must be a string")
    if key == "count":
        valid = op in {"equals", "at_least"} and type(expected) is int and expected >= 0
    elif key == "position":
        valid = op == "equals" and isinstance(expected, str) and expected in {
            "left_of_reference", "right_of_reference",
        }
    elif key == "shape":
        valid = op == "equals" and isinstance(expected, str) and bool(expected)
    else:
        valid = ((op == "equals" and isinstance(expected, str) and bool(expected))
                 or (op == "one_of" and isinstance(expected, list)
                     and len(expected) == 3 and all(isinstance(x, str) and x for x in expected)
                     and expected == [expected[0], f"light {expected[0]}", f"dark {expected[0]}"]))
    if not valid:
        raise ValueError(f"Invalid operator or expected value for {key}")
    return Condition(key, op, deepcopy(expected))


def parse_plan(value: Any) -> InstructionPlan:
    if not isinstance(value, dict) or set(value) != {
        "edits", "allow_identity_change", "allow_background_change",
    }:
        raise ValueError("Instruction plan has unexpected fields")
    for key in ("allow_identity_change", "allow_background_change"):
        if type(value[key]) is not bool:
            raise ValueError(f"{key} must be boolean")
    if not isinstance(value["edits"], list) or len(value["edits"]) > 4:
        raise ValueError("Expected at most four requested edits")
    conditions = [parse_condition(edit) for edit in value["edits"]]
    if len({condition.key for condition in conditions}) != len(conditions):
        raise ValueError("Duplicate requested check")
    return InstructionPlan(tuple(sorted(conditions, key=lambda condition: condition.key)),
                           value["allow_identity_change"], value["allow_background_change"])
