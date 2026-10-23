"""Explain the fixed matched-editor comparison without fitting new policies."""
import argparse
from collections import Counter, defaultdict
from pathlib import Path

from critical.core.decision.artifacts import save_json, digest
from run.calitree_accuracy_headroom_v37 import encoded, accuracy
from run.calitree_continuous_policy_v43 import examples_and_scores
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint

STUDY = ROOT / 'logs/exps/261021-matched-policy-v58'
COLLECTION = ROOT / 'logs/exps/261021-sibling-training-v57'
COMPARISONS = {'prior': ('boundary_zero_w1.0', 'routed'),
               'expanded_same_coverage': ('forest_full_w5.0', 'routed'),
               'expanded_tighter_gate': ('boundary_full_w1.0', 'gate_0.5')}


def run(out):
    if out.exists():
        raise ValueError('Fresh analysis directory required')
    source = read(STUDY / 'predictions.json')
    records = {key: {r['case']: r for r in source if r['candidate'] == candidate}
               for key, (candidate, arm) in COMPARISONS.items()}
    results = read(STUDY / 'results.json')['candidates']
    summary = {}
    for key, (candidate, arm) in COMPARISONS.items():
        rows = list(records[key].values())
        threshold = arm[5:] if arm.startswith('gate_') else '0.0'
        accepted = [r for r in rows if r['accept_' + threshold]]
        corrections, losses, changed = [], [], []
        for r in rows:
            before = records['prior'][r['case']]['routed']
            if before != r[arm]:
                changed.append(r['case'])
            if before != r['reference'] and r[arm] == r['reference']:
                corrections.append(r['case'])
            if before == r['reference'] and r[arm] != r['reference']:
                losses.append(r['case'])
        summary[key] = {'candidate': candidate, 'arm': arm, **accuracy(rows, arm),
                        'class_recall': results[candidate]['metrics']['all'][arm]['class_recall'],
                        'confusion_reference_rows_prediction_columns': [[sum(r['reference'] == c and r[arm] == p for r in rows) for p in (-1, 0, 1, 2)] for c in (0, 1, 2)],
                        'tree_accepted': len(accepted), 'accepted_correct': sum(r[arm] == r['reference'] for r in accepted),
                        'regular_fallbacks': len(rows) - len(accepted),
                        'original_retention': results[candidate]['retention'][arm],
                        'changed_vs_prior': changed, 'corrections_vs_prior': corrections, 'new_errors_vs_prior': losses}
    local, recent, experts, _ = examples_and_scores(True)
    extra = read(COLLECTION / 'training_data.json')
    examples = local + recent + extra
    names, X, _ = encoded(examples, experts)
    columns = [i for i, name in enumerate(names) if not name.startswith('expert_')]
    buckets = defaultdict(list)
    for e, vector in zip(examples, X[:, columns]):
        buckets[digest(vector.tolist())].append(e)
    conflicts = [es for es in buckets.values() if len({e['reference'] for e in es}) > 1]
    affected_originals = []
    for es in conflicts:
        for e in es:
            if e['case'] in {r['case'] for r in local}:
                affected_originals.append({'case': e['case'], 'reference': e['reference'],
                                          'other_reference_counts': dict(Counter(r['reference'] for r in es if r['case'] != e['case'])),
                                          'other_cases': [r['case'] for r in es if r['case'] != e['case']]})
    data = {'comparisons': summary, 'regular': accuracy(list(records['prior'].values()), 'regular'),
            'reference_counts': {'prior375': dict(Counter(e['reference'] for e in local + recent)),
                                 'new540': dict(Counter(e['reference'] for e in extra)),
                                 'pool915': dict(Counter(e['reference'] for e in examples))},
            'feature_identifiability': {'pool_cases': 915, 'distinct_semantic_vectors': len(buckets),
                  'contradictory_feature_groups': len(conflicts),
                  'equality_upper_bound_correct': sum(max(Counter(e['reference'] for e in es).values()) for es in buckets.values()),
                  'original_examples_in_conflicting_groups': affected_originals,
                  'note': 'Descriptive equality bound only, not a fitted policy or achievable unseen accuracy. Conflicting feature groups are not used as inference lookup rules.'},
            'new_model_calls': 0, 'new_policy_fits': 0, 'reserved_sources_used': 0,
            'scope': 'Post-comparison development error analysis; no new model selection or serving changes.'}
    out.mkdir(parents=True)
    save_json(out / 'analysis.json', data)
    save_json(out / 'manifest.json', {'analysis_code_sha256': fingerprint(__file__),
              'study_results_sha256': fingerprint(STUDY / 'results.json'), 'training_data_sha256': fingerprint(COLLECTION / 'training_data.json')})
    (out / 'run.log').write_text('Recounted class recall, coverage, corrections/losses, label mix and semantic-vector conflicts; zero fits/calls.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')
    print({key: {k: v for k, v in value.items() if k in ('correct', 'total', 'class_recall', 'tree_accepted', 'accepted_correct', 'regular_fallbacks')}
           for key, value in summary.items()}, flush=True)
    print(data['feature_identifiability'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())
