"""Replay moderate-weight models and semantic heads from numeric JSON only."""
import argparse
from pathlib import Path
import shutil

from catboost import CatBoostClassifier
import numpy as np
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score

from critical.core.calibration.tempered_weights_v147 import weights
from critical.core.calibration.class_balance_v141 import classification_metrics, weight_receipt
from critical.core.calibration.semantic_residual_runtime_v104 import admissible
from critical.core.calibration import local_warranted_rubric_v97 as local
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_tempered_balance_v147 import EXPONENTS
from run.calitree_compact_balance_v143 import CACHE, CACHE_AUDIT, VERIFIED, SOURCE
from run.verify_calitree_semantic_residual_v105 import load, fold_arrays
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, data, read
from run.calitree_seeded_rubric_v73 import attach
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS


def native_scores(native, X):
    X = np.asarray(X, dtype=np.float32)
    columns = {f['feature_index']: f['flat_feature_index'] for f in native['features_info']['float_features']}
    scores = np.zeros((len(X), 3))
    for tree in native['oblivious_trees']:
        indices = np.zeros(len(X), dtype=int)
        for bit, split in enumerate(tree.get('splits') or []):
            assert split['split_type'] == 'FloatFeature'
            indices += (X[:, columns[split['float_feature_index']]] > np.float32(split['border'])).astype(int)*(2**bit)
        scores += np.asarray(tree['leaf_values']).reshape(-1, 3)[indices]
    scale, bias = native['scale_and_bias']
    return scores*scale+np.asarray(bias)


def audit(study, out):
    if out.exists():
        raise ValueError('Fresh moderate-weight audit required')
    producer = read(study/'manifest.json'); protocol = read(study/'protocol.json')
    assert producer['protocol_ref'] == digest(protocol)
    for p, sha in producer['code_sha256'].items():
        assert file_hash(p) == file_hash(study/'source_snapshot'/Path(p).relative_to(ROOT)) == sha
    assert producer['selected_pipeline_sha256'] == file_hash(ROOT/'critical/core/calibration/artifacts/calitree_current.json')
    d = load(CACHE, CACHE_AUDIT); examples, names, X = data(); assert examples == d['examples']
    prior = {r['case']: r for r in read(VERIFIED/'predictions.json')}
    slots = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    out.mkdir(parents=True); (out/'run.log').write_text('Independent native main/head execution and class-weight replay started.\n')
    (out/'llm-histories.log').write_text('Zero API/encoder/observer calls. Existing data and fitted native JSON only.\n')
    rows = []; retention = []; maximum_main = 0.; models = 0
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        a = fold_arrays(d, f); train = [d['pos'][case] for case in f['train_cases']]
        assert not set(d['groups'][train]) & set(d['groups'][a['held']])
        for exponent in EXPONENTS:
            folder = study/'teachers'/('eta'+str(exponent))/a['folder']
            metadata = read(folder/'metadata.json'); contract = metadata['contract']
            assert contract['rows'] == train
            columns = [names.index(n) for n in contract['columns']]
            assert contract['matrix_ref'] == digest(X[train][:, columns].tolist())
            assert contract['targets_ref'] == digest(d['y'][train].tolist())
            w = weights(d['y'][train], exponent, np.asarray(train) < 99, metadata['original_multiplier'])
            assert metadata['weight_ref'] == digest(w.tolist())
            assert metadata['weight_receipt'] == weight_receipt(d['y'][train], w)
            native = read(folder/'native.json'); logits = native_scores(native, X[:, columns])
            probability = np.exp(logits-logits.max(axis=1, keepdims=True)); probability /= probability.sum(axis=1, keepdims=True)
            stored = np.asarray(read(folder/'support.json'))
            maximum_main = max(maximum_main, float(np.max(np.abs(probability-stored))))
            assert np.allclose(probability, stored, atol=1e-12, rtol=0)
            model = CatBoostClassifier(); model.load_model(str(folder/'model.cbm'))
            assert np.allclose(model.predict_proba(X[:, columns]), probability, atol=1e-12, rtol=0)
            assert np.all(np.argmax(probability[:99], axis=1) == d['y'][:99])
            current = np.argmax(probability, axis=1)
            current[a['locked']] = a['current'][a['locked']]
            current[~d['valid']] = d['regular'][~d['valid']]
            review = d['valid'] & ~a['locked'] & (probability.max(axis=1) < .8)
            local_matrix = d['extra']*review[:, None]
            for i in np.flatnonzero(review & d['available']):
                for key, value in local.view_flags(d['flags_by_row'][i], int(np.argmax(probability[i])), int(d['regular'][i])).items():
                    local_matrix[i, d['extra_names'].index(key)] = int(value)
            full = np.concatenate([attach(d['raw'], d['semantic'], probability, d['regular']), local_matrix, probability], axis=1)
            head_metadata = read(SOURCE/a['folder']/'contextual_depth2.json')
            head_columns = [d['names'].index(n) for n in head_metadata['features']]
            delta = native_scores(read(SOURCE/a['folder']/'contextual_depth2-native.json'), full[:, head_columns])
            trials = []; outcomes = {}
            for strength in (1., .75, .5, .25, 0.):
                if strength > head_metadata['strength']:
                    continue
                scores = np.maximum(probability+strength*delta, 1e-9)
                scores /= scores.sum(axis=1, keepdims=True)
                proposed = np.argmax(scores, axis=1); p = current.copy()
                for i in np.flatnonzero(review & d['available']):
                    if admissible(d['flags_by_row'][i], int(np.argmax(probability[i])), int(d['regular'][i]), int(proposed[i])):
                        p[i] = proposed[i]
                trials.append({'strength': strength, 'original_correct': int(np.sum(p[:99] == d['y'][:99]))})
                outcomes[strength] = p
            chosen = next(t['strength'] for t in trials if t['original_correct'] == 99)
            assert read(folder/'head_strength.json') == {'selected_strength': chosen, 'trials': trials}
            variants = {'main_prior': current, 'fixed_head': outcomes[head_metadata['strength']], 'protected_head': outcomes[chosen]}
            for variant, p in variants.items():
                name = 'eta'+str(exponent)+'_'+variant
                assert p.tolist() == read(folder/(variant+'-predictions.json'))
                assert np.array_equal(p[a['locked']], a['current'][a['locked']])
                assert np.array_equal(p[~d['valid']], d['regular'][~d['valid']])
                correct = int(np.sum(p[:99] == d['y'][:99]))
                count = int(sum(p[d['pos'][r['case']]] == r['reference'] for r in slots))
                retention.append({'candidate': name, 'fold': f['fold'], 'original_correct': correct,
                                  'slots_correct': count, 'eligible': correct == 99 and count == 144})
                for i in a['held']:
                    e = examples[i]
                    rows.append({**e, 'candidate': name, 'fold': f['fold'], 'prediction': int(p[i]),
                        'baseline': prior[e['case']]['prediction'], 'review': bool(review[i]),
                        'local_available': bool(review[i] and d['available'][i])})
            models += 1
        print({'fold': f['fold'], 'main_models': models}, flush=True)
    assert sorted(rows, key=lambda r: (r['candidate'], r['case'])) == sorted(read(study/'predictions.json'), key=lambda r: (r['candidate'], r['case']))
    assert sorted(retention, key=lambda r: (r['candidate'], r['fold'])) == sorted(read(study/'retention.json'), key=lambda r: (r['candidate'], r['fold']))
    results = read(study/'results.json')
    for name, result in results.items():
        rr = [r for r in rows if r['candidate'] == name]
        assert len(rr) == len({r['case'] for r in rr}) == 276
        metric = classification_metrics(rr); assert result['metrics'] == metric
        y, p = [r['reference'] for r in rr], [r['prediction'] for r in rr]
        assert abs(metric['balanced_accuracy']-balanced_accuracy_score(y, p)) < 1e-14
        assert abs(metric['accuracy']-accuracy_score(y, p)) < 1e-14
        assert abs(metric['macro_f1']-f1_score(y, p, labels=[0, 1, 2], average='macro')) < 1e-14
        assert result['all_original_cases_and_slots_retained'] == all(r['eligible'] for r in retention if r['candidate'] == name)
        assert result['coverage'] == 273
    result = {'passed': True, 'main_models_checked': models, 'main_and_head_rows': 2*models*len(examples),
        'max_native_main_error': maximum_main, 'results': results, 'new_api_or_neural_calls': 0,
        'reserved_sources_used': 0, 'selected_default_changed': False}
    save_json(out/'verification.json', result); save_json(out/'predictions.json', rows)
    save_json(out/'manifest.json', {'auditor_sha256': file_hash(__file__), 'study_manifest_sha256': file_hash(study/'manifest.json')})
    dest = out/'source_snapshot/run'/Path(__file__).name; dest.parent.mkdir(parents=True); shutil.copyfile(__file__, dest)
    (out/'run.log').write_text('All18 main classifiers and frozen heads replay from numeric JSON; weights, source folds, grades, retention and metrics match.\n')
    print({'passed': True, 'models': models, 'maximum_main_error': maximum_main}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--study', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True); a = p.parse_args()
    audit(a.study.resolve(), a.output_dir.resolve())
