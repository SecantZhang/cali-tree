"""Recompute comparison results and replay saved leaves without new model calls."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from critical.checkpoint import CheckpointStore
from critical.core.decision.artifacts import save_json, restore_program
from critical.core.decision.executor import ProgramExecutor
from critical.core.optimization.program.evaluation import summarize
from critical.core.optimization.prompt.calitree.node.program_leaf import validate_program_leaves, judge_program_leaf
from run.calitree_optimizer_comparison import summary, METHODS, dependency_fingerprints

root=Path(__file__).resolve().parent
manifest=json.loads((root/'manifest.json').read_text())
result=json.loads((root/'results.json').read_text())
bundle=validate_program_leaves(json.loads((root/'leaves.json').read_text()))
budget=json.loads((root/'budget.json').read_text())
assert result['status']=='completed' and len(bundle['nodes'])==36
assert len(manifest['cases'])==len({r['group'] for r in manifest['cases']})==12
assert manifest['dependencies']==dependency_fingerprints()
for path,expected in manifest['code_hashes'].items():
    assert sha256((root/'source_snapshot'/path).read_bytes()).hexdigest()==expected
jobs=[json.loads(p.read_text()) for p in (root/'jobs').glob('*.json')]
assert len(jobs)==budget['calls']<=1800
assert budget['completion_tokens_or_reserved']<=2304000
assert all(c['search']<=26 and c['final']<=24 for c in budget['cases'].values())
for job in jobs:
    assert job['max_tokens']<=(1024 if job['stage']=='check' else 2048)
    if job['stage'] in ('check','audit','compile'):
        assert not {'reference_label','target_label','feedback','evaluation'} & set(job['payload'])
    if 'response' in job: assert job['response']['model']=='gpt-6-luna'
replays=0
for raw in manifest['cases']:
    for key,path in raw['evidence'].items():
        assert sha256(Path(path).read_bytes()).hexdigest()==raw['image_hashes'][key]
    for method in METHODS:
        row=result['cases'][raw['id']][method]
        node=bundle['nodes'][f'leaf:{method}/{raw["id"]}']
        assert node['fit_scope']==[raw['id']] and node['result']['seed']==raw['seed']
        for arm in ('seed','selected'):
            report=row['final'][arm]
            assert summarize(report['draws'],raw['target'])==report
            assert report['repeat_count']==3 and report['independent_cases']==1
            artifact=node['result'][arm]
            assert all(d['program_ref']==artifact['program_ref'] for d in report['draws'])
            restore_program(artifact)
        audit=node['result']['candidates'].get(node['program_ref'],{}).get('audit',{})
        final=row['final']['selected']
        assert (row['support_status']=='locally_fitted')==(audit.get('accepted',False) and final['agreement']==1 and final['coverage']==1)
        class ReadOnlyChecker:
            identity=node['executor_identity']
            def check(self,*args,**kwargs):
                raise AssertionError('Replay attempted a provider call')
        executor=ProgramExecutor(ReadOnlyChecker(),checkpoint=CheckpointStore(root/method/'observations.jsonl'))
        replay=judge_program_leaf(bundle,node['id'],raw['evidence'],executor,repeat=f'{method}/{raw["id"]}/final/selected/0')
        assert replay.to_dict()==final['draws'][0]
        replays+=1
metrics=summary(result,manifest)
by_method={}
for method in METHODS:
    scoped=[j for j in jobs if j['case_id'].startswith(method+'/')]
    rows=[result['cases'][r['id']][method] for r in manifest['cases']]
    matches=sum(d['label']==raw['target'] for raw in manifest['cases'] for d in result['cases'][raw['id']][method]['final']['selected']['draws'])
    resolved=sum(d['label'] is not None for r in rows for d in r['final']['selected']['draws'])
    by_method[method]={'resolved_final_draws':resolved, 'matching_final_draws':matches,
                      'agreement_on_resolved_draws':matches/resolved if resolved else None,
                      'calls':len(scoped),'stages':dict(Counter(j['stage'] for j in scoped)),
                      'outcomes':dict(Counter(j['outcome'] for j in scoped)),
                      'measured_completion_tokens':sum(j.get('response',{}).get('completionTokens',0) for j in scoped),
                      'measured_input_tokens':sum(j.get('response',{}).get('promptTokens',0) for j in scoped)}
checks={'verified':True,'reloaded_leaves':replays,'cases':12,'total_calls':budget['calls'],
        'completion_tokens_or_reserved':budget['completion_tokens_or_reserved'],'methods':by_method,'summary':metrics}
save_json(root/'audit.json',checks)
print(json.dumps(checks,indent=2))
