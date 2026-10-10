"""Independent exact score arithmetic, protected mass, observation isolation and zero-call replay."""
from collections import Counter
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from critical.core.decision.artifacts import save_json
from critical.core.decision.fulfillment import restore_program,export_program,variant
from critical.core.optimization.program.robust.metrics import NoAuditRobustPolicy
from critical.core.optimization.prompt.calitree.node.program_leaf import validate_program_leaves
from run.calitree_adaptive_leaf import execute


def category(f):return 'yes' if f>=Fraction(9,10) else 'no' if f<=Fraction(1,10) else 'partial'


def analyze(directory,replay=False):
    p=Path(directory);m=json.loads((p/'manifest.json').read_text());r=json.loads((p/'results.json').read_text())
    assert m['scoring']=='fulfillment' and m['arms']==['binary','fulfillment'] and m['routes']=={}
    assert m['semantic_audit'] is False and m['model_readout'] is False and m['policy']['agreement']==1
    assert m['thresholds']=={'yes':.9,'no':.1} and m['scope_limits']=={'search':107,'final':42}
    source=json.loads((ROOT/'logs/exps/261006-optimizer-comparison-v1/manifest.json').read_text())
    assert [c['id'] for c in m['cases']]==[c['id'] for c in source['cases']]
    assert Counter(c['target'] for c in m['cases'])=={'yes':4,'partial':4,'no':4}
    assert len({c['group'] for c in m['cases']})==12
    for c in m['cases']:
        for key,path in c['evidence'].items():assert sha256(Path(path).read_bytes()).hexdigest()==c['image_hashes'][key]
    budget=r['budget'];jobs={q.stem:json.loads(q.read_text()) for q in (p/'jobs').glob('*.json')}
    ordered=[jobs[k] for k in budget['attempted_slots']]
    assert set(jobs)==set(budget['attempted_slots']) and len(jobs)==budget['calls']
    assert len(set((j['case_id'],j['stage'],j['slot']) for j in ordered))==len(jobs)
    assert budget['calls']<=m['max_calls'] and budget['completion_tokens_or_reserved']<=m['max_completion_tokens']
    assert sum((j.get('response') or {}).get('completionTokens',j['max_tokens']) for j in ordered)==budget['completion_tokens_or_reserved']
    for j in ordered:
        assert j.get('route') is None and j['stage'] in ('compile_fulfillment','check_fulfillment','propose_fulfillment','gradient','visual_discovery')
        if j['stage'] in ('compile_fulfillment','check_fulfillment','visual_discovery'):
            assert not {'reference_label','feedback'} & set(j['payload'])
        if j['stage']=='check_fulfillment':
            assert not {'weights','scoring_mode','thresholds'} & set(j['payload'])
            assert not any(k.startswith('weight') or k=='root_id' for k in j['payload']['condition'])
            assert len([x for x in j['media_identity'] if x['type']=='image'])==2
        assert j['max_tokens']==(1024 if j['stage']=='check_fulfillment' else 4096 if j['stage']=='propose_fulfillment' else 2048)
    phases=[j['phase'] for j in ordered]
    if 'final' in phases:
        first=phases.index('final');freeze=json.loads((p/'selection_freeze.json').read_text())
        assert freeze['calls_before_final']==first and len(freeze['hashes'])==24
        assert all(j['stage']=='check_fulfillment' and j['phase']=='final' for j in ordered[first:])
        for rel,h in freeze['hashes'].items():assert sha256((p/rel).read_bytes()).hexdigest()==h
    recoveries=0

    def verify_trace(t,program):
        assert t['program_ref']==program.ref and len(t['observations'])==len(program.nodes)
        rows=[(n,o) for n,o in zip(program.nodes,t['observations']) if n.role=='decision' and o['eligible']]
        assert all(n.id==o['check_id'] for n,o in zip(program.nodes,t['observations']))
        mass=sum((Fraction(n.weight_numerator,n.weight_denominator) for n,o in rows),Fraction())
        lo=Fraction();hi=Fraction();values=[]
        for n,o in rows:
            w=Fraction(n.weight_numerator,n.weight_denominator);f=o.get('fulfillment_score') if o['valid'] else None
            if f is None:
                hi+=w;values.append(None)
            else:
                assert type(f) in (int,float) and 0<=f<=1
                lo+=w*Fraction(str(f));hi+=w*Fraction(str(f));values.append(f)
                assert o['binary_status']==('pass' if f==1 else 'fail')
                assert o['status']=={'yes':'pass','no':'fail','partial':'partial'}[category(Fraction(str(f)))]
        low,high=(lo/mass,hi/mass) if mass else (None,None)
        unknown_app=any(o.applicability=='unknown' for o in program.outcomes)
        if unknown_app:low,high=Fraction(0),Fraction(1)
        grade=None if low is None or unknown_app or category(low)!=category(high) else category(low)
        binary=None if not values or None in values or unknown_app else 'yes' if all(f==1 for f in values) else 'no' if all(f<1 for f in values) else 'partial'
        expected=binary if program.scoring_mode=='binary' else grade
        assert t['label']==expected and t['resolved']==(expected is not None)
        assert t['fulfillment']['binary_label']==binary and t['fulfillment']['fulfillment_label']==grade
        assert t['fulfillment']['lower']==(float(low) if low is not None else None)
        assert t['fulfillment']['upper']==(float(high) if high is not None else None)

    def verify_report(rep,program,target):
        nonlocal recoveries
        assert rep['draws']==len(rep['traces'])
        for t in rep['traces']:verify_trace(t,program)
        assert rep['agreement']==sum(t['label']==target for t in rep['traces'])/rep['draws']
        assert rep['coverage']==sum(t['resolved'] for t in rep['traces'])/rep['draws']
        if 'raw_measurements' not in rep:return
        raw=rep['raw_measurements'];verify_report(raw,program,target);changes=[]
        for i,(a,b) in enumerate(zip(raw['traces'],rep['traces'])):
            for j,(before,after) in enumerate(zip(a['observations'],b['observations'])):
                if before!=after:changes.append((i,j,before,after))
        recovery=rep['transport_recovery']
        if recovery:
            recoveries+=1
            first=next((i,j) for i,t in enumerate(raw['traces']) for j,o in enumerate(t['observations']) if o['event']=='transport_failure')
            assert len(changes)==1 and changes[0][:2]==first
            i,j,before,after=changes[0];assert after['attempts'][0]==before and len(after['attempts'])==2
            assert jobs[before['execution_ref']]['outcome']=='transport_error'
            assert jobs[after['attempts'][1]['execution_ref']]['slot']==recovery['slot']+'/'+before['check_id']
            assert after['completion_tokens']==sum(o['completion_tokens'] for o in after['attempts'])
        else:assert not changes
        for mode in ('binary','fulfillment'):
            assert rep['counterfactual_agreement'][mode]==sum(t['fulfillment'][mode+'_label']==target for t in rep['traces'])/rep['draws']

    policy=NoAuditRobustPolicy(**m['policy']);components={};counts=Counter()
    for i,c in enumerate(m['cases']):
        prep_path=p/'prepared'/f'{i}.json'
        if not prep_path.exists():continue
        prep=json.loads(prep_path.read_text());assert 'seed_audit' not in prep
        assert sum(j['case_id']=='prepare/'+c['id'] for j in ordered)<=1
        for arm in m['arms']:
            path=p/'frozen'/arm/f'{i}.json'
            if not path.exists():continue
            bundle=json.loads(path.read_text())
            if 'error' in bundle:counts['invalid_seed']+=1;continue
            validate_program_leaves(bundle);saved=bundle['nodes']['leaf:'+c['id']]['result']
            common=restore_program(prep['seed']);assert saved['seed']==export_program(variant(common,arm))
            for candidate in saved['candidates'].values():
                program=restore_program(candidate)
                assert program.weight_roots==common.weight_roots and program.scoring_mode==arm
                assert program.to_dict()['requirements']==c['original']['program']['requirements']
                assert program.to_dict()['outcomes']==c['original']['program']['outcomes']
                audit=candidate['audit'];assert audit['performed'] is False and audit['status']=='disabled' and 'accepted' not in audit
                for tier in ('screen','confirmation'):
                    if candidate.get(tier):verify_report(candidate[tier],program,c['target'])
                if candidate.get('confirmation'):
                    assert candidate['confirmation']['draws']==5 and candidate['screen']['agreement']==candidate['screen']['coverage']==1
            counts[arm+'/changed']+=saved['seed']['program_ref']!=saved['selected']['program_ref']
            row=r['cases'].get(c['id'],{}).get(arm,{})
            if 'selected' not in row.get('final',{}):continue
            for which,report in row['final'].items():
                verify_report(report,restore_program(saved[which]),c['target']);assert report['draws']==5
            if row['support_status']=='locally_robust':
                selected=saved['candidates'][saved['selected']['program_ref']]
                assert policy.assess(selected['confirmation'])['qualified'] and policy.assess(row['final']['selected'])['qualified']
            components.setdefault(c['id'],{})[arm]={'instruction':c['instruction'],'reference':c['target'],
                'seed':saved['seed'],'selected':saved['selected'],'final':row['final'],'status':row['support_status']}
    if replay:
        before=deepcopy(r);save_json(p/'replay_before_results.json',before)
        def forbidden(cap):raise AssertionError('Replay tried a model call')
        again=json.loads(json.dumps(execute(p,m,forbidden,forbidden,progress=False)))
        assert again['cases']==before['cases'] and again['budget']==before['budget'] and again['status']==before['status']
    ratios={};final_measured=r['status']=='completed'
    for arm in m['arms']:
        reports=[r['cases'].get(c['id'],{}).get(arm,{}).get('final',{}).get('selected',{}) for c in m['cases']]
        ratios[arm]={'effective_accurate_repeatable':sum(v.get('agreement')==v.get('coverage')==1 for v in reports) if final_measured else None,
            'raw_accurate_repeatable':sum(v.get('raw_measurements',{}).get('agreement')==v.get('raw_measurements',{}).get('coverage')==1 for v in reports) if final_measured else None,
            'correct_draws':round(sum(v.get('agreement',0)*5 for v in reports)) if final_measured else None, 'cases':len(reports)}
    report={'status':r['status'],'calls':budget['calls'],'charged_completion_tokens':budget['completion_tokens_or_reserved'],
        'weight_and_score_arithmetic':True,'observer_label_mode_weight_isolation':True,'shared_seed_parity':True,
        'frozen_before_final':'final' in phases,'unique_logical_slots':True,'no_auditor_or_model_readout':True,
        'recovery_records_verified':recoveries,'selection_counts':dict(counts),'zero_call_replay':replay,'final_accuracy_measured':final_measured,
        'frozen_scopes':len(list((p/'frozen').rglob('*.json'))),'accurate_repeatable':ratios}
    save_json(p/'component_analysis.json',components);save_json(p/'protocol_verification.json',report)
    print(json.dumps(report,indent=2));return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--replay',action='store_true');args=parser.parse_args();analyze(args.directory,args.replay)
