"""Describe remaining decision headroom without claiming an evidence oracle."""
import argparse
from collections import Counter
from pathlib import Path

from critical.core.decision.artifacts import save_json
from run.calitree_continuous_policy_v43 import examples_and_scores
from run.calitree_accuracy_headroom_v37 import encoded
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint


def run(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    local, recent, experts, means = examples_and_scores(True)
    _, _, actions = encoded(local + recent, experts)
    source = ROOT / 'logs/exps/261020-expanded-simplified-v44/predictions.json'
    predictions = {r['case']: r for r in read(source) if r['candidate'] == 'dedup_noexpert_sqrt'}
    counts, rows = Counter(), []
    for i, e in enumerate(recent, len(local)):
        p = predictions[e['case']]
        available = e['reference'] in actions[i]
        counts['oracle_available_correct'] += available
        if p['routed'] == e['reference']:
            continue
        kind = 'wrong_selection' if available else 'unavailable_label'
        harmful = e['regular'] == e['reference']
        counts[kind] += 1
        counts['harmful_override'] += harmful
        values = e['features']['features'] if e['features'] else {}
        rows.append({'case': e['case'], 'source_group': e['source_group'], 'cohort': e['cohort'],
                     'instruction': e['program']['instruction'] if e['program'] else None,
                     'reference': e['reference'], 'human_mean': means[e['case']], 'regular': e['regular'],
                     'prediction': p['routed'], 'confidence': p['confidence'], 'label_availability': kind,
                     'harmful_override': harmful, 'available_judge_labels': sorted(set(actions[i])),
                     'semantic_conditions': [k for k, value in values.items() if value and k.startswith('meaning_') and k.endswith('_all')]})
    summary = {'development_cases': len(recent), 'wrong': len(rows), **dict(counts), 'new_model_calls': 0,
               'remaining_cases_needed_for_over_85': 20, 'multi_requirement_examples_in_full_pool': sum(len(e['program']['requirements']) > 1 for e in local + recent if e['program']),
               'confidence_review_bounds': [],
               'interpretation': 'Available correct labels are an optimistic action bound, not proof of correct physical evidence or a reliable expert. No oracle routing or source/case lookup is deployed.'}
    for threshold in (.5, .6, .65, .75, .8):
        low = [r for r in predictions.values() if r['confidence'] < threshold]
        summary['confidence_review_bounds'].append({'threshold': threshold, 'cases': len(low),
             'wrong': sum(r['routed'] != r['reference'] for r in low),
             'regular_would_correct': sum(r['routed'] != r['reference'] and r['regular'] == r['reference'] for r in low)})
    out.mkdir(parents=True)
    save_json(out / 'summary.json', summary)
    save_json(out / 'errors.json', rows)
    save_json(out / 'manifest.json', {'code_sha256': fingerprint(__file__), 'source_predictions_sha256': fingerprint(source),
                                    'fitting_data_sha256': fingerprint(ROOT / 'logs/exps/261020-training-expansion-v42/training_data.json')})
    (out / 'run.log').write_text('Counted action availability, harmful overrides, confidence-review upper bounds and multi-requirement incidence. No causal evidence-grounding verdicts inferred from human labels alone.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')
    print(summary, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())
