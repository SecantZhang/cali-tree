"""Deterministic bounded multiobjective archives, one evidence tier at a time."""
import random

def objectives(report):
    return (report['agreement'], report['coverage'], report['requirement_consistency'],
            -report['mean_checks'] / 4, -report['mean_completion_tokens'] / 4096)

def dominates(left, right):
    return all(a >= b for a, b in zip(left, right)) and any(a > b for a, b in zip(left, right))

class ParetoArchive:
    def __init__(self, draws, capacity=6):
        if capacity < 5:
            raise ValueError('Need room for five objective extremes')
        self.draws, self.capacity, self.reports, self.history = draws, capacity, {}, []

    def update(self, reports):
        if any(r['draws'] != self.draws for r in reports.values()):
            raise ValueError('Cannot compare different evidence tiers')
        all_reports = {**self.reports, **reports}
        vectors = {k: objectives(v) for k, v in all_reports.items()}
        front = [k for k in sorted(vectors) if not any(dominates(v, vectors[k]) for j, v in vectors.items() if j != k)]
        keep = []
        if len(front) > self.capacity:
            for axis in range(5):
                extreme = min(front, key=lambda k: (-vectors[k][axis], k))
                if extreme not in keep:
                    keep.append(extreme)
            while len(keep) < self.capacity:
                candidates = [k for k in front if k not in keep]
                choice = min(candidates, key=lambda k: (-min(sum((a-b)**2 for a, b in zip(vectors[k], vectors[j])) for j in keep), k))
                keep.append(choice)
        else:
            keep = front
        self.reports = {k: all_reports[k] for k in sorted(keep)}
        self.history.append({'draws': self.draws, 'objectives': {k: list(v) for k, v in vectors.items()},
            'retained': sorted(keep), 'dominated': sorted(set(vectors) - set(front)), 'pruned': sorted(set(front)-set(keep))})
        return list(self.reports)

    def sample(self, rng, count):
        keys = sorted(self.reports)
        if not keys:
            return []
        vectors = {k: objectives(self.reports[k]) for k in keys}
        weights = [1 + sum(vectors[k][i] == max(v[i] for v in vectors.values()) for i in range(5)) for k in keys]
        return rng.choices(keys, weights=weights, k=count)
