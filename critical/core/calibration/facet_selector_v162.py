"""Compact semantic regions choosing a source-bound outcome expert."""
from copy import deepcopy

import numpy as np

from .base import Calibrator
from .local_warranted_rubric_v97 import DESCRIPTIONS as LEGACY
from ..decision import facet_policy_v150 as facets, outcome_policy_v160 as outcome
from ..decision.artifacts import digest

LABELS = ('no', 'partial', 'yes')
DEFAULT_SEEDS = {k: 'facet_'+label+'_outcome_ready' for k, label in enumerate(LABELS)}
FACETS = {'facet_available': 'A validated observation from the pinned source-bound Sol facet profile is available.'}
for field, states in facets.FIELDS.items():
    for state in states:
        FACETS['facet_'+field+'__'+state] = 'The observer reports '+field.replace('_', ' ')+' as '+state.replace('_', ' ')+'.'
for label in LABELS:
    FACETS['facet_'+label+'_outcome_ready'] = 'The explicit outcome-primary rubric proposes '+label+' from affirmative, resolved progress/completion/scope observations. This is a fallible model warrant.'
DESCRIPTIONS = {**LEGACY, **FACETS}
PREFIXES = ('meaning_', 'requires_', 'task_', 'intent_', 'rubric_', 'local_', 'rationale_', 'view_')


def allowed(name):
    return name in FACETS or (name in LEGACY and name.startswith(PREFIXES))


def project(value):
    flags = {name: False for name in FACETS}
    if value is None:
        return flags
    facets.validate(value); flags['facet_available'] = True
    for field in facets.FIELDS:
        flags['facet_'+field+'__'+value[field]] = True
    grade = outcome.decide(value)
    if grade is not None:
        flags['facet_'+LABELS[grade]+'_outcome_ready'] = True
    return flags


def bits(values):
    return sum(1 << int(i) for i in np.flatnonzero(values))


def merge_adjacent(rules, *, seed_names=None):
    """Exact union reduction only for adjacent rules with the same action.

    Absorption and A&x OR A&!x preserve the Boolean function for every input,
    without moving a rule across an intervening different expert action.
    """
    seed_names = DEFAULT_SEEDS if seed_names is None else seed_names
    result = deepcopy(rules); changed = True
    while changed:
        changed = False
        for i in range(len(result)-1):
            a, b = result[i:i+2]
            if (a['from_grade'], a['grade']) != (b['from_grade'], b['grade']):
                continue
            left = frozenset((t['feature'], t['value']) for t in a['conditions'])
            right = frozenset((t['feature'], t['value']) for t in b['conditions'])
            reduced = left if left <= right else right if right <= left else None
            difference = left ^ right
            if reduced is None and len(difference) == 2:
                d = list(difference)
                if d[0][0] == d[1][0] and d[0][1] != d[1][1]:
                    reduced = left & right
            if reduced is None:
                continue
            anchor = (seed_names[a['grade']], True)
            if anchor not in reduced:
                raise ValueError('Logical merge cannot remove the affirmative outcome witness')
            merged = {k: v for k, v in a.items() if k not in ('conditions', 'support')}
            merged['conditions'] = [{'feature': n, 'value': v} for n, v in sorted(reduced)]
            result[i:i+2] = [merged]; changed = True; break
    return result


class FacetSelector(Calibrator):
    version = 'source-bound-semantic-facet-selector-v162'
    seed_names = DEFAULT_SEEDS
    descriptions = DESCRIPTIONS
    contract_ref = outcome.CONTRACT_REF
    accepts_feature = staticmethod(allowed)
    rubric_intro = ('Apply the first matching semantic region inside the validated covered input route; otherwise retain V112.',
        'Every new grade needs a positive outcome witness. Preservation/operation observations are selective learned guards, not universal caps. An unestablished guard is not evidence for its physical opposite.')

    def __init__(self, names, *, guards=2, loss_cost=2., max_rules=4, min_sources=3):
        if (not names or len(names) != len(set(names)) or any(not self.accepts_feature(n) for n in names) or
            not set(self.seed_names.values()) <= set(names) or
            guards not in (1, 2) or loss_cost not in (1., 2.) or max_rules != 4 or min_sources != 3):
            raise ValueError('Closed named semantic vocabulary, outcome witnesses and fixed small rule budget required')
        self.names = list(names); self.guards = guards; self.loss_cost = loss_cost
        self.max_rules = max_rules; self.min_sources = min_sources; self.rules = []

    def _matrix(self, X):
        a = np.asarray(X)
        if a.ndim != 2 or a.shape[1] != len(self.names) or not np.all((a == 0) | (a == 1)):
            raise ValueError('Aligned explicit Boolean semantic indicators required')
        return a.astype(bool)

    def fit(self, X, y, *, base, eligible, groups, protected_X, protected_y,
            protected_base, protected_eligible, sample_weight=None):
        if sample_weight is not None:
            raise ValueError('Explicit class-normalized objective required')
        a, p = self._matrix(X), self._matrix(protected_X)
        y, base, eligible = np.asarray(y), np.asarray(base), np.asarray(eligible)
        py, pb, pe = np.asarray(protected_y), np.asarray(protected_base), np.asarray(protected_eligible)
        if (set(np.unique(y)) != {0, 1, 2} or any(v.shape != (len(a),) for v in (y, base, eligible)) or
            any(v.shape != (len(p),) for v in (py, pb, pe)) or eligible.dtype != bool or pe.dtype != bool or
            len(groups) != len(a) or not np.all(np.isin(base, (-1, 0, 1, 2))) or not np.array_equal(py, pb)):
            raise ValueError('Three fitting grades, source support and correct protected baseline required')
        label_masks = [bits(y == k) for k in range(3)]; counts = [int(np.sum(y == k)) for k in range(3)]
        grade_masks = [bits(base == k) for k in range(3)]; protected_grades = [bits(pb == k) for k in range(3)]
        sources = [bits(np.asarray(groups) == g) for g in sorted(set(groups))]
        active, protected_active = bits(eligible), bits(pe); positions = {n: i for i, n in enumerate(self.names)}
        atoms = []
        for i in range(len(self.names)):
            for truth in (False, True):
                am, pm = a[:, i] == truth, p[:, i] == truth
                # A guard constant on fitting cases may still exclude a
                # protected counterexample and must remain available.
                if np.any(am) and (not np.all(am) or not np.all(pm)):
                    atoms.append((i, truth, bits(am), bits(pm)))
        def value(mask):
            return sum((mask & label_masks[k]).bit_count()/(3*counts[k]) for k in range(3))
        self.rules = []
        for _ in range(self.max_rules):
            best = None
            for before in range(3):
                for target in range(3):
                    if before == target:
                        continue
                    col = positions[self.seed_names[target]]
                    m = active & grade_masks[before] & bits(a[:, col])
                    pm = protected_active & protected_grades[before] & bits(p[:, col])
                    beam = [(((col, True),), m, pm)] if m else []
                    for depth in range(self.guards+1):
                        for conditions, mask, protect in beam:
                            gm, bm = mask & label_masks[target], mask & label_masks[before]
                            gain, loss = value(gm), value(bm)
                            nsource = sum(bool(gm & s) for s in sources)
                            score = gain-self.loss_cost*loss
                            if not protect and nsource >= self.min_sources and score > 1e-12:
                                rank = (-score, -nsource, loss, len(conditions), before, target, conditions)
                                if best is None or rank < best[0]:
                                    best = (rank, before, target, conditions, mask)
                        if depth == self.guards:
                            break
                        expanded = {}
                        for conditions, mask, protect in beam:
                            used = {i for i, _ in conditions}
                            for column, truth, atomic, patomic in atoms:
                                if column in used:
                                    continue
                                selected = mask & atomic; gm = selected & label_masks[target]
                                if gm.bit_count() < self.min_sources:
                                    continue
                                terms = tuple(sorted((*conditions, (column, truth))))
                                newp = protect & patomic
                                score = value(gm)-self.loss_cost*value(selected & label_masks[before])
                                rank = (-score+newp.bit_count(), -value(gm), terms)
                                expanded[terms] = (rank, terms, selected, newp)
                        beam = [(terms, mask, pm) for _, terms, mask, pm in sorted(expanded.values())[:16]]
            if best is None:
                break
            _, before, target, conditions, mask = best
            self.rules.append({'from_grade': before, 'grade': target,
                'conditions': [{'feature': self.names[i], 'value': truth} for i, truth in conditions]})
            active &= ~mask
        self.native_rules = deepcopy(self.rules); self.rules = merge_adjacent(self.rules, seed_names=self.seed_names)
        remaining = eligible.copy()
        for rule in self.rules:
            mask = remaining & (base == rule['from_grade'])
            for term in rule['conditions']:
                mask &= a[:, positions[term['feature']]] == term['value']
            gm = mask & (y == rule['grade']); bm = mask & (y == rule['from_grade'])
            supported = len({groups[i] for i in np.flatnonzero(gm)})
            assert supported >= self.min_sources
            rule['support'] = {'gain_sources': supported, 'gains': int(np.sum(gm)), 'losses': int(np.sum(bm)),
                'balanced_gain': value(bits(gm)), 'balanced_loss': value(bits(bm)),
                'matched_fitting_cases': int(np.sum(mask))}
            remaining[mask] = False
        self.training = {'rows': len(a), 'class_counts': counts, 'native_rules': len(self.native_rules),
            'merged_rules': len(self.rules), 'native_literals': sum(len(r['conditions']) for r in self.native_rules),
            'merged_literals': sum(len(r['conditions']) for r in self.rules), 'protected_cases': len(p)}
        assert np.array_equal(self.predict(p, base=pb, eligible=pe), py)
        native = self._predict(a, base, eligible, self.native_rules)
        assert np.array_equal(native, self.predict(a, base=base, eligible=eligible))
        return self

    def _predict(self, a, base, eligible, rules):
        output = np.asarray(base).copy(); available = np.asarray(eligible).copy()
        if output.shape != (len(a),) or available.shape != output.shape or available.dtype != bool:
            raise ValueError('Aligned current grades and explicit eligible routes required')
        positions = {n: i for i, n in enumerate(self.names)}
        for rule in rules:
            mask = available & (np.asarray(base) == rule['from_grade'])
            for term in rule['conditions']:
                mask &= a[:, positions[term['feature']]] == term['value']
            output[mask] = rule['grade']; available[mask] = False
        return output

    def predict(self, X, *, base, eligible):
        return self._predict(self._matrix(X), base, eligible, self.rules)

    def artifact(self):
        used = sorted({t['feature'] for r in self.rules for t in r['conditions']})
        rubric = list(self.rubric_intro)
        for i, rule in enumerate(self.rules, 1):
            terms = [self.descriptions[t['feature']] if t['value'] else 'Not established: '+self.descriptions[t['feature']] for t in rule['conditions']]
            rubric.append(str(i)+'. IF V112 proposes '+LABELS[rule['from_grade']]+' AND '+' AND '.join(terms)+' THEN '+LABELS[rule['grade']]+'.')
        artifact = {'version': self.version, 'rules': self.rules, 'feature_names': used,
            'feature_descriptions': {n: self.descriptions[n] for n in used}, 'rubric': '\n'.join(rubric)+'\n',
            'config': {'guards': self.guards, 'loss_cost': self.loss_cost, 'max_rules': self.max_rules, 'min_sources': self.min_sources},
            'training': self.training, 'outcome_contract_ref': self.contract_ref,
            'native_rules_ref': digest(self.native_rules)}
        artifact['artifact_ref'] = digest(artifact)
        return artifact


def execute(artifact, values, grade, eligible, *, contract_ref=outcome.CONTRACT_REF, seed_names=None):
    if artifact.get('artifact_ref') != digest({k: v for k, v in artifact.items() if k != 'artifact_ref'}):
        raise ValueError('Changed facet selector artifact')
    if artifact['outcome_contract_ref'] != contract_ref:
        raise ValueError('Wrong reconstructed outcome policy')
    if not eligible:
        return grade
    seed_names = DEFAULT_SEEDS if seed_names is None else seed_names
    for rule in artifact['rules']:
        anchor = (seed_names[rule['grade']], True)
        if anchor not in {(t['feature'], t['value']) for t in rule['conditions']}:
            raise ValueError('Affirmative outcome witness required')
        if any(t['feature'] not in values or type(values[t['feature']]) is not bool for t in rule['conditions']):
            raise ValueError('Complete explicit Boolean evidence required')
        if grade == rule['from_grade'] and all(values[t['feature']] == t['value'] for t in rule['conditions']):
            return rule['grade']
    return grade
