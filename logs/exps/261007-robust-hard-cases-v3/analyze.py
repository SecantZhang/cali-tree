"""Rebuild supplementary pilot analysis from frozen artifacts; makes no model calls."""
from collections import Counter
from pathlib import Path
import json
from critical.core.optimization.program.robust.metrics import RobustPolicy

root = Path(__file__).resolve().parent
manifest = json.loads((root/'manifest.json').read_text())
results = json.loads((root/'results.json').read_text())
policy = RobustPolicy(**manifest['policy'])
rows = []
for i, case in enumerate(manifest['cases']):
    for arm in manifest['arms']:
        result = results['cases'].get(case['id'], {}).get(arm, {})
        frozen_path = root/'frozen'/arm/f'{i}.json'
        frozen = json.loads(frozen_path.read_text()) if frozen_path.exists() else {}
        node = frozen.get('nodes', {}).get('leaf:' + case['id'], {})
        search = node.get('result', {})
        stats = {}
        for which in ('seed', 'selected'):
            artifact = search.get(which) or {}
            program = artifact.get('program', {})
            report = result.get('final', {}).get(which, {})
            candidate = search.get('candidates', {}).get(artifact.get('program_ref'), {})
            audit = candidate.get('audit', {})
            stats[which] = {k: report.get(k) for k in ('agreement', 'coverage', 'label_consistency', 'requirement_consistency',
                                                    'confidence_pass', 'mean_checks', 'mean_completion_tokens')}
            stats[which].update(qualified=policy.assess(report, audit)['qualified'], audit_accepted=audit.get('accepted', False),
                stored_nodes=len(program.get('nodes', [])), conditional_nodes=sum(bool(n['parent']) for n in program.get('nodes', [])),
                evidence_edges=sum(len(n['dependencies']) for n in program.get('nodes', [])),
                inference_rules=sum(len(n['inferences']) for n in program.get('nodes', [])))
        candidates = search.get('candidates', {})
        rows.append({'case': case['id'], 'instruction': case['instruction'], 'target': case['target'], 'arm': arm,
            **stats, 'changed': search.get('seed') != search.get('selected'),
            'candidate_count': len(candidates), 'audited_candidates': sum('audit' in c for c in candidates.values()),
            'audit_rejections': sum(c.get('audit', {}).get('accepted') is False for c in candidates.values()),
            'status': result.get('support_status', 'unattempted'), 'reasons': result.get('acceptance', {}).get('reasons', []),
            'usage': result.get('usage', {}), 'error': result.get('error') or frozen.get('error'),
            'lineage_errors': [x['error'] for x in search.get('lineage', []) if 'error' in x]})
summary = {}
for arm in manifest['arms']:
    group = [r for r in rows if r['arm'] == arm]
    s = {'cases': len(group), 'changed': sum(r['changed'] for r in group),
         'reasons': dict(Counter(reason for r in group for reason in r['reasons'])),
         'audit_rejections': sum(r['audit_rejections'] for r in group)}
    for which in ('seed', 'selected'):
        s[which] = {key: sum(r[which][key] or 0 for r in group)/len(group) for key in
                      ('agreement','coverage','label_consistency','requirement_consistency','mean_checks','mean_completion_tokens')}
        s[which]['qualified_cases'] = sum(r[which]['qualified'] for r in group)
        s[which]['cases_with_conditional_nodes'] = sum(r[which]['conditional_nodes'] > 0 for r in group)
        s[which]['class_agreement'] = {label: sum(r[which]['agreement'] or 0 for r in group if r['target'] == label)/sum(r['target'] == label for r in group)
                                     for label in ('yes','partial','no') if any(r['target'] == label for r in group)}
    summary[arm] = s
jobs = [json.loads(p.read_text()) for p in (root/'jobs').glob('*.json')]
prior = manifest.get('prior_attempt', {})
budget = results['budget']
analysis = {'scope': manifest['scope'], 'status': results['status'], 'arms': summary, 'cases': rows,
    'job_outcomes': dict(Counter(j['outcome'] for j in jobs)), 'stages': dict(Counter(j['stage'] for j in jobs)),
    'returned_models': results.get('returned_models'),
    'combined_calls': budget['calls'] + prior.get('calls_charged', 0),
    'combined_completion_tokens_or_reserved': budget['completion_tokens_or_reserved'] + prior.get('completion_tokens_charged', 0),
    'current_input_tokens': budget['input_tokens']}
(root/'analysis.json').write_text(json.dumps(analysis, indent=2)+'\n')
lines = ['# Supplementary robust leaf analysis', '', manifest['scope'], '', 'Status: '+results['status'], '',
         '| Arm | Seed → selected agreement | Seed → selected robust cases | Selected coverage | Selected label consistency | Selected conditional programs |',
         '|---|---:|---:|---:|---:|---:|']
for arm,s in summary.items():
    a,b=s['seed'],s['selected']
    lines.append(f"| {arm} | {a['agreement']:.1%} → {b['agreement']:.1%} | {a['qualified_cases']} → {b['qualified_cases']} / {len(manifest['cases'])} | {b['coverage']:.1%} | {b['label_consistency']:.1%} | {b['cases_with_conditional_nodes']} / {len(manifest['cases'])} |")
lines += ['', '| Instruction | Reference | Arm | Seed → selected agreement | Final status | Failure reasons |',
          '|---|---|---|---:|---|---|']
for r in rows:
    a,b=r['seed']['agreement'],r['selected']['agreement']
    fmt=lambda x:'unavailable' if x is None else f'{x:.0%}'
    lines.append('| '+' | '.join([r['instruction'],r['target'],r['arm'],fmt(a)+' → '+fmt(b),r['status'],', '.join(r['reasons']) or r['error'] or 'none'])+' |')
lines += ['', 'Agreement uses fresh five-draw final executions. Repeats are not independent cases. Confidence is generated self-report, not calibrated correctness.',
          'Unvisited branches remain untested; programs without conditional nodes do not experimentally distinguish flat versus tree routing.',
          'No final verification outcome was used to retune a program. Semantic audits are evidence, not proof of atomic correctness.',
          '', 'Combined calls including prior failed attempt: '+str(analysis['combined_calls']),
          'Combined completion tokens / conservative reservations: '+str(analysis['combined_completion_tokens_or_reserved']),
          'Input tokens in this run: '+str(analysis['current_input_tokens']),
          'Returned model identities: '+json.dumps(analysis['returned_models']),
          'Job outcomes: '+json.dumps(analysis['job_outcomes'])]
(root/'assessment.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({k:analysis[k] for k in ('status','combined_calls','combined_completion_tokens_or_reserved','job_outcomes','returned_models','arms')},indent=2))
