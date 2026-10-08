"""Offline verification and exact scoring replay of the frozen DSG comparison."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from critical.checkpoint import CheckpointStore
from critical.core.decision import dsg
from critical.core.decision.artifacts import digest, restore_program, save_json
from critical.core.decision.calls import DurableCalls, CaseCalls
from critical.core.decision.executor import ModelChecker, ProgramExecutor
from run.calitree_dsg_fidelity import summary, case_metrics, preflight, execute

root=Path(__file__).resolve().parent
m=preflight(root)
r=json.loads((root/'results.json').read_text())
b=json.loads((root/'budget.json').read_text())
assert r['status']=='completed'
assert len(m['cases'])==len({c['group'] for c in m['cases']})==12
assert Counter(c['target'] for c in m['cases'])=={'yes':4,'partial':4,'no':4}
for relative,expected in m['code_hashes'].items():
    assert sha256((root/'source_snapshot'/relative).read_bytes()).hexdigest()==expected
migration=json.loads((root/'migration.json').read_text())
old=Path(migration['from'])
assert sha256((old/'manifest.json').read_bytes()).hexdigest()==migration['previous_manifest_sha256']
assert sha256((old/'budget.json').read_bytes()).hexdigest()==migration['retained_budget_sha256']
old_jobs=list((old/'jobs').glob('*.json'))
assert len(old_jobs)==migration['retained_attempts']
for job in old_jobs:assert job.read_bytes()==(root/'jobs'/job.name).read_bytes()
for draw in (old/'draws').rglob('*.json'):assert draw.read_bytes()==(root/'draws'/draw.relative_to(old/'draws')).read_bytes()
jobs=[json.loads(p.read_text()) for p in (root/'jobs').glob('*.json')]
assert len(jobs)==len(set(b['attempted_slots']))==b['calls']<=450
assert set(j['execution_ref'] for j in jobs)==set(b['attempted_slots'])
assert b['completion_tokens_or_reserved']<=512000
for scope,counts in b['cases'].items():
    assert counts['search']<=(4 if scope.startswith('prepare/') else 0)
    assert counts['final']<=(10 if scope.startswith('original/') else 5 if scope.startswith('dsg/') else 0)
for job in jobs:
    # All payload constructors are separately tested for recursive label isolation.
    assert not {'reference_label','target_label','target','feedback','original_prediction'} & set(job['payload'])
    assert job['max_tokens']==(2048 if job['stage'] in ('dsg_tuples','dsg_questions','dsg_dependencies','dsg_audit') else 1024)
    if 'response' in job:assert job['response']['model']=='gpt-6-luna'
    assert sum(i['type']=='image' for i in job['media_identity'])==(2 if job['stage'] in ('check','dsg_vqa') else 0)

class ReadOnlyCalls(DurableCalls):
    def call(self,stage,payload,schema,*,template,media=(),slot='0',final=False,max_tokens=2048,case_id=None):
        media_ids=[{'type':i['type'],'sha256':sha256(Path(i['path']).read_bytes()).hexdigest()} if i['type']=='image' else i for i in media]
        key=digest([self.identity,case_id,stage,payload,schema,template,media_ids,slot,max_tokens])
        assert (self.directory/'jobs'/(key+'.json')).exists() or key in self.budget['attempted_slots'], ('Unknown replay slot',stage,key)
        return super().call(stage,payload,schema,template=template,media=media,slot=slot,final=final,max_tokens=max_tokens,case_id=case_id)

def reject(cap):raise AssertionError('Offline replay attempted a provider call')
before=(root/'budget.json').read_bytes()
calls=ReadOnlyCalls(root,reject,identity={k:m[k] for k in ('model','temperature','reasoning_effort')},
    **{k:m[k] for k in ('max_calls','max_completion_tokens','reserve_calls','reserve_tokens')})
replayed=0;per_case=[]
for index,case in enumerate(m['cases']):
    row=r['cases'][case['id']];prep=row['preparation'];assert row['completed']
    original=restore_program(case['seed'])
    executor=ProgramExecutor(ModelChecker(CaseCalls(calls,'original/'+case['id'])),checkpoint=CheckpointStore(root/'original_observations.jsonl'))
    if prep['status']=='ready':
        graph=dsg.build_graph(original,prep['tuples'],prep['questions'],prep['dependencies'])
        assert graph==prep['graph'] and digest(graph)==prep['graph_ref']
    for arm in ('original','dsg'):
        assert len(row['draws'][arm])==5
        for repeat,draw in enumerate(row['draws'][arm]):
            if arm=='original':
                replay=executor.execute(original,case['evidence'],repeat=f'{case["id"]}/original/{repeat}',final=True).to_dict()
                assert replay==draw,(index,arm,repeat)
            elif prep['status']=='ready':
                replay=dsg.execute(CaseCalls(calls,f'dsg/{case["id"]}/draw/{repeat}'),graph,case['evidence'],repeat)
                for key in ('graph_ref','repeat','observations','outcomes','label','dsg_score','requested_fraction','execution_refs'):
                    assert replay[key]==draw[key],(index,arm,repeat,key)
            else:
                assert draw['label'] is None
                continue
            replayed+=1
    per_case.append({'case':index+1,'id':case['id'],'instruction':case['instruction'],'target':case['target'],
        'nodes':len(prep.get('graph',{}).get('nodes',[])) if prep.get('graph') else 0,'preparation':prep['status'],
        'audit':prep.get('audit'),'metrics':case_metrics(row,case['target'])})
assert before==(root/'budget.json').read_bytes()
# Full completed-run resume may not contact the provider or change the results.
resumed=execute(root,m,reject)
assert resumed==r and before==(root/'budget.json').read_bytes()
methods={}
for arm in ('prepare','original','dsg'):
    scoped=[j for j in jobs if j['case_id'].startswith(arm+'/')]
    methods[arm]={'calls':len(scoped),'outcomes':dict(Counter(j['outcome'] for j in scoped)),
        'measured_input_tokens':sum(j.get('response',{}).get('promptTokens',0) for j in scoped),
        'measured_completion_tokens':sum(j.get('response',{}).get('completionTokens',0) for j in scoped)}
audit={'verified':True,'replayed_draws':replayed,'zero_call_resume':True,'total_calls':b['calls'],
    'charged_completion_tokens':b['completion_tokens_or_reserved'],'methods':methods,'summary':summary(r,m),'per_case':per_case}
save_json(root/'audit.json',audit)
print(json.dumps({k:v for k,v in audit.items() if k!='per_case'},indent=2))
