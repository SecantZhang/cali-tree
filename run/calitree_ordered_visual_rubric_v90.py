"""Test human-grade order with the existing visual/semantic Boolean features.

The learned boundaries predict human grade thresholds; they do not certify
physical progress or completion. The unchanged explicit rubric supplies any
affirmative evidence warrant required by a gated arm.
"""
import argparse
from pathlib import Path
import shutil

import catboost
import numpy as np

from critical.core.calibration.ordinal_boost_v62 import OrdinalBoost
from critical.core.decision.artifacts import digest, save_json
from run.calitree_source_excluded_calibration_v89 import baseline_predictions, EXPERT
from run.calitree_seeded_rubric_v73 import arrays
from run.calitree_semantic_rubric_v70 import data, ROOT, STUDY, read, fingerprint
from run.calitree_warranted_rubric_v71 import TEACHERS
from run.calitree_ordinal_boost_v62 import fitting_metadata
from run.calitree_continuous_policy_v43 import examples_and_scores
from run.calitree_matched_policy_v58 import COLLECTION
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS
from run.calitree_accuracy_headroom_v37 import accuracy

CONFIGS = [(family, alpha, warranted) for family in ('ordinal', 'relative_mean')
           for alpha in (.25, .5, 1.) for warranted in (False, True)]


def candidate_name(family, alpha, warranted):
    return family+'_weight'+str(alpha)+'_warrant'+str(warranted)


def run(out):
    if out.exists():
        raise ValueError('Fresh experiment directory required')
    examples, feature_names, X = data(); semantic_examples, names, raw, semantic = arrays()
    assert examples == semantic_examples and len(examples) == 915
    y = np.asarray([e['reference'] for e in examples]); groups = np.asarray([e['source_group'] for e in examples])
    regular = np.asarray([e['regular'] for e in examples]); valid = np.asarray([e['covered'] for e in examples]); pos = {e['case']: i for i, e in enumerate(examples)}
    # Obtain only the already authorized fitting/development labels. No newly
    # collected contrastive responses or reserved labels enter this experiment.
    local, recent, _, _ = examples_and_scores(True)
    extra = read(COLLECTION/'training_data.json'); metadata = local+recent+extra
    assert [e['case'] for e in metadata] == [e['case'] for e in examples]
    means, tasks = fitting_metadata(metadata)
    originals = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    # Use precisely the existing generic expert labels selected in the verified
    # v87 replay, without reading the new contrastive pilot or sending requests.
    from run.calitree_cached_sol_router_v85 import cached
    sol, _ = cached(examples)
    prior = {r['case']: r for r in read(EXPERT/'predictions.json')}
    warrants = np.asarray([[s['rubric_'+label+'_ready'] for label in ('no', 'partial', 'yes')] for s in semantic], dtype=bool)
    protocol = {
        'version': 'ordered-visual-semantic-rubric-v90', 'configs': CONFIGS,
        'motivation': 'The prior ordinal/continuous objectives preceded paired vision. Test the ordered human-grade objectives with the exact stronger v64/v69 Boolean visual/semantic features, rather than adjusting multiclass scores alone.',
        'features': 'Exactly the train-only feature selection and outer membership of boost_full_vision; no new encoder calls, raw embeddings, IDs or object names.',
        'models': {'ordinal': 'Two1200-tree depth8 binary classifiers predict human grade>0 and>1. Project second support<=first, then form No/Partial/Yes masses.', 'relative_mean': 'Depth8/1200-tree shared-split regression to human mean and within-fitting-task centered human mean. Inference uses only the global-mean output with unchanged .5/1.5 grade boundaries.'},
        'interpretation': 'The two binary supports estimate human grade thresholds; they are not direct physical progress/endpoint measurements or calibrated probabilities of correctness.',
        'fitting': 'Seed20261021, learning_rate.05, no bootstrap/random_strength,2threads. Original weight first of1/5/25 retaining99 actual argmax predictions; no held-label early stopping or parameter choice.',
        'arms': 'Geometric-free convex support blends with the old teacher, alpha .25/.5/1, optionally requiring an affirmative same-requirement warrant for every changed grade. No runtime labels or query references enter blending.',
        'priority': 'Existing v72/v87 keep their original v69 teacher context and precedence. Missing bound semantics retains regular fallback.',
        'scope': 'Same276 reviewed development cases/84sources/five outer source folds, all held-source siblings excluded; fold5 fits all915 without scoring. No untouched validation claim.',
        'new_api_calls': 0, 'new_encoder_calls': 0, 'reserved_sources_used': 0, 'new_pilot_responses_used': 0, 'serving_changed': False,
        'catboost_version': catboost.__version__,
    }
    out.mkdir(parents=True); save_json(out/'protocol.json', protocol)
    (out/'run.log').write_text('Ordered visual/semantic grading comparison started.\n')
    (out/'llm-histories.log').write_text('Zero API calls, uploads, neural inference or newly collected v75 response reads. Existing fitting labels and cached evidence only.\n')
    files = [Path(__file__), ROOT/'critical/core/calibration/ordinal_boost_v62.py', ROOT/'run/calitree_source_excluded_calibration_v89.py']
    code_hashes = {str(p): fingerprint(p) for p in files}
    for p in files:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    records, retention, memberships = [], [], []
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        train = [pos[c] for c in f['train_cases']]; held = [pos[c] for c in f['held_cases']]; folder = 'fold'+str(f['fold'])
        assert not set(groups[train]) & set(groups[held]) and set(range(99)) <= set(train)
        for task in set(tasks[train]):
            assert np.sum(tasks[train] == task) == 5
        cols = [feature_names.index(n) for n in f['selected_features']]; matrix = X[:, cols]
        ps = np.asarray(read(TEACHERS/folder/'predictions.json')['support'])
        current, locked = baseline_predictions(folder, names, raw, semantic, ps, regular, sol, valid)
        assert all(current[i] == prior[examples[i]['case']]['prediction'] for i in held)
        for family in ('ordinal', 'relative_mean'):
            model = OrdinalBoost(family=family, depth=8).fit(matrix[train], y[train], original=np.asarray(train) < 99, means=means[train], tasks=tasks[train])
            support = model.predict_proba(matrix); path = out/folder/family; path.mkdir(parents=True)
            native_models = model.models if family == 'ordinal' else [model.model]
            for j, native in enumerate(native_models):
                native.save_model(str(path/('model'+str(j)+'.cbm')))
            save_json(path/'model.json', {'family': family, 'depth': 8, 'iterations': 1200, 'columns': f['selected_features'],
                        'train_cases': f['train_cases'], 'held_cases': f['held_cases'], 'training_sources': sorted(set(groups[train])),
                        'held_sources': sorted(set(groups[held])), 'weight_trials': model.weight_trials,
                        'original_weight': model.original_weight, 'support': support.tolist(),
                        'matrix_ref': digest(matrix[train].tolist()), 'targets_ref': digest(y[train].tolist()),
                        'means_ref': digest(means[train].tolist()) if family == 'relative_mean' else None,
                        'tasks_ref': digest(tasks[train].tolist()) if family == 'relative_mean' else None})
            for _, alpha, warranted in [c for c in CONFIGS if c[0] == family]:
                name = candidate_name(family, alpha, warranted)
                prediction = np.argmax((1.-alpha)*ps+alpha*support, axis=1)
                if warranted:
                    veto = ~warrants[np.arange(len(prediction)), prediction]; prediction[veto] = np.argmax(ps[veto], axis=1)
                prediction[locked] = current[locked]; prediction[~valid] = regular[~valid]
                original_correct = int(np.sum(prediction[:99] == y[:99])); slots = int(sum(prediction[pos[r['case']]] == r['reference'] for r in originals))
                retention.append({'candidate': name, 'fold': f['fold'], 'original_correct': original_correct, 'original_slots': slots})
                save_json(path/(name+'.json'), {'alpha': alpha, 'requires_grading_warrant': warranted, 'predictions': prediction.tolist()})
                for i in held:
                    records.append({**examples[i], 'prediction': int(prediction[i]), 'baseline': int(current[i]),
                                    'candidate': name, 'fold': f['fold'], 'prior_rule_priority': bool(locked[i])})
            print({'fold': f['fold'], 'family': family, 'original_weight': model.original_weight, 'raw_original_correct': model.original_correct}, flush=True)
        memberships.append({'fold': f['fold'], 'train_cases': f['train_cases'], 'held_cases': f['held_cases'], 'selected_features': f['selected_features']})
        save_json(out/'predictions.json', records); save_json(out/'retention.json', retention); save_json(out/'memberships.json', memberships)
    results = {}
    for config in CONFIGS:
        name = candidate_name(*config); rows = [r for r in records if r['candidate'] == name]
        retained = all(r['original_correct'] == 99 and r['original_slots'] == 144 for r in retention if r['candidate'] == name)
        results[name] = {'accuracy': accuracy(rows, 'prediction'), 'baseline': accuracy(rows, 'baseline'),
                         'gains': sum(r['prediction'] == r['reference'] != r['baseline'] for r in rows),
                         'losses': sum(r['baseline'] == r['reference'] != r['prediction'] for r in rows),
                         'changes': sum(r['prediction'] != r['baseline'] for r in rows),
                         'all_original_cases_and_slots_retained': retained, 'upstream_evidence_coverage': sum(r['covered'] for r in rows),
                         'target_exceeded': retained and accuracy(rows, 'prediction')['correct'] >= 235}
    assert all(r['baseline']['correct'] == 225 and r['upstream_evidence_coverage'] == 273 for r in results.values())
    assert all(fingerprint(p) == sha for p, sha in code_hashes.items())
    save_json(out/'results.json', results)
    save_json(out/'manifest.json', {'protocol_ref': digest(protocol), 'code_sha256': code_hashes,
                'matrix_ref': digest(X.tolist()), 'targets_ref': digest(y.tolist()), 'means_ref': digest(means.tolist()),
                'tasks_ref': digest(tasks.tolist()), 'folds_sha256': fingerprint(STUDY/'folds.json'),
                'catboost_binary_sha256': fingerprint(catboost._catboost.__file__)})
    (out/'run.log').write_text('Completed two fixed ordered objectives and twelve decoding arms with unchanged source folds. Retention, coverage and measured comparisons are in results.json; no serving change.\n')
    print(results, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    run(p.parse_args().output_dir.resolve())
