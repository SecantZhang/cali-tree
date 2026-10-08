"""Small production-owned offline example; no dependency on test helpers."""
from dataclasses import replace
from pathlib import Path
from critical.core.decision.models import Requirement, Outcome, Check, ProgramSpec
from critical.core.decision.compiler import template
from .models import Case, Edit, Transaction
RUBRIC = ('Judge requested image editing: yes means all requested changes are complete, no means no requested '
          'change has progressed, partial means some progress without complete fulfillment. '
          'Unrelated edits are not requested progress. Insufficient evidence stays unresolved.')

def seed_program(instruction='Make the square red'):
    return ProgramSpec(instruction, RUBRIC, (Requirement('r1', instruction, instruction),),
        (Outcome('o1', ('r1',), instruction, 'square'),),
        (Check('c1', 'o1', 'requested', 'Is the square red?', 'red', 'partly red', 'not red', 'cannot see'),), template('check'))
class DemoCompiler:
    def compile(self, instruction, rubric, *, slot):
        return seed_program(instruction)
    def audit(self, program, *, slot):
        return {'accepted': True, 'reason': 'Synthetic contract fixture'}
class DemoChecker:
    identity = {'checker': 'synthetic-v2'}
    def check(self, program, check, outcome, evidence, dependencies, *, slot, final=False):
        return {'status': 'complete' if 'SOURCE comparison' in check.question else 'absent',
                'evidence': 'Synthetic controlled response', 'completion_tokens': 1}
class DemoProposer:
    def propose(self, program, case, reference_label, feedback, *, slot, limit):
        c = replace(program.checks[0], question='Is the square red after SOURCE comparison?')
        return [Transaction((Edit('revise', c.id, checks=(c,)),), 'Add source comparison')]

def demo_case(directory):
    from PIL import Image
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    for name, color in [('source', 'blue'), ('edited', 'red')]:
        Image.new('RGB', (16, 16), color).save(directory / (name + '.png'))
    return Case('synthetic', 'Make the square red', {k + '_image': str(directory / (k + '.png')) for k in ('source', 'edited')})
