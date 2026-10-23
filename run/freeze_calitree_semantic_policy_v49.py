"""Freeze and round-trip the independently selected research candidate."""
import argparse
from pathlib import Path

import numpy as np

from critical.core.calibration.semantic_expert_policy_v49 import export_forest, SemanticExpertPolicy
from critical.core.decision.artifacts import save_json
from run.calitree_accuracy_headroom_v37 import encoded, Probe
from run.calitree_continuous_policy_v43 import examples_and_scores
from run.calitree_simplified_policy_v44 import feature_columns
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint


def run(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    audit = ROOT / 'logs/exps/261020-expanded-policy-audit-v47/verification.json'
    winner = read(audit)['best_verified_routed_policy']
    assert (winner['study'], winner['candidate'], winner['arm']) == ('simplified', 'dedup_noexpert_sqrt', 'gate_0.0')
    local, recent, experts, _ = examples_and_scores(True)
    examples = local + recent
    names, X, actions = encoded(examples, experts)
    y = np.asarray([e['reference'] for e in examples])
    columns = feature_columns(names, X, list(range(len(examples))), 'dedup_noexpert')
    model = Probe('forest', 'sqrt').fit(X[:, columns], y).model
    artifact = export_forest(model, [names[i] for i in columns], experts)
    runtime = SemanticExpertPolicy(artifact)
    records = []
    for i, (e, probability) in enumerate(zip(examples, model.predict_proba(X[:, columns]))):
        route = runtime.resolve(e['program'], e['features'], e['regular'])
        available = sorted({p for p in actions[i] if p >= 0})
        expected = max(available, key=lambda c: (float(probability[c]), -c)) if available else -1
        if e['features'] is None:
            expected = e['regular']
        else:
            assert np.allclose(route['probabilities'], probability, rtol=0, atol=1e-12)
        assert route['prediction'] == expected
        records.append({'case': e['case'], 'reference': e['reference'], 'prediction': expected,
                        'covered': route['covered'], 'confidence': route['confidence']})
    assert all(r['prediction'] == r['reference'] and r['covered'] for r in records[:99])
    result = {'original_training_correct': 99, 'original_training_cases': 99, 'original_training_slots': 144,
              'round_trip_cases': len(examples), 'full_fitting_correct': sum(r['prediction'] == r['reference'] for r in records),
              'full_fitting_covered': sum(r['covered'] for r in records), 'trees': len(artifact['forest']),
              'feature_columns': len(columns), 'expert_input_columns': sum(n.startswith('expert_') for n in artifact['feature_names']),
              'source_held_out_development': winner, 'target_met': False, 'serving_default_changed': False,
              'scope': 'Frozen research candidate fit on all 375 current examples. Fitting accuracy is not generalization accuracy.',
              'new_model_calls': 0, 'reserved_validation_sources_used': 0}
    out.mkdir(parents=True)
    save_json(out / 'selector.json', artifact)
    save_json(out / 'fitting_predictions.json', records)
    save_json(out / 'verification.json', result)
    save_json(out / 'manifest.json', {'selection_audit_sha256': fingerprint(audit), 'code_hashes': {str(p): fingerprint(p) for p in
              (Path(__file__).resolve(), ROOT / 'critical/core/calibration/semantic_expert_policy_v49.py',
               ROOT / 'run/calitree_simplified_policy_v44.py')}})
    (out / 'run.log').write_text('Froze selected optional semantic expert selector; all 375 JSON/sklearn predictions match and all 99 original cases remain covered/correct. Serving defaults unchanged.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')
    print(result, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())
