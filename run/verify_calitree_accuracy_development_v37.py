"""Audit protected probes, approved paired calls, and blinded reservation."""
import argparse
from collections import Counter
from pathlib import Path

import numpy as np

from critical.core.decision.artifacts import digest, save_json
from critical.core.optimization.prompt.calitree import task_coverage as task
from run.calitree_accuracy_headroom_v37 import dataset, encoded, Probe, accuracy
from run.calitree_disagreement_coverage_v36r1 import context
from run.calitree_fallback_routing_v34 import old_examples
from run.calitree_adjudicator_diagnostic_v38 import verify as verify_diagnostic
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint


def audit(out):
    if out.exists():
        raise ValueError('Fresh audit directory required')
    local, recent, experts = dataset()
    local_by_case = {e['case']: e for e in local}
    slots = 0
    for bank in (1, 2, 3):
        examples = {e['case']: e for e in old_examples(bank)}
        for r in context(bank)[0]:
            e, distinct = examples[r['case']], local_by_case[r['case']]
            assert e['program'] == distinct['program'] and e['regular'] == distinct['regular']
            assert e['features'] == distinct['features'] and r['features'] == distinct['features']
            assert e['reference'] == distinct['reference'] == r['reference']
            slots += 1
    assert slots == 144
    source_groups = {e['source_group'] for e in local + recent}
    roots = {name: ROOT / ('logs/exps/' + name) for name in (
        '261020-accuracy-headroom-v37', '261020-expert-region-policy-v40', '261020-goal-progress-policy-v41')}
    candidate_count = 0
    for directory in roots.values():
        manifest = read(directory / 'manifest.json')
        for p, h in manifest['code_hashes'].items():
            assert fingerprint(p) == h, p
        results = read(directory / 'results.json')['candidates']
        predictions = read(directory / 'predictions.json')
        for candidate, expected in results.items():
            rows = [r for r in predictions if r['candidate'] == candidate]
            assert len(rows) == len({r['case'] for r in rows}) == 116
            for cohort in ('all', 'pilot80', 'forward36'):
                selected = [r for r in rows if cohort == 'all' or r['cohort'] == cohort]
                for arm in ('regular', 'direct', 'routed'):
                    assert accuracy(selected, arm) == expected['metrics'][cohort][arm]
            assert expected.get('minimum_local_correct_across_folds', expected.get('minimum_local_correct')) == 99
            candidate_count += 1
        for f in read(directory / 'folds.json'):
            held = {f['held_source']} if 'held_source' in f else set(f['held_sources'])
            assert not held & set(f['training_sources'])
            assert held | set(f['training_sources']) == source_groups

    # Independently reproduce the strongest observed router from raw inputs.
    examples = local + recent
    names, X, actions = encoded(examples, experts)
    n = len(local)
    y = np.asarray([e['reference'] for e in examples])
    raw_records = read(roots['261020-accuracy-headroom-v37'] / 'predictions.json')
    stored = {r['case']: r for r in raw_records if r['candidate'] == 'forest_full_sqrt'}
    recreated = 0
    for group in sorted({e['source_group'] for e in recent}):
        train = [i for i, e in enumerate(examples) if e['source_group'] != group]
        held = [i for i, e in enumerate(examples) if i >= n and e['source_group'] == group]
        model = Probe('forest', 'sqrt').fit(X[train], y[train])
        assert model.predict(X[:n]) == [e['reference'] for e in local]
        for i, probability in zip(held, model.model.predict_proba(X[held])):
            scores = {int(c): float(p) for c, p in zip(model.model.classes_, probability)}
            available = {p for p in actions[i] if p >= 0}
            prediction = max(available, key=lambda c: (scores[c], -c)) if available else -1
            if examples[i]['features'] is None:
                prediction = examples[i]['regular']
            assert prediction == stored[examples[i]['case']]['routed']
            recreated += 1

    diagnostic = ROOT / 'logs/exps/261020-adjudicator-training-v38'
    verify_diagnostic(diagnostic)
    budget = read(diagnostic / 'ledger/budget.json')
    assert budget['limits']['identity'] == read(diagnostic / 'protocol.json')['identity']
    assert budget['limits']['scope_limits'] == {'search': 2, 'final': 0}
    assert budget['limits']['max_calls'] == 48 and budget['limits']['max_completion_tokens'] == 393216
    assert budget['calls'] == len(budget['attempted_slots']) == len(set(budget['attempted_slots'])) == 48
    assert 0 <= budget['completion_tokens_or_reserved'] <= 393216
    cases = {e['case']: e for e in read(diagnostic / 'cases.json')}
    jobs = read(diagnostic / 'jobs.json')
    slots_seen, outcomes, inputs, completions = set(), Counter(), 0, 0
    arm_correct, failure_cases = Counter(), []
    for job in jobs:
        media = [{'type': m['type'], 'sha256': fingerprint(m['path'])} if m['type'] == 'image' else m for m in job['media']]
        key = digest([budget['limits']['identity'], job['case'], 'semantic_adjudication_v38', job['payload'], task.SCHEMA,
                      job['template'], media, job['arm'], 8192])
        raw = read(diagnostic / 'ledger/jobs' / (key + '.json'))
        assert raw['execution_ref'] == key and raw['case_id'] == job['case'] and raw['slot'] == job['arm']
        response = read(diagnostic / 'responses' / (job['case'] + '-' + job['arm'] + '.json'))
        slots_seen.add(key)
        outcomes[raw['outcome']] += 1
        if raw['outcome'] == 'completed':
            assert response['judgment'] == raw['parsed'] and response['execution_ref'] == key
            inputs += raw['response']['promptTokens']
            completions += raw['response']['completionTokens']
            label = raw['parsed']['label']
            arm_correct[job['arm']] += (task.LABELS.index(label) if label in task.LABELS else -1) == cases[job['case']]['reference']
        else:
            assert response['judgment'] is None and response['error']
            failure_cases.append({'case': job['case'], 'arm': job['arm']})
        assert cases[job['case']]['source_group'] not in job['example_source_groups']
    assert slots_seen == set(budget['attempted_slots'])
    assert inputs == budget['input_tokens']
    assert completions + 8192 * len(failure_cases) == budget['completion_tokens_or_reserved']
    assert all(c['search'] == 2 and c['final'] == 0 for c in budget['cases'].values())
    reported = read(diagnostic / 'results.json')['correct']
    assert arm_correct['direct'] == reported['direct'] and arm_correct['calibrated'] == reported['calibrated']
    reserved = ROOT / 'logs/exps/261020-validation-reservation-v39'
    reserved_inputs = read(reserved / 'inputs_without_labels.json')
    assert len(reserved_inputs) == len({e['source_group'] for e in reserved_inputs}) == 80
    assert not source_groups & {e['source_group'] for e in reserved_inputs}
    assert all('reference' not in e and 'human_score' not in e for e in reserved_inputs)
    result = {'passed': True, 'original_training_slots_verified': slots, 'original_distinct_cases': n,
              'candidate_configurations_recounted': candidate_count, 'best_router_predictions_refitted': recreated,
              'best_router_correct': sum(r['routed'] == r['reference'] for r in stored.values()),
              'overall_target_met': False, 'fresh_validation_performed': False,
              'diagnostic': {'attempts': 48, 'outcomes': dict(outcomes), 'known_input_tokens': inputs,
                             'known_completion_tokens': completions, 'completion_tokens_or_reserved': budget['completion_tokens_or_reserved'],
                             'correct': dict(arm_correct), 'failures_retained': failure_cases,
                             'recorded_usage_estimate_usd': inputs * 2 / 1e6 + completions * 10 / 1e6,
                             'cost_including_failed_output_reservations_usd': inputs * 2 / 1e6 + budget['completion_tokens_or_reserved'] * 10 / 1e6},
              'reserved_validation_sources_disjoint': 80}
    out.mkdir(parents=True)
    save_json(out / 'verification.json', result)
    (out / 'run.log').write_text('Recounted 22 candidate configurations; refitted best 52-source router; independently audited 48 paid diagnostic attempts and reservation.\n')
    (out / 'llm-histories.log').write_text('Zero additional model calls in this audit.\n')
    save_json(out / 'manifest.json', {'auditor_sha256': fingerprint(__file__), 'source_results': {str(p / 'results.json'): fingerprint(p / 'results.json') for p in roots.values()},
              'diagnostic_budget_sha256': fingerprint(diagnostic / 'ledger/budget.json')})
    print(result, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    audit(args.output_dir.resolve())
