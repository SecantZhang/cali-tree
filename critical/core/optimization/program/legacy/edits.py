"""Apply bounded edit transactions atomically to the authoritative leaf graph."""
from dataclasses import replace
from critical.core.decision.validation import validate_program

OPERATORS = ('add', 'remove', 'split', 'rebind', 'applicability', 'revise')
def apply_transaction(program, transaction):
    validate_program(program)
    if not 1 <= len(transaction.edits) <= 4 or not transaction.reason.strip():
        raise ValueError('Transaction needs a reason and one to four edits')
    outcomes, checks = list(program.outcomes), list(program.checks)
    mappings = []
    for edit in transaction.edits:
        os, cs = {o.id: o for o in outcomes}, {c.id: c for c in checks}
        if edit.operator not in OPERATORS:
            raise ValueError('Unknown edit operator')
        if edit.operator == 'add':
            if edit.target or not (edit.outcomes or edit.checks):
                raise ValueError('Add needs new nodes and an empty target')
            outcomes.extend(edit.outcomes); checks.extend(edit.checks)
        elif edit.operator == 'remove':
            if edit.outcomes or edit.checks or edit.target not in {*os, *cs}:
                raise ValueError('Invalid removal')
            if edit.target in os:
                outcomes = [o for o in outcomes if o.id != edit.target]
                checks = [c for c in checks if c.outcome_id != edit.target]
                mappings.append({'before': edit.target, 'after': []})
            else:
                checks = [c for c in checks if c.id != edit.target]
        elif edit.operator == 'split':
            if edit.target not in os or len(edit.outcomes) < 2:
                raise ValueError('Split needs an outcome and two or more replacements')
            covered = {r for o in edit.outcomes for r in o.requirement_ids}
            if not set(os[edit.target].requirement_ids) <= covered:
                raise ValueError('Split loses requirement provenance')
            outcomes = [o for o in outcomes if o.id != edit.target] + list(edit.outcomes)
            checks = [c for c in checks if c.outcome_id != edit.target] + list(edit.checks)
            mappings.append({'before': edit.target, 'after': [o.id for o in edit.outcomes]})
        elif edit.operator in ('rebind', 'applicability'):
            if edit.target not in os or len(edit.outcomes) != 1 or edit.checks:
                raise ValueError('Binding edit requires one existing outcome')
            original, new = os[edit.target], edit.outcomes[0]
            allowed = ('description', 'target', 'reference') if edit.operator == 'rebind' else ('applicability',)
            if replace(original, **{k: getattr(new, k) for k in allowed}) != new:
                raise ValueError('Binding edit changes protected provenance or identity')
            outcomes = [new if o.id == edit.target else o for o in outcomes]
            mappings.append({'before': edit.target, 'after': [new.id]})
        else:
            if edit.target not in cs or len(edit.checks) != 1 or edit.outcomes:
                raise ValueError('Revision requires one existing check')
            old, new = cs[edit.target], edit.checks[0]
            if (old.id, old.role, old.outcome_id) != (new.id, new.role, new.outcome_id):
                raise ValueError('Revision changes check identity or role')
            checks = [new if c.id == edit.target else c for c in checks]
    candidate = replace(program, outcomes=tuple(outcomes), checks=tuple(checks),
                        requirements=program.requirements + transaction.requirements)
    validate_program(candidate)
    if candidate == program:
        raise ValueError('Transaction has no effect')
    return candidate, mappings
