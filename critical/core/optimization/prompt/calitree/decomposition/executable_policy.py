"""Validated, data-only boolean decisions compiled from an optimized rubric.

Predicate meanings and label boundaries come from the rubric compiler. This
module supplies only expression validation and three-valued execution; it has
no image-editing thresholds or hand-specified grading rules.
"""

from copy import deepcopy
from dataclasses import dataclass
import re

from .vision_models import SemanticRubric, nonempty_text


EXECUTABLE_VERSION = "calitree-decomposition-executable-v1"


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}", value):
        raise ValueError("Invalid execution identifier")
    return value


def expression_references(expression, allowed, depth=0):
    if depth > 8 or not isinstance(expression, dict) or len(expression) != 1:
        raise ValueError("Invalid or excessively nested boolean expression")
    operator, value = next(iter(expression.items()))
    if operator == "predicate":
        if not isinstance(value, str) or value not in allowed:
            raise ValueError("Unknown predicate reference")
        return {value}
    if operator == "not":
        return expression_references(value, allowed, depth+1)
    if operator not in {"all", "any"} or not isinstance(value, list) or not 1 <= len(value) <= 16:
        raise ValueError("Unsupported boolean expression")
    return set().union(*(expression_references(child, allowed, depth+1) for child in value))


def evaluate_expression(expression, values):
    """Kleene logic: decisive false/true operands dominate all/any respectively."""
    operator, value = next(iter(expression.items()))
    if operator == "predicate":
        return values[value]
    if operator == "not":
        result = evaluate_expression(value, values)
        return None if result is None else not result
    results = [evaluate_expression(child, values) for child in value]
    if operator == "all":
        return False if False in results else None if None in results else True
    if operator == "any":
        return True if True in results else None if None in results else False
    raise ValueError("Unsupported boolean expression")


@dataclass(frozen=True)
class ExecutableRubric:
    source: SemanticRubric
    program: dict

    def to_dict(self):
        return {"version": EXECUTABLE_VERSION, "source": self.source.to_dict(),
                "program": deepcopy(self.program)}

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != {"version", "source", "program"} or value["version"] != EXECUTABLE_VERSION:
            raise ValueError("Invalid executable rubric artifact")
        return parse_executable_policy(value["program"], SemanticRubric.from_dict(value["source"]))

    def decide(self, findings):
        # Validate even directly constructed/mutated instances before execution.
        policy = ExecutableRubric.from_dict(self.to_dict())
        allowed = {p["id"] for p in policy.program["predicates"]}
        if not isinstance(findings, dict) or set(findings) != allowed or any(type(v) is not bool and v is not None for v in findings.values()):
            raise ValueError("Every predicate needs a true/false/unknown finding")
        attempts = []
        for rule in policy.program["rules"]:
            result = evaluate_expression(rule["when"], findings)
            attempts.append({"rule_id": rule["id"], "result": result})
            if result is None:
                # A later true rule cannot safely override an earlier unresolved
                # decision. Unknown is never silently interpreted as false.
                raise ValueError(f"Unresolved predicate blocks rule {rule['id']}")
            if result:
                return {"label": rule["label"], "rule_id": rule["id"],
                        "rubric_unit_ids": deepcopy(rule["rubric_unit_ids"]),
                        "rules_checked": attempts}
        return {"label": policy.program["default"], "rule_id": None,
                "rubric_unit_ids": deepcopy(policy.program["default_rubric_unit_ids"]),
                "rules_checked": attempts}


def parse_executable_policy(value, source):
    source = SemanticRubric.from_dict(source.to_dict())
    if not isinstance(value, dict) or set(value) != {"predicates", "rules", "default", "default_rubric_unit_ids"}:
        raise ValueError("Malformed executable policy")
    units = {u["id"] for u in source.units}
    covered = set()

    def citations(ids):
        if not isinstance(ids, list) or not ids or any(not isinstance(x, str) or x not in units for x in ids) or len(set(ids)) != len(ids):
            raise ValueError("Invalid execution rubric citations")
        covered.update(ids)

    predicates, rules = value["predicates"], value["rules"]
    if not isinstance(predicates, list) or not 1 <= len(predicates) <= 16 or not isinstance(rules, list) or not 1 <= len(rules) <= 12:
        raise ValueError("Expected bounded nonempty execution predicates/rules")
    identifiers = set()
    for predicate in predicates:
        if not isinstance(predicate, dict) or set(predicate) != {"id", "question", "rubric_unit_ids"}:
            raise ValueError("Malformed execution predicate")
        identifier = _identifier(predicate["id"])
        if identifier in identifiers:
            raise ValueError("Duplicate execution predicate")
        identifiers.add(identifier)
        nonempty_text(predicate["question"], "Predicate question")
        citations(predicate["rubric_unit_ids"])
    rule_ids, referenced = set(), set()
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) != {"id", "when", "label", "rubric_unit_ids"}:
            raise ValueError("Malformed execution rule")
        identifier = _identifier(rule["id"])
        if identifier in rule_ids:
            raise ValueError("Duplicate execution rule")
        rule_ids.add(identifier)
        if not isinstance(rule["label"], str) or rule["label"] not in {"no", "partial", "yes"}:
            raise ValueError("Invalid execution label")
        referenced.update(expression_references(rule["when"], identifiers))
        citations(rule["rubric_unit_ids"])
    if referenced != identifiers:
        raise ValueError("Every compiled predicate must be used by a rule")
    if not isinstance(value["default"], str) or value["default"] not in {"no", "partial", "yes"}:
        raise ValueError("Invalid default execution label")
    citations(value["default_rubric_unit_ids"])
    required = {u["id"] for u in source.units if u["kind"] in {"decision", "exception"}}
    if not required <= covered:
        raise ValueError(f"Execution omitted a decision or exception unit: {sorted(required - covered)}")
    return ExecutableRubric(source, deepcopy(value))
