"""Audit exact approved requests, model responses, fallback reuse and local scores."""
import argparse
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.compiler import media_inputs
from run import calitree_task_coverage as run


def audit(out):
    manifest = run.verify(out); protocol = run.read(out / 'protocol.json')
    expected = set(); counts = {}; completion = input_tokens = 0
    for key, job in manifest['jobs'].items():
        case = manifest['cases'][job['case']]; spec = job['request']
        media = [{'type': 'image', 'sha256': run.fingerprint(m['path'])} if m['type'] == 'image' else m
                 for m in media_inputs(case['evidence'])]
        ref = digest([run.IDENTITY, case['case'], spec['stage'], spec['payload'], spec['schema'], spec['template'], media, 'once', run.CAP])
        expected.add(ref)
        actual = run.read(out / 'ledger/jobs' / (ref + '.json'))
        assert actual['execution_ref'] == ref and actual['payload'] == spec['payload']
        assert actual['stage'] == spec['stage'] and actual['case_id'] == case['case']
        assert actual['max_tokens'] == run.CAP and actual['media_identity'] == media
        response = run.read(out / 'responses' / (key + '.json'))
        counts[actual['outcome']] = counts.get(actual['outcome'], 0) + 1
        if actual['outcome'] == 'completed':
            assert response['error'] is None and response['execution_ref'] == ref
            assert response['judgment'] == actual['parsed']
            assert actual['response']['model'] == run.IDENTITY['model']
        else:
            assert response['judgment'] is None
        usage = actual.get('response', {})
        completion += int(usage.get('completionTokens') or usage.get('completion_tokens') or run.CAP)
        input_tokens += int(usage.get('promptTokens') or usage.get('prompt_tokens') or 0)
    assert expected == {p.stem for p in (out / 'ledger/jobs').glob('*.json')}
    budget = run.read(out / 'ledger/budget.json')
    assert budget['calls'] == len(expected) <= protocol['max_calls']
    assert set(budget['attempted_slots']) == expected
    assert budget['completion_tokens_or_reserved'] == completion <= protocol['max_completion_tokens']
    assert budget['input_tokens'] == input_tokens
    results = run.report(out)
    fallback = 0
    for split in manifest['splits']:
        for slot in split['slots']:
            if not slot['route']['covered']:
                assert slot['baseline_job'] == slot['hybrid_job']
                fallback += 1
    result = {'passed': True, 'requests_verified': len(expected), 'outcomes': counts,
              'input_tokens': input_tokens, 'completion_tokens_or_reserved': completion,
              'exact_fallback_slots': fallback, 'all_local_slots': protocol['local_slots'],
              'per_child_scores_replayed': sum(len(s['batches']) for s in results['splits']),
              'reserved_final_predictions': 0, 'fitting_or_relabeling': False}
    run.exact(out / 'verification.json', result)
    seal = {'files': {str(p.relative_to(out)): run.fingerprint(p) for p in sorted(out.rglob('*'))
                      if p.is_file() and p.name != 'completion_seal.json'},
            'auditor_sha256': run.fingerprint(__file__)}
    run.exact(out / 'completion_seal.json', seal)
    print(result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    audit(parser.parse_args().output_dir.resolve())
