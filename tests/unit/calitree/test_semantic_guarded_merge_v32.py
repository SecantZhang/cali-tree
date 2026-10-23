from copy import deepcopy

import pytest

from critical.core.calibration import semantic_guarded_merge_v32 as fixed
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import synthetic_record
from tests.unit.calitree.test_task_coverage import program
from tests.unit.calitree.test_semantic_regions_v26 import fixture

A='meaning_progress_requested_endpoint_all'
B='meaning_collateral_materiality_none_all'


def values(**changes):
    result=dict.fromkeys(fixed.FEATURES,False);result.update(changes);return result


def protected():
    return [{'values':values(**{A:True}),'prediction':label,'reference':label}for label in(0,1,2)]


def test_verdict_conditioned_clause_rejects_error_without_rejecting_other_labels():
    errors=[{'values':values(),'prediction':2,'reference':0}]
    verifier=fixed.fit_verifier(protected(),errors)
    assert fixed.passes(verifier['clauses']['2'],values(**{A:True}))
    assert not fixed.passes(verifier['clauses']['2'],values())
    assert fixed.passes(verifier['clauses']['0'],values())


def test_two_literal_disjunction_retains_distinct_correct_semantic_contexts():
    positives=protected()+[{'values':values(**{B:True}),'prediction':2,'reference':2}]
    verifier=fixed.fit_verifier(positives,[{'values':values(),'prediction':2,'reference':0}])
    assert all(fixed.passes(verifier['clauses']['2'],e['values'])for e in positives if e['prediction']==2)
    assert not fixed.passes(verifier['clauses']['2'],values())
    assert any(len(c)==2 for c in verifier['clauses']['2'])


def test_inseparable_training_error_is_disclosed_not_given_a_case_exception():
    data=protected();error={**data[2],'reference':0}
    verifier=fixed.fit_verifier(data,[error])
    assert verifier['training_counts']['2']['unseparated_training_errors']==1
    assert fixed.passes(verifier['clauses']['2'],error['values'])
    assert 'case'not in str(verifier)


def test_scope_specific_proof_prevents_cross_product_of_legacy_semantic_exceptions():
    children=[{'prediction':2,'term':frozenset({(A,True),(B,True)}),'tasks':{'s'}},
              {'prediction':2,'term':frozenset({(A,False),(B,False)}),'tasks':{'s'}}]
    parent={'prediction':2,'term':frozenset(),'tasks':{'s'}}
    assert not fixed.preserve_obligations(children,parent)['passed']
    children[0]['tasks']={'s1'};children[1]['tasks']={'s2'};parent['tasks']={'s1','s2'}
    assert not fixed.preserve_obligations(children,parent)['passed']


def test_merge_may_relax_nonsemantic_details_while_retaining_goal_obligation():
    children=[{'prediction':2,'term':frozenset({(A,True),('preservation_all_true_all',True)}),'tasks':{'s'}},
              {'prediction':2,'term':frozenset({(A,True),('identity_all_true_all',True)}),'tasks':{'s'}}]
    parent={'prediction':2,'term':frozenset({(A,True)}),'tasks':{'s'}}
    assert fixed.preserve_obligations(children,parent)['passed']


def test_new_false_acceptance_is_rejected_even_when_regular_also_wrong():
    region={'prediction':2,'term':frozenset({(A,True)}),'tasks':{'s'},'experts':{'expert'}}
    verifier=fixed.fit_verifier(protected(),[])
    example={'scope':'s','values':values(**{A:True}),
             'core_route':{'covered':True,'prediction':2,'matches':[{'expert_ref':'expert'}]},
             'baseline':{'covered':False,'prediction':-1},'reference':0,'regular':1}
    result=fixed.check_bank({'parent':region},verifier,[example])
    assert not result['passed'] and result['failures'][0]['reason']=='new_false_acceptance'


def test_verified_gate_roundtrip_retains_local_routes_and_base_conflicts(monkeypatch):
    rows,programs,_,v26=fixture()
    from critical.core.calibration.shared_regions_v27 import build
    gate,_=build(v26,rows,programs);examples=[]
    for r in rows:
        examples.append({'prediction':r['reference'],'reference':r['reference'],
                         'values':fixed.shared.evidence.feature_values(programs[r['source_group']],r['features'])})
    verifier=fixed.fit_verifier(examples,[]);wrapped=fixed.VerifiedRegionGate(gate,verifier)
    restored=fixed.VerifiedRegionGate.restore(wrapped.export())
    for r in rows:
        route=restored.select(programs[r['source_group']],r['features'])
        assert route['covered']and route['prediction']==r['reference']
    veto={'covered':False,'prediction':-1,'reason':'conflicting_supported_experts','matches':[]}
    monkeypatch.setattr(restored.base,'select',lambda *args:veto)
    assert restored.select(program('new request'),synthetic_record(meaning_available=True))==veto
    artifact=wrapped.export();artifact['verifier']['clauses']['2']=[[{'feature':'case_id','value':True}]]
    with pytest.raises(ValueError):fixed.VerifiedRegionGate.restore(artifact)


def test_fit_order_invariance_and_incorrect_protection_rejected():
    data=protected();errors=[{'values':values(),'prediction':2,'reference':0}]
    assert fixed.fit_verifier(data,errors)==fixed.fit_verifier(list(reversed(data)),list(reversed(errors)))
    bad=deepcopy(data);bad[0]['reference']=2
    with pytest.raises(ValueError,match='Incorrect protected'):fixed.fit_verifier(bad,errors)
