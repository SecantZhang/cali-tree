"""Short executable semantic rubrics distilled from a boosted teacher.

Training groups and protected membership constrain fitting only. Inference reads
named Boolean evidence and an optional teacher grade, never source identities.
"""
from dataclasses import asdict, dataclass

import numpy as np

from .base import Calibrator
from . import evidence_coverage_v20 as evidence
from . import judge_semantics_v60 as language
from ...vision import paired_features_v69 as vision
from ..decision.artifacts import digest

VERSION = 'teacher-guided-semantic-rubric-v70'
DESCRIPTIONS = {**evidence.FEATURES, **language.SPECS, **vision.SPECS}
LABELS = ('No', 'Partial', 'Yes')


def allowed_feature(name, family):
    if name not in DESCRIPTIONS or name.endswith('_available'):
        return False
    if family not in ('semantic', 'grounded', 'auxiliary'):
        raise ValueError('Unknown semantic rubric vocabulary')
    if name.startswith(('meaning_', 'requires_', 'task_', 'intent_')):
        return True
    if family in ('grounded', 'auxiliary') and name in evidence.FEATURES:
        return True
    return family == 'auxiliary' and name.startswith('vision_')


def anchor(conditions):
    # A task type or a similarity threshold alone must never justify a grade.
    return any(c['value'] and c['feature'].startswith('meaning_') and
               c['feature'] != 'meaning_available' for c in conditions)


@dataclass(frozen=True)
class Config:
    family: str = 'semantic'
    mode: str = 'reconstruct'
    max_literals: int = 3
    max_rules: int = 8
    max_features: int = 96
    beam_width: int = 24
    min_sources: int = 3
    minimum_precision: float = 1.
    loss_cost: float = 2.

    def __post_init__(self):
        if self.family not in ('semantic', 'grounded', 'auxiliary') or self.mode not in ('reconstruct', 'correct'):
            raise ValueError('Invalid rubric configuration')
        if any(type(v) is not int or v < 1 for v in
               (self.max_literals, self.max_rules, self.max_features, self.beam_width, self.min_sources)):
            raise ValueError('Positive integer search bounds required')
        if not 0 < self.minimum_precision <= 1 or self.loss_cost < 1:
            raise ValueError('Invalid rule precision or error cost')


class SemanticRubric(Calibrator):
    version = VERSION

    def __init__(self, feature_names, config=Config()):
        if len(set(feature_names)) != len(feature_names) or not feature_names:
            raise ValueError('Unique named evidence required')
        self.names, self.config, self.rules = list(feature_names), config, []

    def _matrix(self, X):
        matrix = np.asarray(X)
        if matrix.ndim != 2 or matrix.shape[1] != len(self.names) or not np.all((matrix == 0) | (matrix == 1)):
            raise ValueError('Declared Boolean evidence matrix required')
        return matrix.astype(bool)

    def accepts_clause(self, label, conditions):
        return anchor(conditions)

    def fit(self, X, y, *, sample_weight=None, groups=None, base_predictions=None,
            protected_X=None, protected_y=None, protected_base=None, priority=None):
        if sample_weight is not None:
            raise ValueError('Rubrics use explicit source support and protected-case vetoes')
        matrix, target = self._matrix(X), np.asarray(y, dtype=int)
        n = len(matrix)
        if target.shape != (n,) or not np.all(np.isin(target, (0, 1, 2))):
            raise ValueError('Three-class fitting targets required')
        if groups is None or len(groups) != n:
            raise ValueError('Distinct-source fitting support required')
        baseline = np.full(n, -1) if base_predictions is None else np.asarray(base_predictions, dtype=int)
        if baseline.shape != (n,) or not np.all(np.isin(baseline, (-1, 0, 1, 2))):
            raise ValueError('Invalid teacher grades')
        protect = self._matrix(protected_X) if protected_X is not None else matrix[:0]
        py = np.asarray(protected_y if protected_y is not None else [], dtype=int)
        pb = np.asarray(protected_base if protected_base is not None else [-1] * len(protect), dtype=int)
        if len(py) != len(protect) or len(pb) != len(protect):
            raise ValueError('Protected evidence and actual teacher grades must align')
        priority = priority or {}
        eligible = [i for i, name in enumerate(self.names) if allowed_feature(name, self.config.family) and
                    np.any(matrix[:, i]) and not np.all(matrix[:, i])]
        eligible.sort(key=lambda i: (-priority.get(self.names[i], 0.), self.names[i]))
        eligible = eligible[:self.config.max_features]
        # Equivalent columns share one named literal, selected using fitting data.
        unique, seen = [], set()
        for i in eligible:
            signature = matrix[:, i].tobytes()
            if signature not in seen:
                unique.append(i)
                seen.add(signature)
        self.search_features = [self.names[i] for i in unique]
        full = (1 << n) - 1
        def bitmask(values):
            return sum(1 << int(i) for i in np.flatnonzero(values))
        target_masks = [bitmask(target == c) for c in range(3)]
        base_masks = [bitmask(baseline == c) for c in range(3)]
        correct_mask = bitmask(baseline == target)
        atoms = [(i, truth, bitmask(matrix[:, i] == truth)) for i in sorted(unique) for truth in (False, True)]
        source_counts = {}
        def source_count(mask):
            if mask not in source_counts:
                remaining, values = mask, set()
                while remaining:
                    bit = remaining & -remaining
                    values.add(groups[bit.bit_length() - 1])
                    remaining ^= bit
                source_counts[mask] = len(values)
            return source_counts[mask]
        candidates, examined = {}, 0
        for label in range(3):
            contexts = (None,) if self.config.mode == 'reconstruct' else tuple(c for c in range(3) if c != label)
            for context in contexts:
                scope = full if context is None else base_masks[context]
                positive = target_masks[label] & scope
                negative = (full ^ target_masks[label]) & scope if context is None else correct_mask & scope
                protect_scope = np.ones(len(protect), dtype=bool) if context is None else pb == context
                beam = [((), scope)]
                for depth in range(1, self.config.max_literals + 1):
                    next_states = {}
                    for conditions, parent in beam:
                        last = conditions[-1][0] if conditions else -1
                        for column, truth, atomic in atoms:
                            if column <= last:
                                continue
                            selected = parent & atomic
                            good, bad = (selected & positive).bit_count(), (selected & negative).bit_count()
                            if good < self.config.min_sources:
                                continue
                            terms = conditions + ((column, truth),)
                            examined += 1
                            protect_match = protect_scope.copy()
                            for c, t in terms:
                                protect_match &= protect[:, c] == t
                            conflicts = int(np.sum(protect_match & (py != label)))
                            ranking = (good / (bad + 1.), good - self.config.loss_cost * bad - 4 * conflicts,
                                       good, -bad, -len(terms))
                            previous = next_states.get(selected)
                            if previous is None or ranking > previous[0] or (ranking == previous[0] and terms < previous[1]):
                                next_states[selected] = (ranking, terms)
                            descriptions = [{'feature': self.names[c], 'value': bool(t)} for c, t in terms]
                            if (not conflicts and self.accepts_clause(label, descriptions) and good / (good + bad) >= self.config.minimum_precision
                                    and good - self.config.loss_cost * bad > 0
                                    and source_count(selected & positive) >= self.config.min_sources):
                                key = (label, context, selected)
                                if key not in candidates or terms < candidates[key]['terms']:
                                    candidates[key] = {'terms': terms, 'mask': selected, 'label': label, 'context': context,
                                                       'positive': positive, 'negative': negative}
                    ranked = sorted(next_states.items(), key=lambda item: (tuple(-v for v in item[1][0]), item[1][1]))
                    beam = [(terms, mask) for mask, (_, terms) in ranked[:self.config.beam_width]]
        uncovered, self.rules = full, []
        for _ in range(self.config.max_rules):
            passing = []
            for c in candidates.values():
                selected = c['mask'] & uncovered
                good, bad = (selected & c['positive']).bit_count(), (selected & c['negative']).bit_count()
                if (good < self.config.min_sources or good / (good + bad) < self.config.minimum_precision or
                        good - self.config.loss_cost * bad <= 0 or source_count(selected & c['positive']) < self.config.min_sources):
                    continue
                rank = (-(good - self.config.loss_cost * bad), -good, bad, len(c['terms']), c['label'],
                        -1 if c['context'] is None else c['context'], c['terms'])
                passing.append((rank, c, selected, good, bad))
            if not passing:
                break
            _, c, selected, good, bad = min(passing, key=lambda row: row[0])
            self.rules.append({'conditions': [{'feature': self.names[i], 'value': bool(t)} for i, t in c['terms']],
                               'prediction': c['label'], 'teacher_grade': c['context'],
                               'support': {'correct_sources': source_count(selected & c['positive']),
                                           'correct_cases': good, 'incorrect_cases': bad}})
            uncovered &= full ^ selected
        self.fit_stats = {'candidate_conditions_examined': examined, 'candidate_rules': len(candidates),
                          'rules': len(self.rules), 'fitting_rows': n}
        return self

    def predict(self, X, *, base_predictions=None):
        matrix = self._matrix(X)
        baseline = np.full(len(matrix), -1, dtype=int) if base_predictions is None else np.asarray(base_predictions, dtype=int)
        if baseline.shape != (len(matrix),):
            raise ValueError('Teacher grade count mismatch')
        output, assigned = baseline.copy(), np.zeros(len(matrix), dtype=bool)
        positions = {name: i for i, name in enumerate(self.names)}
        for rule in self.rules:
            match = ~assigned
            if rule['teacher_grade'] is not None:
                match &= baseline == rule['teacher_grade']
            for term in rule['conditions']:
                match &= matrix[:, positions[term['feature']]] == term['value']
            output[match], assigned[match] = rule['prediction'], True
        return output.tolist()

    def metadata(self):
        return {'version': self.version, 'config': asdict(self.config), 'rules': self.rules,
                'feature_names': sorted({t['feature'] for r in self.rules for t in r['conditions']}),
                'training': self.fit_stats}

    def render(self):
        lines = ['Apply rules in order to validated instruction-relative evidence. If none applies, retain the boosted teacher grade.',
                 'An unestablished predicate is not evidence for its physical opposite. Similarity tests remain measurements, not factual guarantees.']
        for i, rule in enumerate(self.rules, 1):
            parts = [] if rule['teacher_grade'] is None else ['the boosted teacher proposes ' + LABELS[rule['teacher_grade']]]
            parts += [(DESCRIPTIONS[t['feature']] if t['value'] else 'Not established: ' + DESCRIPTIONS[t['feature']])
                      for t in rule['conditions']]
            lines.append(f'{i}. IF ' + ' AND '.join(parts) + ' THEN grade ' + LABELS[rule['prediction']] + '.')
        return '\n'.join(lines) + '\n'

    def artifact(self, teacher_ref):
        value = {**self.metadata(), 'teacher_ref': teacher_ref,
                 'contract_ref': digest(DESCRIPTIONS), 'rubric': self.render()}
        value['artifact_ref'] = digest(value)
        return value
