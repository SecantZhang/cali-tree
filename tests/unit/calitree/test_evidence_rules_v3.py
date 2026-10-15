"""Three labels, uncertainty relevance and anonymous monotone rules; no APIs."""
from copy import deepcopy
import json

import numpy as np
import pytest

from critical.core.calibration.evidence_rules_v3 import (
    DOMAIN, DOMAIN_ARRAY, EDGES, FEATURES, EvidenceRuleCalibrator,
    evidence_bounds, prediction, monotone, validate_tree, vector,
)
from critical.core.decision.rich_evidence import COLLATERAL_FIELDS


def record(core='complete', constraint='complete', *, loss='none'):
    instruction = 'Change the object with the requested relation'
    return {'instruction': instruction, 'observations': {
        'instruction_scope': 'Change the intended object with its requested relation.',
        'target': {'state': 'matched', 'evidence': 'The target is identifiable.'},
        'source_integrity': {'state': 'preserved', 'evidence': 'The source meaning is retained.'},
        'requirements': [
            {'id': 'c', 'source_quote': 'Change the object', 'question': 'Is the change realized?',
             'role': 'core', 'state': core, 'evidence': 'Visible transformation evidence.'},
            {'id': 'q', 'source_quote': 'the requested relation', 'question': 'Is the relation realized?',
             'role': 'constraint', 'state': constraint, 'evidence': 'Visible relation evidence.'}],
        'collateral': {k: {'state': loss if k == 'entity_loss' else 'none', 'evidence': 'Collateral comparison.'} for k in COLLATERAL_FIELDS},
        'verification_visibility': {'state': 'full', 'evidence': 'Relevant content visible.'},
    }}


@pytest.fixture(scope='module')
def fitted():
    X = [record(constraint=state) for state in ('absent', 'absent', 'incomplete', 'incomplete', 'complete', 'complete')]
    return EvidenceRuleCalibrator().fit(X, [0, 0, 1, 1, 2, 2], source_groups=list('abcdef'))


def test_no_can_be_learned_even_when_some_core_is_complete(fitted):
    assert fitted.predict([record(constraint=s) for s in ('absent', 'incomplete', 'complete')]) == [0., 1., 2.]
    assert min(fitted.metadata()['leaf_support'].values()) >= 2


def test_previously_forced_no_can_be_recalibrated():
    X = [record('absent', loss=state) for state in ('none', 'none', 'present', 'present')]
    X += [record(), record()]
    model = EvidenceRuleCalibrator().fit(X, [1, 1, 0, 0, 2, 2], source_groups=list('abcdef'))
    assert model.predict([record('absent'), record('absent', loss='present'), record()]) == [1., 0., 2.]


def test_irrelevant_unknown_does_not_force_abstention(fitted):
    value = record(loss='unknown')
    p = fitted.predict_records([value])[0]
    assert p['label'] == 'yes' and p['resolved']
    assert 'collateral_continuity' in p['uncertain_features']
    assert p['label_bounds'] == ['yes', 'yes']


def test_decision_relevant_unknown_remains_unresolved(fitted):
    p = fitted.predict_records([record(constraint='unknown')])[0]
    assert p['label'] is None and p['label_bounds'] == ['no', 'yes']
    assert p['evidence_bounds']['lower']['constraint_minimum'] == 0
    assert p['evidence_bounds']['upper']['constraint_minimum'] == 2


def test_unknown_target_is_not_assigned_an_immutable_label():
    value = record(); value['observations']['target']['state'] = 'unknown'
    bounds = evidence_bounds(value)
    assert bounds['lower']['target_match'] == 0 and bounds['upper']['target_match'] == 1
    tree = {'predicate': 'target_matches', 'when_true': {'label': 'yes'}, 'when_false': {'label': 'no'}}
    assert monotone(tree) and prediction(tree, bounds)['label'] is None


def test_all_known_improvements_preserve_ordinal_monotonicity(fitted):
    assert len(DOMAIN) == 972
    assert np.all(DOMAIN_ARRAY[:, FEATURES.index('core_minimum')] <= DOMAIN_ARRAY[:, FEATURES.index('core_maximum')])
    scores = vector(fitted.metadata()['tree'])
    assert all(scores[a] <= scores[b] for a, b in EDGES)
    assert scores[-1] == 2


def test_unknown_extremes_bound_all_concrete_completions(fitted):
    value = record(constraint='unknown', loss='unknown')
    bounds = evidence_bounds(value)
    lo = prediction(fitted.metadata()['tree'], bounds)['label_bounds'][0]
    hi = prediction(fitted.metadata()['tree'], bounds)['label_bounds'][1]
    labels = ('no', 'partial', 'yes')
    for state in ('absent', 'incomplete', 'complete'):
        for loss in ('none', 'present'):
            result = fitted.predict_records([record(constraint=state, loss=loss)])[0]['label']
            assert labels.index(lo) <= labels.index(result) <= labels.index(hi)


def test_text_names_order_and_counts_cannot_be_identity_features(fitted):
    original = record(); changed = deepcopy(original); changed['instruction'] = 'An anonymous instruction'
    obs = changed['observations']; obs['instruction_scope'] = 'Different descriptive words.'
    for i, q in enumerate(obs['requirements']):
        q.update(id='anon'+str(i), source_quote=changed['instruction'], question='Anonymous question '+str(i), evidence='Anonymous evidence.')
    q = obs['requirements'][0]
    obs['requirements'].append({**q, 'id': 'duplicate', 'question': 'Equivalent extra question?'})
    obs['requirements'].reverse()
    assert evidence_bounds(original) == evidence_bounds(changed)
    assert fitted.predict_records([original]) == fitted.predict_records([changed])


@pytest.mark.parametrize('key', ['reference', 'case_id', 'human_score', 'task', 'editing_model'])
def test_metadata_rejected(key):
    value = record(); value[key] = 'forbidden'
    with pytest.raises(ValueError): evidence_bounds(value)


def test_portable_artifact_replay_and_forbidden_rule_rejection(fitted):
    restored = EvidenceRuleCalibrator.restore(json.loads(json.dumps(fitted.metadata())))
    assert restored.predict_records([record(), record(loss='unknown')]) == fitted.predict_records([record(), record(loss='unknown')])
    with pytest.raises(ValueError): validate_tree({'predicate': 'specific_instruction', 'when_true': {'label':'yes'}, 'when_false': {'label':'no'}})
    broken = fitted.metadata(); broken['tree'] = {'predicate':'every_core_complete','when_true':{'label':'no'},'when_false':{'label':'yes'}}
    with pytest.raises(ValueError): EvidenceRuleCalibrator.restore(broken)


def test_sources_must_be_distinct_and_supported():
    with pytest.raises(ValueError): EvidenceRuleCalibrator().fit([record(), record()], [1, 2], source_groups=['same', 'same'])
    with pytest.raises(ValueError): EvidenceRuleCalibrator().fit([record()], [2], source_groups=['one'])
