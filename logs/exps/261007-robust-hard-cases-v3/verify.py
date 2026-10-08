"""Read-only post-run protocol verification, independent of model scores."""
import json
from pathlib import Path
from critical.core.optimization.prompt.calitree.node.program_leaf import validate_program_leaves
from critical.core.decision.robust.models import restore_program

root=Path(__file__).resolve().parent
m=json.loads((root/'manifest.json').read_text())
b=json.loads((root/'budget.json').read_text())
r=json.loads((root/'results.json').read_text())
jobs={p.stem:json.loads(p.read_text()) for p in (root/'jobs').glob('*.json')}
assert r['status']=='completed', r.get('error')
assert len(jobs)==b['calls']==len(set(b['attempted_slots']))
ordered=[jobs[k] for k in b['attempted_slots']]
phases=[j['phase'] for j in ordered]
first_final=phases.index('final')
assert all(phase=='final' for phase in phases[first_final:]), 'Search after final verification'
assert b['calls'] <= m['max_calls']
assert b['completion_tokens_or_reserved'] <= m['max_completion_tokens']
for scope,v in b['cases'].items():
    assert v['search'] <= (2 if scope.startswith('prepare/') else 109)
    assert v['final'] <=40
for j in jobs.values():
    assert j['max_tokens']<= (1024 if j['stage']=='check' else 2048)
    if j['stage'] in ('compile','check','audit','audit_views'):
        assert not any(key in json.dumps(j['payload']) for key in ('reference_label','textual_gradients','rejected_diagnostics'))
    if j['stage'] in ('compile','audit','audit_views'):
        assert not j['media_identity']
    if j['phase']=='final':
        assert j['stage']=='check'
    if j.get('response'):
        assert j['response']['model']=='gpt-6-luna'
leaves=validate_program_leaves(json.loads((root/'leaves.json').read_text()))
counts={'frozen':0,'final_draws':0,'selected_programs':0}
for i,case in enumerate(m['cases']):
    assert set(r['cases'][case['id']])==set(m['arms'])
    for arm in m['arms']:
        frozen=json.loads((root/'frozen'/arm/f'{i}.json').read_text())
        counts['frozen']+=1
        if 'error' in frozen:
            continue
        validate_program_leaves(frozen)
        node=frozen['nodes']['leaf:'+case['id']]
        published=leaves['nodes']['leaf:'+arm+'/'+case['id']]
        assert published['program_ref']==node['program_ref']
        for artifact in node['result']['candidates'].values():
            restore_program(artifact)
        row=r['cases'][case['id']][arm]
        for which,report in row['final'].items():
            assert report['draws']==len(report['traces'])==5
            counts['final_draws']+=len(report['traces'])
            assert all(t['program_ref']==node['result'][which]['program_ref'] for t in report['traces'])
        if node['program_ref']:
            counts['selected_programs']+=1
        if row['support_status']=='locally_robust':
            assert row['acceptance']['qualified'] and row['final']['selected']['agreement']>=.8
            assert row['final']['selected']['coverage']==1
print(json.dumps({'verification':'passed','jobs':len(jobs),**counts},indent=2))
