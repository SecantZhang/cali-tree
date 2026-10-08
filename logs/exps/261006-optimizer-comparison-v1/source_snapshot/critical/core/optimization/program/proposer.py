from critical.core.decision.compiler import (object_schema, array, enum, TEXT, OUTCOME_SCHEMA,
    CHECK_SCHEMA, REQUIREMENT_SCHEMA, template, media_inputs)
from .base import EditProposer
from .models import Transaction
from .edits import OPERATORS
EDIT_SCHEMA = object_schema({'operator': enum(OPERATORS), 'target': TEXT, 'outcomes': array(OUTCOME_SCHEMA), 'checks': array(CHECK_SCHEMA)})
TRANSACTION_SCHEMA = object_schema({'edits': array(EDIT_SCHEMA), 'reason': TEXT, 'requirements': array(REQUIREMENT_SCHEMA)})
PROPOSAL_SCHEMA = object_schema({'transactions': array(TRANSACTION_SCHEMA)})
class ModelEditProposer(EditProposer):
    def __init__(self, calls):
        self.calls = calls
    def propose(self, program, case, reference_label, feedback, *, slot, limit):
        row, _ = self.calls.call('propose', {'program': program.to_dict(), 'instruction': case.instruction,
                       'reference_label': reference_label, 'feedback': feedback, 'limit': limit},
                       PROPOSAL_SCHEMA, template=template('propose'), media=media_inputs(case.evidence), slot=slot)
        if not isinstance(row.get('transactions'), list) or len(row['transactions']) > limit:
            raise ValueError('Invalid transaction count')
        # Parsing each transaction is isolated: one malformed sibling must not erase valid alternatives.
        return row['transactions']
