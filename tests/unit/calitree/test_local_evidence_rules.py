"""Reusable rule syntax, semantic invariants, local fitting and replay; no APIs."""
from copy import deepcopy
import json

import pytest

from critical.core.calibration.local_evidence_rules import (
    DOMAIN, FEATURES, LIMITS, LocalEvidenceRuleCalibrator, decide,
    feature_conflicts, monotone, summarize, validate_tree,
)


def record(state='incomplete', integrity='preserved'):
    return {'instruction': 'Change the intended object', 'observations': {
        'instruction_scope': 'A requested change of the intended object.',
        'target': {'state': 'matched', 'evidence': 'The intended target is identifiable.'},
        'source_integrity': {'state': integrity, 'evidence': 'Source comparison evidence.'},
        'requirements': [{'id': 'r', 'source_quote': 'Change the intended object',
                          'question': 'Is the requested change realized?', 'role': 'core',
                          'state': state, 'evidence': 'Observed result and any remaining shortfall.'}],
    }}


def fitted():
    X = [record(), record(), record(integrity='material_deviation'), record(integrity='material_deviation'),
         record('absent'), record('absent')]
    return LocalEvidenceRuleCalibrator().fit(X, [2, 2, 1, 1, 0, 0], source_groups=list('abcdef'))


def test_local_fit_learns_shared_policy_with_supported_leaves():
    model = fitted()
    assert model.predict([record(), record(integrity='material_deviation'), record('absent')]) == [2., 1., 0.]
    meta = model.metadata()
    assert meta['tree']['predicate'] == 'source_preserved'
    assert min(meta['leaf_support'].values()) >= LIMITS['min_leaf_sources']
    assert monotone(meta['tree'])


def test_renaming_instruction_entities_questions_and_evidence_does_not_change_prediction():
    original = record(); renamed = deepcopy(original)
    renamed['instruction'] = 'Modify another subject'
    obs = renamed['observations']; obs['instruction_scope'] = 'An unrelated wording and entity.'
    obs['target']['evidence'] = 'Completely different evidence prose.'
    obs['requirements'][0].update(id='new_identifier', source_quote='Modify another subject',
                                  question='A differently worded question?', evidence='Different objects and colors.')
    assert summarize(original) == summarize(renamed)
    assert fitted().predict_records([original]) == fitted().predict_records([renamed])


def test_extra_complete_constraints_and_duplicate_checks_cannot_act_as_case_signatures():
    original = record(); changed = deepcopy(original)
    r = changed['observations']['requirements'][0]
    changed['observations']['requirements'] += [
        {**r, 'id': 'constraint', 'question': 'An already satisfied qualifier?', 'role': 'constraint', 'state': 'complete'},
        {**r, 'id': 'duplicate', 'question': 'Another equivalent wording?'},
    ]
    assert summarize(original) == summarize(changed)


@pytest.mark.parametrize('name', ['case_id', 'reference', 'human_score', 'task', 'editing_model'])
def test_metadata_is_rejected_at_the_policy_input_boundary(name):
    value = record(); value[name] = 'forbidden'
    with pytest.raises(ValueError): summarize(value)


def test_improving_fulfillment_or_preservation_never_worsens_label_over_entire_domain():
    tree = fitted().metadata()['tree']
    for before in DOMAIN:
        for after in DOMAIN:
            if all(before[k] <= after[k] for k in FEATURES):
                assert ('partial', 'yes').index(decide(tree, before)) <= ('partial', 'yes').index(decide(tree, after))
    assert fitted().predict([record('complete')]) == [2.]


def test_wrong_target_and_unknown_evidence_are_not_relaxed_to_fit_labels():
    wrong = record('complete'); wrong['observations']['target']['state'] = 'wrong_target'
    values = fitted().predict_records([wrong, record('unknown')])
    assert values[0]['label'] == 'no' and values[0]['guard'] == 'fixed_no'
    assert values[1]['label'] is None and values[1]['guard'] == 'unresolved'


def test_conflicting_anonymous_cases_are_reported_instead_of_memorized():
    rows = [record('complete'), record('complete')]
    model = LocalEvidenceRuleCalibrator().fit(rows, [1, 2], source_groups=['source1', 'source2'])
    assert model.predict(rows) == [2., 2.]
    conflicts = feature_conflicts(rows, [1, 2])
    assert conflicts['feature_only_fitting_ceiling'] == 1
    assert conflicts['identical_feature_conflicts'][0]['target_counts'] == {'partial': 1, 'yes': 1}


def test_source_duplicates_and_singleton_training_are_rejected():
    with pytest.raises(ValueError): LocalEvidenceRuleCalibrator().fit([record(), record()], [1, 2], source_groups=['same', 'same'])
    with pytest.raises(ValueError): LocalEvidenceRuleCalibrator().fit([record()], [2], source_groups=['only'])


def test_portable_artifact_and_case_order_do_not_change_executable_policy():
    model = fitted(); restored = LocalEvidenceRuleCalibrator.restore(json.loads(json.dumps(model.metadata())))
    assert restored.predict_records([record(), record('absent')]) == model.predict_records([record(), record('absent')])
    rows = [record(), record(), record(integrity='material_deviation'), record(integrity='material_deviation')]
    a = LocalEvidenceRuleCalibrator().fit(rows, [2, 2, 1, 1], source_groups=list('abcd'))
    b = LocalEvidenceRuleCalibrator().fit(rows[::-1], [1, 1, 2, 2], source_groups=list('dcba'))
    assert a.metadata()['tree'] == b.metadata()['tree']


@pytest.mark.parametrize('tree', [
    {'predicate': 'exact_instruction', 'when_true': {'label': 'yes'}, 'when_false': {'label': 'partial'}},
    {'label': 'no'},
    {'predicate': 'source_preserved', 'when_true': {'label': 'yes'}, 'when_false': {'label': 'partial'}, 'case_id': 'F01'},
])
def test_case_specific_or_unsupported_executable_rules_are_rejected(tree):
    with pytest.raises(ValueError): validate_tree(tree)


def test_nonmonotone_artifact_is_rejected():
    artifact = fitted().metadata()
    artifact['tree'] = {'predicate': 'every_core_complete', 'when_true': {'label': 'partial'}, 'when_false': {'label': 'yes'}}
    with pytest.raises(ValueError): LocalEvidenceRuleCalibrator.restore(artifact)
