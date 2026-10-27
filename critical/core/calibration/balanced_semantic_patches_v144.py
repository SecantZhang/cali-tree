"""Few warrant-seeded corrections learned for class-normalized accuracy gain."""
import itertools

import numpy as np

from .local_warranted_rubric_v97 import DESCRIPTIONS, LABELS
from ..decision.artifacts import digest


def bits(values):
    return sum(1 << int(i) for i in np.flatnonzero(values))


class BalancedSemanticPatches:
    def __init__(self, names, *, partial_only=True, loss_cost=2., guards=1, max_rules=4, min_sources=2):
        if (not names or len(set(names)) != len(names) or any(n not in DESCRIPTIONS for n in names) or
                type(partial_only) is not bool or loss_cost not in (1., 2.) or guards not in (1, 2) or
                max_rules != 4 or min_sources != 2):
            raise ValueError('Closed semantic vocabulary and fixed small patch budget required')
        self.names = list(names); self.partial_only = partial_only; self.loss_cost = loss_cost
        self.guards = guards; self.max_rules = max_rules; self.min_sources = min_sources; self.rules = []

    def _matrix(self, X):
        a = np.asarray(X)
        if a.ndim != 2 or a.shape[1] != len(self.names) or not np.all((a == 0) | (a == 1)):
            raise ValueError('Aligned Boolean semantic claims required')
        return a.astype(bool)

    def fit(self, X, y, base, eligible, groups, *, protected_X, protected_y, protected_base, protected_eligible):
        a = self._matrix(X); p = self._matrix(protected_X)
        y, base, eligible = np.asarray(y), np.asarray(base), np.asarray(eligible)
        py, pb, pe = np.asarray(protected_y), np.asarray(protected_base), np.asarray(protected_eligible)
        if (set(np.unique(y)) != {0, 1, 2} or any(v.shape != (len(a),) for v in (y, base, eligible)) or
                any(v.shape != (len(p),) for v in (py, pb, pe)) or eligible.dtype != bool or pe.dtype != bool or
                len(groups) != len(a) or not np.all(np.isin(base, (-1, 0, 1, 2))) or not np.array_equal(py, pb)):
            raise ValueError('Three fitting grades, source support and correct original decisions required')
        labels = [bits(y == k) for k in range(3)]; counts = [int(np.sum(y == k)) for k in range(3)]
        grade = [bits(base == k) for k in range(3)]; protected_grade = [bits(pb == k) for k in range(3)]
        source_masks = [bits(np.asarray(groups) == g) for g in sorted(set(groups))]
        active, protected_active = bits(eligible), bits(pe)
        columns = {n: i for i, n in enumerate(self.names)}
        actions = [(0, 1)] if self.partial_only else [(b, t) for b in range(3) for t in range(3) if b != t]
        atoms = [(i, value, bits(a[:, i] == value), bits(p[:, i] == value))
                 for i in range(len(self.names)) if np.any(a[:, i]) and not np.all(a[:, i])
                 for value in (False, True)]

        def value(mask):
            return sum((mask & labels[k]).bit_count()/(3*counts[k]) for k in range(3))

        def measure(mask, before, target):
            good = mask & labels[target]; bad = mask & labels[before]
            return value(good), value(bad), good, bad

        self.rules = []
        for _ in range(self.max_rules):
            best = None
            for before, target in actions:
                for seed in ('rubric_'+LABELS[target]+'_ready', 'local_'+LABELS[target]+'_ready'):
                    if seed not in columns:
                        continue
                    col = columns[seed]
                    m = active & grade[before] & bits(a[:, col]); pm = protected_active & protected_grade[before] & bits(p[:, col])
                    if not m:
                        continue
                    beam = [(((col, True),), m, pm)]
                    for depth in range(self.guards+1):
                        for conditions, mask, protected_mask in beam:
                            good, bad, gm, bm = measure(mask, before, target)
                            sources = sum(bool(gm & s) for s in source_masks)
                            score = good-self.loss_cost*bad
                            if protected_mask or score <= 1e-12 or sources < self.min_sources:
                                continue
                            rank = (-score, -sources, bad, len(conditions), before, target, conditions)
                            if best is None or rank < best[0]:
                                best = (rank, before, target, conditions, mask, good, bad, sources,
                                        gm.bit_count(), bm.bit_count())
                        if depth == self.guards:
                            break
                        expanded = {}
                        for conditions, mask, pmask in beam:
                            used = {c for c, _ in conditions}
                            for col, truth, atom, patom in atoms:
                                if col in used:
                                    continue
                                new = mask & atom
                                if not new:
                                    continue
                                cond = tuple(sorted((*conditions, (col, truth))))
                                newp = pmask & patom
                                good, bad, gm, bm = measure(new, before, target)
                                if gm.bit_count() < self.min_sources:
                                    continue
                                # Permit an intermediate protected conflict;
                                # another guard may exclude that original row.
                                rank = (-(good-self.loss_cost*bad)+newp.bit_count(), -good, bad, cond)
                                expanded[cond] = (rank, cond, new, newp)
                        beam = [(c, m, pm) for _, c, m, pm in sorted(expanded.values())[:16]]
            if best is None:
                break
            _, before, target, conditions, mask, good, bad, sources, gains, losses = best
            self.rules.append({'from_grade': before, 'grade': target,
                'conditions': [{'feature': self.names[i], 'value': truth} for i, truth in conditions],
                'support': {'gain_sources': sources, 'gains': gains, 'losses': losses,
                            'balanced_gain': good, 'balanced_loss': bad}})
            active &= ~mask
        self.class_counts = counts
        assert np.array_equal(self.predict(p, pb, pe), py)
        return self

    def predict(self, X, base, eligible):
        a = self._matrix(X); result = np.asarray(base).copy(); available = np.asarray(eligible).copy()
        if result.shape != (len(a),) or available.shape != result.shape or available.dtype != bool:
            raise ValueError('Aligned grades and eligible routes required')
        columns = {n: i for i, n in enumerate(self.names)}
        for rule in self.rules:
            matched = available & (np.asarray(base) == rule['from_grade'])
            for term in rule['conditions']:
                matched &= a[:, columns[term['feature']]] == term['value']
            result[matched] = rule['grade']; available[matched] = False
        return result

    def artifact(self):
        used = sorted({t['feature'] for r in self.rules for t in r['conditions']})
        lines = ['Apply the first matching correction after the existing v112 pipeline; earlier semantic/expert overrides keep priority. Otherwise retain the v112 grade.',
                 'Every grade requires a positive same-requirement rubric or bound local-model warrant. These are fallible model claims.']
        for i, rule in enumerate(self.rules, 1):
            terms = [DESCRIPTIONS[t['feature']] if t['value'] else 'Not established: '+DESCRIPTIONS[t['feature']] for t in rule['conditions']]
            lines.append(str(i)+'. IF the current grade is '+LABELS[rule['from_grade']]+' AND '+' AND '.join(terms)+' THEN grade '+LABELS[rule['grade']]+'.')
        value = {'version': 'balanced-semantic-patches-v144', 'partial_only': self.partial_only,
            'loss_cost': self.loss_cost, 'max_guards': self.guards, 'max_rules': self.max_rules,
            'min_sources': self.min_sources, 'rules': self.rules, 'feature_names': used,
            'feature_descriptions': {n: DESCRIPTIONS[n] for n in used}, 'rubric': '\n'.join(lines)+'\n'}
        value['artifact_ref'] = digest(value)
        return value


def execute(artifact, values, grade, eligible):
    """Independent scalar first-match executor over the exported named rubric."""
    if artifact.get('artifact_ref') != digest({k: v for k, v in artifact.items() if k != 'artifact_ref'}):
        raise ValueError('Changed semantic patch artifact')
    if not eligible:
        return grade
    for rule in artifact['rules']:
        anchors = {('rubric_'+LABELS[rule['grade']]+'_ready', True), ('local_'+LABELS[rule['grade']]+'_ready', True)}
        terms = {(t['feature'], t['value']) for t in rule['conditions']}
        if not anchors & terms:
            raise ValueError('Affirmative same-grade warrant required')
        if grade == rule['from_grade'] and all(values[t['feature']] == t['value'] for t in rule['conditions']):
            return rule['grade']
    return grade
