"""Independent count replay and completion audit of the approved 36-case run."""
import argparse
from collections import Counter
from pathlib import Path

from critical.core.decision.artifacts import save_json
from run.calitree_aurora_pilot_v29 import read, fingerprint
from run.collect_calitree_guarded_forward_v32 import verify
from run.analyze_calitree_guarded_forward_v35 import policies, verify_collection
from run.calitree_fallback_routing_v34 import old_examples

LABELS = ('no', 'partial', 'yes')


def count_metrics(rows, arm):
    n = len(rows)
    correct = sum(r[arm] == r['reference'] for r in rows)
    accepted = [r for r in rows if arm != 'regular' and r['routes'][arm]['covered']]
    f1, recalls = [], {}
    for label, name in enumerate(LABELS):
        tp = sum(r[arm] == label and r['reference'] == label for r in rows)
        fp = sum(r[arm] == label and r['reference'] != label for r in rows)
        fn = sum(r[arm] != label and r['reference'] == label for r in rows)
        f1.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0)
        recalls[name] = tp / (tp + fn) if tp + fn else 0
    return {'total': n, 'correct': correct, 'accuracy': correct / n,
            'macro_f1': sum(f1) / 3, 'class_recall': recalls,
            'unresolved': sum(r[arm] == -1 for r in rows), 'tree_accepted': len(accepted),
            'tree_coverage': len(accepted) / n,
            'accepted_accuracy': sum(r[arm] == r['reference'] for r in accepted) / len(accepted) if accepted else None}


def audit(out, serving):
    verify(out)
    policies(out)
    execution = verify_collection(out)
    authorization = read(out / 'authorization.json')
    assert authorization['max_requests'] == 36 and authorization['max_completion_tokens'] == 73728
    assert authorization['collector_plan_sha256'] == fingerprint(out / 'execution_plan.json')
    plan = read(out / 'supplemental_v35/analysis_plan.json')
    for file, expected in plan['analysis_code_hashes'].items():
        assert fingerprint(file) == expected, file
    rows = read(out / 'supplemental_v35/full_predictions.json')
    reported = read(out / 'supplemental_v35/full_results.json')
    inputs = {e['case']: e for e in read(out / 'inputs.json')}
    fit_sources = set(read(out.parent / '261020-regular-aware-v35/freeze.json')['training_source_groups'])
    for bank in (1, 2, 3):
        fit_sources.update(e['source_group'] for e in old_examples(bank))
    assert not fit_sources & {e['source_group'] for e in inputs.values()}
    assert len(rows) == 36 and len({r['source_group'] for r in rows}) == 36
    assert Counter(r['reference'] for r in rows) == {0: 12, 1: 12, 2: 12}
    for arm, expected in reported['metrics'].items():
        actual = count_metrics(rows, arm)
        assert actual == expected, (arm, actual, expected)
    successful = [r for r in rows if r['regular_error'] is None and inputs[r['case']]['features'] is not None]
    wins = {}
    for bank in (1, 2, 3):
        arm = f'regular_aware_split{bank}'
        old = f'v27_split{bank}'
        wins[str(bank)] = {'wins': [r['case'] for r in rows if r[arm] == r['reference'] and r[old] != r['reference']],
                           'losses': [r['case'] for r in rows if r[arm] != r['reference'] and r[old] == r['reference']]}
    assert [len(wins[str(b)]['wins']) for b in (1, 2, 3)] == [0, 0, 1]
    assert all(not v['losses'] for v in wins.values())
    serving_result = read(serving / 'verification.json')
    assert serving_result['passed'] and serving_result['counts']['local_routes_retained'] == 144
    assert serving_result['counts']['previous_correct_routes_retained'] == 179
    assert serving_result['counts']['hypothetical_wrapper_scenarios'] == 432
    completed = [read(p) for p in (out / 'ledger/jobs').glob('*.json') if read(p)['outcome'] == 'completed']
    known_completion = sum(j['response']['completionTokens'] for j in completed)
    known_input = sum(j['response']['promptTokens'] for j in completed)
    assert known_input == execution['input_tokens']
    result = {'passed': True, 'execution': execution, 'metric_arms_independently_recounted': len(reported['metrics']),
              'serving_default_vs_v27': wins, 'source_groups': 36, 'fitting_source_overlap': False,
              'new_fitting': False, 'known_completion_tokens': known_completion,
              'failed_attempt_completion_reservation': execution['completion_tokens_or_reserved'] - known_completion,
              'recorded_usage_cost_estimate_usd': known_input * .10 / 1e6 + known_completion * .50 / 1e6,
              'cost_including_failed_output_reservation_usd': known_input * .10 / 1e6 + execution['completion_tokens_or_reserved'] * .50 / 1e6,
              'cost_note': 'Estimate at previously verified Luna rates; failed-request billing/input usage is unknown. Not an invoice.',
              'regular_failures': [r['case'] for r in rows if r['regular_error']],
              'missing_upstream_evidence': [k for k, e in inputs.items() if e['features'] is None],
              'both_stages_successful_cases': len(successful),
              'both_stages_successful_metrics': {a: count_metrics(successful, a) for a in ('regular', 'v27_split1', 'v27_split2', 'v27_split3',
                                                                                       'regular_aware_split1', 'regular_aware_split2', 'regular_aware_split3')},
              'limitations': ['Older research exposure is disclosed; sources excluded from fitting these fixes.',
                              'Only one additional correct decision on the 36-case cohort, not strong statistical evidence.',
                              'Serving mode was selected after comparing predeclared arms; all banks are reported.']}
    save_json(out / 'execution_audit.json', result)
    print(result, flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--serving-audit-dir', type=Path, required=True)
    args = parser.parse_args()
    audit(args.output_dir.resolve(), args.serving_audit_dir.resolve())
