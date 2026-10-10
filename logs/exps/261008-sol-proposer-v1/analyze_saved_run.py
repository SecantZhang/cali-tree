"""Verify and explain the saved proposer comparison without new provider calls."""
from collections import Counter,defaultdict
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile

from critical.core.decision.artifacts import save_json
from critical.core.decision.robust.models import restore_program
from critical.core.decision.robust.refinement import validate_refinement
from critical.core.optimization.program.robust.typed import apply_typed_transaction,nested_nodes
from run.calitree_sol_proposer import execute

OUTPUT=Path(__file__).resolve().parent


def main():
    m=json.loads((OUTPUT/'manifest.json').read_text());r=json.loads((OUTPUT/'results.json').read_text());b=json.loads((OUTPUT/'budget.json').read_text())
    for rel,h in m['code_hashes'].items():
        assert sha256((OUTPUT/'source_snapshot'/rel).read_bytes()).hexdigest()==h
        assert sha256(Path(rel).read_bytes()).hexdigest()==h,'Restore frozen runtime: '+rel
    for rel,h in m['source_hashes'].items():assert sha256((Path(m['source_directory'])/rel).read_bytes()).hexdigest()==h
    assert len(m['cases'])==3 and len({c['group'] for c in m['cases']})==3
    assert Counter(c['target'] for c in m['cases'])=={'yes':1,'no':1,'partial':1}
    jobs={p.stem:json.loads(p.read_text()) for p in (OUTPUT/'jobs').glob('*.json')}
    ordered=[jobs[k] for k in b['attempted_slots']];final=False
    for j in ordered:
        if j['phase']=='final':final=True
        if final:assert j['phase']=='final' and j['stage']=='check'
        if j.get('route'):
            assert j['route']=='sol-proposer' and j['stage']=='propose_typed' and j['case_id'].startswith('sol-proposer/')
            assert j['requested_identity']==m['routes']['sol-proposer'] and j['max_tokens']==4096
        if j['stage'] in ('check','audit','visual_discovery'):
            assert 'reference_label' not in j['payload'] and 'feedback' not in j['payload']
        if j['stage']=='check':
            assert sum(v['type']=='image' for v in j['media_identity'])==(2 if j['payload']['node']['role']=='support' else 0)
            if j['outcome']=='completed' and 'observation_validation_error' not in j:
                assert j['parsed']['used_dependency_ids']==j['payload']['node']['dependencies']
    assert sum(j.get('route')=='sol-proposer' for j in ordered)<=45
    assert b['calls']<=900 and b['completion_tokens_or_reserved']<=1152000
    rows=[]
    for i,c in enumerate(m['cases']):
        seed,original=restore_program(c['seed']),restore_program(c['original']);validate_refinement(seed,original)
        for key,path in c['evidence'].items():assert sha256(Path(path).read_bytes()).hexdigest()==c['image_hashes'][key]
        for arm in m['arms']:
            local=json.loads((OUTPUT/'frozen'/arm/f'{i}.json').read_text());saved=next(iter(local['nodes'].values()))['result']
            selected=restore_program(saved['selected']);validate_refinement(selected,original)
            counts=Counter();history=saved['lineage'][:-1]
            for item in history:
                if item.get('error'):counts['structural_or_transport_rejection']+=1
                elif item.get('duplicate'):counts['duplicate']+=1
                elif item.get('audit',{}).get('accepted'):counts['semantic_accepted']+=1
                elif item.get('audit',{}).get('accepted') is False:counts['semantic_rejected']+=1
                if item.get('construction'):
                    parent=restore_program(saved['candidates'][item['parent']]);applied=apply_typed_transaction(parent,item['transaction'])
                    assert applied.program.ref==item['program_ref']
            candidate=saved['candidates'][selected.ref];result=r['cases'][c['id']][arm]
            trace=result['final']['selected']['traces']
            observations=[o for t in trace for o in t['observations'] if o['queried']]
            values=[o['confidence'] for o in observations if o['confidence'] is not None]
            rows.append({'case':c['instruction'],'target':c['target'],'arm':arm,'proposal_counts':dict(counts),
                'proposal_transactions':len(history),'empty_proposal_responses':sum(j['case_id']==arm+'/'+c['id'] and j['stage']=='propose_typed'
                    and (j.get('parsed') or {}).get('transactions')==[] for j in ordered),
                'selected_ref':selected.ref,'nodes':selected.to_dict()['nodes'],'nested_checks':nested_nodes(selected,seed),
                'minimum_confidence':min(values) if values else None,'missing_confidence':sum(o['confidence'] is None for o in observations),
                'confirmation':{k:v for k,v in candidate.get('confirmation',{}).items() if k not in ('traces','nodes')},
                'result':result,'audit':candidate.get('audit'),'rounds':saved['lineage'][-1].get('search_schedule'),
                'direct_final_failures':dict(Counter(o['failure'] for o in observations if o.get('failure')))})
    save_json(OUTPUT/'component_analysis.json',rows)
    models=defaultdict(lambda:Counter())
    for j in ordered:
        model=m['routes'][j['route']]['model'] if j.get('route') else m['primary_identity']['model']
        models[model]['calls']+=1;models[model]['reported_input_tokens']+=j.get('response',{}).get('promptTokens',0)
        models[model]['reported_completion_tokens']+=j.get('response',{}).get('completionTokens',0)
        models[model]['reserved_failed_completion_tokens']+=j['max_tokens'] if j['outcome'] in ('transport_error','interrupted') else 0
    usage={}
    for model,count in models.items():
        price=m['pricing_per_million_tokens'][model]
        usage[model]={**count,'estimated_uncached_reported_usage_usd':round((count['reported_input_tokens']*price['input']+
            count['reported_completion_tokens']*price['output'])/1e6,4)}
    save_json(OUTPUT/'usage_by_model.json',{'models':usage,'pricing':m['pricing_per_million_tokens'],
        'note':'List-price estimate on reported tokens only. Cached-input discounts and unknown usage on failed requests are not measured; this is not an invoice.'})
    summary={}
    for arm in m['arms']:
        group=[x for x in rows if x['arm']==arm];counts=Counter()
        for x in group:counts.update(x['proposal_counts'])
        summary[arm]={'proposal_transactions':sum(x['proposal_transactions'] for x in group),**dict(counts),
            'seed_final_matches':sum(round(x['result']['final']['seed']['agreement']*5) for x in group),
            'selected_final_matches':sum(round(x['result']['final']['selected']['agreement']*5) for x in group),
            'selected_resolved':sum(round(x['result']['final']['selected']['coverage']*5) for x in group),
            'locally_robust':sum(x['result']['support_status']=='locally_robust' for x in group)}
    save_json(OUTPUT/'summary.json',summary)
    lines=['# Proposer model comparison: saved-data analysis','',m['scope'],'',
        '**Both arms used Luna for all visual checks, feedback, discovery and semantic review. Only Sol-arm proposal requests used Sol 6.1 with medium reasoning.**',
        '', '| Proposer | Transactions proposed | Semantically approved | Seed → selected reference matches / 15 | Selected resolved / 15 | Robust cases / 3 |',
        '|---|---:|---:|---:|---:|---:|']
    for arm,s in summary.items():lines.append(f"| {arm} | {s['proposal_transactions']} | {s.get('semantic_accepted',0)} | {s['seed_final_matches']} → {s['selected_final_matches']} | {s['selected_resolved']} | {s['locally_robust']} |")
    lines+=['','A transaction approval is the label-blind reviewer’s opinion about meaning preservation, not proof of correctness. '
        'Reference matches count five fresh draws per case; repeats are not additional cases. '
        'Resolved means a usable answer, whether correct or wrong. '
        'Mandatory insertion remains an experimental restriction. A valid existing-check repair can remain an intermediate without qualifying.',
        '', '| Case | Proposer | Seed → selected matches / 5 | Selected resolved / 5 | Lowest confidence / missing values | Checks | Result |',
        '|---|---|---:|---:|---|---:|---|']
    for x in rows:
        result=x['result'];a=result['final']['seed'];s=result['final']['selected'];v=x['minimum_confidence']
        lines.append('| '+' | '.join([x['case'],x['arm'],f"{round(a['agreement']*5)} → {round(s['agreement']*5)}",str(round(s['coverage']*5)),
            (f'{v:.2f}' if v is not None else 'missing')+f" / {x['missing_confidence']}",str(result['checks']),result['support_status']])+' |')
    lines+=['','Self-reported confidence is not calibrated probability. Missing confidence fails the frozen gate. '
        '`structural_failure` here also covers an added check that was not reached in at least three final draws; it does not necessarily mean an invalid graph.',
        '', '## Measured cost','',json.dumps(usage,indent=2),'',
        'These are uncached list-price estimates on reported tokens, excluding unknown failed-request input/output usage and cache discounts. '
        'All completion charges and reservations remain in budget.json. Returned identities: '+json.dumps(r['returned_models'])+'.',
        '', '## Per-case diagnostics']
    for x in rows:
        lines+=['','### '+x['case']+' / '+x['arm'],'',
            'Proposals: '+json.dumps(x['proposal_counts'])+'.',
            'Search rounds: '+json.dumps(x['rounds'])+'. Stop: '+x['result']['stop_reason']+'.',
            'Final rejection reasons: '+json.dumps(x['result']['acceptance']['reasons'])+'.',
            'Direct final-call failures: '+json.dumps(x['direct_final_failures'])+'.',
            '| Check | Question | Evidence dependencies | Final states |', '|---|---|---|---|']
        for node in x['nodes']:
            states=x['result']['final']['selected']['nodes'][node['id']]['states']
            lines.append('| '+' | '.join([node['id'],node['question'].replace('|','/'),str(node['dependencies']),json.dumps(states)])+' |')
    (OUTPUT/'analysis.md').write_text('\n'.join(lines)+'\n')
    contacted=[]
    def forbidden(cap):contacted.append(cap);raise AssertionError('Saved replay must not contact any provider')
    with tempfile.TemporaryDirectory(prefix='sol-proposer-replay-') as tmp:
        clone=Path(tmp)/'run';shutil.copytree(OUTPUT,clone,ignore=shutil.ignore_patterns('source_snapshot','llm-histories.log','console.log','textgrad-v3'))
        replay=execute(clone,m,forbidden,forbidden)
        assert not contacted and replay['cases']==r['cases'] and replay['budget']['calls']==b['calls']
    verification={'source_runtime_image_hashes':True,'original_requirements_preserved':True,'typed_edits_replay':True,
        'proposer_only_sol_routing':True,'label_isolation':True,'all_selections_before_finals':True,'budgets':True,'zero_call_replay':True}
    save_json(OUTPUT/'protocol_verification.json',verification)
    print(json.dumps({'summary':summary,'usage':usage,'verification':verification}))


if __name__=='__main__':main()
