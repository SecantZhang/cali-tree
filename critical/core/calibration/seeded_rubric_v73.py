"""Warrant-seeded semantic grading and judge-reliability rules.

Distinct semantic predicates remain distinct even if fitting columns coincide.
Every search begins with an explicit grading warrant or a review/defer reason.
"""
from dataclasses import dataclass, asdict

import numpy as np

from .base import Calibrator
from .semantic_rubric_v70 import DESCRIPTIONS as OLD, allowed_feature
from .rubric_evidence_v73 import SPECS, CONTRACT_REF
from ..decision.artifacts import digest

DESCRIPTIONS = {**OLD, **SPECS}
LABELS = ('no', 'partial', 'yes')
REVIEW = ('rubric_uncertainty_any', 'rubric_endpoint_contradiction_any',
          'rubric_physical_semantic_mismatch_any', 'rubric_goal_witness_missing_any',
          'rubric_identity_objection_to_authorized_change_any', 'rubric_outcome_unknown_any', 'rubric_duplicate_conflict_any')


@dataclass(frozen=True)
class Search:
    family: str = 'semantic'
    mode: str = 'hybrid'
    max_guards: int = 2
    max_rules: int = 12
    max_features: int = 120
    beam_width: int = 24
    min_sources: int = 2
    loss_cost: float = 2.

    def __post_init__(self):
        if self.family not in ('semantic', 'grounded', 'auxiliary') or self.mode not in ('grades', 'routes', 'hybrid'):
            raise ValueError('Invalid rubric search family/mode')
        if any(type(n) is not int or n < 1 for n in (self.max_rules, self.max_features, self.beam_width, self.min_sources)) or not 0 <= self.max_guards <= 3 or self.loss_cost < 1:
            raise ValueError('Invalid bounded search configuration')


def seeds(action):
    if action in (0, 1, 2):
        return [((f'rubric_{LABELS[action]}_ready', True),)]
    if action == 'regular':
        return [(('view_disagrees', True), (name, True)) for name in REVIEW] + [
            (('view_disagrees', True), ('view_teacher_unwarranted', True), ('view_regular_warranted', True))]
    raise ValueError('Unknown rubric action')


class SeededRubric(Calibrator):
    version = 'warrant-seeded-judge-rubric-v73'
    descriptions = DESCRIPTIONS
    evidence_specs = SPECS
    evidence_contract_ref = CONTRACT_REF

    def __init__(self, feature_names, config=Search()):
        if not feature_names or len(set(feature_names)) != len(feature_names) or any(n not in self.descriptions for n in feature_names):
            raise ValueError('Closed named semantic/view predicates required')
        self.names, self.config, self.rules = list(feature_names), config, []

    def accepts_feature(self, name):
        return name in self.evidence_specs or allowed_feature(name, self.config.family)

    def rule_seeds(self, action):
        return seeds(action)

    def _matrix(self, X):
        a = np.asarray(X)
        if a.ndim != 2 or a.shape[1] != len(self.names) or not np.all((a == 0) | (a == 1)):
            raise ValueError('Boolean rubric evidence required')
        return a.astype(bool)

    def fit(self, X, y, *, sample_weight=None, groups=None, base=None, regular=None,
            protected_X=None, protected_y=None, protected_base=None, protected_regular=None, priority=None):
        if sample_weight is not None:
            raise ValueError('Source support and explicit protected-case vetoes required')
        a, y, base, regular = self._matrix(X), np.asarray(y), np.asarray(base), np.asarray(regular)
        n, full = len(a), (1 << len(a)) - 1
        if any(v.shape != (n,) for v in (y, base, regular)) or groups is None or len(groups) != n:
            raise ValueError('Aligned grades and source groups required')
        if not np.all(np.isin(y, (0, 1, 2))) or not np.all(np.isin(base, (0, 1, 2))) or not np.all(np.isin(regular, (-1, 0, 1, 2))):
            raise ValueError('Invalid fitting grade')
        p = self._matrix(protected_X) if protected_X is not None else a[:0]
        py = np.asarray(protected_y if protected_y is not None else [])
        pb = np.asarray(protected_base if protected_base is not None else [])
        pr = np.asarray(protected_regular if protected_regular is not None else [])
        if any(len(v) != len(p) for v in (py, pb, pr)):
            raise ValueError('Protected actual predictions must align')
        positions = {name: i for i, name in enumerate(self.names)}
        priority = priority or {}
        eligible = [i for i, name in enumerate(self.names) if
                    self.accepts_feature(name) and np.any(a[:, i]) and not np.all(a[:, i])]
        eligible.sort(key=lambda i: (-(priority.get(self.names[i], 0.) + (2000 if self.names[i].startswith('view_') else 0)), self.names[i]))
        eligible = eligible[:self.config.max_features]
        # No observed-column deduplication: equal measurements do not make two
        # physical or semantic concepts interchangeable.
        def mask(values):
            return sum(1 << int(i) for i in np.flatnonzero(values))
        atoms = [(i, truth, mask(a[:, i] == truth)) for i in sorted(eligible) for truth in (False, True)]
        source_cache = {}
        def count_sources(m):
            if m not in source_cache:
                remaining, seen = m, set()
                while remaining:
                    bit = remaining & -remaining
                    seen.add(groups[bit.bit_length() - 1]); remaining ^= bit
                source_cache[m] = len(seen)
            return source_cache[m]
        actions = ([0, 1, 2] if self.config.mode != 'routes' else []) + (['regular'] if self.config.mode != 'grades' else [])
        candidates, examined = {}, 0
        for context in (0, 1, 2):
            for action in actions:
                if action == context:
                    continue
                wanted = regular if action == 'regular' else np.full(n, action)
                scope = mask((base == context) & (wanted >= 0) & (wanted != base))
                positive = mask((wanted == y) & (base != y)) & scope
                negative = mask((base == y) & (wanted != y)) & scope
                if positive.bit_count() < self.config.min_sources:
                    continue
                p_wanted = pr if action == 'regular' else np.full(len(p), action)
                p_scope = (pb == context) & (p_wanted >= 0) & (p_wanted != pb)
                for seed in self.rule_seeds(action):
                    terms = tuple(sorted((positions[name], truth) for name, truth in seed))
                    initial = scope
                    for col, truth in terms:
                        initial &= mask(a[:, col] == truth)
                    beam = [((), initial)]
                    for depth in range(self.config.max_guards + 1):
                        next_states = []
                        for guards, selected in beam:
                            combined = tuple(sorted(terms + guards))
                            good, bad = (selected & positive).bit_count(), (selected & negative).bit_count()
                            if good < self.config.min_sources:
                                continue
                            protect = p_scope.copy()
                            for col, truth in combined:
                                protect &= p[:, col] == truth
                            conflicts = int(np.sum(protect & (p_wanted != py)))
                            examined += 1
                            if not conflicts and good - self.config.loss_cost * bad > 0 and count_sources(selected & positive) >= self.config.min_sources:
                                key = (context, str(action), combined)
                                candidates[key] = {'context': context, 'action': action, 'terms': combined, 'seed': seed,
                                                   'mask': selected, 'positive': positive, 'negative': negative}
                            if depth == self.config.max_guards:
                                continue
                            used = {i for i, _ in combined}
                            last = guards[-1][0] if guards else -1
                            for column, truth, atomic in atoms:
                                if column <= last or column in used:
                                    continue
                                chosen = selected & atomic
                                g, b = (chosen & positive).bit_count(), (chosen & negative).bit_count()
                                if g < self.config.min_sources:
                                    continue
                                p_match = protect & (p[:, column] == truth)
                                pc = int(np.sum(p_match & (p_wanted != py)))
                                rank = (-(g - self.config.loss_cost * b - 4 * pc), -g / (b + 1.), -g,
                                        guards + ((column, truth),))
                                next_states.append((rank, guards + ((column, truth),), chosen))
                        next_states.sort(key=lambda row: row[0])
                        beam = [(guards, selected) for _, guards, selected in next_states[:self.config.beam_width]]
        self.rules, uncovered = [], full
        for _ in range(self.config.max_rules):
            passing = []
            for c in candidates.values():
                chosen = c['mask'] & uncovered
                g, b = (chosen & c['positive']).bit_count(), (chosen & c['negative']).bit_count()
                if g - self.config.loss_cost * b <= 0 or count_sources(chosen & c['positive']) < self.config.min_sources:
                    continue
                rank = (-(g - self.config.loss_cost * b), -count_sources(chosen & c['positive']), b,
                        len(c['terms']), c['context'], str(c['action']), c['terms'])
                passing.append((rank, c, chosen, g, b))
            if not passing:
                break
            _, c, chosen, g, b = min(passing, key=lambda r: r[0])
            self.rules.append({'teacher_grade': c['context'], 'action': c['action'],
                'conditions': [{'feature': self.names[i], 'value': bool(t)} for i, t in c['terms']],
                'warrant': [{'feature': n, 'value': t} for n, t in c['seed']],
                'support': {'gain_sources': count_sources(chosen & c['positive']), 'gains': g, 'losses': b}})
            uncovered &= full ^ chosen
        self.stats = {'candidate_states': examined, 'candidate_rules': len(candidates), 'rules': len(self.rules)}
        return self

    def predict(self, X, *, base, regular):
        a, output = self._matrix(X), np.asarray(base).copy()
        baseline, regular = np.asarray(base), np.asarray(regular)
        if baseline.shape != (len(a),) or regular.shape != (len(a),):
            raise ValueError('Aligned current judge views required')
        positions, used = {n: i for i, n in enumerate(self.names)}, np.zeros(len(a), dtype=bool)
        for rule in self.rules:
            match = ~used & (baseline == rule['teacher_grade'])
            for term in rule['conditions']:
                match &= a[:, positions[term['feature']]] == term['value']
            wanted = regular if rule['action'] == 'regular' else np.full(len(a), rule['action'])
            match &= wanted >= 0
            output[match], used[match] = wanted[match], True
        return output.tolist()

    def metadata(self):
        return {'version': self.version, 'config': asdict(self.config), 'rules': self.rules,
                'feature_names': sorted({t['feature'] for r in self.rules for t in r['conditions']}), 'training': self.stats,
                'evidence_contract_ref': self.evidence_contract_ref}

    def render(self):
        lines = ['Apply these semantic grading/reliability rules in order; otherwise retain the boosted teacher.',
                 'A review/defer rule selects an independent image judge; it never turns uncertainty itself into failure.',
                 'Shared rubric definitions:']
        for name in ('rubric_no_ready', 'rubric_partial_ready', 'rubric_yes_ready'):
            lines.append(name + ': ' + self.evidence_specs[name])
        for i, rule in enumerate(self.rules, 1):
            conditions = ['the boosted teacher proposes ' + LABELS[rule['teacher_grade']]]
            conditions += [(self.descriptions[t['feature']] if t['value'] else 'Not established: ' + self.descriptions[t['feature']]) for t in rule['conditions']]
            action = 'use the independent regular visual judgment' if rule['action'] == 'regular' else 'grade ' + LABELS[rule['action']]
            lines.append(str(i) + '. IF ' + ' AND '.join(conditions) + ' THEN ' + action + '.')
        return '\n'.join(lines) + '\n'

    def artifact(self, teacher_ref):
        value = {**self.metadata(), 'teacher_ref': teacher_ref, 'rubric': self.render()}
        value['artifact_ref'] = digest(value)
        return value
