"""Readable comparison derived only from frozen artifacts and final traces."""
from collections import Counter
import json
from pathlib import Path

OUTPUT=Path(__file__).resolve().parent


def main():
    manifest=json.loads((OUTPUT/'manifest.json').read_text())
    result=json.loads((OUTPUT/'results.json').read_text())
    budget=json.loads((OUTPUT/'budget.json').read_text())
    deviations=json.loads((OUTPUT/'protocol_deviations.json').read_text())
    affected=set(deviations.get('affected_scopes',[]))
    names=['White DVD','Closed jacket','Pencil drawing','Helmet','Basketball background','Mug position',
           'Book position','Paper in cup','Comic style','Chalk drawing','Frog in toilet','Brown cylinder']
    rows=[]
    for i,case in enumerate(manifest['cases']):
        for arm in manifest['arms']:
            row=result['cases'].get(case['id'],{}).get(arm,{})
            final=row.get('final',{});seed,selected=final.get('seed',{}),final.get('selected',{})
            local=json.loads((OUTPUT/'frozen'/arm/f'{i}.json').read_text())
            saved=next(iter(local.get('nodes',{}).values()),{}).get('result',{})
            candidate=saved.get('candidates',{}).get(saved.get('selected',{}).get('program_ref'),{})
            observations=[o for trace in selected.get('traces',[]) for o in trace['observations'] if o['queried']]
            confidence=[o['confidence'] for o in observations if o['confidence'] is not None]
            entry={'case_id':case['id'],'name':names[i],'arm':arm,'target':case['target'],
                'seed':seed,'selected':selected,'status':row.get('support_status','pending'),
                'excluded':arm+'/'+case['id'] in affected,'audit':candidate.get('audit',{}),
                'rounds':(row.get('search_schedule') or {}).get('rounds_completed'),
                'checks':row.get('checks',0),'minimum_confidence':min(confidence) if confidence else None,
                'missing_confidence':sum(o['confidence'] is None for o in observations),
                'direct_failures':dict(Counter(o['failure'] for o in observations if o.get('failure'))),
                'reasons':row.get('acceptance',{}).get('reasons',[]),'error':row.get('error'),
                'usage':row.get('usage',{}),'nested_checks':row.get('nested_checks',[])}
            rows.append(entry)
    completed=result['status']=='completed'
    summary={}
    for arm in manifest['arms']:
        group=[r for r in rows if r['arm']==arm]
        summary[arm]={'cases':12,'measured_selected_cases':sum(bool(r['selected']) for r in group),
            'verified_locally_robust':sum(r['status']=='locally_robust' and not r['excluded'] for r in group),
            'excluded_scopes':sum(r['excluded'] for r in group),
            'preparation_failures':sum(bool(r['error']) for r in group),
            'final_seed_matches':sum(round(r['seed'].get('agreement',0)*5) for r in group),
            'final_selected_matches':sum(round(r['selected'].get('agreement',0)*5) for r in group),
            'final_seed_resolved':sum(round(r['seed'].get('coverage',0)*5) for r in group),
            'final_selected_resolved':sum(round(r['selected'].get('coverage',0)*5) for r in group)}
    lines=['# Twelve-case typed optimizer: saved final comparison','',
        'Status: '+result['status']+'. Twelve previously observed local fitting cases; four per reference class. '
        'Repeats are measurements within cases, not additional cases or evidence of generalization.',
        '', '## Definitions', '',
        '- Matches: final predictions equal to the reference label, out of five fresh draws.',
        '- Resolved: draws that produced a usable final label, whether correct or wrong.',
        '- Confidence: lowest numeric self-reported confidence across executed checks; missing values are counted separately. It is not calibrated probability.',
        '- Checks: saved program size; skipped or failed calls can lower actual executed checks.',
        '- Robust: approved semantic audit, qualifying complete confirmation, and all frozen final gates. Nested-required additionally needs an executed added evidence-context check.',
        '', '## Raw measurements', '',
        '| Method | Seed → selected matches / 60 | Seed → selected resolved / 60 | Verified robust cases |',
        '|---|---:|---:|---:|']
    for arm,s in summary.items():
        lines.append(f"| {arm} | {s['final_seed_matches']} → {s['final_selected_matches']} | {s['final_seed_resolved']} → {s['final_selected_resolved']} | {s['verified_locally_robust']} |")
    lines+=['','The raw denominators retain all twelve cases, including failed preparation. '
        +('All final measurements are complete.' if completed else 'Pending final draws are not an accuracy result; raw totals above are partial.'),
        '', '**Protocol caveat:** the first continuation repeated seven nested-mug proposal slots because replay changed a saved failure diagnostic. '
        'All costs remain charged. That scope is excluded from valid robustness claims and the paired comparison below; the raw measurements retain it for transparency. '
        'The second continuation preserves historical diagnostics and guards inherited logical slots before any new request.',
        '', '## Paired comparison excluding the affected mug case', '',
        'Both methods use the same remaining eleven cases; the two invalid-seed cases remain failures. This subset is no longer class-balanced.',
        '', '| Method | Seed → selected matches / 55 | Selected resolved / 55 |', '|---|---:|---:|']
    excluded_cases={r['case_id'] for r in rows if r['excluded']}
    for arm in manifest['arms']:
        g=[r for r in rows if r['arm']==arm and r['case_id'] not in excluded_cases]
        lines.append(f"| {arm} | {sum(round(r['seed'].get('agreement',0)*5) for r in g)} → {sum(round(r['selected'].get('agreement',0)*5) for r in g)} | {sum(round(r['selected'].get('coverage',0)*5) for r in g)} |")
    lines+=['','## Per-case results','','| Case / reference | Method | Seed → selected matches / 5 | Selected resolved / 5 | Lowest confidence (missing) | Checks | Result |',
        '|---|---|---:|---:|---|---:|---|']
    for r in rows:
        measured=bool(r['selected']);confidence=f"{r['minimum_confidence']:.2f}" if r['minimum_confidence'] is not None else '—'
        status=r['status']+(' / protocol deviation' if r['excluded'] else '')
        lines.append('| '+' | '.join([r['name']+' / '+r['target'],r['arm'],
            f"{round(r['seed'].get('agreement',0)*5)} → {round(r['selected'].get('agreement',0)*5)}" if measured else 'not executed',
            str(round(r['selected'].get('coverage',0)*5)) if measured else 'not executed',
            confidence+f" ({r['missing_confidence']})",str(r['checks']),status])+' |')
    lines+=['','## Usage and verification','','Combined model calls: '+str(budget['calls'])+'. Final calls: '+str(budget.get('final_calls',0))+'.',
        'Charged completion tokens: '+str(budget['completion_tokens_or_reserved'])+'. Input tokens: '+str(budget['input_tokens'])+'.',
        'Ceilings remain 3,600 calls and 4,608,000 completion tokens. Inherited ledgers are not added again. '
        'Synthetic TLS diagnostics made no model calls and are not part of these optimizer measurements.',
        'Returned model identities: '+json.dumps(result.get('returned_models',[]))+'.',
        '', 'Exact programs, observations, audits and lineages remain in `frozen/`, `prepared/`, `observations/` and `jobs/`. '
        'See `analysis.md`, `component_analysis.json`, `protocol_verification.json`, `continuation_verification.json` and `protocol_deviations.json`.']
    for r in rows:
        lines+=['','### '+r['name']+' / '+r['arm'],'',
            'Rejection reasons: '+json.dumps(r['reasons'])+'. Preparation error: '+str(r['error'])+'.',
            'Direct final-call failures: '+json.dumps(r['direct_failures'])+'.',
            'Completed search rounds: '+str(r['rounds'])+'. Added evidence-context checks: '+json.dumps(r['nested_checks'])+'.',
            'Requirement consistency: '+str(r['selected'].get('requirement_consistency'))+'. '
            'Mean executed checks: '+str(r['selected'].get('mean_checks'))+'. '
            'Mean charged checker completion tokens per draw: '+str(r['selected'].get('mean_completion_tokens'))+'.',
            'Case-arm usage: '+json.dumps(r['usage'])+'.']
    (OUTPUT/'comparison_report.md').write_text('\n'.join(lines)+'\n')
    (OUTPUT/'validated_summary.json').write_text(json.dumps({'status':result['status'],'arms':summary,
        'excluded_scopes':sorted(affected),'paired_case_count':12-len(excluded_cases)},indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':main()
