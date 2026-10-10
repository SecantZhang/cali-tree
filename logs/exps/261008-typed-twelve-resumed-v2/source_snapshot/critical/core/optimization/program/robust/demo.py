"""Offline executable example, independent of test fixtures and external services."""
from dataclasses import asdict, replace
from pathlib import Path
from PIL import Image
from critical.core.decision.models import Requirement, Outcome
from critical.core.decision.robust.models import RobustProgram, Node, restore_program
from critical.core.decision.robust.executor import RobustExecutor
from critical.core.decision.robust.compiler import template
from critical.core.decision.artifacts import save_json
from critical.core.optimization.program.models import Case
from critical.core.optimization.prompt.calitree import CaliTreeBuilder
from .search import RobustLeafOptimizer
from .metrics import RobustEvaluator, RobustPolicy

RUBRIC = 'All requested edits complete means yes; none progressed means no; otherwise partial. Unknown remains unresolved.'

def example_program():
    return RobustProgram('Make the square red', RUBRIC, (Requirement('r', 'Make the square red', 'Make the square red'),),
        (Outcome('o', ('r',), 'Square color changed to red', 'the square'),),
        (Node('color', 'requested', 'o', '', (), (), 'Is the square red?',
              'Assess red color using an ambiguous hue boundary', 'same square in both images'),), template('check'))


def revision(program, criteria):
    node = replace(program.nodes[0], criteria=criteria)
    return {'reason': 'Clarify the hue criterion using the original color requirement.',
            'edits': [{'operator': 'checker_revision', 'remove_nodes': [], 'nodes': [asdict(node)],
                       'remove_outcomes': [], 'outcomes': [], 'node_order': []}], 'outcome_mapping': []}

class DemoCompiler:
    def compile(self, instruction, rubric, *, slot):
        return example_program()
    def audit(self, program, *, slot):
        return {'accepted': 'force' not in program.nodes[0].criteria, 'reason': 'Synthetic semantic contract'}

class DemoChecker:
    identity = {'checker': 'synthetic-robust-v3'}
    def check(self, program, node, outcome, evidence, dependencies, *, slot, final=False):
        improved = 'dominant red hue' in node.criteria
        return {'status': 'complete' if improved else 'absent', 'evidence': 'Synthetic red square',
                'confidence': .95 if improved else .6, 'completion_tokens': 10}

class DemoGradient:
    def feedback(self, program, case, target, report, *, slot):
        return {'color': ['Assess dominant red hue without demanding one exact RGB value.']}

class DemoProposer:
    def propose(self, program, case, reference_label, feedback, *, slot, limit):
        return [revision(program, 'Complete: dominant red hue across the square; partial: some red; absent: no red; unknown: unidentifiable square.')]


def run_demo(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    evidence = {}
    for key, color in (('source_image', 'blue'), ('edited_image', 'red')):
        path = output/(key + '.png')
        Image.new('RGB', (20, 20), color).save(path)
        evidence[key] = str(path.resolve())
    case = Case('synthetic-red-square', 'Make the square red', evidence)
    evaluator = RobustEvaluator(RobustExecutor(DemoChecker()))
    optimizer = RobustLeafOptimizer(DemoCompiler(), DemoProposer(), evaluator, DemoGradient(), rubric=RUBRIC)
    bundle = CaliTreeBuilder.build_program_leaves([case], reference_labels={case.id: 'yes'}, optimizer_factory=lambda _: optimizer)
    node = bundle['nodes']['leaf:' + case.id]
    report = evaluator.evaluate(restore_program(node['result']['selected']), case, 'yes', repeats=5, namespace='final-demo', final=True)
    acceptance = RobustPolicy().assess(report, {'accepted': True})
    node.update(support_status='locally_robust' if acceptance['qualified'] else 'unresolved', final_comparison=report)
    save_json(output/'leaves.json', bundle)
    save_json(output/'results.json', {'synthetic': True, 'acceptance': acceptance, 'final': report})
    return {'status': node['support_status'], 'synthetic': True, 'output': str(output)}
