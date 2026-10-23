from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from itertools import product

import pytest

from critical.core.calibration import shared_tree_fit_v24 as fit
from critical.core.calibration import pairwise_merge_v24 as merge
from critical.core.calibration import evidence_coverage_v20 as coverage, evidence_support_v21 as support
from critical.core.calibration import counterexample_coverage_v23 as rejection
from critical.core.decision.artifacts import digest
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import synthetic_record
from tests.unit.calitree.test_regularized_tree_v13 import rows
from tests.unit.calitree.test_task_coverage import program
from tests.unit.calitree.test_local_compression_v18 import fitted


NAMES = ['meaning_identity_evidence_same_instance_all', 'meaning_identity_materiality_no_shortfall_all',
         'meaning_collateral_materiality_none_all', 'meaning_evidence_consistency_coherent_all']


def sharing_fixture():
    patterns = [(1,0,0,0), (0,1,0,1), (1,0,1,0), (1,1,1,1), (1,1,0,1), (0,0,1,1), (0,1,1,0), (1,0,1,1)]
    labels = [1,1,0,1,1,1,1,0]; batches = [1,1,0,1,0,0,1,1,1,1,0,0,0,1,1,1]; data = []
    for pattern, label in zip(patterns, labels):
        for _ in range(2):
            i = len(data)
            data.append({'case': str(i), 'source_group': str(i), 'instruction': f'task {i}', 'reference': label,
                         'batch': str(batches[i]), 'features': synthetic_record(meaning_available=True, **dict(zip(NAMES, map(bool, pattern))))})
    return data


def test_sharing_preference_changes_search_without_spending_accuracy_or_rules():
    data = sharing_fixture(); req = [{'sources': [r['source_group'] for r in data], 'correct': 16}]
    cfg = fit.Config(max_depth=4, max_states=10000)
    control, _ = fit.fit(data, req, max_rules=8, config=replace(cfg, prefer_shared=False))
    parent, report = fit.fit(data, req, max_rules=8, config=cfg)
    assert control['metrics']['correct'] == parent['metrics']['correct'] == 16
    assert control['complexity']['rules'] == parent['complexity']['rules'] == 4
    assert control['sharing']['shared_correct'] == 12 and parent['sharing']['shared_correct'] == 14
    assert report['selected_shared_correct'] == 14


def test_shared_objective_matches_exhaustive_small_tree_enumeration():
    data = sharing_fixture()
    @lru_cache(None)
    def enumerate_scores(indices, depth):
        selected = [data[i] for i in indices]; counts = [sum(r['reference'] == k for r in selected) for k in range(3)]
        label = max(range(3), key=lambda k: (counts[k], -k))
        batches = [sum(r['reference'] == label and r['batch'] == b for r in selected) for b in ('0','1')]
        correct = max(counts); shared = correct if all(batches) else 0; balance = correct - max(batches)
        found = {(len(selected)-correct, 1, shared, balance, 0)}
        if depth:
            for name in NAMES:
                a, b = [tuple(i for i in indices if data[i]['features']['features'][name] == value) for value in (True,False)]
                if min(len(a),len(b)) < 2:
                    continue
                for left,right in product(enumerate_scores(a,depth-1),enumerate_scores(b,depth-1)):
                    found.add(tuple(left[k]+right[k] for k in range(4)) + (1+max(left[4],right[4]),))
        return found
    options = [s for s in enumerate_scores(tuple(range(len(data))),4) if s[0] == 0 and s[1] <= 8]
    optimum = min(options, key=lambda s:(s[0],s[1],-s[2],-s[3],s[4]))
    parent,_ = fit.fit(data,[{'sources':[r['source_group'] for r in data],'correct':16}],max_rules=8,config=fit.Config(max_depth=4))
    assert (0,parent['complexity']['rules'],parent['sharing']['shared_correct'],parent['sharing']['cross_batch_support'],parent['complexity']['depth']) == optimum


def test_wrong_examples_from_other_batches_do_not_count_as_shared_support():
    data = rows(8)
    for i,r in enumerate(data):
        r['reference'] = 0 if i < 4 else 1; r['batch'] = 'A' if i < 4 else 'B'
    constant = fitted(data[:4]); measured = fit.sharing(constant,data)
    assert measured['shared_correct'] == measured['cross_batch_support'] == measured['shared_rules'] == 0


def system_fixture():
    data = rows(24)
    for i,r in enumerate(data):
        r['batch'] = 'A' if i < 12 else 'B'
    programs = {r['source_group']:program(r['instruction']) for r in data}; models=[]
    for cohort,quantifier in ((data[:12],'all'),(data[12:],'any')):
        model,_ = fit.fit(cohort,[{'sources':[r['source_group'] for r in cohort],'correct':12}],max_rules=4,
                          config=fit.Config(max_depth=3,quantifier=quantifier))
        model['fit_sources'] = model['policy']['training']['source_groups']; models.append(model)
    assert models[0]['runtime']['artifact_ref'] != models[1]['runtime']['artifact_ref']
    core,_ = coverage.build(models,data,programs)
    # Ensure both correct expert functions participate in this starting gate,
    # even if the coverage set cover happens to choose only one of them.
    artifact = core.export()
    for model in models:
        ref=model['runtime']['artifact_ref']
        if ref not in artifact['experts']:
            artifact['experts'][ref]=model['runtime'];r=deepcopy(artifact['rules'][0]);r['expert_ref']=ref;artifact['rules'].append(r)
    artifact['artifact_ref']=digest({k:v for k,v in artifact.items() if k!='artifact_ref'})
    core=coverage.EvidenceCoverageGate(artifact); semantic=support.build(core,data,programs)
    examples=[{'case':r['case'],'program':programs[r['source_group']],'features':r['features'],'reference':r['reference']} for r in data]
    gate,_=rejection.fit(semantic,examples,[])
    return data,programs,models,examples,gate


def test_pairwise_merge_rebuilds_gate_and_preserves_all_local_routes():
    data,programs,models,probes,gate=system_fixture()
    result=merge.develop(models,data,programs,gate,probes,config=merge.Config(max_rounds=1),fit_config=fit.Config(max_depth=3))
    assert len(result['accepted'])==1
    assert result['initial_complexity']['experts']==2 and result['final_complexity']['experts']==1
    assert result['initial_complexity']['terminal_rules']==6 and result['final_complexity']['terminal_rules']==3
    assert result['accepted'][0]['sharing']['shared_correct']==24
    assert result['final_routing_check']['passed']
    assert result['gate']['support_clauses']==gate.artifact['support_clauses']
    parent=result['accepted'][0]['parent'];retention=parent['pairwise_lineage']['child_retention']['retention']
    assert all(r['after']>=r['correct'] for r in retention)
    assert set(parent['policy']['training']['source_groups'])=={r['source_group'] for r in data}
    assert result['work']['gate_rebuilds'] > 0


def test_routing_regression_rejects_an_accurate_compact_parent(monkeypatch):
    data,programs,models,probes,gate=system_fixture();original=merge.rebuild_gate
    def broken_rebuild(*args,**kwargs):
        rebuilt,report=original(*args,**kwargs);a=rebuilt.export();semantic=a['previous_gate']
        for rule in semantic['base_gate']['rules']:
            if rule['expert_prediction']==0:
                conditions=semantic['envelopes'][digest(rule)]['conditions']
                for condition in conditions:
                    if condition['feature']=='meaning_progress_requested_endpoint_all':condition['value']=True
        semantic['artifact_ref']=digest({k:v for k,v in semantic.items() if k!='artifact_ref'})
        a['artifact_ref']=digest({k:v for k,v in a.items() if k!='artifact_ref'})
        return rejection.RejectionCoverageGate(a),report
    monkeypatch.setattr(merge,'rebuild_gate',broken_rebuild)
    result=merge.develop(models,data,programs,gate,probes,config=merge.Config(max_rounds=1),fit_config=fit.Config(max_depth=3))
    assert not result['accepted'] and result['gate']==gate.export()
    assert any('routing_regression' in t.get('reasons',[]) for t in result['trials'])


@pytest.mark.parametrize('before,after,reason',[(False,True,'new_unvalidated_acceptance'),(True,False,'lost_protected_coverage')])
def test_routing_gate_checks_coverage_not_just_final_accuracy(before,after,reason):
    class Gate:
        def __init__(self,covered):self.covered=covered
        def select(self,p,r):return {'covered':self.covered,'prediction':0 if self.covered else -1}
    result=merge.routing_regressions(Gate(before),Gate(after),[{'case':'probe','program':{},'features':None}])
    assert not result['passed'] and result['failures'][0]['regression']==reason


def test_overlapping_child_scopes_are_deduplicated_and_batch_floors_retained():
    data,_,models,_,_=system_fixture()
    larger=fitted(data);larger['fit_sources']=larger['policy']['training']['source_groups']
    reqs=merge.requirements([models[0],larger],data)
    assert len({tuple(r['sources']) for r in reqs})==len(reqs)
    assert any(len(r['sources'])==24 and r['correct']==24 for r in reqs)
    assert sum(len(r['sources'])==12 and r['correct']==12 for r in reqs)==2


def test_exhausted_fit_does_not_drop_existing_experts():
    data,programs,models,probes,gate=system_fixture()
    result=merge.develop(models,data,programs,gate,probes,config=merge.Config(max_rounds=1),fit_config=fit.Config(max_states=1))
    assert not result['accepted'] and result['gate']==gate.export()


def test_merge_abstention_support_uses_prior_routes_not_reference_labels():
    data,programs,models,probes,candidate=system_fixture()
    name='intermediate_contact_unknown_all'
    class Prior:
        def select(self,p,record):
            if record['features'][name]:
                return {'covered':False,'prediction':-1,'reason':'old_disagreement','matches':[]}
            return candidate.select(p,record)
    extra=deepcopy(probes[0]);extra['case']='newly-accepted';extra['features']['features'][name]=True
    checks=probes+[extra]
    preserved,report=merge.route_support.preserve_routes(Prior(),candidate,checks)
    assert report['status']=='preserved_with_compact_clauses' and report['human_reference_labels_used'] is False
    assert len(preserved.artifact['clauses'])==1
    assert preserved.artifact['core_gate']['support_clauses']==candidate.artifact['support_clauses']
    assert not preserved.select(extra['program'],extra['features'])['covered']
    assert all(preserved.select(p['program'],p['features'])['covered'] for p in probes)
    changed=deepcopy(checks)
    for p in changed:p['reference']=(p['reference']+1)%3;p['case']='renamed'
    again,_=merge.route_support.preserve_routes(Prior(),candidate,list(reversed(changed)))
    assert again.export()==preserved.export()
    restored=merge.route_support.restore(preserved.export())
    assert restored.select(extra['program'],extra['features'])==preserved.select(extra['program'],extra['features'])
    assert merge.complexity(preserved)['stored_conditions']==merge.complexity(candidate)['stored_conditions']+1


def test_abstention_support_cannot_repair_lost_local_coverage():
    _,_,_,probes,candidate=system_fixture()
    class Missing:
        def select(self,p,r):return {'covered':False,'prediction':-1}
    fixed,report=merge.route_support.preserve_routes(candidate,Missing(),probes)
    assert fixed is None and report['status']=='cannot_repair_lost_coverage_or_verdict'


def test_equally_compact_proposals_prefer_correct_batch_sharing_before_storage_ties():
    shared={'sharing':{'shared_correct':17,'cross_batch_support':6},'runtime':{'artifact_ref':'a'}}
    less_shared={'sharing':{'shared_correct':15,'cross_batch_support':5},'runtime':{'artifact_ref':'b'}}
    a={'experts':3,'terminal_rules':19,'stored_conditions':442}
    b={'experts':3,'terminal_rules':19,'stored_conditions':394}
    assert merge.proposal_rank(shared,a)<merge.proposal_rank(less_shared,b)
    # A real terminal-rule reduction still takes precedence over sharing ties.
    assert merge.proposal_rank(less_shared,{**b,'terminal_rules':18})<merge.proposal_rank(shared,a)
