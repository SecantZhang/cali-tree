from copy import deepcopy

import pytest

from critical.core.calibration import semantic_region_merge_v28 as merging
from critical.core.calibration import evidence_support_v21 as support, counterexample_coverage_v23 as rejection
from tests.unit.calitree.test_semantic_regions_v26 import fixture as old_fixture


def fixture():
    rows, programs, old_core, original = old_fixture()
    core = merging.shared.evidence.EvidenceCoverageGate(old_core.artifact['previous_gate']['base_gate'])
    used = set().union(*(set(ex.artifact['predicate_descriptions']) for ex in core.experts.values()))
    used.update(c['feature'] for rule in core.artifact['rules'] for c in rule['guards'])
    features = [f for f in support.SEMANTIC if f not in used][:2]
    for i,row in enumerate(rows):
        for f in features:
            row['features']['features'][f] = bool((i//3)%2)
    # Give each correct expert an explicit supported rule for every label so
    # contributor links are genuine, rather than unused metadata.
    artifact = core.export(); existing = {(r['expert_ref'],r['expert_prediction']) for r in artifact['rules']}
    for expert in sorted(core.experts):
        for label in range(3):
            if (expert,label) not in existing:
                source = next(r for r in artifact['rules'] if r['expert_prediction']==label)
                extra = deepcopy(source);extra['expert_ref']=expert;artifact['rules'].append(extra)
    artifact['artifact_ref']=merging.digest({k:v for k,v in artifact.items() if k!='artifact_ref'})
    core=merging.shared.evidence.EvidenceCoverageGate(artifact)
    semantic = support.build(core, rows, programs)
    examples = [{'program':programs[r['source_group']], 'features':r['features'], 'reference':r['reference']} for r in rows]
    previous, _ = rejection.fit(semantic, examples, [])
    v26 = merging.shared.old.build(previous, rows, programs)
    gate, _ = merging.shared.build(v26, rows, programs)
    bank = merging.definitions(gate); chosen = next(ref for ref,r in bank.items() if r['prediction']==0)
    template = bank.pop(chosen); expert_refs = sorted(core.experts)
    assert len(expert_refs)==2
    for truth,expert in zip((False,True),expert_refs):
        region = deepcopy(template);region['experts']={expert};region['term'] |= frozenset((f,truth) for f in features)
        bank[str(truth)]=region
    local_probes=merging.prepared(gate,examples)
    baseline=merging.pack(gate,bank,rows,programs,local_probes).executor
    novel=deepcopy(next(e for e in examples if e['reference']==0))
    novel['features']['features'][features[0]]=True;novel['features']['features'][features[1]]=False
    assert baseline.previous.select(novel['program'],novel['features'])['covered']
    assert not baseline.select(novel['program'],novel['features'])['covered']
    return baseline,rows,programs,examples,novel


def test_similarity_requires_more_than_matching_label():
    a={'prediction':1,'term':frozenset({('meaning_available',True)}),'tasks':{'s'},'experts':{'A'}}
    b={**a,'experts':{'B'}}
    assert merging.pair_candidates({'a':a,'b':b},merging.Config())==[]
    a['term']=frozenset({('meaning_progress_requested_endpoint_all',True)})
    b={**a,'experts':{'B'}}
    assert len(merging.pair_candidates({'a':a,'b':b},merging.Config()))==1
    for changed in ({**b,'tasks':{'other'}},{**b,'prediction':2},{**b,'experts':{'A'}}):
        assert not merging.pair_candidates({'a':a,'b':changed},merging.Config())


def test_cross_expert_merge_can_broaden_regions_without_local_regression():
    baseline,rows,programs,examples,novel=fixture()
    gate,report=merging.develop(baseline,rows,programs,examples,config=merging.Config(max_rounds=2))
    assert len(report['accepted'])==1
    assert report['before']['regions']==4 and report['after']['regions']==3
    assert report['after']['cross_expert_regions']==report['before']['cross_expert_regions']+1
    assert report['baseline_boolean_coverage_retained'] and report['boolean_regions_broadened']
    assert gate.select(novel['program'],novel['features'])['covered']
    for row in rows:
        assert gate.select(programs[row['source_group']],row['features'])['prediction']==row['reference']
    assert all(v['sources']==v['retained'] for v in report['accepted'][0]['child_retention'])
    assert gate.executor.artifact['core_gate']==baseline.artifact['core_gate']


def test_known_deferred_probe_blocks_a_similar_and_locally_accurate_merge():
    baseline,rows,programs,examples,novel=fixture()
    gate,report=merging.develop(baseline,rows,programs,examples+[novel],config=merging.Config(max_rounds=2))
    assert not report['accepted']
    assert any('routing_regression' in t['reasons'] for t in report['trials'])
    assert not gate.select(novel['program'],novel['features'])['covered']
    assert report['after']['regions']==report['before']['regions']


def test_reference_labels_and_case_names_in_regression_probes_are_ignored():
    baseline,rows,programs,examples,novel=fixture()
    a,report=merging.develop(baseline,rows,programs,examples+[novel])
    changed=[{**e,'reference':99,'case':'unrelated'} for e in examples+[novel]]
    b,other=merging.develop(baseline,list(reversed(rows)),programs,changed)
    assert a.export()==b.export() and report==other


def test_support_is_deduplicated_and_serialized_runtime_preserves_veto(monkeypatch):
    baseline,rows,programs,examples,_=fixture();gate,_=merging.develop(baseline,rows,programs,examples)
    restored=merging.SemanticMergedRegionGate(gate.export())
    for ref,r in restored.executor.regions.items():
        selected=[row for row in rows if ref in restored.select(programs[row['source_group']],row['features'])['semantic_regions']]
        assert r['support']['sources']==len({row['source_group'] for row in selected})
    veto={'covered':False,'prediction':-1,'reason':'conflicting_supported_experts','matches':[]}
    monkeypatch.setattr(restored.executor.previous,'select',lambda *args:veto)
    assert restored.select(examples[0]['program'],examples[0]['features'])['reason']==veto['reason']
    assert not restored.shortlist(examples[0]['program'])['decision_ready']
    damaged=gate.export();damaged['contract_ref']='wrong'
    with pytest.raises(ValueError):merging.SemanticMergedRegionGate(damaged)


def test_duplicate_proposed_definitions_pack_once():
    baseline,rows,programs,examples,_=fixture();bank=merging.definitions(baseline)
    bank['duplicate']=deepcopy(next(iter(bank.values())))
    gate=merging.pack(baseline,bank,rows,programs,merging.prepared(baseline,examples))
    assert len(gate.executor.regions)==len(bank)-1


@pytest.mark.parametrize('settings',[{'max_rounds':0},{'max_candidates_per_round':0},{'min_literal_similarity':1.1},{'min_literal_similarity':True}])
def test_invalid_search_settings_rejected(settings):
    with pytest.raises(ValueError):merging.Config(**settings)


def test_unrelated_core_expert_cannot_authorize_a_merged_region(monkeypatch):
    baseline,rows,programs,examples,_=fixture();gate,_=merging.develop(baseline,rows,programs,examples)
    e=examples[0];route=gate.executor.previous.select(e['program'],e['features'])
    assert route['covered']
    alien=deepcopy(route)
    for match in alien['matches']:match['expert_ref']='unrelated-expert'
    monkeypatch.setattr(gate.executor.previous,'select',lambda *args:alien)
    result=gate.select(e['program'],e['features'])
    assert not result['covered'] and result['reason']=='outside_semantic_rule_regions'
