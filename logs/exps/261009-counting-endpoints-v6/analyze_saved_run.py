"""Verify flat counting and replay saved results without model calls."""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from critical.core.decision.artifacts import save_json
from critical.core.decision.counting_v6 import restore_program
from critical.core.decision.counting import count_states, AGGREGATION
from critical.core.optimization.program.robust.metrics import NoAuditRobustPolicy
from critical.core.optimization.prompt.calitree.node.program_leaf import validate_program_leaves
from run.calitree_adaptive_leaf import execute


def analyze(directory,replay=False):
    p=Path(directory);m=json.loads((p/'manifest.json').read_text());r=json.loads((p/'results.json').read_text());policy=NoAuditRobustPolicy(**m['policy'])
    assert m['scoring']=='endpoints' and m['semantic_audit'] is False and m['model_readout'] is False
    assert m['policy']['agreement']==1 and m['transport_recovery_per_report']==1
    assert m['scope_limits']=={'search':107,'final':42} and m['reserve_calls']==1008
    assert m['aggregation']==AGGREGATION
    budget=r['budget'];jobs={f.stem:json.loads(f.read_text()) for f in (p/'jobs').glob('*.json')}
    assert budget['calls']<=m['max_calls'] and budget['completion_tokens_or_reserved']<=m['max_completion_tokens']
    assert len(set(budget['attempted_slots']))==len(budget['attempted_slots'])==budget['calls']
    assert set(jobs)==set(budget['attempted_slots'])
    ordered=[jobs[k] for k in budget['attempted_slots']]
    logical=[(j['case_id'],j['stage'],j['slot']) for j in ordered]
    assert len(logical)==len(set(logical))
    source=json.loads((ROOT/'logs/exps/261006-optimizer-comparison-v1/manifest.json').read_text())
    assert [c['id'] for c in m['cases']]==[c['id'] for c in source['cases']]
    assert Counter(c['target'] for c in m['cases'])=={'yes':4,'partial':4,'no':4}
    assert len({c['group'] for c in m['cases']})==12
    for c in m['cases']:
        for key,path in c['evidence'].items():assert sha256(Path(path).read_bytes()).hexdigest()==c['image_hashes'][key]
    for j in ordered:
        assert 'audit' not in j['stage'] and j['stage'] in ('compile_counting','check_counting','propose_counting','gradient','visual_discovery')
        if j['stage'] in ('compile_counting','check_counting','visual_discovery'):
            assert 'reference_label' not in j['payload'] and 'feedback' not in j['payload']
        if j['stage']=='check_counting':
            assert j['payload']['decision']['role']=='decision' and 'outcome' not in j['payload']
            assert j['max_tokens']==1024 and len([x for x in j['media_identity'] if x['type']=='image'])==2
        if j['stage']=='compile_counting':assert not j['media_identity']
        if j.get('route'):
            assert j['stage']=='propose_counting' and j['route']=='sol-proposer' and j['case_id'].startswith('luna_then_sol/')
            assert j['requested_identity']==m['routes']['sol-proposer']
        assert j['max_tokens']==(4096 if j['stage']=='propose_counting' else 1024 if j['stage']=='check_counting' else 2048)
    route_counts=Counter(j.get('route','primary') for j in ordered);assert route_counts['sol-proposer']<=144
    phases=[j['phase'] for j in ordered]
    if 'final' in phases:
        first=phases.index('final');assert all(j['phase']=='final' and j['stage']=='check_counting' for j in ordered[first:])
        freeze=json.loads((p/'selection_freeze.json').read_text());assert freeze['calls_before_final']==first and len(freeze['hashes'])==24
        for rel,h in freeze['hashes'].items():assert sha256((p/rel).read_bytes()).hexdigest()==h
    components={};edits=Counter();counts=Counter()

    def validate_report(rep,program):
        assert rep['draws']==len(rep['traces'])
        if 'raw_measurements' in rep:
            raw=rep['raw_measurements'];validate_report(raw,program)
            recovery=rep['transport_recovery'];changed=[]
            for i,(a,b) in enumerate(zip(raw['traces'],rep['traces'])):
                for j,(old,new) in enumerate(zip(a['observations'],b['observations'])):
                    if old!=new:changed.append((i,j,old,new))
            if recovery:
                first=next((i,j) for i,t in enumerate(raw['traces']) for j,o in enumerate(t['observations']) if o['event']=='transport_failure')
                assert len(changed)==1 and changed[0][:2]==first
                i,j,old,new=changed[0];assert recovery['draw']==i and recovery['check_id']==old['check_id']
                assert new['attempts'][0]==old and len(new['attempts'])==2
                assert jobs[old['execution_ref']]['outcome']=='transport_error'
                attempt=new['attempts'][1];job=jobs[attempt['execution_ref']]
                assert job['slot']==recovery['slot']+'/'+old['check_id']
                assert job['stage']=='check_counting' and job['phase']==jobs[old['execution_ref']]['phase']
                assert new['completion_tokens']==sum(a['completion_tokens'] for a in new['attempts'])
            else:assert not changed
        for t in rep['traces']:
            assert len(t['observations'])==len(program.nodes)
            eligible=[o for o in t['observations'] if o['eligible']]
            states=[o['status'] for o in eligible];state=count_states(states)
            assert t['label']=={'complete':'yes','partial':'partial','absent':'no'}.get(state)
            assert t['counting']['passed']==states.count('pass') and t['counting']['failed']==states.count('fail')
            assert t['counting']['unknown']==states.count('unknown') and t['counting']['total']==len(states)
            assert t['counting']['model_readout'] is False and t['counting']['semantic_audit']=='disabled'
            assert all(o['queried'] for o in eligible)
            assert not any(o['event'] in ('conditional_skip','required_dependency_block') for o in t['observations'])

    for i,c in enumerate(m['cases']):
        prep_path=p/'prepared'/f'{i}.json'
        if not prep_path.exists():continue
        prep=json.loads(prep_path.read_text());assert 'seed_audit' not in prep and prep['semantic_audit']['performed'] is False
        assert sum(j['case_id']=='prepare/'+c['id'] for j in ordered)<=1
        for arm in m['arms']:
            path=p/'frozen'/arm/f'{i}.json'
            if not path.exists():continue
            bundle=json.loads(path.read_text())
            if 'error' in bundle:counts['invalid_seed']+=1;continue
            validate_program_leaves(bundle);saved=bundle['nodes']['leaf:'+c['id']]['result'];h=saved['lineage'][-1]
            assert h['semantic_audit']=='disabled' and saved['seed']==prep['seed']
            for cand in saved['candidates'].values():
                prog=restore_program(cand)
                assert prog.to_dict()['requirements']==c['original']['program']['requirements']
                assert prog.to_dict()['outcomes']==c['original']['program']['outcomes']
                assert cand['audit']['status']=='disabled' and cand['audit']['performed'] is False and 'accepted' not in cand['audit']
                for tier in ('screen','confirmation'):
                    if cand.get(tier):validate_report(cand[tier],prog)
                if cand.get('confirmation'):
                    assert cand['confirmation']['draws']==5
                    if cand['program_ref']!=saved['seed']['program_ref']:
                        assert cand['screen']['agreement']==cand['screen']['coverage']==1
            streak=0;switched=False
            for e in h['events']:
                if arm=='luna_then_sol' and streak>=3:switched=True
                assert e['stall_before']==streak and e['route']==('sol-proposer' if switched else 'primary')
                if e.get('completed'):streak=0 if e['improved'] else streak+1
                assert e.get('stall_after',streak)==streak
            for entry in saved['lineage'][:-1]:edits.update(a['operation'] for a in entry['transaction']['actions'])
            counts[arm+'/changed']+=saved['seed']['program_ref']!=saved['selected']['program_ref']
            row=r['cases'].get(c['id'],{}).get(arm,{})
            if 'selected' not in row.get('final',{}):continue
            for which,rep in row['final'].items():
                validate_report(rep,restore_program(saved[which]));assert rep['draws']==5
                refs=[o['execution_ref'] for t in rep['traces'] for o in t['observations'] if o['queried']]
                assert len(refs)==len(set(refs))
            selected=saved['candidates'][saved['selected']['program_ref']]
            if row['support_status']=='locally_robust':
                assert policy.assess(selected['confirmation'],selected['audit'])['qualified']
                assert policy.assess(row['final']['selected'],selected['audit'])['qualified']
            seed_conf=saved['candidates'][saved['seed']['program_ref']].get('confirmation');sel_conf=selected.get('confirmation')
            if seed_conf:
                seed_screen=saved['candidates'][saved['seed']['program_ref']]['screen']
                assert seed_screen['agreement']==seed_screen['coverage']==1
            if seed_conf and sel_conf:
                assert sel_conf['agreement']>=seed_conf['agreement'] and sel_conf['coverage']>=seed_conf['coverage']
            components.setdefault(c['id'],{})[arm]={'instruction':c['instruction'],'reference':c['target'],
                'seed':saved['seed'],'selected':saved['selected'],'status':row['support_status'],
                'final':{w:{'labels':[t['label'] for t in rep['traces']],'counts':[t['counting'] for t in rep['traces']],
                    'observations':[t['observations'] for t in rep['traces']]} for w,rep in row['final'].items()}}
    replayed_ok=None
    if replay:
        before=deepcopy(r);save_json(p/'replay_before_results.json',before)
        def forbidden(cap):raise AssertionError('Replay attempted a model call')
        replayed=json.loads(json.dumps(execute(p,m,forbidden,forbidden,progress=False)))
        assert replayed['budget']==before['budget'] and replayed['cases']==before['cases'] and replayed['status']==before['status']
        replayed_ok=True
    ratios={}
    for arm in m['arms']:
        rows=[r['cases'].get(c['id'],{}).get(arm,{}) for c in m['cases']]
        ratios[arm]={'cases':len(rows),'effective_accurate_repeatable':sum(
            v.get('final',{}).get('selected',{}).get('agreement')==1 and v.get('final',{}).get('selected',{}).get('coverage')==1 for v in rows),
            'raw_accurate_repeatable':sum(v.get('final',{}).get('selected',{}).get('raw_measurements',{}).get('agreement')==1 and
                v.get('final',{}).get('selected',{}).get('raw_measurements',{}).get('coverage')==1 for v in rows)}
    report={'status':r['status'],'calls':budget['calls'],'charged_completion_tokens':budget['completion_tokens_or_reserved'],
        'route_calls':dict(route_counts),'edits':dict(edits),'selection_counts':dict(counts),'no_auditor_calls':True,
        'no_model_readout_calls':True,'deterministic_counts_verified':True,'label_isolation':True,'fresh_final_slots':True,
        'frozen_before_final':'final' in phases,'duplicate_logical_slots':False,'zero_call_replay':replayed_ok,
        'raw_effective_recovery_verified':True,'accurate_repeatable':ratios}
    save_json(p/'component_analysis.json',components);save_json(p/'protocol_verification.json',report)
    print(json.dumps(report,indent=2));return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--replay',action='store_true');args=parser.parse_args();analyze(args.directory,args.replay)
