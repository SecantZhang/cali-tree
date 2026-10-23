"""Score frozen v35 forward policies without fitting or making model calls.

--bounds evaluates every possible regular-judge label, including unresolved.
It gives exact bounds, not an estimate of actual matched accuracy. --report
requires the separately authorized baseline to have completed.
"""
import argparse
import hashlib
from collections import Counter
from pathlib import Path

from critical.core.calibration.regular_aware_gate_v35 import RegularAwareGate
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.compiler import media_inputs
from critical.core.optimization.prompt.calitree.task_coverage import LABELS
from run.calitree_aurora_pilot_v29 import read, fingerprint, exact, IDENTITY
from run.collect_calitree_guarded_forward_v32 import verify
from run.collect_calitree_aurora_pilot_v29r1 import validate_regular, metrics


def policies(out):
    verify(out)
    freeze = read(out / 'supplemental_v35/freeze.json')
    assert fingerprint(out / 'inputs.json') == freeze['forward_inputs_sha256']
    assert fingerprint(out.parent / '261020-regular-aware-v35/freeze.json') == freeze['source_freeze_sha256']
    assert freeze['policy_fixed_before_new_regular_collection']
    for path, expected in freeze['code_hashes'].items():
        assert fingerprint(path) == expected, path
    gates = {}
    for bank in (1, 2, 3):
        gate = RegularAwareGate.restore(read(out / f'supplemental_v35/split{bank}.json'))
        assert gate.artifact['artifact_ref'] == freeze['gates'][str(bank)]
        gates[bank] = gate
    return gates


def route(gate, example, regular, corrections=True):
    if example['features'] is None:
        return {'covered': False, 'prediction': -1, 'reason': 'missing_or_invalid_evidence', 'matches': []}
    return gate.resolve(example['program'], example['features'], regular, corrections=corrections)


def predict(selection, regular):
    return selection['prediction'] if selection['covered'] else regular


def scenario_table(gates, examples, frozen, references):
    """Enumerate comparator labels; no choices are selected using references."""
    cases = []
    for example in examples:
        case = example['case']
        reference = LABELS.index(references[case])
        result = {'case': case, 'reference': reference, 'banks': {}}
        for bank, gate in gates.items():
            scenarios = []
            old = frozen[case]['routes'][f'v27_split{bank}']
            for regular in (-1, 0, 1, 2):
                selection = route(gate, example, regular)
                prediction = predict(selection, regular)
                prior = predict(old, regular)
                scenarios.append({'regular': regular, 'prediction': prediction,
                                  'covered': selection['covered'], 'v27_prediction': prior,
                                  'accuracy_delta_vs_regular': int(prediction == reference) - int(regular == reference),
                                  'accuracy_delta_vs_v27': int(prediction == reference) - int(prior == reference)})
            result['banks'][str(bank)] = scenarios
        cases.append(result)
    summary = {}
    for bank in gates:
        rows = [c['banks'][str(bank)] for c in cases]
        entry = {}
        for baseline in ('regular', 'v27'):
            key = f'accuracy_delta_vs_{baseline}'
            minimum = sum(min(s[key] for s in ss) for ss in rows)
            maximum = sum(max(s[key] for s in ss) for ss in rows)
            entry[f'versus_{baseline}'] = {'minimum_correct_delta': minimum, 'maximum_correct_delta': maximum,
                'minimum_accuracy_delta': minimum / len(cases), 'maximum_accuracy_delta': maximum / len(cases),
                'cases_with_possible_loss': [c['case'] for c in cases if min(s[key] for s in c['banks'][str(bank)]) < 0],
                'cases_with_guaranteed_gain': [c['case'] for c in cases if min(s[key] for s in c['banks'][str(bank)]) > 0]}
        summary[str(bank)] = entry
    return {'cases': cases, 'bounds': summary}


def bounds(out):
    gates = policies(out)
    frozen = {r['case']: r for r in read(out / 'frozen_predictions.json')}
    result = scenario_table(gates, read(out / 'inputs.json'), frozen, read(out / 'references.json'))
    result.update({'new_model_calls': 0, 'new_fitting': False, 'regular_outputs_observed': False,
                   'interpretation': 'Exact extrema over hypothetical regular predictions. Not actual accuracy or a statistical interval.',
                   'policy_freeze_sha256': fingerprint(out / 'supplemental_v35/freeze.json'),
                   'analyzer_sha256': fingerprint(__file__)})
    exact(out / 'supplemental_v35/hypothetical_bounds.json', result)
    print(result['bounds'], flush=True)
    return result


def verify_collection(out):
    """Validate every durable attempt, including retained failures/reservations."""
    examples = read(out / 'inputs.json')
    assert 0 < len(examples) <= 36
    budget = read(out / 'ledger/budget.json')
    limits = budget['limits']
    assert limits == {'max_calls': 36, 'max_completion_tokens': 73728,
                      'reserve_calls': 0, 'reserve_tokens': 0, 'identity': IDENTITY,
                      'scope_limits': {'search': 1, 'final': 0}}
    assert budget['calls'] == len(examples) == len(budget['attempted_slots']) == len(set(budget['attempted_slots']))
    assert set(budget['cases']) == {e['case'] for e in examples}
    assert 0 <= budget['completion_tokens_or_reserved'] <= 73728
    assert 0 <= budget['input_tokens']
    slots = []
    states = Counter()
    token_totals = Counter()
    for e in examples:
        media = [{'type': m['type'], 'sha256': hashlib.sha256(Path(m['path']).read_bytes()).hexdigest()}
                 if m['type'] == 'image' else m for m in media_inputs(e['evidence'])]
        payload = {'instruction': e['instruction']}
        key = digest([IDENTITY, e['case'], 'flat_judge', payload, task_schema(),
                      regular_prompt(), media, 'once', 2048])
        assert key in budget['attempted_slots']
        slots.append(key)
        counts = budget['cases'][e['case']]
        assert counts['search'] == 1 and counts['final'] == 0
        response = read(out / 'regular_responses' / (e['case'] + '.json'))
        path = out / 'ledger/jobs' / (key + '.json')
        completion, input_tokens = 2048, 0
        if path.exists():
            job = read(path)
            assert job['execution_ref'] == key and job['case_id'] == e['case']
            assert job['stage'] == 'flat_judge' and job['slot'] == 'once'
            assert job['payload'] == payload and job['media_identity'] == media
            assert job['max_tokens'] == 2048 and job['phase'] == 'search'
            states[job['outcome']] += 1
            if 'response' in job:
                body = job['response']
                completion = int(body.get('completionTokens', body.get('completion_tokens', 2048)) or 0)
                input_tokens = int(body.get('promptTokens', body.get('prompt_tokens', 0)) or 0)
                assert 0 <= completion <= 2048 and input_tokens >= 0
            if response['judgment'] is not None:
                validate_regular(response['judgment'])
                assert job['outcome'] == 'completed' and job['parsed'] == response['judgment']
                assert response['execution_ref'] == key and response['error'] is None
            else:
                assert response['execution_ref'] is None and response['error']
        else:
            # The durable reservation can precede a crash before the job write.
            assert response['judgment'] is None and response['execution_ref'] is None and response['error']
            states['interrupted_before_job_write'] += 1
        assert counts['completion_tokens_or_reserved'] == completion
        assert counts.get('input_tokens', 0) == input_tokens
        token_totals['completion'] += completion
        token_totals['input'] += input_tokens
    assert set(slots) == set(budget['attempted_slots'])
    assert {p.stem for p in (out / 'ledger/jobs').glob('*.json')} <= set(slots)
    assert budget['completion_tokens_or_reserved'] == token_totals['completion']
    assert budget['input_tokens'] == token_totals['input']
    return {'passed': True, 'attempts': budget['calls'], 'input_tokens': budget['input_tokens'],
            'completion_tokens_or_reserved': budget['completion_tokens_or_reserved'],
            'outcomes': dict(states), 'budget_sha256': fingerprint(out / 'ledger/budget.json')}


def regular_prompt():
    from critical.core.optimization.prompt.calitree.task_coverage import TEMPLATES
    return (TEMPLATES / 'regular.txt').read_text()


def task_schema():
    from critical.core.optimization.prompt.calitree.task_coverage import SCHEMA
    return SCHEMA


def report(out):
    gates = policies(out)
    collection = verify_collection(out)
    # Require the original collector report as well as a completed response per
    # case. A stopped/incomplete collection cannot silently become a subset.
    original = {r['case']: r for r in read(out / 'full_predictions.json')}
    examples = read(out / 'inputs.json')
    references = read(out / 'references.json')
    assert set(original) == {e['case'] for e in examples}
    rows = []
    for e in examples:
        response = read(out / 'regular_responses' / (e['case'] + '.json'))
        value = response['judgment']
        if value is not None:
            validate_regular(value)
        regular = LABELS.index(value['label']) if value is not None and value['label'] in LABELS else -1
        previous = original[e['case']]
        assert regular == previous['regular']
        assert previous['reference'] == LABELS.index(references[e['case']])
        r = {**previous, 'routes': dict(previous['routes'])}
        for bank, gate in gates.items():
            for method, corrections in (('regular_aware', False), ('regular_aware_correction', True)):
                arm = f'{method}_split{bank}'
                selection = route(gate, e, regular, corrections)
                r['routes'][arm] = selection
                r[arm] = predict(selection, regular)
        rows.append(r)
    arms = ['regular', *rows[0]['routes']]
    result = {'cases': len(rows), 'source_groups': len({r['source_group'] for r in rows}),
              'class_counts': dict(Counter(r['reference'] for r in rows)),
              'metrics': {arm: metrics(rows, arm) for arm in arms},
              'paired': {}, 'collection_verification': collection, 'new_model_calls': 0, 'new_fitting': False,
              'legacy_research_exposure': True,
              'policy_freeze_sha256': fingerprint(out / 'supplemental_v35/freeze.json'),
              'original_results_sha256': fingerprint(out / 'full_results.json'),
              'analyzer_sha256': fingerprint(__file__)}
    for bank in gates:
        arm = f'regular_aware_correction_split{bank}'
        result['paired'][str(bank)] = {}
        for baseline in ('regular', f'v27_split{bank}', f'v28_split{bank}'):
            result['paired'][str(bank)][baseline] = {
                'wins': sum(r[arm] == r['reference'] and r[baseline] != r['reference'] for r in rows),
                'losses': sum(r[arm] != r['reference'] and r[baseline] == r['reference'] for r in rows)}
    exact(out / 'supplemental_v35/full_predictions.json', rows)
    exact(out / 'supplemental_v35/full_results.json', result)
    save_json(out / 'supplemental_v35/report_seal.json', {
        'predictions_sha256': fingerprint(out / 'supplemental_v35/full_predictions.json'),
        'results_sha256': fingerprint(out / 'supplemental_v35/full_results.json'),
        'analyzer_sha256': fingerprint(__file__)})
    print(result, flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--bounds', action='store_true')
    mode.add_argument('--report', action='store_true')
    args = parser.parse_args()
    if args.bounds:
        bounds(args.output_dir.resolve())
    else:
        report(args.output_dir.resolve())
