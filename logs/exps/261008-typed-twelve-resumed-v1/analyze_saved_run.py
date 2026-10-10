"""Analyze all frozen cases and verify complete replay without model calls."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile

from critical.core.decision.artifacts import save_json,restore_program as restore_legacy
from critical.core.decision.robust.models import restore_program
from critical.core.decision.robust.refinement import validate_refinement
from critical.core.optimization.program.robust.typed import apply_typed_transaction,nested_nodes
from run.calitree_typed_twelve import execute,bridge_reference

OUTPUT=Path(__file__).resolve().parent


def main():
    m=json.loads((OUTPUT/'manifest.json').read_text());r=json.loads((OUTPUT/'results.json').read_text());b=json.loads((OUTPUT/'budget.json').read_text())
    assert len(m['cases'])==12 and len({c['group'] for c in m['cases']})==12
    assert Counter(c['target'] for c in m['cases'])=={'yes':4,'partial':4,'no':4}
    for rel,h in m['code_hashes'].items():
        assert sha256((OUTPUT/'source_snapshot'/rel).read_bytes()).hexdigest()==h
        assert sha256(Path(rel).read_bytes()).hexdigest()==h,'Use frozen runtime after source changes: '+rel
    jobs={p.stem:json.loads(p.read_text()) for p in (OUTPUT/'jobs').glob('*.json')}
    ordered=[jobs[k] for k in b['attempted_slots'] if k in jobs];final=False
    for j in ordered:
        if j['phase']=='final':final=True
        if final:assert j['phase']=='final' and j['stage']=='check'
        if j['stage'] in ('compile_typed','audit','check','visual_discovery'):
            assert 'reference_label' not in j['payload'] and 'feedback' not in j['payload']
        if j['stage']=='check':
            assert sum(x['type']=='image' for x in j['media_identity'])==(2 if j['payload']['node']['role']=='support' else 0)
            if j['outcome']=='completed' and 'observation_validation_error' not in j:
                assert j['parsed']['used_dependency_ids']==j['payload']['node']['dependencies']
    assert b['calls']<=3600 and b['completion_tokens_or_reserved']<=4608000
    rows=[]
    for i,c in enumerate(m['cases']):
        original=restore_program(c['original']);legacy=restore_legacy(c['legacy_seed'])
        assert bridge_reference(c['legacy_seed'])==original
        assert original.requirements==legacy.requirements and original.outcomes==legacy.outcomes
        for key,path in c['evidence'].items():assert sha256(Path(path).read_bytes()).hexdigest()==c['image_hashes'][key]
        prepared=json.loads((OUTPUT/'prepared'/f'{i}.json').read_text()) if (OUTPUT/'prepared'/f'{i}.json').exists() else {}
        if 'seed' in prepared:
            seed=restore_program(prepared['seed']);validate_refinement(seed,original)
        else:seed=None
        for arm in m['arms']:
            row={'case_id':c['id'],'instruction':c['instruction'],'target':c['target'],'arm':arm,
                 'result':r['cases'].get(c['id'],{}).get(arm,{}),'preparation_error':prepared.get('error')}
            path=OUTPUT/'frozen'/arm/f'{i}.json';local=json.loads(path.read_text()) if path.exists() else {}
            if 'nodes' in local:
                saved=next(iter(local['nodes'].values()))['result'];selected=restore_program(saved['selected'])
                validate_refinement(selected,original)
                for candidate in saved['candidates'].values():restore_program(candidate)
                history=[h for h in saved['lineage'] if 'transaction' in h]
                for h in history:
                    if h.get('construction'):
                        parent=restore_program(saved['candidates'][h['parent']]);applied=apply_typed_transaction(parent,h['transaction'])
                        assert applied.program.ref==h['program_ref']
                summary=saved['lineage'][-1];schedule=summary.get('search_schedule',{})
                assert 0<=schedule.get('rounds_completed',0)<=schedule.get('rounds_started',0)<=15
                row.update(seed_ref=seed.ref,selected_ref=selected.ref,program_changed=seed.ref!=selected.ref,
                    nodes=selected.to_dict()['nodes'],audit=saved['candidates'][selected.ref].get('audit'),
                    history=history,search_schedule=schedule,search_stop=saved['stop_reason'],search_status=saved['status'],nested_checks=nested_nodes(selected,seed),
                    confirmation=saved['candidates'][selected.ref].get('confirmation',{}))
            rows.append(row)
    usage={'calls':b['calls'],'completion_tokens_charged':b['completion_tokens_or_reserved'],
        'completion_tokens_reported':sum(int(j.get('response',{}).get('completionTokens',0)) for j in jobs.values()),
        'input_tokens':b['input_tokens'],'outcomes':dict(Counter(j['outcome'] for j in jobs.values())),
        'stages':dict(Counter(j['stage'] for j in jobs.values())),'returned_models':r.get('returned_models',[])}
    save_json(OUTPUT/'component_analysis.json',rows);save_json(OUTPUT/'usage_summary.json',usage)
    class_metrics={}
    for arm in m['arms']:
        class_metrics[arm]={}
        for label in ('yes','partial','no'):
            group=[x for x in rows if x['arm']==arm and x['target']==label]
            class_metrics[arm][label]={'cases':len(group),'mean_selected_agreement':sum(x['result'].get('final',{}).get('selected',{}).get('agreement',0) for x in group)/len(group),
                'mean_selected_coverage':sum(x['result'].get('final',{}).get('selected',{}).get('coverage',0) for x in group)/len(group),
                'locally_robust':sum(x['result'].get('support_status')=='locally_robust' for x in group), 'finalized_cases':sum(bool(x['result'].get('final',{}).get('selected')) for x in group)}
            if not class_metrics[arm][label]['finalized_cases']:
                class_metrics[arm][label].update(mean_selected_agreement=None,mean_selected_coverage=None,locally_robust=None)
    save_json(OUTPUT/'class_metrics.json',class_metrics)
    lines=['# Twelve-case saved-data analysis','',m['scope'],'','Status: '+r['status'],'',
        '| Case / reference | Arm | Seed → selected matches / 5 | Usable / 5 | Completed rounds | Checks | Status |',
        '|---|---|---:|---:|---:|---:|---|']
    for x in rows:
        final=x['result'].get('final',{});a=final.get('seed',{});s=final.get('selected',{})
        lines.append('| '+' | '.join([x['instruction']+' / '+x['target'],x['arm'],
            f"{round(a.get('agreement',0)*5)} → {round(s.get('agreement',0)*5)}" if final else "pending",str(round(s.get('coverage',0)*5)) if final else "pending",
            str(x.get('search_schedule',{}).get('rounds_completed','unavailable')),str(len(x.get('nodes',[]))),
            x['result'].get('support_status',x.get('search_status') or ('preparation_failed' if x.get('preparation_error') else x['result'].get('phase','unattempted')))])+' |')
    lines+=['','Pending final measurements are unavailable, not zero accuracy. Missing/invalid cases will remain in the full denominator of a completed comparison. Five repeats are measurements within cases, not independent cases. Confidence is self-report and atomic consistency is not correctness.','',
        '## Class metrics','',json.dumps(class_metrics,indent=2),'','## Usage','',json.dumps(usage,indent=2)]
    for x in rows:
        lines+=['','## '+x['case_id']+' / '+x['arm'],'','Acceptance: '+json.dumps(x['result'].get('acceptance',{})),
            'Stop: '+str(x['result'].get('stop_reason',x.get('search_stop') or x.get('preparation_error'))),'Audit: '+json.dumps(x.get('audit',{})),
            '| Check | Question | Evidence context | Final states | Consistency |','|---|---|---|---|---:|']
        stats=x['result'].get('final',{}).get('selected',{}).get('nodes',{})
        for n in x.get('nodes',[]):
            st=stats.get(n['id'],{});lines.append('| '+' | '.join([n['id'],n['question'].replace('|','/'),str(n['dependencies']),json.dumps(st.get('states',{})),str(st.get('consistency'))])+' |')
    (OUTPUT/'analysis.md').write_text('\n'.join(lines)+'\n')
    verified={'source_image_program_hashes':True,'legacy_bridge_preserves_coverage':True,'typed_constructions':True,
        'label_media_dependency_isolation':True,'all_selections_before_finals':True,'budgets':True,'round_counts':True,'zero_call_replay':None}
    if r['status']=='completed':
        with tempfile.TemporaryDirectory(prefix='calitree-twelve-replay-') as temporary:
            clone=Path(temporary)/'run';shutil.copytree(OUTPUT,clone,ignore=shutil.ignore_patterns('source_snapshot','llm-histories.log','console.log'))
            contacted=[]
            def forbidden(cap):contacted.append(cap);raise AssertionError('Replay must not call a provider')
            replay=execute(clone,m,forbidden)
            assert not contacted and replay['budget']['calls']==b['calls'] and replay['cases']==r['cases']
        verified['zero_call_replay']=True
    save_json(OUTPUT/'protocol_verification.json',verified)
    print(json.dumps({'status':r['status'],'usage':usage,'verification':verified}))


if __name__=='__main__':main()
