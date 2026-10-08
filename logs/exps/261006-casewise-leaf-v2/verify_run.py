"""Recompute and validate the completed pilot without any provider calls."""
from pathlib import Path
import json
from hashlib import sha256
from collections import Counter
from critical.core.decision.artifacts import restore_program, save_json
from critical.core.optimization.program.evaluation import summarize
from critical.core.optimization.prompt.calitree.node.program_leaf import validate_program_leaves, judge_program_leaf
from critical.core.decision.executor import ProgramExecutor
from critical.checkpoint import CheckpointStore

root = Path(__file__).resolve().parent
manifest = json.loads((root / 'manifest.json').read_text())
result = json.loads((root / 'results.json').read_text())
bundle = validate_program_leaves(json.loads((root / 'leaves.json').read_text()))
assert result['status'] == 'completed'
assert len(result['cases']) == len(manifest['cases']) == len(bundle['nodes']) == 12
assert len({r['group'] for r in manifest['cases']}) == 12
assert Counter(r['target'] for r in manifest['cases']) == {'yes': 4, 'partial': 4, 'no': 4}
for path, expected in manifest['code_hashes'].items():
    assert sha256((root / 'source_snapshot' / path).read_bytes()).hexdigest() == expected
jobs = [json.loads(p.read_text()) for p in (root / 'jobs').glob('*.json')]
budget = json.loads((root / 'budget.json').read_text())
assert len(jobs) == budget['calls'] <= 600
assert budget['completion_tokens_or_reserved'] <= 768000
for counts in budget['cases'].values():
    assert counts['search'] <= 26 and counts['final'] <= 24
for job in jobs:
    assert job['max_tokens'] <= (1024 if job['stage'] == 'check' else 2048)
    if job['stage'] != 'propose':
        assert not {'reference_label', 'feedback', 'target_label', 'selection'} & set(job['payload'])
    if 'response' in job:
        assert job['response']['model'] == 'gpt-6-luna'
for case in manifest['cases']:
    node = bundle['nodes']['leaf:' + case['id']]
    assert node['fit_scope'] == [case['id']]
    for key, path in case['evidence'].items():
        assert sha256(Path(path).read_bytes()).hexdigest() == case['image_hashes'][key]
    row = result['cases'][case['id']]
    for arm, metrics in row['final'].items():
        assert summarize(metrics['draws'], row['target']) == metrics
        program = restore_program(node['result'][arm])
        assert all(d['program_ref'] == node['result'][arm]['program_ref'] for d in metrics['draws'])
        assert program.instruction == case['instruction']
    selected = row['final'].get('selected', {})
    if selected:
        class ReadOnlyChecker:
            identity = node['executor_identity']
            def check(self, *args, **kwargs):
                raise AssertionError('Reload attempted a new model call')
        replay = judge_program_leaf(bundle, node['id'], case['evidence'],
                     ProgramExecutor(ReadOnlyChecker(), checkpoint=CheckpointStore(root / 'observations.jsonl')),
                     repeat=case['id'] + '/final/selected/0')
        assert replay.to_dict() == selected['draws'][0]

    audit = node['result']['candidates'].get(node['program_ref'], {}).get('audit', {})
    assert (row['support_status'] == 'locally_fitted') == (
        selected.get('agreement') == 1 and selected.get('coverage') == 1 and audit.get('accepted', False))
summary = {'verified': True, 'cases': 12, 'calls': budget['calls'],
           'completion_tokens_or_reserved': budget['completion_tokens_or_reserved'],
           'measured_completion_tokens': sum(j.get('response', {}).get('completionTokens', 0) for j in jobs),
           'input_tokens': budget['input_tokens'],
           'stages': dict(Counter(j['stage'] for j in jobs)),
           'job_outcomes': dict(Counter(j['outcome'] for j in jobs)),
           'support_status': dict(Counter(r['support_status'] for r in result['cases'].values())),
           'seed_mean_agreement': sum(r['final'].get('seed', {}).get('agreement', 0) for r in result['cases'].values()) / 12,
           'selected_mean_agreement': sum(r['final'].get('selected', {}).get('agreement', 0) for r in result['cases'].values()) / 12,
           'changed_programs': sum(n['result']['seed'] != n['result']['selected'] for n in bundle['nodes'].values()),
           'independent_cases': 12, 'draws_per_arm_per_case': 3}
save_json(root / 'audit.json', summary)
print(json.dumps(summary, indent=2))
