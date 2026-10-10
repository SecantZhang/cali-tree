"""Case-level objectives and explicitly conditional repeat statistics."""
from collections import Counter
from dataclasses import asdict, dataclass
from critical.core.optimization.program.base import LeafEvaluator, AcceptancePolicy

@dataclass(frozen=True)
class RobustPolicy(AcceptancePolicy):
    repeats: int = 5
    agreement: float = .8
    consistency: float = .8
    confidence: float = .8
    minimum_eligible: int = 3

    def assess(self, report, audit):
        reasons = []
        if not audit.get('accepted'):
            reasons.append('semantic_audit')
        if report.get('draws', 0) != self.repeats:
            reasons.append('insufficient_draws')
        if report.get('coverage', 0) != 1:
            reasons.append('unresolved')
        if report.get('agreement', 0) < self.agreement:
            reasons.append('target_mismatch')
        if report.get('requirement_consistency', 0) < self.consistency:
            reasons.append('requirement_instability')
        for node, stats in report.get('nodes', {}).items():
            if not stats['eligible']:
                continue  # Explicitly reported untested; no all-path robustness claim.
            if stats['eligible'] < self.minimum_eligible:
                reasons.append('insufficient_activation:' + node)
            if stats['consistency'] < self.consistency:
                reasons.append('node_instability:' + node)
        if not report.get('confidence_pass', False):
            reasons.append('confidence')
        return {'qualified': not reasons, 'reasons': reasons, 'policy': asdict(self)}

    def rank(self, report, program=None):
        return (report['agreement'], report['coverage'], report['requirement_consistency'],
                -report['mean_checks'], -report['mean_completion_tokens'])


def summarize(program, traces, target, policy):
    count = len(traces)
    if not count:
        raise ValueError('At least one complete scheduled draw required')
    nodes = {}
    queried = [o for t in traces for o in t['observations'] if o['queried']]
    for node in program.nodes:
        rows = [o for t in traces for o in t['observations'] if o['check_id'] == node.id]
        eligible = sum(o['eligible'] for o in rows)
        states = Counter(o['status'] for o in rows if o['eligible'])
        valid = Counter(o['status'] for o in rows if o['eligible'] and o['valid'] and o['status'] != 'unknown')
        nodes[node.id] = {'eligible': eligible, 'queried': sum(o['queried'] for o in rows),
            'activation_rate': eligible / count, 'states': dict(states),
            'consistency': max(valid.values(), default=0) / eligible if eligible else None,
            'assessment': 'untested' if not eligible else 'insufficient' if eligible < policy.minimum_eligible else 'assessed',
            'confidence': [o['confidence'] for o in rows if o['queried']]}
    requirements = {}
    for req in program.requirements:
        values = Counter(t['requirements'][req.id] for t in traces)
        requirements[req.id] = {'states': dict(values), 'consistency': max(
            (n for s, n in values.items() if s != 'unknown'), default=0) / count,
            'coverage': sum(n for s, n in values.items() if s != 'unknown') / count}
    labels = Counter(t['label'] or 'unresolved' for t in traces)
    return {'draws': count, 'agreement': sum(t['label'] == target for t in traces) / count,
        'coverage': sum(t['resolved'] for t in traces) / count,
        'label_consistency': max((n for s, n in labels.items() if s != 'unresolved'), default=0) / count,
        'label_distribution': dict(labels), 'nodes': nodes, 'requirements': requirements,
        'requirement_consistency': min(v['consistency'] for v in requirements.values()),
        'confidence_pass': bool(queried) and all(o['confidence'] is not None and o['confidence'] >= policy.confidence for o in queried),
        'mean_checks': len(queried) / count,
        'mean_completion_tokens': sum(o['completion_tokens'] for o in queried) / count,
        'traces': traces}

class RobustEvaluator(LeafEvaluator):
    def __init__(self, executor, policy=None):
        self.executor, self.policy = executor, policy or RobustPolicy()
    def evaluate(self, program, case, reference_label, *, repeats, namespace, final=False):
        if repeats < 1:
            raise ValueError('Positive repeat count required')
        traces = [self.executor.execute(program, case.evidence, repeat=f'{namespace}/{i}', final=final) for i in range(repeats)]
        return summarize(program, traces, reference_label, self.policy)


class NoAuditRobustPolicy(RobustPolicy):
    """Keep empirical gates without fabricating a semantic-review approval."""
    def assess(self, report, audit=None):
        assessment=super().assess(report,audit or {})
        assessment['reasons']=[r for r in assessment['reasons'] if r!='semantic_audit']
        assessment['qualified']=not assessment['reasons']
        assessment['semantic_audit']='disabled'
        return assessment
