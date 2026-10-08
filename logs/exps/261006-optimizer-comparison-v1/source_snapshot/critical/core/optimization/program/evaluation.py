"""Repeated local agreement; repeats are never independent cases."""
from collections import Counter
from .base import LeafEvaluator, AcceptancePolicy

def summarize(draws, target):
    n = len(draws)
    labels = [d['label'] for d in draws]
    atomic = {}
    for draw in draws:
        for obs in draw['observations']:
            atomic.setdefault(obs['check_id'], []).append(obs['status'] if obs['valid'] else 'unknown')
    unstable = sum(len(v) != n or len(set(v)) != 1 or 'unknown' in v for v in atomic.values())
    return {'draws': draws, 'agreement': sum(l == target for l in labels) / n if n else 0,
            'coverage': sum(l is not None for l in labels) / n if n else 0,
            'flip_rate': 1 - max(Counter(labels).values()) / n if n else 0,
            'atomic_unstable_or_unknown_rate': unstable / len(atomic) if atomic else 1,
            'executed_checks': sum(len(d['observations']) for d in draws),
            'completion_tokens': sum(o['completion_tokens'] for d in draws for o in d['observations']),
            'independent_cases': 1, 'repeat_count': n}

class RepeatedEvaluator(LeafEvaluator):
    def __init__(self, executor):
        self.executor = executor
    def evaluate(self, program, case, reference_label, *, repeats, namespace, final=False):
        if repeats < 1:
            raise ValueError('Need positive repeat count')
        draws = [self.executor.execute(program, case.evidence, repeat=f'{namespace}/{i}', final=final).to_dict()
                 for i in range(repeats)]
        return summarize(draws, reference_label)

class LocalAcceptance(AcceptancePolicy):
    def rank(self, report, program):
        return (report['agreement'], report['coverage'], -report['flip_rate'], -len(program.checks),
                -report['completion_tokens'] / max(1, report['repeat_count']))
