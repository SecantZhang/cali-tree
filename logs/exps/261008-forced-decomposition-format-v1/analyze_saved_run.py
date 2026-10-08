"""Plain-language analysis of saved outcomes only; no model access."""
from collections import Counter
import json
from pathlib import Path

from critical.core.decision.artifacts import save_json


def analyze(directory):
    directory=Path(directory)
    manifest=json.loads((directory/'manifest.json').read_text())
    result=json.loads((directory/'results.json').read_text())
    rows=[]
    lines=['# Broad versus forced decomposition: saved-data analysis','',
        'Each row is one previously observed case fitted by one method. Seed and selected programs each have five fresh final draws. '
        'Repeated draws measure local behavior; there are only three independent cases.','',
        '| Case | Method | Correct seed answers / 5 | Correct selected answers / 5 | Usable selected answers / 5 | Selected checks | Changed program? | Passed all robustness gates? |',
        '|---|---|---:|---:|---:|---:|---|---|']
    for i,case in enumerate(manifest['cases']):
        for arm in manifest['arms']:
            local=json.loads((directory/'frozen'/arm/f'{i}.json').read_text())
            measured=result['cases'][case['id']].get(arm,{})
            if 'error' in local:
                lines.append(f"| {case['instruction']} | {arm} | 0 | 0 | 0 | unavailable | unavailable | no: preparation failed |")
                continue
            node=local['nodes']['leaf:'+case['id']];search=node['result']
            selected=search['selected']['program'];final=measured.get('final',{})
            seed=final.get('seed',{});winner=final.get('selected',{})
            changed=search['seed']['program_ref']!=search['selected']['program_ref']
            edits=[v for v in search['lineage'] if 'transaction' in v]
            audit=search['candidates'].get(search['selected']['program_ref'],{}).get('audit',{})
            row={'case_id':case['id'],'instruction':case['instruction'],'reference_label':case['target'],'arm':arm,
                'seed_reference_matches':round(5*seed.get('agreement',0)),
                'selected_reference_matches':round(5*winner.get('agreement',0)),
                'selected_usable_answers':round(5*winner.get('coverage',0)),
                'program_changed':changed,'seed_check_count':len(search['seed']['program']['nodes']),
                'selected_check_count':len(selected['nodes']),'selected_audit':audit,
                'status':measured.get('support_status'),'acceptance':measured.get('acceptance'),
                'seed_labels':dict(Counter(str(t['label']) for t in seed.get('traces',[]))),
                'selected_labels':dict(Counter(str(t['label']) for t in winner.get('traces',[]))),
                'proposed_transactions':len(edits),'proposal_errors':dict(Counter(v['error'] for v in edits if 'error' in v)),
                'usage':measured.get('usage',{}),'components':[]}
            for n in selected['nodes']:
                observations=[o for t in winner.get('traces',[]) for o in t['observations'] if o['check_id']==n['id']]
                confidence=[o['confidence'] for o in observations if o['queried'] and o['confidence'] is not None]
                row['components'].append({**n,'final_states':dict(Counter(o['status'] for o in observations)),
                    'lowest_reported_confidence':min(confidence) if confidence else None,
                    'stability':winner.get('nodes',{}).get(n['id'],{})})
            rows.append(row)
            lines.append('| '+' | '.join([case['instruction'],arm,str(row['seed_reference_matches']),str(row['selected_reference_matches']),
                str(row['selected_usable_answers']),str(row['selected_check_count']),str(changed).lower(),
                'yes' if row['status']=='locally_robust' else 'no: '+str(row['status'])])+' |')
    lines+=['','Correct answers = matching the saved reference label; unanswered/invalid calls count as incorrect. '
        'Usable answers = resolved yes/partial/no, even if wrong. Changed program = different executable hash. '
        'Passing all gates also requires audit approval, consistency and confidence; it cannot be inferred from correctness alone.','']
    for row in rows:
        lines += ['## '+row['instruction']+' — '+row['arm'],'',
            'Reference label: `'+row['reference_label']+'`. Seed labels: '+json.dumps(row['seed_labels'])+
            '; selected labels: '+json.dumps(row['selected_labels'])+'.',
            'Selected semantic audit: '+str(row['selected_audit'].get('accepted'))+'; '+str(row['selected_audit'].get('reason')),
            'Proposed transactions: '+str(row['proposed_transactions'])+'; rejected diagnostics: '+json.dumps(row['proposal_errors'])+'.',
            'Final acceptance: '+json.dumps(row['acceptance'])+'.','',
            '| Component | Visual input | Question | Final states | Lowest reported confidence |',
            '|---|---|---|---|---:|']
        for n in row['components']:
            visual='saved evidence only' if row['arm'].startswith('decomposed') and n['role']=='requested' else 'source and edited images'
            lines.append('| '+' | '.join([n['id']+' ('+n['role']+')',visual,n['question'],json.dumps(n['final_states']),str(n['lowest_reported_confidence'])])+' |')
        lines+=['','Measured scope usage, including preparation-independent search and final checks: '+json.dumps(row['usage'])+'.','']
    lines+=['## Interpretation limits','',
        'Forcing several calls does not guarantee a useful decomposition. A component set must record the relation or property needed for fulfillment, '
        'and its readout must preserve the original scoring rules. A rejected semantic audit remains a rejection even when observed labels match. '
        'Proposal-format failures limit what this test says about the effectiveness of structural repair. '
        'Confidence is reported by the model and is not calibrated probability. No final observations were used to change the frozen selected programs. '
        'Broad-versus-decomposed fidelity is recorded separately in scoring_fidelity.json.']
    save_json(directory/'component_analysis.json',rows)
    (directory/'analysis.md').write_text('\n'.join(lines)+'\n')
    return rows


if __name__=='__main__': analyze(Path(__file__).resolve().parent)
