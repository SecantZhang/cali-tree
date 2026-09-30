"""Lossless rubric units and open-vocabulary instruction conditions."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import re
from typing import Any


VISION_VERSION = "calitree-decomposition-vision-v1"


def nonempty_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    return value


@dataclass(frozen=True)
class SemanticRubric:
    rubric: str
    units: tuple[dict[str, Any], ...]

    def to_dict(self):
        return {"version": VISION_VERSION, "rubric": self.rubric,
                "rubric_sha256": hashlib.sha256(self.rubric.encode()).hexdigest(),
                "units": deepcopy(list(self.units))}

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != {"version", "rubric", "rubric_sha256", "units"}:
            raise ValueError("Invalid semantic rubric artifact")
        rubric = nonempty_text(value["rubric"], "Rubric")
        if value["version"] != VISION_VERSION or value["rubric_sha256"] != hashlib.sha256(rubric.encode()).hexdigest():
            raise ValueError("Semantic rubric version/hash mismatch")
        if not isinstance(value["units"], list) or any(not isinstance(u, dict) or set(u) != {"id", "kind", "lines", "text"} for u in value["units"]):
            raise ValueError("Malformed semantic rubric units")
        groups = {"units": [{"kind": u["kind"], "lines": u["lines"]} for u in value["units"]]}
        result = parse_semantic_rubric(groups, rubric)
        if result.to_dict() != value:
            raise ValueError("Semantic rubric units differ from their source")
        return result


def parse_semantic_rubric(value, rubric):
    nonempty_text(rubric, "Rubric")
    if not isinstance(value, dict) or set(value) != {"units"} or not isinstance(value["units"], list) or not value["units"]:
        raise ValueError("Expected nonempty rubric units")
    lines = rubric.splitlines()
    expected = {i for i, line in enumerate(lines, 1) if line.strip()}
    seen, groups = [], []
    for unit in value["units"]:
        if not isinstance(unit, dict) or set(unit) != {"kind", "lines"}:
            raise ValueError("Invalid rubric unit fields: expected exactly kind and lines")
        if not isinstance(unit["kind"], str) or unit["kind"] not in {"decision", "exception", "scope", "output"}:
            raise ValueError(f"Invalid rubric unit kind {unit['kind']!r}; allowed kinds: decision, exception, scope, output")
        ids = unit["lines"]
        if not isinstance(ids, list) or not ids or any(type(i) is not int or i not in expected for i in ids) or ids != sorted(set(ids)):
            raise ValueError("Invalid rubric line references")
        seen.extend(ids)
        groups.append({"kind": unit["kind"], "lines": ids})
    if Counter(seen) != Counter(expected):
        raise ValueError("Every nonempty rubric line must occur exactly once")
    # A model may group distant output/scope clauses together. Canonicalize
    # these classifications into consecutive runs in SOURCE order rather than
    # reordering their text or discarding valid line coverage.
    kinds = {line: unit["kind"] for unit in groups for line in unit["lines"]}
    groups = []
    for line in sorted(expected):
        if not groups or groups[-1]["kind"] != kinds[line]:
            groups.append({"kind": kinds[line], "lines": []})
        groups[-1]["lines"].append(line)
    for unit in groups:
        unit["text"] = "\n".join(lines[i-1] for i in unit["lines"])
    for i, unit in enumerate(groups, 1):
        unit["id"] = f"u{i}"
    return SemanticRubric(rubric, tuple(deepcopy(groups)))


@dataclass(frozen=True)
class SemanticCondition:
    id: str
    requirement: str
    target: str
    reference: str | None
    source_phrase: str

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class SemanticInstruction:
    instruction: str
    conditions: tuple[SemanticCondition, ...]

    def to_dict(self):
        return {"instruction": self.instruction, "conditions": [c.to_dict() for c in self.conditions]}


def parse_semantic_instruction(value, instruction):
    nonempty_text(instruction, "Instruction")
    if not isinstance(value, dict) or set(value) != {"conditions"} or not isinstance(value["conditions"], list) or not 1 <= len(value["conditions"]) <= 12:
        raise ValueError("Expected 1-12 requested conditions")
    conditions, seen, covered = [], set(), set()
    for row in value["conditions"]:
        if not isinstance(row, dict) or set(row) != {"id", "requirement", "target", "reference", "source_phrase"}:
            raise ValueError("Malformed semantic condition")
        for key in ("id", "requirement", "target", "source_phrase"):
            nonempty_text(row[key], key)
        if row["id"] in seen or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}", row["id"]):
            raise ValueError("Invalid or duplicate condition ID")
        seen.add(row["id"])
        if row["reference"] is not None:
            nonempty_text(row["reference"], "Reference")
        phrase = row["source_phrase"]
        if phrase not in instruction:
            match = re.search(re.escape(phrase), instruction, flags=re.IGNORECASE)
            if match is None:
                raise ValueError("Condition source_phrase must be verbatim instruction text")
            # Repair only casing of a quote by copying actual source bytes;
            # this cannot invent an omitted word or paraphrase an action.
            phrase = match.group()
            row = {**row, "source_phrase": phrase}
        for match in re.finditer(re.escape(phrase), instruction, flags=re.IGNORECASE):
            covered.update(range(match.start(), match.end()))
        conditions.append(SemanticCondition(**row))
    # Editing requests can use a question wrapper rather than an imperative;
    # do not confuse that wrapper or purpose connectors with missing content.
    wrapper = re.match(r"\s*what\s+if\s+", instruction, flags=re.IGNORECASE)
    if wrapper:
        covered.update(range(wrapper.end()))
    for word in re.finditer(r"\w+", instruction):
        if word.group().lower() not in {"and", "then", "to"} and any(i not in covered for i in range(word.start(), word.end())):
            raise ValueError("Instruction words were omitted from the source coverage")
    return SemanticInstruction(instruction, tuple(conditions))


def parse_finding(value):
    fields = {"fulfillment", "source_observation", "edited_observation", "explanation"}
    if not isinstance(value, dict) or set(value) != fields or not isinstance(value["fulfillment"], str) or value["fulfillment"] not in {"complete", "partial", "absent", "unknown"}:
        raise ValueError("Invalid condition finding")
    for key in fields - {"fulfillment"}:
        nonempty_text(value[key], key)
    return deepcopy(value)


def parse_preservation(value):
    if not isinstance(value, dict) or set(value) != {"recognizability", "scene_continuity", "unrequested_changes", "explanation"}:
        raise ValueError("Invalid preservation report")
    if not isinstance(value["recognizability"], str) or not isinstance(value["scene_continuity"], str) or value["recognizability"] not in {"clear", "unclear", "lost"} or value["scene_continuity"] not in {"same", "partly_changed", "replaced", "unknown"}:
        raise ValueError("Invalid preservation status")
    nonempty_text(value["explanation"], "Preservation explanation")
    if not isinstance(value["unrequested_changes"], list) or len(value["unrequested_changes"]) > 20:
        raise ValueError("Invalid unrequested changes")
    for row in value["unrequested_changes"]:
        if not isinstance(row, dict) or set(row) != {"description", "severity", "evidence"} or not isinstance(row["severity"], str) or row["severity"] not in {"minor", "meaningful", "major"}:
            raise ValueError("Invalid unrequested change")
        nonempty_text(row["description"], "Change description")
        nonempty_text(row["evidence"], "Change evidence")
    return deepcopy(value)
