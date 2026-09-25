"""Protocol checks for the focused challenger; no live provider calls."""
from types import SimpleNamespace
from run import focused_robust_repair as r
from run.robust_prompt_repair_pilot import load_cases


def test_block_penalty_prefers_consistent_candidate_and_keeps_incumbent_on_tie():
    bank={'gepa_baseline':'a', 'bursty':'b', 'consistent':'c'}
    dev={'gepa_baseline':[{'accuracy':x} for x in (.5,.5,.5)],
         'bursty':[{'accuracy':x} for x in (1.,.2,1.)],
         'consistent':[{'accuracy':x} for x in (.7,.7,.7)]}
    assert r.select(bank,dev)=='consistent'
    dev['consistent']=[{'accuracy':x} for x in (.5,.5,.5)]
    assert r.select(bank,dev)=='gepa_baseline'  # Bursty score 0.533 is below the 0.55 margin.


def test_confirmation_rejects_ties_and_weak_floor(monkeypatch):
    case=load_cases()[0]
    bank={'gepa_baseline':'baseline','challenge':'changed'}
    pilot=SimpleNamespace(config={'seed':44})
    def stub(*args,**kwargs):
        return {'gepa_baseline':[{'accuracy':.8}]*3,
                'challenge':[{'accuracy':.9}]*3}
    monkeypatch.setattr(r,'evaluate_blocks',stub)
    decision=r.confirm(pilot,case,bank,'challenge')
    assert decision['selected']=='challenge'
    monkeypatch.setattr(r,'evaluate_blocks',lambda *a,**k:{'gepa_baseline':[{'accuracy':1}]*3,
                                                             'challenge':[{'accuracy':1}]*3})
    assert r.confirm(pilot,case,bank,'challenge')['selected']=='gepa_baseline'
    assert r.confirm(pilot,case,bank,'gepa_baseline')['selected']=='gepa_baseline'


def test_final_shares_identical_prompts_and_measures_only_changed_case(tmp_path):
    import json
    from run.robust_prompt_repair_pilot import digest,save
    cases=load_cases()
    targets={c['case_id']:c['target_label'] for c in cases}
    prior=json.loads(r.PRIOR.read_text())
    bank={'C08':{'gepa_baseline':prior['C08']['single'],
                 'scene_seed':prior['C08']['single']+'\n'+r.SCENE_RULE},
          'C05':{'gepa_baseline':prior['C05']['single']}}
    decisions={'C08':{'candidate':'scene_seed','prompt_sha256':digest(bank['C08']['scene_seed'])},
               'C05':{'candidate':'gepa_baseline','prompt_sha256':digest(bank['C05']['gepa_baseline'])}}
    selection=tmp_path/'frozen_selection.json'
    save(selection,decisions)
    save(tmp_path/'frozen_manifest.json',{'sha256':digest(selection.read_bytes())})
    class Store:
        def __init__(self):self.rows={};self.spent=0
        def call(self,identity,request):
            if identity not in self.rows:
                cid,arm=identity.split('/')[:2]
                assert 'target_label' not in request and 'human_score' not in request
                label='yes' if cid=='C08' and arm=='baseline' else targets[cid]
                self.rows[identity]={'parsed':{'label':label,'valid':True,'rationale':'synthetic'}}
            return self.rows[identity]
    store=Store()
    pilot=SimpleNamespace(config={'seed':44,'final_repeats':2,'concurrency':2,
                                  'model':'gpt-5.4-mini','temperature':.3,
                                  'judge_max_tokens':512},store=store)
    results=r.fresh_final(pilot,[c for c in cases if c['case_id'] in r.FOCUS],prior,bank,decisions,tmp_path)
    assert len(store.rows)==22  # 20 controls, plus two calls for changed C08 only.
    assert results['C05']['baseline']==results['C05']['challenger']
    assert results['C08']['baseline'][0]['label']=='yes'
    assert results['C08']['challenger'][0]['label']=='partial'
    summary=r.report(tmp_path,[c for c in cases if c['case_id'] in r.FOCUS],results,decisions,store,pilot.config)
    assert summary['difference']==.1


def test_contrastive_coaching_reaches_real_gepa_reflection_offline(tmp_path,monkeypatch):
    import json
    import pytest
    from pathlib import Path
    from run import robust_prompt_repair_pilot as base
    python=Path(base.ROOT/'.venv-gepa/bin/python')
    if not python.exists():pytest.skip('GEPA runtime not installed')
    case=next(c for c in load_cases() if c['case_id']=='C08')
    seed=case['prompt']; candidate=seed+'\n\n'+r.SCENE_RULE
    seen=[]
    class Store:
        def call(self,identity,request):
            assert request['kind']=='reflect'
            seen.append(json.dumps(request['messages']))
            return {'response':{'choices':[{'finish_reason':'stop'}]},
                    'raw':f'```\n{candidate}\n```'}
    conf={'seed':44,'gepa_python':str(python),'search_repeats':5,
          'model':'gpt-5.4-mini','reflection_max_tokens':4096}
    pilot=base.Pilot(tmp_path,conf,[case],Store())
    def evaluate(case,arm,rnd,stage,prompt,repeats):
        label=case['target_label'] if prompt!=seed else 'yes'
        return base.aggregate([{'label':label,'rationale':'synthetic','valid':True}]*repeats,
                              case['target_label'])
    monkeypatch.setattr(pilot,'evaluate',evaluate)
    result=pilot.propose(case,'contrastive',1,seed,coaching=r.COACHING)
    assert result['prompt']==candidate
    assert result['candidate_evaluation']['accuracy']==1
    assert any('Contrastive correction' in msg and 'three lit candles' in msg for msg in seen)
