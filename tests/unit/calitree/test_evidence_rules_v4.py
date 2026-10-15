"""Objective regression: accuracy must not win by abandoning a class. No APIs."""
from copy import deepcopy
from fractions import Fraction
import json

import pytest

from critical.core.calibration.evidence_rules_v4 import (
    ClassBalancedEvidenceRuleCalibrator, VERSION, classification_metrics, objective_rank,
)
from critical.core.decision.rich_evidence import COLLATERAL_FIELDS


def record(constraint='complete'):
    instruction = 'Change the object with the requested relation'
    return {'instruction': instruction, 'observations': {
        'instruction_scope': 'The intended object and requested relation.',
        'target': {'state': 'matched', 'evidence': 'Intended target visible.'},
        'source_integrity': {'state': 'preserved', 'evidence': 'Same source meaning.'},
        'requirements': [
            {'id':'c','source_quote':'Change the object','question':'Is the core change present?',
             'role':'core','state':'complete','evidence':'Visible core fulfillment.'},
            {'id':'q','source_quote':'the requested relation','question':'Is the relation realized?',
             'role':'constraint','state':constraint,'evidence':'Visible relation evidence.'}],
        'collateral': {k:{'state':'none','evidence':'No collateral change.'} for k in COLLATERAL_FIELDS},
        'verification_visibility': {'state':'full','evidence':'Required content visible.'},
    }}


@pytest.fixture(scope='module')
def fitted():
    X = [record(s) for s in ('absent','absent','incomplete','incomplete','complete','complete')]
    return ClassBalancedEvidenceRuleCalibrator().fit(X,[0,0,1,1,2,2],source_groups=list('abcdef'))


def test_higher_accuracy_class_collapse_cannot_win():
    y = [0]*12+[1]*12+[2]*12
    collapsed = [0]*12+[0]*8+[2]*4+[2]*10+[0]*2
    balanced = [0]*5+[1]*4+[2]*2+[-1] + [0]+[1]*5+[2]*3+[-1]*3 + [2]*10+[1]+[-1]
    bad_rank, bad = objective_rank(collapsed,y)
    good_rank, good = objective_rank(balanced,y)
    assert bad['correct'] == 22 and good['correct'] == 20
    assert bad['per_class']['partial']['correct'] == 0 and bad_rank is None
    assert good_rank is not None and good['macro_f1'] > bad['macro_f1']


def test_unknowns_count_as_false_negatives_and_are_not_dropped():
    m, exact, worst = classification_metrics([0,0,1,-1,2,2],[0,0,1,1,2,2])
    assert exact == Fraction(8,9) and worst == Fraction(1,2)
    assert m['total'] == 6 and m['unresolved'] == 1 and m['per_class']['partial']['support'] == 2
    assert m['per_class']['partial']['f1'] == pytest.approx(2/3)


def test_objective_prioritizes_macro_f1_then_worst_recall_before_simplicity():
    a, m = objective_rank([0,0,1,1,2,2],[0,0,1,1,2,2],splits=3,departures=5)
    b, _ = objective_rank([0,0,1,1,2,2],[0,0,1,1,2,2],splits=2,departures=100)
    assert a[:3] == (Fraction(1),Fraction(1),6) and b > a
    assert m['macro_f1'] == 1.


def test_fit_recognizes_all_three_classes_with_source_support(fitted):
    assert fitted.predict([record('absent'),record('incomplete'),record('complete')]) == [0.,1.,2.]
    metadata = fitted.metadata()
    assert metadata['version'] == VERSION
    assert all(v['correct'] >= 2 for v in metadata['training_metrics']['per_class'].values())
    assert min(metadata['leaf_support'].values()) >= 2


def test_no_collapsed_fallback_if_coverage_is_impossible():
    with pytest.raises(ValueError,match='refusing a collapsed fallback'):
        ClassBalancedEvidenceRuleCalibrator().fit([record() for _ in range(6)],[0,0,1,1,2,2],source_groups=list('abcdef'))


def test_uncertainty_semantics_are_unchanged(fitted):
    value = record(); value['observations']['collateral']['entity_loss']['state'] = 'unknown'
    assert fitted.predict_records([value])[0]['label'] == 'yes'
    value = record('unknown')
    assert fitted.predict_records([value])[0]['label'] is None


def test_artifact_roundtrip_and_class_collapse_rejection(fitted):
    artifact = json.loads(json.dumps(fitted.metadata()))
    restored = ClassBalancedEvidenceRuleCalibrator.restore(artifact)
    assert restored.predict_records([record()]) == fitted.predict_records([record()])
    assert restored.predict_records([record()])[0]['version'] == VERSION
    artifact['training_metrics']['per_class']['partial']['correct'] = 0
    with pytest.raises(ValueError): ClassBalancedEvidenceRuleCalibrator.restore(artifact)


def test_metadata_and_text_cannot_be_predicates(fitted):
    a=record();b=deepcopy(a);b['instruction']='Anonymous request'
    for i,q in enumerate(b['observations']['requirements']):q.update(id=str(i),source_quote=b['instruction'],question='Check '+str(i),evidence='Other words')
    assert fitted.predict_records([a]) == fitted.predict_records([b])
    b['reference']='yes'
    with pytest.raises(ValueError): fitted.predict_records([b])


@pytest.mark.parametrize('y', [[0,0,1,1,2],[0,0,0,1,1,1]])
def test_training_requires_two_sources_per_reference_class(y):
    with pytest.raises(ValueError): ClassBalancedEvidenceRuleCalibrator().fit([record() for _ in y],y,source_groups=list(range(len(y))))
