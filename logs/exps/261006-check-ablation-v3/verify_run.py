"""Verify and replay the paired experiment without new provider calls."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from critical.core.decision.ablation import execute_draw, draw_metrics, aggregate_observations, make_bank
from critical.core.decision.artifacts import digest, restore_program, save_json
from critical.core.decision.calls import DurableCalls, CaseCalls
from run.calitree_check_ablation import summarize, ARMS

root=Path(__file__).resolve().parent
manifest=json.loads((root/'manifest.json').read_text())
result=json.loads((root/'results.json').read_text())
budget=json.loads((root/'budget.json').read_text())
assert result['status']=='completed'
assert len(manifest['cases'])==len({r['group'] for r in manifest['cases']})==12
assert Counter(r['target'] for r in manifest['cases'])=={'yes':4,'partial':4,'no':4}
for relative,expected in manifest['code_hashes'].items():
    assert sha256((root/'source_snapshot'/relative).read_bytes()).hexdigest()==expected
jobs=[json.loads(p.read_text()) for p in (root/'jobs').glob('*.json')]
assert len(jobs)==len(set(budget['attempted_slots']))==budget['calls']<=400
assert budget['completion_tokens_or_reserved']<=409600
assert all(v['search']<=26 and v['final']<=24 for v in budget['cases'].values())
for job in jobs:
    assert not {'reference_label','target_label','feedback'} & set(job['payload'])
    assert job['max_tokens']==(2048 if job['stage'] in ('compile','audit','repair') else 1024)
    if 'response' in job:assert job['response']['model']=='gpt-6-luna'
    images=sum(row['type']=='image' for row in job['media_identity'])
    assert images==(0 if job['stage']=='fulfillment' else 2)

def reject_provider(cap):
    raise AssertionError('Replay attempted a new provider call')

before=(root/'budget.json').read_bytes()
calls=DurableCalls(root,reject_provider,identity={k:manifest[k] for k in ('model','temperature','reasoning_effort')},
    **{k:manifest[k] for k in ('max_calls','max_completion_tokens','reserve_calls','reserve_tokens')})
replayed=0
per_case=[]
for index,case in enumerate(manifest['cases']):
    for key,path in case['evidence'].items():
        assert sha256(Path(path).read_bytes()).hexdigest()==case['image_hashes'][key]
    row=result['cases'][case['id']];prepared=row['preparation']
    if prepared['status']=='ready':
        bank=prepared['bank'];assert digest(bank)==prepared['bank_ref'] and prepared['audit']['accepted']
        assert make_bank(restore_program(case['seed']),{k:bank[k] for k in ('representable','reason','facts','decisions')})==bank
    for arm in ARMS:
        draws=row['draws'][arm];assert len(draws)==5
        for repeat,draw in enumerate(draws):
            assert draw['arm']==arm and draw['repeat']==repeat
            if prepared['status']=='ready':
                replay=execute_draw(CaseCalls(calls,arm+'/'+case['id']),bank,case['evidence'],arm,repeat)
                for key in ('bank_ref','facts','outcomes','label'):
                    assert replay[key]==draw[key], (index,arm,repeat,key)
                assert aggregate_observations(bank,draw['facts'],draw['outcomes'])==draw['label']
                replayed+=1
            else:assert draw['label'] is None
        metrics=draw_metrics(draws,case['target']);assert metrics['independent_cases']==1
        per_case.append({'case':index+1,'id':case['id'],'instruction':case['instruction'],'target':case['target'],
                         'arm':arm,'preparation':prepared['status'],'metrics':metrics})
assert before==(root/'budget.json').read_bytes()
methods={}
for arm in (*ARMS,'prepare'):
    scoped=[j for j in jobs if j['case_id'].startswith(arm+'/')]
    methods[arm]={'calls':len(scoped),'outcomes':dict(Counter(j['outcome'] for j in scoped)),
        'measured_input_tokens':sum(j.get('response',{}).get('promptTokens',0) for j in scoped),
        'measured_completion_tokens':sum(j.get('response',{}).get('completionTokens',0) for j in scoped)}
audit={'verified':True,'replayed_draws':replayed,'total_calls':budget['calls'],
       'charged_completion_tokens':budget['completion_tokens_or_reserved'],'methods':methods,
       'summary':summarize(result,manifest),'per_case':per_case}
save_json(root/'audit.json',audit)
print(json.dumps({k:v for k,v in audit.items() if k!='per_case'},indent=2))
