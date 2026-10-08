"""Model feedback proposes typed edits; a separate label-free audit checks semantics."""
from critical.core.decision.compiler import object_schema, PREDICATE_SCHEMA, TEXT, template
from critical.core.decision.models import PredicateSpec

from .base import EditProposer
from .edits import OPERATORS
from .models import ProgramEdit

EDIT_SCHEMA = object_schema({"operator": {"type": "string", "enum": list(OPERATORS)},
                             "target": TEXT, "replacements": {"type": "array", "items": PREDICATE_SCHEMA},
                             "reason": TEXT})
PROPOSAL_SCHEMA = object_schema({"edits": {"type": "array", "items": EDIT_SCHEMA}})
AUDIT_SCHEMA = object_schema({"accepted": {"type": "boolean"}, "reason": TEXT})


class ModelEditProposer(EditProposer):
    def __init__(self, calls):
        self.calls = calls

    def propose(self, program, feedback, *, slot, limit):
        value, _ = self.calls.call("propose", {"program": program.to_dict(), "training_feedback": feedback,
                                   "limit": limit}, PROPOSAL_SCHEMA, template=template("propose"), slot=slot)
        if not isinstance(value.get("edits"), list) or len(value["edits"]) > limit:
            raise ValueError("Proposal exceeds edit allowance")
        return [ProgramEdit(e["operator"], e["target"], tuple(PredicateSpec.from_dict(p) for p in e["replacements"]),
                            e["reason"]) for e in value["edits"]]

    def audit(self, before, after, edit, *, slot):
        # Deliberately omit the target-conditioned rationale and all case feedback.
        value, _ = self.calls.call("audit", {"before": before.to_dict(), "after": after.to_dict(),
                                            "operator": edit.operator}, AUDIT_SCHEMA,
                                   template=template("audit"), slot=slot, max_tokens=1024)
        if type(value.get("accepted")) is not bool or not isinstance(value.get("reason"), str):
            raise ValueError("Invalid semantic audit")
        return value
