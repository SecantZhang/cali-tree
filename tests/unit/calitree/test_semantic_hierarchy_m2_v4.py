from copy import deepcopy
import json

import pytest

from critical.core.calibration.semantic_hierarchy.features_v4 import project, FEATURES, synthetic_record, validate_record
from critical.core.calibration.semantic_hierarchy.conflict_tree_v4 import ConflictAwareSemanticTree, LIMITS, conflict_report
from critical.core.decision.artifacts import digest
from critical.core.decision.bound_evidence_v2 import bind_program
from tests.unit.calitree.test_bound_evidence_v2 import draft
from tests.unit.calitree.test_bound_evidence import observation


def samples(n=12):
    X, y = [], []
    for i in range(n):
        label = i % 3
        X.append(synthetic_record(outcome_all_true_any=label > 0, outcome_all_true_all=label == 2,
                                  identity_all_false_all=True, identity_all_unknown_any=label == 2))
        y.append(label)
    return X, y, [f'source-{i:03}' for i in range(n)], ['old-group-'+str(i//12) for i in range(n)]


def fit(data, **kwargs):
    X,y,s,b=data
    return ConflictAwareSemanticTree(**kwargs).fit(X,y,source_groups=s,source_batches=b)


@pytest.mark.parametrize('n',[12,24,48,96])
def test_scaling_fits_restores_and_keeps_all_labels(n):
    d=samples(n);m=fit(d)
    assert [r['prediction'] for r in m.predict_records(d[0])]==d[1]
    restored=ConflictAwareSemanticTree.restore(json.loads(json.dumps(m.metadata())))
    assert restored.predict_records(d[0])==m.predict_records(d[0])


def test_identity_failure_and_unknown_are_not_mandatory_yes_vetoes():
    d=samples();m=fit(d)
    yes=d[0][2]
    assert yes['features']['identity_all_false_all'] and yes['features']['identity_all_unknown_any']
    assert m.predict_records([yes])[0]['prediction']==2


def test_counts_and_majorities_distinguish_old_any_all_collision():
    def example(states):
        d=draft()
        for i in range(1,len(states)):
            c=deepcopy(d['checks'][0]);c['id']='endpoint'+str(i);d['checks'].append(c)
        p=bind_program('Move the bowl left',d)
        values={'endpoint' if i==0 else 'endpoint'+str(i):s for i,s in enumerate(states)}
        return project(p,observation(p,**values),'pair')
    a=example(['true','false']);b=example(['true','true','false'])
    for key in ('outcome_spatial_relation_true_any','outcome_spatial_relation_true_all'):
        assert a['features'][key]==b['features'][key]
    assert not a['features']['outcome_spatial_relation_true_majority']
    assert b['features']['outcome_spatial_relation_true_majority']


def test_projection_keeps_unknown_distinct_and_rejects_misbound_observation():
    p=bind_program('Move the bowl left',draft());o=observation(p,endpoint='unknown')
    f=project(p,o,'pair')['features']
    assert f['outcome_all_unknown_all'] and not f['outcome_all_false_any']
    with pytest.raises(ValueError):project(p,o,'wrong-pair')
    o['checks']['endpoint']['question']='Another physical question'
    with pytest.raises(ValueError):project(p,o,'pair')


def test_projection_invariant_to_names_and_check_order():
    a=bind_program('Move the bowl left',draft());d=draft('Move the vase left');d['checks'].reverse()
    b=bind_program('Move the vase left',d)
    assert project(a,observation(a),'pair')==project(b,observation(b),'pair')
    assert 'vase' not in json.dumps(project(b,observation(b),'pair'))


def test_empty_family_never_becomes_all_true_and_negative_polarity_is_respected():
    p=bind_program('Move the bowl left',draft());x=project(p,observation(p),'pair')
    assert not x['features']['outcome_style_true_all']
    assert x['features']['collateral_disappearance_all_true_all']


def test_exact_conflicts_report_an_unattainable_target_without_relabeling():
    x=synthetic_record();rows=[x,x,None];targets=[0,1,2]
    report=conflict_report(rows,targets,['a','b','c'])
    assert len(report['exact_conflicts'])==1
    assert report['feature_identifiability_upper_bound']==1 and report['missing_sources']==['c']
    assert targets==[0,1,2]
    m=ConflictAwareSemanticTree().fit(rows,targets,source_groups=['a','b','c'],source_batches=['g']*3)
    assert m.metadata()['training']['metrics']['correct']==1
    assert m.predict_records([x])[0]['conflicted_leaf']


def test_missing_case_is_retained_and_never_receives_a_label():
    X,y,s,b=samples();X[0]=None;m=fit((X,y,s,b))
    metric=m.metadata()['training']['metrics']
    assert metric['total']==12 and metric['correct']==11 and metric['unresolved']==1
    assert m.predict_records([None])[0]['group_id'] is None


def test_source_duplicates_and_prediction_label_inputs_are_rejected():
    X,y,s,b=samples()
    with pytest.raises(ValueError):fit((X,y,['same']*12,b))
    bad=deepcopy(X[0]);bad['reference']=2
    with pytest.raises(ValueError):validate_record(bad)
    bad=deepcopy(X[0]);bad['features']['case_id']=True
    with pytest.raises(ValueError):validate_record(bad)


def test_tree_and_groups_do_not_depend_on_original_batch_or_row_order():
    X,y,s,b=samples(24);a=fit((X,y,s,b));z=fit((X[::-1],y[::-1],s[::-1],b[::-1]))
    assert a.metadata()==z.metadata()
    other=fit((X,y,s,['different']*24))
    assert a.predict_records(X)==other.predict_records(X)
    assert [g['conditions'] for g in a.metadata()['groups']]==[g['conditions'] for g in other.metadata()['groups']]


def test_every_terminal_rule_has_multiple_sources_and_closed_predicates():
    m=fit(samples(24));a=m.metadata()
    def visit(node):
        if node['type']=='leaf':assert node['support']>=2 and len(set(node['source_groups']))==node['support']
        else:
            assert node['feature'] in FEATURES
            visit(node['true']);visit(node['false'])
    visit(a['tree'])
    all_sources=[s for g in a['groups'] for s in g['source_groups']]
    assert len(all_sources)==len(set(all_sources))==24


def test_restore_rejects_tampering_and_rehashed_case_predicates():
    a=fit(samples()).metadata();a['tree']['feature']='case_id'
    with pytest.raises(ValueError):ConflictAwareSemanticTree.restore(a)
    a['artifact_ref']=digest({k:v for k,v in a.items() if k!='artifact_ref'})
    with pytest.raises(ValueError,match='Non-semantic'):ConflictAwareSemanticTree.restore(a)


def test_single_class_group_is_allowed_and_absent_recall_is_explicit():
    x=[synthetic_record()]*4
    m=ConflictAwareSemanticTree().fit(x,[1]*4,source_groups=list('abcd'),source_batches=['g']*4)
    metric=m.metadata()['groups'][0]['metrics']
    assert metric['correct']==4 and metric['per_class']['yes']['recall'] is None


def test_search_budget_is_reported_instead_of_claiming_optimality():
    m=fit(samples(24),limits={**LIMITS,'max_search_states':1})
    assert m.metadata()['search']['budget_exhausted']
    assert not m.metadata()['search']['global_optimality_claim']
