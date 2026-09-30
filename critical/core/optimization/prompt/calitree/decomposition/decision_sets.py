"""Data contracts for frozen casewise criteria and reusable neutral evidence.

These artifacts preserve observations and their origins. They do not claim that
fitted criteria are faithful to their prompt or that local condition fingerprints
are a shared semantic ontology.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json

CRITERIA_VERSION = "calitree-frozen-criteria-v1"
EVIDENCE_VERSION = "calitree-neutral-evidence-v1"
STATUS = ("complete", "partial", "absent", "unknown")
CONDITION_FIELDS = ("id", "requirement", "source_selector", "complete_when",
                    "partial_when", "absent_when", "unknown_when")
NEUTRAL_PROPERTIES = {
    "existence_attributes": "List all visible instances of {object_class}, with distinguishing shape, color, material, relative size and image location; report if none can be identified.",
    "count": "Count and separately describe every visible instance of {object_class}, including partial or uncertain instances, their sizes, attributes and locations.",
    "spatial_relations": "Describe positions of all visible instances of {object_class} relative to every visible instance of {reference_class}; distinguish horizontal, vertical and depth relations, with uncertainty.",
    "body_state": "Describe visible posture, orientation, gaze, gestures, contact with objects and obstructions for every visible {object_class}; distinguish observation from interpretation.",
    "facial_expression": "Describe observable mouth shape, eyes, face geometry, equipment or occlusion for every visible {object_class}. List plausible interpretations of the expression and their visual support without presuming one.",
    "interaction": "Describe visible contacts and relative positions among every {object_class} and {reference_class}, including whether they are touching, supported, held, disconnected or obscured. Do not infer an unobserved action.",
    "style_distribution": "Describe the visual rendering style of the entire scene and its major regions. Identify any regions with differing style, their approximate extent, and whether they are pictures within the scene rather than the scene itself.",
}


def json_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def text_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected nonempty text")
    return value


def _hashes(value):
    if not isinstance(value, list) or len(value) != 2 or any(
        not isinstance(s, str) or len(s) != 64 or any(c not in "0123456789abcdef" for c in s) for s in value
    ):
        raise ValueError("Expected SOURCE and EDITED SHA-256 identities")


def validate_criteria(value):
    if not isinstance(value, dict) or set(value) != {"conditions", "rubric_conflicts"}:
        raise ValueError("Expected conditions and rubric_conflicts")
    conditions = value["conditions"]
    if not isinstance(conditions, list) or not 1 <= len(conditions) <= 8:
        raise ValueError("Expected 1-8 conditions")
    for condition in conditions:
        if not isinstance(condition, dict) or set(condition) != set(CONDITION_FIELDS):
            raise ValueError("Incorrect condition fields")
        for item in condition.values():
            _text(item)
    if len({c["id"] for c in conditions}) != len(conditions):
        raise ValueError("Duplicate condition IDs")
    if not isinstance(value["rubric_conflicts"], list):
        raise ValueError("Invalid rubric_conflicts")
    for conflict in value["rubric_conflicts"]:
        _text(conflict)
    return deepcopy(value)


CHECK_SCHEMA = {
    "type": "object", "properties": {
        "source_observation": {"type": "string"},
        "edited_observation": {"type": "string"},
        "status": {"type": "string", "enum": list(STATUS)},
        "rationale": {"type": "string"},
    },
    "required": ["source_observation", "edited_observation", "status", "rationale"],
    "additionalProperties": False,
}


def validate_criterion_check(value):
    if not isinstance(value, dict) or set(value) != set(CHECK_SCHEMA["properties"]):
        raise ValueError("Incorrect check fields")
    for item in value.values():
        _text(item)
    if value["status"] not in STATUS:
        raise ValueError("Invalid condition status")
    return deepcopy(value)


@dataclass(frozen=True)
class FrozenCriteria:
    """Serialized immutable content; to_dict returns an independent copy."""

    _json: str

    @classmethod
    def bind(cls, prompt, instruction, plan, *, feedback_used=False, origin="caller"):
        _text(prompt)
        _text(instruction)
        _text(origin)
        if type(feedback_used) is not bool:
            raise ValueError("feedback_used must be boolean")
        value = {"version": CRITERIA_VERSION, "prompt_sha256": text_hash(prompt),
                 "instruction": instruction, "plan": validate_criteria(plan),
                 "provenance": {"feedback_used": feedback_used, "origin": origin}}
        return cls.from_dict({**value, "artifact_sha256": json_hash(value)})

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != {
            "version", "prompt_sha256", "instruction", "plan", "provenance", "artifact_sha256"
        } or value["version"] != CRITERIA_VERSION:
            raise ValueError("Invalid frozen criteria artifact")
        _hashes([value["prompt_sha256"], value["prompt_sha256"]])
        _text(value["instruction"])
        validate_criteria(value["plan"])
        provenance = value["provenance"]
        if not isinstance(provenance, dict) or set(provenance) != {"feedback_used", "origin"}:
            raise ValueError("Invalid criteria provenance")
        if type(provenance["feedback_used"]) is not bool:
            raise ValueError("Invalid feedback provenance")
        _text(provenance["origin"])
        if value["artifact_sha256"] != json_hash({k: v for k, v in value.items() if k != "artifact_sha256"}):
            raise ValueError("Changed frozen criteria artifact")
        return cls(json.dumps(value, sort_keys=True, allow_nan=False))

    def to_dict(self):
        return json.loads(self._json)

    def validate_context(self, prompt, instruction):
        value = self.to_dict()
        if text_hash(prompt) != value["prompt_sha256"] or instruction != value["instruction"]:
            raise ValueError("Frozen criteria prompt/instruction binding mismatch")
        return value


def probe_descriptor(probe):
    if not isinstance(probe, dict) or set(probe) != {"property", "object_class", "reference_class"}:
        raise ValueError("Unexpected neutral probe fields")
    if not isinstance(probe["property"], str) or probe["property"] not in NEUTRAL_PROPERTIES:
        raise ValueError("Unsupported neutral property")
    _text(probe["object_class"])
    if probe["reference_class"] is not None:
        _text(probe["reference_class"])
    if probe["property"] in {"spatial_relations", "interaction"} and probe["reference_class"] is None:
        raise ValueError("Relation probe requires a reference class")
    # Only lexical normalization: aliases or semantic equivalence require a
    # separate concept mapping audit and must not be inferred here.
    return {key: " ".join(value.lower().split()) if isinstance(value, str) else value
            for key, value in probe.items()}


def compile_neutral_probes(probes):
    """Validate typed properties and render questions without desired states.

    Class nouns are caller-supplied: structural validation is not a semantic
    proof of neutrality. Callers must audit descriptors before fitting on them.
    """
    if not isinstance(probes, list) or not 1 <= len(probes) <= 8:
        raise ValueError("Expected 1-8 neutral probes")
    by_id, records = {}, []
    for raw in probes:
        if not isinstance(raw, dict) or set(raw) not in (
            {"id", "property", "object_class", "reference_class"},
            {"id", "property", "object_class", "reference_class", "condition_ids"},
        ):
            raise ValueError("Unexpected probe import fields")
        old_id = _text(raw["id"])
        if old_id in by_id:
            raise ValueError("Duplicate probe IDs")
        descriptor = probe_descriptor({k: raw[k] for k in ("property", "object_class", "reference_class")})
        key = "probe:" + json_hash(descriptor)
        if any(r["key"] == key for r in records):
            raise ValueError("Duplicate semantic probe descriptor")
        by_id[old_id] = key
        records.append({"key": key, **descriptor,
                        "question": NEUTRAL_PROPERTIES[descriptor["property"]].format(**descriptor)})
    return by_id, records


def validate_neutral_answers(value, ids):
    if not isinstance(value, dict) or set(value) != {"answers"} or not isinstance(value["answers"], list):
        raise ValueError("Invalid neutral answers")
    seen = set()
    for answer in value["answers"]:
        if not isinstance(answer, dict) or set(answer) != {"id", "answer", "uncertainty"}:
            raise ValueError("Unexpected neutral answer fields")
        ident = _text(answer["id"])
        if ident not in ids or ident in seen:
            raise ValueError("Invalid/duplicate neutral answer ID")
        seen.add(ident)
        _text(answer["answer"])
        if not isinstance(answer["uncertainty"], str) or answer["uncertainty"] not in {"low", "medium", "high"}:
            raise ValueError("Invalid neutral uncertainty")
    if seen != set(ids):
        raise ValueError("Incomplete neutral answer coverage")
    return deepcopy(value)


def neutral_answer_schema(ids):
    return {
        "type": "object", "properties": {"answers": {
            "type": "array", "minItems": len(ids), "maxItems": len(ids),
            "items": {"type": "object", "properties": {
                "id": {"type": "string", "enum": list(ids)},
                "answer": {"type": "string"},
                "uncertainty": {"type": "string", "enum": ["low", "medium", "high"]},
            }, "required": ["id", "answer", "uncertainty"], "additionalProperties": False},
        }}, "required": ["answers"], "additionalProperties": False,
    }


@dataclass(frozen=True)
class NeutralEvidence:
    _json: str

    @classmethod
    def bind(cls, probes, observations, image_sha256, *, origin):
        """Import typed probes and raw per-image answers, never final grades.

        Legacy local IDs and condition_ids are used only to join raw answers,
        then removed. Reusable identity comes from property/object/reference.
        """
        _hashes(image_sha256)
        _text(origin)
        by_id, records = compile_neutral_probes(probes)
        if not isinstance(observations, dict) or set(observations) != {"source", "edited"}:
            raise ValueError("Expected exactly source and edited observations")
        answers = {}
        for role in ("source", "edited"):
            raw = validate_neutral_answers(observations[role], by_id)
            answers[role] = sorted(
                [{"key": by_id[a["id"]], "answer": a["answer"], "uncertainty": a["uncertainty"]}
                 for a in raw["answers"]], key=lambda a: a["key"])
        value = {"version": EVIDENCE_VERSION, "image_sha256": list(image_sha256),
                 "probes": sorted(records, key=lambda p: p["key"]), "observations": answers,
                 "origin": origin}
        return cls.from_dict({**value, "artifact_sha256": json_hash(value)})

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != {
            "version", "image_sha256", "probes", "observations", "origin", "artifact_sha256"
        } or value["version"] != EVIDENCE_VERSION:
            raise ValueError("Invalid neutral evidence artifact")
        _hashes(value["image_sha256"])
        _text(value["origin"])
        if value["artifact_sha256"] != json_hash({k: v for k, v in value.items() if k != "artifact_sha256"}):
            raise ValueError("Changed neutral evidence artifact")
        probes = value["probes"]
        if not isinstance(probes, list) or not 1 <= len(probes) <= 8:
            raise ValueError("Invalid probe list")
        keys = []
        for probe in probes:
            if not isinstance(probe, dict) or set(probe) != {"key", "question", "property", "object_class", "reference_class"}:
                raise ValueError("Invalid stored probe")
            descriptor = probe_descriptor({k: probe[k] for k in ("property", "object_class", "reference_class")})
            if probe["key"] != "probe:" + json_hash(descriptor) or probe["question"] != NEUTRAL_PROPERTIES[descriptor["property"]].format(**descriptor):
                raise ValueError("Probe signature/question mismatch")
            keys.append(probe["key"])
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate probe signatures")
        if not isinstance(value["observations"], dict) or set(value["observations"]) != {"source", "edited"}:
            raise ValueError("Invalid stored observations")
        for role in ("source", "edited"):
            rows = value["observations"][role]
            if not isinstance(rows, list) or len(rows) != len(keys):
                raise ValueError("Missing stored answers")
            actual = []
            for row in rows:
                if not isinstance(row, dict) or set(row) != {"key", "answer", "uncertainty"}:
                    raise ValueError("Invalid stored answer")
                actual.append(row["key"])
                _text(row["answer"])
                if row["uncertainty"] not in {"low", "medium", "high"}:
                    raise ValueError("Invalid stored uncertainty")
            if sorted(actual) != sorted(keys):
                raise ValueError("Stored answer coverage mismatch")
        return cls(json.dumps(value, sort_keys=True, allow_nan=False))

    def to_dict(self):
        return json.loads(self._json)

    def checker_payload(self, image_sha256):
        value = self.to_dict()
        if value["image_sha256"] != list(image_sha256):
            raise ValueError("Neutral observations belong to different image bytes")
        # No old condition IDs, human labels, feedback, grading outputs, or
        # provenance text are forwarded to the condition checker.
        ids = {p["key"]: f"q{i + 1}" for i, p in enumerate(value["probes"])}
        return {"questions": [{"id": ids[p["key"]], "question": p["question"]} for p in value["probes"]],
                **{role: {"answers": [{"id": ids[r["key"]], "answer": r["answer"], "uncertainty": r["uncertainty"]}
                                      for r in value["observations"][role]]}
                   for role in ("source", "edited")}}
