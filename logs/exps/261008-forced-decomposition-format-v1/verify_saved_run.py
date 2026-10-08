"""Offline protocol verification and exact replay; never permit new model calls."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import shutil
from collections import Counter

from critical.core.decision.robust.models import restore_program
from critical.core.decision.robust.decomposition import validate_decomposition, validate_broad
from run.calitree_forced_decomposition import execute, preflight


def verify(directory):
    directory=Path(directory)
    manifest=json.loads((directory/'manifest.json').read_text())
    assert preflight(directory)==manifest
    result=json.loads((directory/'results.json').read_text())
    budget=json.loads((directory/'budget.json').read_text())
    jobs={p.stem:json.loads(p.read_text()) for p in (directory/'jobs').glob('*.json')}
    ordered=[jobs.get(key,{'outcome':'interrupted'}) for key in budget['attempted_slots']]
    assert len(budget['attempted_slots'])==len(set(budget['attempted_slots']))==budget['calls']
    assert budget['calls']<=manifest['max_calls']
    assert budget['completion_tokens_or_reserved']<=manifest['max_completion_tokens']
    assert all(row['search']<=109 and row['final']<=40 for row in budget.get('cases',{}).values())
    combined=None
    if manifest.get('prior_attempt'):
        prior=manifest['prior_attempt'];old=Path(prior['path'])
        old_manifest=json.loads((old/'manifest.json').read_text())
        old_budget=json.loads((old/'budget.json').read_text())
        combined={'calls':budget['calls']+old_budget['calls'],
                  'completion_tokens_or_reserved':budget['completion_tokens_or_reserved']+old_budget['completion_tokens_or_reserved']}
        assert combined['calls']<=old_manifest['max_calls']
        assert combined['completion_tokens_or_reserved']<=old_manifest['max_completion_tokens']
        assert not any(j.get('stage') in ('compile_decomposition','audit_pair') for j in ordered)
        for i,_ in enumerate(manifest['cases']):
            assert json.loads((directory/'prepared'/f'{i}.json').read_text())==json.loads((old/'prepared'/f'{i}.json').read_text())
    phases=[j.get('phase') for j in ordered]
    if 'final' in phases:
        first=phases.index('final')
        assert all(phase=='final' for phase in phases[first:])
    checks=Counter(); acknowledgments=0; missing_ack=0; attempted_final=0
    for job in ordered:
        if job.get('stage') in ('compile_decomposition','audit','audit_pair','check'):
            assert 'reference_label' not in job['payload'] and 'feedback' not in job['payload']
        if job.get('stage')=='check':
            assert job['max_tokens']==1024
            node=job['payload']['node']; checks[node['role']]+=1
            if job['phase']=='final': attempted_final+=1
            if job['payload'].get('contract')==manifest['contract']:
                if node['role']=='support':
                    assert sum(m['type']=='image' for m in job['media_identity'])==2
                    assert job['payload']['dependencies']==[]
                else:
                    assert job['media_identity']==[]
                    assert [d['check_id'] for d in job['payload']['dependencies']]==node['dependencies']
                if job['outcome']=='completed':
                    if job['parsed'].get('used_dependency_ids')==node['dependencies']: acknowledgments+=1
                    else:
                        assert job.get('observation_validation_error'); missing_ack+=1
        elif 'max_tokens' in job: assert job['max_tokens']==2048
    topology=[]
    for i,case in enumerate(manifest['cases']):
        original=restore_program(case['broad_seed'])
        for arm in manifest['arms']:
            local=json.loads((directory/'frozen'/arm/f'{i}.json').read_text())
            if 'error' in local: continue
            node=local['nodes']['leaf:'+case['id']]
            for which in ('seed','selected'):
                program=restore_program(node['result'][which])
                (validate_decomposition if arm.startswith('decomposed') else validate_broad)(program,original)
                topology.append({'case_id':case['id'],'arm':arm,'program':which,'hash':program.ref,
                                 'checks':len(program.nodes),'supports':sum(n.role=='support' for n in program.nodes)})
            for report in result['cases'].get(case['id'],{}).get(arm,{}).get('final',{}).values():
                assert report['draws']==len(report['traces'])==5
    saved_cases=deepcopy(result['cases'])
    with tempfile.TemporaryDirectory() as temporary:
        clone=Path(temporary)/'replay';shutil.copytree(directory,clone)
        def forbidden(_): raise AssertionError('Replay attempted a model call')
        replay=execute(clone,manifest,forbidden)
        assert replay['cases']==saved_cases and replay['status']==result['status']
        assert replay['budget']['calls']==budget['calls']
    return {'status':'verified','calls':budget['calls'],'charged_completion_tokens':budget['completion_tokens_or_reserved'],
            'final_check_calls':attempted_final,'role_counts':dict(checks),'acknowledgments':acknowledgments,
            'invalid_acknowledgments':missing_ack,'job_outcomes':dict(Counter(j['outcome'] for j in ordered)),
            'topology':topology,'zero_call_replay':True,'label_isolation':True,'readout_image_isolation':True,
            'all_selection_before_final':True,'limits_preserved':True,'combined_usage':combined}


if __name__=='__main__':
    from critical.core.decision.artifacts import save_json
    directory=Path(__file__).resolve().parent
    report=verify(directory);save_json(directory/'protocol_verification.json',report)
    print(json.dumps(report,indent=2))
