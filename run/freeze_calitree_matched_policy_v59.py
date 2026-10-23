"""Freeze the independently replayed matched-editor research policy."""
import argparse
from pathlib import Path

import numpy as np

from critical.core.calibration.semantic_policy_v59 import export_policy, SemanticPolicy
from critical.core.decision.artifacts import save_json
from run.calitree_accuracy_headroom_v37 import encoded
from run.calitree_continuous_policy_v43 import examples_and_scores
from run.calitree_simplified_policy_v44 import feature_columns
from run.calitree_matched_policy_v58 import COLLECTION, model_for, probabilities, decisions
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint

STUDY = ROOT / 'logs/exps/261021-matched-policy-v58'
AUDIT = ROOT / 'logs/exps/261021-matched-policy-audit-v58'


def run(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    audit = read(AUDIT / 'verification.json')
    assert audit['passed'] and audit['full_original_correct'] == 99 and audit['original_training_slots_correct'] == 144
    winner = read(STUDY / 'selection.json')
    assert winner['candidate'] == audit['candidate'] and winner['arm'] == audit['arm']
    cfg = read(STUDY / 'results.json')['candidates'][winner['candidate']]['config']
    local, recent, experts, _ = examples_and_scores(True)
    extra = [{**e, 'cohort': 'matched540'} for e in read(COLLECTION / 'training_data.json')]
    examples = local + recent + extra
    half = set(read(STUDY / 'manifest.json')['half_cases'])
    chosen = set() if cfg['coverage'] == 'zero' else half if cfg['coverage'] == 'half' else {e['case'] for e in extra}
    train = list(range(375)) + [375 + i for i, e in enumerate(extra) if e['case'] in chosen]
    names, X, actions = encoded(examples, experts)
    y = np.asarray([e['reference'] for e in examples])
    weights = np.ones(len(examples))
    weights[:99] = cfg['original_weight']
    cols = feature_columns(names, X, train, 'dedup_noexpert')
    model = model_for(cfg).fit(X[train][:, cols], y[train], sample_weight=weights[train])
    mode = 'direct' if winner['arm'] == 'direct' else 'routed'
    threshold = float(winner['arm'][5:]) if winner['arm'].startswith('gate_') else 0.
    artifact = export_policy(model, [names[i] for i in cols], experts, family=cfg['family'], mode=mode, threshold=threshold)
    runtime = SemanticPolicy(artifact)
    rows = []
    for i, p in enumerate(probabilities(model, X[:, cols], cfg['family'])):
        e = examples[i]
        expected = decisions(p, e, actions[i])
        actual = runtime.resolve(e['program'], e['features'], e['regular'])
        assert actual['prediction'] == expected[winner['arm']], e['case']
        if e['features'] is not None:
            assert np.allclose(actual['class_support'], p, rtol=0, atol=1e-12), e['case']
        covered_key = 'accept_' + str(threshold)
        assert actual['covered'] == expected[covered_key], e['case']
        rows.append({'case': e['case'], 'reference': e['reference'], 'prediction': actual['prediction'],
                     'covered': actual['covered'], 'support': actual['support'], 'in_full_fit': i in train})
    assert all(r['prediction'] == r['reference'] for r in rows[:99])
    result = {'candidate': winner['candidate'], 'arm': winner['arm'], 'source_held_development': audit['metrics'],
              'original_correct': 99, 'original_cases': 99, 'original_slots_verified': 144,
              'round_trip_pool_cases': len(rows), 'full_fit_rows': len(train),
              'pool_replay_correct': sum(r['prediction'] == r['reference'] for r in rows),
              'pool_replay_covered': sum(r['covered'] for r in rows),
              'fitting_correct': sum(r['prediction'] == r['reference'] for r in rows if r['in_full_fit']),
              'trees': sum(len(h['trees']) for h in artifact['heads']), 'feature_columns': len(cols),
              'new_model_calls': 0, 'reserved_sources_used': 0, 'serving_default_changed': False, 'target_verified': False,
              'scope': 'Optional frozen research artifact. Pool replay/fitting accuracy is not generalization accuracy.'}
    out.mkdir(parents=True)
    save_json(out / 'policy.json', artifact)
    save_json(out / 'pool_replay.json', rows)
    save_json(out / 'verification.json', result)
    upstream = read(COLLECTION / 'preflight_seal.json')['files']
    hashes = {p: sha for p, sha in upstream.items() if Path(p).is_absolute()}
    hashes.update({str(Path(p).resolve()): fingerprint(p) for p in (__file__,
                  ROOT / 'critical/core/calibration/semantic_policy_v59.py', ROOT / 'run/calitree_matched_policy_v58.py',
                  ROOT / 'critical/core/calibration/boundary_experts_v55.py')})
    assert all(fingerprint(p) == expected for p, expected in hashes.items())
    save_json(out / 'manifest.json', {'code_and_prompt_hashes': hashes,
              'selection_sha256': fingerprint(STUDY / 'selection.json'),
              'selection_audit_sha256': fingerprint(AUDIT / 'verification.json'),
              'collection_manifest_sha256': fingerprint(COLLECTION / 'manifest.json'),
              'policy_sha256': fingerprint(out / 'policy.json')})
    (out / 'run.log').write_text('Froze selected research policy; replayed all 915 pool decisions and support scores against sklearn. Original 99 retained. No serving change or final evaluation.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')
    print(result, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())
