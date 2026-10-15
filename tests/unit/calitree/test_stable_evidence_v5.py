from copy import deepcopy

import pytest

from critical.core.calibration.semantic_hierarchy.stable_features_v5 import project, project_with_audit, as_base
from critical.core.decision.bound_evidence_v2 import bind_program
from tests.unit.calitree.test_bound_evidence_v2 import draft
from tests.unit.calitree.test_bound_evidence import observation


def duplicate(program,value,check_id,*,different_state=None):
    d={k:deepcopy(program[k]) for k in ('contract','requirements','checks')}
    for r in d['requirements']:r.pop('check_ids')
    for c in d['checks']:c.pop('check_ref')
    extra=deepcopy(next(c for c in d['checks'] if c['id']==check_id));extra['id']='duplicate_check'
    d['checks'].append(extra);p=bind_program(program['instruction'],d)
    v={'program_ref':p['program_ref'],'image_pair_ref':value['image_pair_ref'],'checks':{}}
    for c in p['checks']:
        row=deepcopy(value['checks'][check_id if c['id']=='duplicate_check' else c['id']])
        row.update(check_ref=c['check_ref'],question=c['question'])
        if c['id']=='duplicate_check' and different_state is not None:row['state']=different_state
        v['checks'][c['id']]=row
    return p,v


def rename_and_reverse(program,value):
    d={k:deepcopy(program[k]) for k in ('contract','requirements','checks')}
    mapping={c['id']:'c'+str(i) for i,c in enumerate(d['checks'])}
    requirements={r['id']:'r'+str(i) for i,r in enumerate(d['requirements'])}
    for r in d['requirements']:
        r.pop('check_ids');r['id']=requirements[r['id']]
    for c in d['checks']:
        c.pop('check_ref');c['id']=mapping[c['id']]
        c['dependencies']=[mapping[k] for k in reversed(c['dependencies'])]
        c['requirement_ids']=[requirements[k] for k in reversed(c['requirement_ids'])]
    d['checks'].reverse();d['requirements'].reverse();p=bind_program(program['instruction'],d)
    inverse={v:k for k,v in mapping.items()};v={'program_ref':p['program_ref'],'image_pair_ref':value['image_pair_ref'],'checks':{}}
    for c in p['checks']:
        row=deepcopy(value['checks'][inverse[c['id']]]);row.update(check_ref=c['check_ref'],question=c['question']);v['checks'][c['id']]=row
    return p,v


def fixture():
    d=draft();c=deepcopy(d['checks'][0]);c.update(id='second',question='Is the requested spatial relationship established?')
    d['checks'].append(c);p=bind_program('Move the bowl left',d)
    return p,observation(p,endpoint='true',second='false')


def test_duplicate_success_does_not_flip_majority_or_any_feature():
    p,o=fixture();p2,o2=duplicate(p,o,'endpoint')
    before=project(p,o,'pair');after,audit=project_with_audit(p2,o2,'pair')
    assert before==after and audit['duplicates_removed']==1
    assert not after['features']['outcome_all_true_majority']


def test_check_and_requirement_ids_order_are_not_features():
    p,o=fixture();p2,o2=rename_and_reverse(p,o)
    assert project(p,o,'pair')==project(p2,o2,'pair')


def test_duplicate_disagreement_becomes_unknown_not_a_majority_vote():
    p,o=fixture();p2,o2=duplicate(p,o,'endpoint',different_state='false')
    x,audit=project_with_audit(p2,o2,'pair')
    assert audit['duplicate_conflicts'] and x['features']['outcome_all_unknown_any']
    assert not x['features']['outcome_all_true_any']


def test_different_targets_are_not_collapsed():
    p,o=fixture();p2,o2=duplicate(p,o,'endpoint')
    d={k:deepcopy(p2[k]) for k in ('contract','requirements','checks')}
    for r in d['requirements']:r.pop('check_ids')
    for c in d['checks']:
        c.pop('check_ref')
        if c['id']=='duplicate_check':c['target']='a distinct second target'
    p3=bind_program(p2['instruction'],d);v=observation(p3,second='false')
    _,audit=project_with_audit(p3,v,'pair')
    assert audit['duplicates_removed']==0


def test_missing_and_wrong_bindings_remain_explicit():
    assert project(None,None,'pair') is None and as_base(None) is None
    p,o=fixture()
    with pytest.raises(ValueError):project(p,o,'wrong-pair')


def test_dependency_ids_can_change_but_dependency_meaning_cannot():
    d=draft();c=deepcopy(d['checks'][0]);c.update(id='identity',role='identity',kind='identity')
    d['checks'].append(c);d['checks'][0]['dependencies']=['identity'];p=bind_program('Move the bowl left',d);o=observation(p)
    p2,o2=rename_and_reverse(p,o)
    assert project(p,o,'pair')==project(p2,o2,'pair')
