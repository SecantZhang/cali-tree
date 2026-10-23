"""Audit the approved frozen final evaluation without calls or fitting."""
import argparse
from collections import Counter
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.core.decision.semantic_interpretation_v5 import make_input, validate
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import project
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import metrics
from run.calitree_three_splits_compiler_v3 import audit_compiler
from run import calitree_frozen_final_v14 as runner


def audit(out):
    manifest = runner.prepare(out)
    protocol = runner.base.read(out / 'protocol.json')
    approval = runner.base.read(out / 'approval.json')
    assert approval['manifest_ref'] == manifest['artifact_ref']
    assert approval['max_requests'] == protocol['new_calls_max'] == 200
    assert approval['max_completion_tokens'] == protocol['completion_tokens_max'] == 2_048_000
    assert approval['model'] == protocol['judge_identity']['model']
    observations = runner.base.read(out / 'extraction/observations.json')
    assert [r['case'] for r in observations] == [r['case'] for r in manifest['cases']]
    physical_audit = audit_compiler(out, manifest, observations)
    assert physical_audit == runner.base.read(out / 'physical_audit.json')
    records = runner.base.read(out / 'portable_records.json')
    assert [r['case'] for r in records] == [r['case'] for r in manifest['cases']]
    by_record = {r['case']: r for r in records}
    expected_jobs = set(); valid_observations = valid_meanings = 0
    for case, observed in zip(manifest['cases'], observations):
        interpretation = runner.base.read(out / 'interpretations' / (case['case'] + '.json'))
        meaning_jobs = list((out / 'interpretation_ledgers' / case['case'] / 'jobs').glob('*.json'))
        assert len(meaning_jobs) == (1 if observed['record'] else 0)
        if observed['record']:
            valid_observations += 1
            job = runner.base.read(meaning_jobs[0])
            pair_ref = image_identity(case['evidence'])[1]
            payload = make_input(observed['compilation']['program'], observed['observation']['observation'], pair_ref)
            assert job['payload'] == payload and job['media_identity'] == []
            assert job['stage'] == 'instruction_relative_interpretation'
            if interpretation['interpretation'] is not None:
                validate(payload, interpretation['interpretation'])
                assert job['outcome'] == 'completed' and job['parsed'] == interpretation['interpretation']
                assert interpretation['execution_ref'] == job['execution_ref']
                valid_meanings += 1
            expected = project(observed['compilation']['program'], observed['observation']['observation'], pair_ref, interpretation['interpretation'])
        else:
            expected = None
            assert interpretation['interpretation'] is None
        assert by_record[case['case']]['features'] == expected
        for stage in ('compile', 'observe'):
            expected_jobs.update(p.relative_to(out).as_posix() for p in (out / 'extraction/ledgers' / case['case'] / stage / 'jobs').glob('*.json'))
        expected_jobs.update(p.relative_to(out).as_posix() for p in meaning_jobs)
    all_jobs = list(out.glob('**/jobs/*.json'))
    assert expected_jobs == {p.relative_to(out).as_posix() for p in all_jobs}
    assert len(all_jobs) <= protocol['new_calls_max']
    calls = tokens = prompt_tokens = actual_completion = 0
    outcomes = Counter(); returned_models = Counter(); by_stage = Counter()
    for budget_path in out.glob('**/budget.json'):
        budget = runner.base.read(budget_path); limits = budget['limits']
        assert limits['identity'] == protocol['judge_identity']
        jobs = [runner.base.read(p) for p in (budget_path.parent / 'jobs').glob('*.json')]
        assert budget['calls'] == len(jobs) == len(set(budget['attempted_slots']))
        assert set(budget['attempted_slots']) == {j['execution_ref'] for j in jobs}
        assert budget['calls'] <= limits['max_calls']
        assert budget['completion_tokens_or_reserved'] <= limits['max_completion_tokens']
        calls += budget['calls']; tokens += budget['completion_tokens_or_reserved']
        for job in jobs:
            assert job['outcome'] != 'interrupted', 'A reserved slot has no terminal outcome'
            assert job['slot'] == 'once' and job['phase'] == 'search'
            outcomes[job['outcome']] += 1; by_stage[job['stage']] += 1
            response = job.get('response') or {}
            prompt_tokens += int(response.get('promptTokens', response.get('prompt_tokens', 0)) or 0)
            actual_completion += int(response.get('completionTokens', response.get('completion_tokens', 0)) or 0)
            returned_models[str(response.get('model', 'unreported'))] += 1
    assert calls == len(all_jobs) <= 200 and tokens <= 2_048_000
    assert set(by_stage) <= {'bound_instruction_v3', 'bound_instruction_v3_repair',
                             'bound_visual_observation_v2', 'instruction_relative_interpretation'}
    policies = runner.base.read(out / 'policies.json')
    saved = runner.base.read(out / 'predictions.json')
    assert saved['case_order'] == [r['case'] for r in records]
    assert set(saved['policies']) == set(policies)
    refs = {r['case']: r['reference'].lower() for r in runner.base.read(runner.RESERVED / 'test_references.json')['cases']}
    targets = [runner.base.LABELS.index(refs[r['case']]) for r in records]
    expected_metrics = {}
    for name, policy in policies.items():
        ps = PortableRuleExecutor(policy).predict_records([r['features'] for r in records])
        assert ps == saved['policies'][name]
        expected_metrics[name] = metrics([p['prediction'] for p in ps], targets)
    result = runner.base.read(out / 'results.json')
    assert result['metrics'] == expected_metrics
    assert result['unique_evaluation_sources'] == 50 and result['fitting_or_selection'] is False
    for i in (1, 2, 3):
        for control in (f'v14_direct_split{i}', f'v12_merge_split{i}'):
            counts = Counter()
            for a, b, y in zip(saved['policies'][f'v14_merge_split{i}'], saved['policies'][control], targets):
                ca, cb = a['prediction'] == y, b['prediction'] == y
                counts['both_correct' if ca and cb else 'v14_merge_only' if ca else 'control_only' if cb else 'both_wrong'] += 1
            assert result['paired'][f'v14_merge_split{i}_vs_{control}'] == dict(counts)
    value = {'passed': True, 'manifest_ref': manifest['artifact_ref'], 'policy_predictions_replayed': len(policies) * 50,
        'unique_sources': 50, 'physical': physical_audit, 'valid_observations': valid_observations,
        'valid_interpretations': valid_meanings, 'requests': calls, 'outcomes': dict(outcomes), 'stages': dict(by_stage),
        'input_tokens_reported': prompt_tokens, 'completion_tokens_reported': actual_completion,
        'completion_tokens_or_conservatively_reserved': tokens, 'returned_models': dict(returned_models),
        'request_cap': 200, 'completion_token_cap': 2_048_000, 'reference_labels_in_requests': False,
        'new_model_calls_in_audit': 0, 'new_fits': 0, 'policy_selection_in_evaluation': False}
    save_json(out / 'verification.json', value)
    files = ['manifest.json', 'protocol.json', 'policies.json', 'approval.json', 'portable_records.json', 'predictions.json',
             'results.json', 'verification.json', 'physical_audit.json', 'extraction/observations.json']
    files += sorted(p.relative_to(out).as_posix() for p in all_jobs)
    files += sorted(p.relative_to(out).as_posix() for p in out.glob('**/budget.json'))
    files += sorted(p.relative_to(out).as_posix() for p in (out / 'interpretations').glob('*.json'))
    seal = {'manifest_ref': manifest['artifact_ref'], 'files': {name: runner.base.fingerprint(out / name) for name in files}}
    runner.base.exact(out / 'completion_seal.json', seal)
    print(value)
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    audit(parser.parse_args().output_dir.resolve())
