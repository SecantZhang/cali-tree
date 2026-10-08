"""Label-free model compilation and binding using versioned templates."""
from pathlib import Path

from .models import OPERATIONS, ProgramSpec, BoundPlan, Outcome
from .artifacts import digest
from .validation import validate_plan

TEMPLATES = Path(__file__).parents[1] / "prompts/templates/decision_program_v1"


def object_schema(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


TEXT = {"type": "string"}
PREDICATE_SCHEMA = object_schema({
    "id": TEXT, "role": {"type": "string", "enum": ["requested", "support"]},
    "applies_to": {"type": "array", "items": {"type": "string", "enum": list(OPERATIONS)}},
    "dependencies": {"type": "array", "items": TEXT},
    **{k: TEXT for k in ("binding", "question", "complete_when", "partial_when", "absent_when", "unknown_when")},
    "provenance": {"type": "string", "enum": ["instruction", "rubric"]}})
OUTCOME_SCHEMA = object_schema({**{k: TEXT for k in ("id", "requirement", "source_phrase", "target", "reference")},
                                "operation": {"type": "string", "enum": list(OPERATIONS)}})
PLAN_SCHEMA = object_schema({"outcomes": {"type": "array", "items": OUTCOME_SCHEMA}})
PROGRAM_SCHEMA = object_schema({"predicates": {"type": "array", "items": PREDICATE_SCHEMA}})


def template(name):
    return (TEMPLATES / (name + ".txt")).read_text()


class ProgramCompiler:
    def __init__(self, calls):
        self.calls = calls

    def compile(self, rubric, instructions):
        from .models import PredicateSpec
        row, _ = self.calls.call("compile", {"rubric": rubric, "instructions": list(instructions)},
                                 PROGRAM_SCHEMA, template=template("compile"))
        return ProgramSpec.from_dict(ProgramSpec(rubric, tuple(PredicateSpec.from_dict(p) for p in row["predicates"])).to_dict())

    def bind(self, instruction, *, final=False):
        row, _ = self.calls.call("bind", {"instruction": instruction}, PLAN_SCHEMA,
                                 template=template("bind"), slot=digest(instruction), final=final)
        plan = BoundPlan(instruction, tuple(Outcome(**o) for o in row["outcomes"]))
        validate_plan(plan)
        return plan
