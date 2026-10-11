"""Native TextGrad node backward passes followed by typed structural proposals."""
from dataclasses import asdict
import json
from critical.core.decision.compiler import object_schema, TEXT, media_inputs
from critical.core.decision.robust.compiler import template
from critical.core.optimization.program.base import EditProposer
from critical.core.optimization.program.backends.textgrad import load_textgrad
from critical.core.optimization.program.robust.edits import PROPOSAL_SCHEMA

from critical.core.optimization.program.shared.feedback import NodeTextGrad

class StructuralProposer(EditProposer):
    def __init__(self, calls):
        self.calls = calls
    def propose(self, program, case, reference_label, feedback, *, slot, limit=2):
        value, _ = self.calls.call('propose', {'instruction': program.instruction, 'rubric': program.rubric,
            'program': program.to_dict(), 'reference_label': reference_label, 'feedback': feedback, 'limit': limit},
            PROPOSAL_SCHEMA, template=template('propose'), media=media_inputs(case.evidence), slot=slot, max_tokens=2048)
        rows = value.get('transactions')
        if not isinstance(rows, list) or len(rows) > limit:
            raise ValueError('Proposal count exceeded or malformed')
        return rows
