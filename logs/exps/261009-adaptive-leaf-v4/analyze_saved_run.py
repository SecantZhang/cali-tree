"""Verify the frozen v4 experiment using saved data; optionally zero-call replay."""
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
from critical.core.decision.robust.v4_models import restore_program
from critical.core.optimization.program.robust.metrics import RobustPolicy
from critical.core.optimization.prompt.calitree.node.program_leaf import validate_program_leaves
from run.calitree_adaptive_leaf import execute


def analyze(directory,replay=False):
    p=Path(directory);m=json.loads((p/'manifest.json').read_text());r=json.loads((p/'results.json').read_text());policy=RobustPolicy(**m['policy'])
    budget=r['budget'];jobs={v.stem:json.loads(v.read_text()) for v in (p/'jobs').glob('*.json')}
    assert budget['calls']<=m['max_calls'] and budget['completion_tokens_or_reserved']<=m['max_completion_tokens']
    assert len(set(budget['attempted_slots']))==len(budget['attempted_slots'])==budget['calls']
    assert set(jobs)==set(budget['attempted_slots'])
    ordered=[jobs[k] for k in budget['attempted_slots']]
    logical=[(j['case_id'],j['stage'],j['slot']) for j in ordered]
    assert len(logical)==len(set(logical))
    source=json.loads((ROOT/'logs/exps/261006-optimizer-comparison-v1/manifest.json').read_text())
    assert [c['id'] for c in source['cases']]==[c['id'] for c in m['cases']]
    assert Counter(c['target'] for c in m['cases'])=={'yes':4,'partial':4,'no':4}
    assert len({c['group'] for c in m['cases']})==12
    for c in m['cases']:
        for key,image in c['evidence'].items():assert sha256(Path(image).read_bytes()).hexdigest()==c['image_hashes'][key]
    for j in ordered:
        if j['stage'] in ('compile_v4','audit_v4','check_v4','visual_discovery'):
            assert 'reference_label' not in j['payload'] and 'feedback' not in j['payload']
        if j['stage'] in ('compile_v4','audit_v4'):assert not j['media_identity']
        if j['stage']=='check_v4':
            assert j['max_tokens']==1024
            if j['payload']['node']['role']=='requested':assert not j['media_identity']
        if j.get('route'):
            assert j['route']=='sol-proposer' and j['stage']=='propose_v4'
            assert j['case_id'].startswith('luna_then_sol/') and j['requested_identity']==m['routes']['sol-proposer']
        assert j['max_tokens']==(4096 if j['stage']=='propose_v4' else 1024 if j['stage']=='check_v4' else 2048)
    routes=Counter(j.get('route','primary') for j in ordered)
    assert routes['sol-proposer']<=144
    phases=[j['phase'] for j in ordered]
    if 'final' in phases:
        first=phases.index('final');assert all(j['phase']=='final' and j['stage']=='check_v4' for j in ordered[first:])
        freeze=json.loads((p/'selection_freeze.json').read_text());assert freeze['calls_before_final']==first
        assert len(freeze['hashes'])==24
        for rel,h in freeze['hashes'].items():assert sha256((p/rel).read_bytes()).hexdigest()==h
    components={};edits=Counter();audit_counts=Counter();escalations=[]
    for i,c in enumerate(m['cases']):
        prep_path=p/'prepared'/f'{i}.json'
        if not prep_path.exists():continue
        prep=json.loads(prep_path.read_text())
        assert sum(j['case_id']=='prepare/'+c['id'] for j in ordered)<=2
        for arm in m['arms']:
            frozen=p/'frozen'/arm/f'{i}.json'
            if not frozen.exists():continue
            bundle=json.loads(frozen.read_text())
            if 'error' in bundle:continue
            validate_program_leaves(bundle);saved=bundle['nodes']['leaf:'+c['id']]['result'];history=saved['lineage'][-1]
            assert saved['seed']==prep['seed']
            for candidate in saved['candidates'].values():
                program=restore_program(candidate)
                assert program.to_dict()['requirements']==c['original']['program']['requirements']
                assert program.to_dict()['outcomes']==c['original']['program']['outcomes']
                confirmation=candidate.get('confirmation')
                if confirmation:
                    assert confirmation['draws']==5
                    if candidate['program_ref']!=saved['seed']['program_ref']:
                        assert candidate['screen']['agreement']==candidate['screen']['coverage']==1
                audit_counts['approved' if candidate.get('audit',{}).get('accepted') else 'not_approved']+=1
            streak=0;escalated=False
            for e in history['events']:
                if arm=='luna_then_sol' and streak>=3:escalated=True
                assert e['stall_before']==streak and e['route']==('sol-proposer' if escalated else 'primary')
                if e.get('completed'):streak=0 if e['improved'] else streak+1
                assert e.get('stall_after',streak)==streak
            for entry in saved['lineage'][:-1]:
                edits.update(a['operation'] for a in entry['transaction']['actions'])
            row=r['cases'].get(c['id'],{}).get(arm,{})
            if 'selected' not in row.get('final',{}):continue
            for which,report in row['final'].items():
                assert report['draws']==5
                assert len({o['execution_ref'] for t in report['traces'] for o in t['observations'] if o['queried']})==sum(o['queried'] for t in report['traces'] for o in t['observations'])
            selected=saved['candidates'][saved['selected']['program_ref']]
            if row['support_status']=='locally_robust':
                assert policy.assess(selected['confirmation'],selected['audit'])['qualified']
                assert policy.assess(row['final']['selected'],selected['audit'])['qualified']
            baseline=saved['candidates'][saved['seed']['program_ref']].get('confirmation')
            chosen=selected.get('confirmation')
            if baseline and chosen:
                assert chosen['agreement']>=baseline['agreement'] and chosen['coverage']>=baseline['coverage']
            program=restore_program(saved['selected'])
            components.setdefault(c['id'],{})[arm]={'instruction':c['instruction'],'reference':c['target'],
                'seed_ref':saved['seed']['program_ref'],'selected_ref':program.ref,'selected_questions':[
                    {'id':n.id,'question':n.question,'criteria':n.criteria,'context':list(n.dependencies),
                     'required':list(n.required_dependencies),'activation':n.activation.__dict__ if n.activation else None} for n in program.nodes],
                'final':{which:{'labels':[t['label'] for t in rep['traces']], 'observations':[
                    [{'question_id':o['check_id'],'answer':o['status'],'event':o['event'],'queried':o['queried'],
                      'confidence':o['confidence'],'evidence':o['evidence']} for o in t['observations']] for t in rep['traces']]} for which,rep in row['final'].items()},
                'status':row['support_status'],'reasons':row['acceptance']['reasons'],'rounds':row['search_schedule']}
            if escalated:escalations.append({'case_id':c['id'],'first_sol_round':next(e['round']+1 for e in history['events'] if e['route']=='sol-proposer')})
    replay_result=None
    if replay:
        before=deepcopy(r)
        save_json(p/'replay_before_results.json',before)
        def forbidden(cap):raise AssertionError('Saved replay attempted a model call')
        replayed=execute(p,m,forbidden,forbidden,progress=False)
        # The executable activation type uses tuples; JSON artifacts use arrays.
        # Compare the actual portable serialization, not Python container types.
        replayed=json.loads(json.dumps(replayed))
        assert replayed['budget']==before['budget'] and replayed['cases']==before['cases'] and replayed['status']==before['status']
        replay_result=True
    verification={'status':r['status'],'calls':budget['calls'],'charged_completion_tokens':budget['completion_tokens_or_reserved'],
        'route_calls':dict(routes),'audit_counts':dict(audit_counts),'typed_actions':dict(edits),'escalations':escalations,
        'label_isolation':True,'image_free_readout':True,'all_selections_frozen_before_final':'final' in phases,
        'fresh_final_slots':True,'regression_guard':True,'duplicate_logical_slots':False,'zero_call_replay':replay_result}
    save_json(p/'component_analysis.json',components);save_json(p/'protocol_verification.json',verification)
    print(json.dumps(verification,indent=2))
    return verification


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--replay',action='store_true');args=parser.parse_args();analyze(args.directory,args.replay)
