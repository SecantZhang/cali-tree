"""Freeze and execute the winning visual policy against all915 bound inputs."""
import argparse
from pathlib import Path

import numpy as np
from catboost import CatBoostClassifier

from critical.core.calibration.visual_semantic_policy_v69 import export_classifier, VisualSemanticPolicy
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.core.decision.artifacts import save_json, digest
from critical.vision import paired_features_v69 as vision
from critical.vision.paired_encoder_v69 import encoder_spec
from run.calitree_visual_policy_v64 import visual_arrays, VISION
from run.calitree_simplified_policy_v44 import feature_columns
from run.calitree_cached_judgments_v60 import judgments
from run.calitree_guarded_forward_v32 import SOURCE
from run.calitree_continuous_policy_v43 import EXPANSION
from run.calitree_matched_policy_v58 import COLLECTION
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint

STUDY = ROOT / 'logs/exps/261021-visual-policy-v64'
AUDIT = ROOT / 'logs/exps/261021-visual-goal-audit-v69'


def bound_inputs(examples):
    old = {}
    for bank in (1, 2, 3):
        old.update(old_inputs(PREVIOUS, bank)[4])
    result, sources = {}, {}
    for e in examples:
        case = e['case']
        if case in old:
            entry = old[case]
            obs, meaning = entry['observation'], entry['interpretation']
        elif case.startswith('N'):
            path = SOURCE / 'extraction/cases' / (case + '.json')
            value = read(path)
            obs = value['observation']['observation'] if value['observation'] else None
            meaning_path = SOURCE / 'interpretations' / (case + '.json')
            meaning = read(meaning_path)['interpretation'] if meaning_path.exists() else None
            sources[str(path)] = fingerprint(path)
            if meaning_path.exists():
                sources[str(meaning_path)] = fingerprint(meaning_path)
        else:
            directory = EXPANSION if case.startswith('T') else COLLECTION if case.startswith('S') else ROOT / 'logs/exps/261020-aurora-pilot80-v29-run1/collection'
            path = directory / 'cases' / (case + '.json')
            value = read(path)
            obs, meaning = value['observation'], value['interpretation']
            sources[str(path)] = fingerprint(path)
        result[case] = {'observation': obs, 'interpretation': meaning}
    return result, sources


def run(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    audited = read(AUDIT / 'verification.json')
    assert audited['passed'] and audited['correct'] == 222 and audited['original_training_slots_correct'] == 144
    local, recent, extra, experts, names, X, actions, _ = visual_arrays()
    examples = local + recent + extra
    y = np.asarray([e['reference'] for e in examples])
    columns = feature_columns(names, X, list(range(915)), 'dedup_noexpert')
    stored = next(f for f in read(STUDY / 'folds.json') if f['candidate'] == 'boost_full_vision' and f['fold'] == 5)
    assert stored['selected_features'] == [names[i] for i in columns]
    weights = np.where(np.arange(915) < 99, stored['original_weight'], 1.)
    model = CatBoostClassifier(loss_function='MultiClass', depth=8, iterations=1200, learning_rate=.05, l2_leaf_reg=3.,
                random_seed=20261021, thread_count=2, verbose=False, allow_writing_files=False, bootstrap_type='No', random_strength=0.)
    model.fit(X[:, columns], y, sample_weight=weights)
    model.set_feature_names([names[i] for i in columns])
    out.mkdir(parents=True)
    model.save_model(str(out / 'classifier-native.json'), format='json')
    identity = read(VISION / 'encoder_identity.json')
    artifact = export_classifier(read(out / 'classifier-native.json'), [names[i] for i in columns], experts, identity)
    save_json(out / 'policy.json', artifact)
    runtime = VisualSemanticPolicy(read(out / 'policy.json'))
    cached, judgment_sources = judgments(examples)
    bounds, bound_sources = bound_inputs(examples)
    inputs = {e['case']: e for e in read(VISION / 'inputs_without_labels.json')}
    rows = []
    for i, (e, probability) in enumerate(zip(examples, model.predict_proba(X[:, columns]))):
        case = e['case']
        pair = image_identity(inputs[case]['evidence'])[1]
        measured = read(VISION / 'cases' / (case + '.json'))['measurements']
        visual = {'version': vision.VERSION, 'feature_contract_ref': vision.CONTRACT_REF,
                  'program_ref': e['program']['program_ref'], 'image_pair_ref': pair,
                  'encoder_spec_ref': digest(encoder_spec(identity)), 'measurements': measured}
        route = runtime.resolve_bound(e['program'], bounds[case]['observation'], pair, bounds[case]['interpretation'], cached[case], visual)
        covered = e['features'] is not None and any(a >= 0 for a in actions[i])
        expected = int(np.argmax(probability)) if covered else e['regular']
        assert route['prediction'] == expected and route['covered'] == covered, (case, route, expected)
        if covered:
            assert np.allclose(route['class_support'], probability, atol=1e-10, rtol=0), case
        rows.append({'case': case, 'reference': e['reference'], 'prediction': route['prediction'], 'covered': route['covered']})
    assert all(r['prediction'] == r['reference'] for r in rows[:99])
    result = {'passed': True, 'source_held_development': audited,
              'original_correct': 99, 'original_cases': 99, 'original_training_slots': 144,
              'bound_runtime_cases_replayed': 915, 'native_json_predictions_match': 915,
              'fitting_correct': sum(r['prediction'] == r['reference'] for r in rows),
              'fitting_covered': sum(r['covered'] for r in rows), 'trees': len(artifact['classifier']['trees']),
              'features': len(columns), 'serving_default_changed': False, 'new_paid_model_calls': 0,
              'scope': 'Frozen reusable inference artifact. Fitting scores are not generalization accuracy.'}
    save_json(out / 'verification.json', result)
    save_json(out / 'fitting_replay.json', rows)
    save_json(out / 'manifest.json', {'policy_sha256': fingerprint(out / 'policy.json'), 'selection_audit_sha256': fingerprint(AUDIT / 'verification.json'),
              'bound_source_hashes': bound_sources, 'judgment_source_hashes': judgment_sources,
              'code_hashes': {str(Path(p).resolve()): fingerprint(p) for p in (__file__, ROOT / 'critical/core/calibration/visual_semantic_policy_v69.py',
               ROOT / 'critical/vision/paired_features_v69.py', ROOT / 'critical/vision/paired_encoder_v69.py')}})
    (out / 'run.log').write_text('Froze classifier and encoder contracts; all915 raw-bound portable JSON predictions match native classifier; original99 retained.\n')
    (out / 'llm-histories.log').write_text('Zero model API calls.\n')
    print(result, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())
