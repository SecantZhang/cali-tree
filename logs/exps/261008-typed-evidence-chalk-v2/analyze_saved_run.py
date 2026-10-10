"""Analyze recorded typed programs and replay completed work without a provider."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile

from critical.core.decision.artifacts import save_json
from critical.core.decision.robust.models import restore_program
from critical.core.decision.robust.refinement import validate_refinement
from critical.core.optimization.program.robust.typed import nested_nodes, apply_typed_transaction
from run.calitree_typed_evidence import execute

OUTPUT=Path(__file__).resolve().parent


def main():
    m=json.loads((OUTPUT/'manifest.json').read_text());r=json.loads((OUTPUT/'results.json').read_text())
    b=json.loads((OUTPUT/'budget.json').read_text());seed=restore_program(m['seed']);original=restore_program(m['case']['broad_seed'])
    for rel,h in m['code_hashes'].items():
        assert sha256((OUTPUT/'source_snapshot'/rel).read_bytes()).hexdigest()==h
        assert sha256(Path(rel).read_bytes()).hexdigest()==h, 'Use the frozen analysis launcher after source changes'
    for key,p in m['case']['evidence'].items():assert sha256(Path(p).read_bytes()).hexdigest()==m['case']['image_hashes'][key]
    jobs={p.stem:json.loads(p.read_text()) for p in (OUTPUT/'jobs').glob('*.json')}
    ordered=[jobs[k] for k in b['attempted_slots'] if k in jobs];seen_final=False
    for j in ordered:
        if j['phase']=='final':seen_final=True
        if seen_final:assert j['phase']=='final' and j['stage']=='check'
        if j['stage'] in ('compile_typed','audit','check','visual_discovery'):
            assert 'reference_label' not in j['payload'] and 'feedback' not in j['payload']
        if j['stage']=='check':
            assert sum(x['type']=='image' for x in j['media_identity'])==(2 if j['payload']['node']['role']=='support' else 0)
            if j['outcome']=='completed' and 'observation_validation_error' not in j:
                assert j['parsed']['used_dependency_ids']==j['payload']['node']['dependencies']
    assert b['calls']<=300 and b['completion_tokens_or_reserved']<=384000
    assert sum(j['case_id'].startswith('prepare/') for j in jobs.values())<=2
    rows=[]
    for arm in m['arms']:
        path=OUTPUT/'frozen'/f'{arm}.json'
        local=json.loads(path.read_text()) if path.exists() else {}
        row={'arm':arm,'result':r['arms'].get(arm,{})}
        if 'nodes' in local:
            saved=next(iter(local['nodes'].values()))['result'];selected=restore_program(saved['selected'])
            validate_refinement(selected,original)
            for c in saved['candidates'].values():restore_program(c)
            history=[h for h in saved['lineage'] if 'transaction' in h]
            for h in history:
                if h.get('construction'):
                    parent=restore_program(saved['candidates'][h['parent']]);applied=apply_typed_transaction(parent,h['transaction'])
                    assert applied.program.ref==h['program_ref'] and applied.details['parent_ref']==h['parent']
            candidate=saved['candidates'].get(selected.ref,{})
            row.update(seed_ref=seed.ref,selected_ref=selected.ref,program_changed=selected.ref!=seed.ref,
                selected_checks=selected.to_dict()['nodes'],inserted_nested_checks=nested_nodes(selected,seed),
                selected_audit=candidate.get('audit',{}),confirmation=candidate.get('confirmation',{}),
                history=history,diagnostic_only=[ref for ref,c in saved['candidates'].items() if 'diagnostic' in c])
        rows.append(row)
    usage={'calls':b['calls'],'charged_completion_tokens':b['completion_tokens_or_reserved'],
        'reported_completion_tokens':sum(int(j.get('response',{}).get('completionTokens',0)) for j in jobs.values()),
        'input_tokens':b['input_tokens'],'outcomes':dict(Counter(j['outcome'] for j in jobs.values())),
        'stages':dict(Counter(j['stage'] for j in jobs.values())),'returned_models':r.get('returned_models',[])}
    save_json(OUTPUT/'component_analysis.json',rows);save_json(OUTPUT/'usage_summary.json',usage)
    lines=['# Typed evidence chalk pilot: saved-data analysis','',m['scope'],'',
        'Checkpoint: '+m['checkpoint_commit'],'Reference: `partial`. Status: '+r['status'],'',
        '| Arm | Seed → selected matches / 5 | Selected usable / 5 | Minimum reported confidence | Checks | Inserted nested checks | Status |',
        '|---|---:|---:|---:|---:|---|---|']
    for row in rows:
        final=row['result'].get('final',{});a=final.get('seed',{});c=final.get('selected',{})
        confidences=[o['confidence'] for t in c.get('traces',[]) for o in t['observations'] if o['queried'] and o['confidence'] is not None]
        lines.append('| '+' | '.join([row['arm'],f"{round(5*a.get('agreement',0))} → {round(5*c.get('agreement',0))}",
            str(round(5*c.get('coverage',0))),str(min(confidences)) if confidences else 'unavailable',
            str(len(row.get('selected_checks',[]))),', '.join(row.get('inserted_nested_checks',[])) or 'none',
            row['result'].get('support_status','unattempted')])+' |')
    lines+=['','Matches mean reference-label agreement; usable answers include wrong labels. Confidence is generated self-report. '
        'Five repeats are measurements within one previously observed case, not independent cases. Actual added-check execution and accuracy are separate outcomes.','']
    for row in rows:
        stats=row['result'].get('final',{}).get('selected',{}).get('nodes',{})
        lines+=['## '+row['arm'],'','Acceptance: '+json.dumps(row['result'].get('acceptance',{})),
            'Selected audit: '+json.dumps(row.get('selected_audit',{})),
            'Complete confirmation: '+json.dumps({k:row.get('confirmation',{}).get(k) for k in ('draws','agreement','coverage','confidence_pass')}),'',
            '| Check | Role / evidence context | Question | Final states | Consistency |',
            '|---|---|---|---|---:|']
        for n in row.get('selected_checks',[]):
            s=stats.get(n['id'],{})
            lines.append('| '+' | '.join([n['id'],n['role']+' / '+str(n['dependencies']),n['question'].replace('|','/'),
                json.dumps(s.get('states',{})),str(s.get('consistency'))])+' |')
        lines+=['','### Typed edit history','']
        for h in row.get('history',[]):
            lines+=['- '+h['transaction']['reason'], '  Operations: '+', '.join(a['operation'] for a in h['transaction']['actions']),
                    '  Result: '+json.dumps({k:v for k,v in h.items() if k not in ('transaction','construction','parent')}),
                    '  Constructed hashes: '+json.dumps({k:h.get('construction',{}).get(k) for k in ('parent_ref','child_ref')})]
    lines+=['','## Preparation','',json.dumps(r.get('preparation',{}),indent=2),'','## Usage','',json.dumps(usage,indent=2),
        '','Semantic audit is evidence, not proof. Supporting observations do not earn completion credit. '
        'Final outcomes never trigger further optimization. Unvisited/unresolved checks and failure slots remain explicit.']
    (OUTPUT/'analysis.md').write_text('\n'.join(lines)+'\n')
    verification={'sources_verified':True,'images_verified':True,'program_hashes_verified':True,
        'typed_constructions_replayed':True,'label_isolation':True,'media_and_dependencies_verified':True,
        'final_isolation':True,'budget_verified':True,'zero_call_replay':None}
    if r['status']=='completed':
        with tempfile.TemporaryDirectory(prefix='calitree-typed-replay-') as temporary:
            clone=Path(temporary)/'run';shutil.copytree(OUTPUT,clone,ignore=shutil.ignore_patterns('source_snapshot','llm-histories.log','console.log'))
            contacted=[]
            def forbidden(cap):contacted.append(cap);raise AssertionError('Replay must not call a provider')
            replay=execute(clone,m,forbidden)
            assert not contacted and replay['budget']['calls']==b['calls'] and replay['arms']==r['arms']
        verification['zero_call_replay']=True
    save_json(OUTPUT/'protocol_verification.json',verification)
    print(json.dumps({'status':r['status'],'usage':usage,'verification':verification}))


if __name__=='__main__':main()
