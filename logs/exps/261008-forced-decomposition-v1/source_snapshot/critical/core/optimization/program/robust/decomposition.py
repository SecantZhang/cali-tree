"""Structural proposals that cannot erase the forced evidence decomposition."""
from critical.core.decision.compiler import media_inputs
from critical.core.decision.robust.decomposition import CONTRACT, template
from .edits import PROPOSAL_SCHEMA
from .proposer import StructuralProposer


class DecompositionProposer(StructuralProposer):
    def propose(self, program, case, reference_label, feedback, *, slot, limit=2):
        value, _ = self.calls.call('propose', {'instruction': program.instruction, 'rubric': program.rubric,
            'program': program.to_dict(), 'reference_label': reference_label, 'feedback': feedback,
            'limit': limit, 'contract': CONTRACT}, PROPOSAL_SCHEMA, template=template('propose'),
            media=media_inputs(case.evidence), slot=slot, max_tokens=2048)
        rows = value.get('transactions')
        if not isinstance(rows, list) or len(rows) > limit:
            raise ValueError('Proposal count exceeded or malformed')
        return rows
