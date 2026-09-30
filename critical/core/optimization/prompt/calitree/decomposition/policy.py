"""Validated data-only policies and deterministic veto/base/cap execution."""

from __future__ import annotations

import json
import hashlib
from copy import deepcopy
from dataclasses import asdict
from typing import Any

from .models import Condition, InstructionPlan, parse_condition, parse_plan

COUNTS = {"edit_count", "satisfied_count", "violated_count", "unknown_count"}
STATUSES = {"satisfied", "violated", "unknown"}
LABELS = {"no", "partial", "yes"}
OPERATORS = {"eq", "ne", "lt", "le", "gt", "ge"}
POLICY_VERSION = "calitree-decomposition-policy-v1"


class UnsupportedDecompositionError(ValueError):
    """The rubric cannot be represented by this strategy's policy language."""


def validate_expression(expr, facts, depth=0):
    if depth > 8 or not isinstance(expr, dict):
        raise ValueError("Invalid or too deeply nested rule expression")
    if set(expr) in ({"all"}, {"any"}):
        children = expr[next(iter(expr))]
        if not isinstance(children, list) or not 1 <= len(children) <= 16:
            raise ValueError("Boolean expressions need 1-16 children")
        for child in children:
            validate_expression(child, facts, depth + 1)
    elif set(expr) == {"fact", "operator", "value"}:
        fact, op, value = expr["fact"], expr["operator"], expr["value"]
        if not isinstance(fact, str) or fact not in facts or not isinstance(op, str) or op not in OPERATORS:
            raise ValueError("Unknown fact or operator")
        kind = "count" if fact in COUNTS else "status"
        if isinstance(value, dict):
            if set(value) != {"fact"} or not isinstance(value["fact"], str) or value["fact"] not in facts:
                raise ValueError("Unknown comparison fact")
            other_kind = "count" if value["fact"] in COUNTS else "status"
            if kind != other_kind:
                raise ValueError("Cannot compare counts with statuses")
            if kind == "status":
                raise ValueError("Guard comparisons require explicit status values")
        elif kind == "count":
            if type(value) is not int or value < 0:
                raise ValueError("Counts require nonnegative integer comparisons")
        elif not isinstance(value, str) or value not in STATUSES:
            raise ValueError("Guard comparisons require known statuses")
        if kind == "status" and op != "eq":
            raise ValueError("Statuses require explicit equality comparisons")
    else:
        raise ValueError("Unknown rule expression")


def evaluate_expression(expr, facts):
    if "all" in expr or "any" in expr:
        key = "all" if "all" in expr else "any"
        values = [evaluate_expression(child, facts) for child in expr[key]]
        return all(values) if key == "all" else any(values)
    left, right = facts[expr["fact"]], expr["value"]
    if isinstance(right, dict):
        right = facts[right["fact"]]
    op = expr["operator"]
    if op == "eq":
        return left == right
    if op == "ne":
        return left != right
    if op == "lt":
        return left < right
    if op == "le":
        return left <= right
    if op == "gt":
        return left > right
    return left >= right


class CompiledPolicy:
    """Validated policy bound to its source rubric, with defensive serialization."""

    def __init__(self, specification: dict[str, Any], rubric: str) -> None:
        validate_policy(specification, rubric)
        self._specification = deepcopy(specification)
        self._rubric = rubric

    @property
    def rubric(self) -> str:
        return self._rubric

    @property
    def specification(self) -> dict[str, Any]:
        return deepcopy(self._specification)

    def to_dict(self) -> dict[str, Any]:
        return {"version": POLICY_VERSION, "rubric": self.rubric,
                "rubric_sha256": hashlib.sha256(self.rubric.encode()).hexdigest(),
                "specification": self.specification}

    @classmethod
    def from_dict(cls, value: Any) -> CompiledPolicy:
        if not isinstance(value, dict) or set(value) != {
            "version", "rubric", "rubric_sha256", "specification",
        } or value["version"] != POLICY_VERSION:
            raise ValueError("Invalid compiled-policy artifact")
        rubric = value["rubric"]
        if not isinstance(rubric, str) or hashlib.sha256(rubric.encode()).hexdigest() != value["rubric_sha256"]:
            raise ValueError("Compiled-policy rubric hash mismatch")
        return cls(value["specification"], rubric)

    def edits(self, plan):
        plan = parse_plan(plan.to_dict())
        conditions = {c.key: c for c in plan.edits if c.key in self._specification["supported_edits"]}
        for value in self._specification.get("criteria", []):
            condition = parse_condition(value)
            conditions[condition.key] = condition
        return tuple(conditions[key] for key in sorted(conditions))

    def guards(self, plan):
        plan = parse_plan(plan.to_dict())
        return tuple(Condition(g["key"], "equals", g["expected"])
                     for g in self._specification["guards"]
                     if not (g["unless_permission"] and getattr(plan, g["unless_permission"])))

    def decide(self, edits, guards, plan):
        for rows, conditions in ((edits, self.edits(plan)), (guards, self.guards(plan))):
            if not isinstance(rows, (list, tuple)) or any(
                not isinstance(row, dict) or "condition" not in row or "status" not in row for row in rows
            ):
                raise ValueError("Malformed condition results")
            if (len(rows) != len(conditions)
                    or {json.dumps(r["condition"], sort_keys=True) for r in rows}
                    != {json.dumps(asdict(c), sort_keys=True) for c in conditions}):
                raise ValueError("Decision requires exactly the applicable checks")
        if any(not isinstance(row["status"], str) or row["status"] not in STATUSES for row in [*edits, *guards]):
            raise ValueError("Invalid atomic status")
        facts = {"edit_count": len(edits)}
        facts.update({f"{status}_count": sum(r["status"] == status for r in edits)
                      for status in ("satisfied", "violated", "unknown")})
        observed = {row["condition"]["key"]: row["status"] for row in guards}
        facts.update({f"guard.{g['key']}": observed.get(g["key"], "satisfied")
                      for g in self._specification["guards"]})
        exempt = [g["key"] for g in self._specification["guards"] if g["key"] not in observed]
        def trace(phase, index, rule):
            return {"phase": phase, "rule": index, "source_line": rule["source"],
                    "source": self.rubric.splitlines()[rule["source"] - 1],
                    "facts": facts, "exempt_guards": exempt}

        if "decision_rules" not in self._specification:
            # Historical flat policies remain inspectable as a frozen baseline.
            for index, rule in enumerate(self._specification["rules"]):
                if evaluate_expression(rule["when"], facts):
                    return rule["label"], trace("legacy", index, rule)
            fallback = self._specification["default"]
            return fallback["label"], trace("legacy", "default", fallback)

        for index, rule in enumerate(self._specification["veto_rules"]):
            if evaluate_expression(rule["when"], facts):
                return rule["label"], trace("veto", index, rule)
        selected, selected_index = self._specification["default"], "default"
        for index, rule in enumerate(self._specification["decision_rules"]):
            if evaluate_expression(rule["when"], facts):
                selected, selected_index = rule, index
                break
        label = selected["label"]
        decision = trace("base", selected_index, selected)
        decision.update({"base_label": label, "caps": []})
        rank = {"no": 0, "partial": 1, "yes": 2}
        for index, rule in enumerate(self._specification["caps"]):
            if evaluate_expression(rule["when"], facts) and rank[rule["label"]] < rank[label]:
                label = rule["label"]
                decision["caps"].append(trace("cap", index, rule))
        decision["final_label"] = label
        return label, decision


def validate_policy(value: Any, rubric: str) -> None:
    if not isinstance(rubric, str) or not rubric.strip():
        raise ValueError("Policy requires a nonempty rubric")
    if isinstance(value, dict) and "unsupported" in value:
        raise UnsupportedDecompositionError(f"Rubric cannot be compiled: {value['unsupported']}")
    legacy_fields = {"supported_edits", "guards", "rules", "default"}
    staged_fields = {"supported_edits", "criteria", "guards", "veto_rules", "decision_rules", "caps", "default"}
    if not isinstance(value, dict) or set(value) not in (legacy_fields, staged_fields):
        raise ValueError("Unexpected policy fields")
    supported = value["supported_edits"]
    if (not isinstance(supported, list) or len(supported) > 4
            or any(not isinstance(x, str) or x not in {"color", "shape", "position", "count"} for x in supported)
            or len(set(supported)) != len(supported)):
        raise ValueError("Invalid supported checks")
    guards = value["guards"]
    if not isinstance(guards, list) or len(guards) > 3:
        raise ValueError("Invalid guards")
    seen = set()
    permissions = {"content_recognizable": None, "subject_identity": "allow_identity_change",
                   "background": "allow_background_change"}
    for guard in guards:
        if not isinstance(guard, dict) or set(guard) != {"key", "expected", "unless_permission"}:
            raise ValueError("Malformed guard")
        key = guard["key"]
        if not isinstance(key, str) or key not in permissions or key in seen:
            raise ValueError("Unsupported or duplicate guard")
        seen.add(key)
        if guard["unless_permission"] not in (None, permissions[key]):
            raise ValueError("Permission belongs to a different guard")
        expected = guard["expected"]
        if ((key == "content_recognizable" and type(expected) is not bool)
                or (key != "content_recognizable" and expected not in ("preserved", "changed"))):
            raise ValueError("Invalid guard expectation")
    facts = COUNTS | {f"guard.{key}" for key in seen}
    if set(value) == staged_fields:
        criteria = value["criteria"]
        if not isinstance(criteria, list) or len(criteria) > 4:
            raise ValueError("Invalid fixed criteria")
        conditions = [parse_condition(item) for item in criteria]
        if len({c.key for c in conditions}) != len(conditions) or any(c.key not in supported for c in conditions):
            raise ValueError("Duplicate or unsupported fixed criterion")
        rules = []
        for phase in ("veto_rules", "decision_rules", "caps"):
            group = value[phase]
            if not isinstance(group, list) or len(group) > 32:
                raise ValueError("Invalid policy rule phase")
            rules.extend(group)
    else:
        rules = value["rules"]
        if not isinstance(rules, list) or not 1 <= len(rules) <= 32:
            raise ValueError("Expected 1-32 decision rules")
    for rule in [*rules, value["default"]]:
        fields = {"label", "source"} if rule is value["default"] else {"when", "label", "source"}
        if not isinstance(rule, dict) or set(rule) != fields:
            raise ValueError("Malformed decision rule")
        if not isinstance(rule["label"], str) or rule["label"] not in LABELS:
            raise ValueError("Invalid decision label")
        if (type(rule["source"]) is not int or not 1 <= rule["source"] <= len(rubric.splitlines())
                or not rubric.splitlines()[rule["source"] - 1].strip()):
            raise ValueError("Rule source is not a nonempty rubric line")
        if "when" in rule:
            validate_expression(rule["when"], facts)


def parse_policy(value: Any, rubric: str) -> CompiledPolicy:
    return CompiledPolicy(value, rubric)
