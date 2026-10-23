"""Veto harmful tree/regular disagreements while protecting correct routes.

Fit short semantic support clauses separately for each predicted-label pair.
Only cases where regular is correct and the tree is wrong are rejection targets.
Correct protected and calibration decisions must all survive. Runtime has no
case IDs, source membership, reference labels or feature-signature lookups.
"""
from copy import deepcopy

from ..decision.artifacts import digest
from . import regular_aware_gate_v35 as aware

VERSION = 'disagreement-coverage-v36'
CONTRACT = digest({'version': VERSION, 'parent': aware.CONTRACT, 'features': aware.NAMES,
                   'grammar': 'Per tree/regular disagreement pair: at most eight one/two-literal CNF support clauses.',
                   'fit': 'Retain all correct protected/calibration tree decisions; target only wrong trees replacing correct regular judgments.',
                   'inference': 'A veto defers to the unchanged regular judge; no new tree labels or coverage.'})


def prepare(base, examples):
    result = []
    for e in examples:
        if e['features'] is None:
            continue
        selection = base.resolve(e['program'], e['features'], e['regular'], corrections=False)
        if not selection['covered'] or e['regular'] < 0 or selection['prediction'] == e['regular']:
            continue
        result.append({'prediction': selection['prediction'], 'regular': e['regular'], 'reference': e['reference'],
                       'source_group': e['source_group'],
                       'values': aware.values_with_judge(e['program'], e['features'], e['regular'])})
    return result


def fit(base, protected, calibration, *, max_clauses=4):
    if type(max_clauses) is not int or not 1 <= max_clauses <= 8:
        raise ValueError('Support budget must be between one and eight clauses')
    if any(e['prediction'] != e['reference'] for e in protected):
        raise ValueError('Protected decisions must be correct')
    clauses, counts = {}, {}
    for prediction in (0, 1, 2):
        for regular in (0, 1, 2):
            if prediction == regular:
                continue
            key = f'{prediction}:{regular}'
            pos = [e for e in protected + calibration if e['prediction'] == prediction
                   and e['regular'] == regular and e['reference'] == prediction]
            neg = [e for e in calibration if e['prediction'] == prediction
                   and e['regular'] == regular and e['reference'] == regular]
            # No positive context means there is no supported semantic boundary
            # to fit. Do not replace that lack of evidence with a blanket veto.
            cs = aware.fit_label([e['values'] for e in pos], [e['values'] for e in neg], max_clauses) if pos and neg else []
            assert all(aware.fixed.passes(cs, e['values']) for e in pos)
            rejected = sum(not aware.fixed.passes(cs, e['values']) for e in neg)
            clauses[key] = cs
            counts[key] = {'protected_correct': len(pos), 'harmful': len(neg), 'rejected_harmful': rejected,
                           'unseparated_harmful': len(neg) - rejected,
                           'correct_sources': len({e['source_group'] for e in pos}),
                           'harmful_sources': len({e['source_group'] for e in neg})}
    support = {'version': VERSION, 'contract_ref': CONTRACT, 'clauses': clauses, 'training_counts': counts,
               'max_clauses': max_clauses}
    support['artifact_ref'] = digest(support)
    return DisagreementCoverageGate(base, support)


def validate_support(a):
    keys = {f'{p}:{r}' for p in (0, 1, 2) for r in (0, 1, 2) if p != r}
    if (set(a) != {'version', 'contract_ref', 'clauses', 'training_counts', 'max_clauses', 'artifact_ref'}
            or a['version'] != VERSION or a['contract_ref'] != CONTRACT
            or a['artifact_ref'] != digest({k: v for k, v in a.items() if k != 'artifact_ref'})
            or set(a['clauses']) != keys or set(a['training_counts']) != keys
            or type(a['max_clauses']) is not int or not 1 <= a['max_clauses'] <= 8):
        raise ValueError('Changed disagreement support contract')
    for key, clauses in a['clauses'].items():
        if len(clauses) > a['max_clauses']:
            raise ValueError('Too many support clauses')
        for cs in clauses:
            if not 1 <= len(cs) <= 2 or len({c['feature'] for c in cs}) != len(cs):
                raise ValueError('Invalid disagreement clause')
            for c in cs:
                if set(c) != {'feature', 'value'} or c['feature'] not in aware.NAMES or type(c['value']) is not bool:
                    raise ValueError('Undeclared disagreement predicate')
        counts = a['training_counts'][key]
        if (set(counts) != {'protected_correct', 'harmful', 'rejected_harmful', 'unseparated_harmful', 'correct_sources', 'harmful_sources'}
                or any(type(v) is not int or v < 0 for v in counts.values())
                or counts['rejected_harmful'] + counts['unseparated_harmful'] != counts['harmful']
                or counts['correct_sources'] > counts['protected_correct'] or counts['harmful_sources'] > counts['harmful']
                or (clauses and not counts['protected_correct'])):
            raise ValueError('Invalid disagreement support counts')


class DisagreementCoverageGate:
    def __init__(self, base, support):
        validate_support(support)
        self.base, self.support = base, deepcopy(support)
        self.artifact = {'version': VERSION, 'contract_ref': CONTRACT, 'base_gate': base.export(), 'support': deepcopy(support)}
        self.artifact['artifact_ref'] = digest(self.artifact)

    def export(self):
        return deepcopy(self.artifact)

    @classmethod
    def restore(cls, a):
        if (set(a) != {'version', 'contract_ref', 'base_gate', 'support', 'artifact_ref'}
                or a['version'] != VERSION or a['contract_ref'] != CONTRACT
                or a['artifact_ref'] != digest({k: v for k, v in a.items() if k != 'artifact_ref'})):
            raise ValueError('Changed disagreement gate')
        validate_support(a['support'])
        result = cls(aware.RegularAwareGate.restore(a['base_gate']), a['support'])
        if result.export() != a:
            raise ValueError('Noncanonical disagreement gate')
        return result

    def resolve(self, program, record, regular, *, corrections=False):
        if type(regular) is not int or regular not in (-1, 0, 1, 2):
            raise ValueError('Invalid regular judgment')
        before = self.base.resolve(program, record, regular, corrections=corrections)
        if not before['covered'] or regular < 0 or before['prediction'] == regular:
            return before
        key = f"{before['prediction']}:{regular}"
        clauses = self.support['clauses'][key]
        values = aware.values_with_judge(program, record, regular)
        failed = [cs for cs in clauses if not aware.fixed.passes([cs], values)]
        if failed:
            return {'covered': False, 'prediction': -1, 'reason': 'outside_disagreement_support', 'matches': [],
                    'rejected_route': before, 'regular_prediction': regular, 'failed_support_clauses': deepcopy(failed),
                    'disagreement_support_ref': self.support['artifact_ref']}
        return before
