"""Graph constraints preserve explicit coverage, not unprovable semantic truth."""
import re
from .models import APPLICABILITY, VERSION

def validate_program(program, max_checks=4):
    if program.version != VERSION or program.aggregation != 'requested-all-some-none-v2':
        raise ValueError('Unsupported program version')
    for value in (program.instruction, program.rubric, program.checker_template):
        if not isinstance(value, str) or not value.strip():
            raise ValueError('Empty program context')
    groups = (program.requirements, program.outcomes, program.checks)
    ids = [n.id for group in groups for n in group]
    if len(ids) != len(set(ids)) or any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', i) for i in ids):
        raise ValueError('Invalid or duplicate graph identity')
    if not all(groups):
        raise ValueError('Empty requirements, outcomes or checks')
    if len(program.checks) > max_checks:
        raise ValueError('Check cap exceeded; requirements must not be truncated')
    for r in program.requirements:
        if not r.text.strip() or not r.source_phrase or r.source_phrase not in program.instruction:
            raise ValueError('Requirement must quote the instruction exactly')
    requirements = {r.id for r in program.requirements}
    covered = set()
    outcomes = {o.id: o for o in program.outcomes}
    checks = {c.id: c for c in program.checks}
    for o in program.outcomes:
        if not o.requirement_ids or not set(o.requirement_ids) <= requirements:
            raise ValueError('Outcome references missing requirement')
        if not o.description.strip() or not o.target.strip() or o.applicability not in APPLICABILITY:
            raise ValueError('Invalid outcome binding or applicability')
        covered.update(o.requirement_ids)
        if sum(c.role == 'requested' and c.outcome_id == o.id for c in program.checks) != 1:
            raise ValueError('Each outcome needs exactly one fulfillment check')
    if covered != requirements:
        raise ValueError('Uncovered required instruction outcome')
    for c in program.checks:
        if c.role not in ('requested', 'support') or c.outcome_id not in outcomes:
            raise ValueError('Invalid check role or outcome')
        if any(not isinstance(getattr(c, k), str) or not getattr(c, k).strip() for k in
               ('question', 'complete_when', 'partial_when', 'absent_when', 'unknown_when')):
            raise ValueError('Missing check criteria')
        if len(set(c.dependencies)) != len(c.dependencies):
            raise ValueError('Duplicate dependencies')
        if any(d not in checks or checks[d].role != 'support' or checks[d].outcome_id != c.outcome_id for d in c.dependencies):
            raise ValueError('Broken supporting dependency')
    reached, pending = set(), set()
    def visit(key):
        if key in pending:
            raise ValueError('Cyclic dependencies')
        if key not in reached:
            pending.add(key)
            for d in checks[key].dependencies:
                visit(d)
            pending.remove(key)
            reached.add(key)
    for c in program.checks:
        if c.role == 'requested':
            visit(c.id)
    if reached != set(checks):
        raise ValueError('Orphan supporting check')

def ordered_checks(program, max_checks=4):
    validate_program(program, max_checks)
    by_id = {c.id: c for c in program.checks}
    outcomes = {o.id: o for o in program.outcomes}
    ordered, seen = [], set()
    def visit(c):
        if c.id not in seen:
            for d in c.dependencies:
                visit(by_id[d])
            seen.add(c.id)
            ordered.append(c)
    for c in program.checks:
        if c.role == 'requested' and outcomes[c.outcome_id].applicability == 'applicable':
            visit(c)
    return ordered
