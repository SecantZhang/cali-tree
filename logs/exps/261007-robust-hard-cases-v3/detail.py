"""Saved-data topology, confidence, failures and case-by-case comparison."""
from collections import Counter
import json
from pathlib import Path

root = Path(__file__).resolve().parent
manifest = json.loads((root/'manifest.json').read_text())
results = json.loads((root/'results.json').read_text())
rows, candidate_nodes, operations = [], Counter(), Counter()
audit_rejections = 0
for i, case in enumerate(manifest['cases']):
    for arm in manifest['arms']:
        frozen = json.loads((root/'frozen'/arm/f'{i}.json').read_text())
        node = frozen.get('nodes', {}).get('leaf:' + case['id'], {})
        search = node.get('result', {})
        final = results['cases'][case['id']][arm]
        candidate_nodes.update(len(c['program']['nodes']) for c in search.get('candidates', {}).values())
        audit_rejections += sum(c.get('audit', {}).get('accepted') is False for c in search.get('candidates', {}).values())
        for item in search.get('lineage', []):
            for edit in item.get('transaction', {}).get('edits', []):
                operations[edit.get('operator', 'unknown')] += 1
        metrics = {}
        for which in ('seed', 'selected'):
            report = final.get('final', {}).get(which, {})
            observations = [o for t in report.get('traces', []) for o in t['observations'] if o['queried']]
            confidence = [o['confidence'] for o in observations if o['confidence'] is not None]
            artifact = search.get(which) or {}
            nodes = artifact.get('program', {}).get('nodes', [])
            metrics[which] = {
                **{k: report.get(k) for k in ('agreement','coverage','label_consistency','requirement_consistency',
                    'confidence_pass','mean_checks','mean_completion_tokens','label_distribution')},
                'reported_confidences': len(confidence), 'queried_observations': len(observations),
                'minimum_reported_confidence': min(confidence, default=None),
                'missing_confidence': len(observations) - len(confidence),
                'program_ref': artifact.get('program_ref'), 'stored_checks': len(nodes),
                'conditional_checks': sum(bool(n['parent']) for n in nodes),
                'supporting_checks': sum(n['role'] == 'support' for n in nodes),
                'failed_observations': sum(o.get('failure') is not None for o in observations),
                'failure_details': [o['evidence'] for o in observations if o.get('failure')],
            }
        rows.append({'case_id': case['id'], 'instruction': case['instruction'], 'reference': case['target'], 'arm': arm,
                     'same_seed_and_selected_program': metrics['seed']['program_ref'] == metrics['selected']['program_ref'],
                     'status': final.get('support_status'), 'reasons': final.get('acceptance', {}).get('reasons'), **metrics})
jobs = [json.loads(p.read_text()) for p in (root/'jobs').glob('*.json')]
prior = json.loads((root/'optimizer_equivalence.json').read_text())
out = {'status': results['status'], 'candidate_checks_histogram': dict(candidate_nodes),
       'proposed_operations': dict(operations), 'candidate_audit_rejections': audit_rejections,
       'rows': rows, 'job_outcomes': dict(Counter(j['outcome'] for j in jobs)),
       'job_failures': [{k:j.get(k) for k in ('execution_ref','stage','phase','outcome','error','case_id')}
                        for j in jobs if j.get('error')], 'optimizer_equivalence': prior}
(root/'detail.json').write_text(json.dumps(out, indent=2)+'\n')
lines = ['# Harder-case confidence and topology', '',
         '| Case | Arm | Seed → selected matching draws / 5 | Selected resolved / 5 | Lowest reported confidence | Selected label consistency | Stored checks | Changed program | Final status |',
         '|---|---|---:|---:|---:|---:|---:|---|---|']
for row in rows:
    a,b=row['seed'],row['selected']
    fmt=lambda x: 'unavailable' if x is None else f'{x:.2f}'
    count=lambda x: 'unavailable' if x is None else str(round(5*x))
    lines.append('| '+' | '.join([row['instruction'],row['arm'],count(a['agreement'])+' → '+count(b['agreement']),
         count(b['coverage']),fmt(b['minimum_reported_confidence']),fmt(b['label_consistency']),str(b['stored_checks']),
         'no' if row['same_seed_and_selected_program'] else 'yes',row['status'] or 'unavailable'])+' |')
lines += ['', 'Candidate check-count histogram: '+json.dumps(out['candidate_checks_histogram']),
          'Proposed operations: '+json.dumps(out['proposed_operations']),
          'Audit rejections: '+str(audit_rejections), 'Job outcomes: '+json.dumps(out['job_outcomes']), '',
          'Confidence is reported by the model. Stable agreement does not certify the individual reasoning. '
          'If seed and selected programs are identical, any score difference comes from fresh observations, not an edit. '
          'Programs with one check cannot demonstrate the benefit of decomposition or conditional routing.']
(root/'detail.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({k:out[k] for k in ('status','candidate_checks_histogram','proposed_operations','candidate_audit_rejections','job_outcomes')}))
