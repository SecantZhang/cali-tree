"""Compare source-balanced and original-anchored semantic score corrections."""
import argparse
from pathlib import Path
import shutil

import numpy as np

from critical.core.calibration.semantic_residual_v103 import SemanticResidual
from critical.core.calibration.semantic_residual_runtime_v104 import SUPPORT, admissible
from critical.core.calibration.local_warranted_rubric_v97 import DESCRIPTIONS
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.verify_calitree_semantic_residual_v105 import load, fold_arrays
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, read
from run.calitree_accuracy_headroom_v37 import accuracy
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS
from run.calitree_warranted_rubric_v71 import TEACHERS


CONFIGS = [(pool, anchors, depth) for pool in ('all', 'primary') for anchors in (False, True) for depth in (2, 3)]


def run(cache, cache_audit, out):
    if out.exists():
        raise ValueError('Fresh anchored-study directory required')
    d = load(cache, cache_audit); examples, names, y = d['examples'], d['names'], d['y']
    protocol = {'version': 'anchored-semantic-residual-v106', 'configs': CONFIGS, 'iterations': 128,
        'pool': 'All genuinely source-excluded review fitting cases, versus primary training cases only (99:375). No held-source siblings in either pool.',
        'anchors': 'Optionally include the actual review originals with valid observations as supervised fitting anchors, using their actual teacher supports. They were already fitting sources; no held cases enter. All actual originals still veto strength and all99/144 are checked.',
        'features': 'Same contextual named concepts plus three teacher supports as v103, no raw visual vectors or source/editor/case IDs.',
        'score': 'Same depth2/3 residual and fit-only strength selection as v103. All primary development cases remain in the denominator.',
        'flow': 'Same fixed source folds, .8 review region, v72/v87 priority and valid local-record requirement. Measure both score-only and the unchanged affirmative-warrant/independent-review guard.',
        'new_api_calls': 0, 'new_observer_calls': 0, 'reserved_sources_used': 0, 'serving_changed': False}
    out.mkdir(parents=True); save_json(out/'protocol.json', protocol)
    (out/'run.log').write_text('Strict cache accepted; original-anchor and fitting-pool comparisons started.\n'); (out/'llm-histories.log').write_text('Offline cached evidence only; no new calls or extraction.\n')
    files = [Path(__file__), ROOT/'run/verify_calitree_semantic_residual_v105.py', ROOT/'critical/core/calibration/semantic_residual_v103.py', ROOT/'critical/core/calibration/semantic_residual_runtime_v104.py']
    for p in files:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    columns = [i for i, n in enumerate(names) if n in SUPPORT or n.startswith(('local_', 'view_', 'meaning_', 'task_', 'intent_', 'requires_', 'rationale_', 'rubric_'))]
    feature_names = [names[i] for i in columns]; descriptions = {**DESCRIPTIONS, **SUPPORT}
    slots = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]; records = []; retention = []
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        a = fold_arrays(d, f); folder = a['folder']; protected = a['protected']
        for pool, anchors, depth in CONFIGS:
            fit = [i for i in a['fit'] if pool == 'all' or 99 <= i < 375]
            chosen = fit+(protected if anchors else []); matrix = np.concatenate([a['T'][fit][:, columns], a['full'][protected][:, columns]], axis=0) if anchors else a['T'][fit][:, columns]
            supports = np.concatenate([a['oof'][fit], a['ps'][protected]], axis=0) if anchors else a['oof'][fit]
            assert len(set(chosen)) == len(chosen) and set(chosen) <= set(a['train']) and not set(d['groups'][chosen]) & set(d['groups'][a['held']])
            model = SemanticResidual(feature_names, depth=depth).fit(matrix, y[chosen], support=supports, groups=d['groups'][chosen],
                protected_X=a['full'][protected][:, columns], protected_y=y[protected], protected_support=a['ps'][protected])
            base_name = pool+('_anchors' if anchors else '_noanchors')+'_depth'+str(depth)
            metadata = model.artifact(descriptions); metadata.update(teacher_ref=digest(read(TEACHERS/folder/'teacher.json')['contract']), observer_identity_ref=digest(d['profile']),
                fit_cases=[examples[i]['case'] for i in fit], anchor_cases=[examples[i]['case'] for i in protected] if anchors else [],
                protected_review_cases=[examples[i]['case'] for i in protected], pool=pool)
            save_json(out/folder/(base_name+'.json'), metadata); model.model.save_model(str(out/folder/(base_name+'.cbm'))); model.model.save_model(str(out/folder/(base_name+'-native.json')), format='json')
            proposed = np.argmax(model.predict_proba(a['full'][:, columns], support=a['ps']), axis=1)
            for guarded in (False, True):
                candidate = base_name+('_guarded' if guarded else '_score'); p = a['current'].copy()
                for i in np.flatnonzero(a['actual'] & d['available']):
                    if not guarded or admissible(d['flags_by_row'][i], int(np.argmax(a['ps'][i])), int(d['regular'][i]), int(proposed[i])):
                        p[i] = proposed[i]
                assert np.all(p[:99] == y[:99]) and np.array_equal(p[~(a['actual'] & d['available'])], a['current'][~(a['actual'] & d['available'])])
                count = int(sum(p[d['pos'][r['case']]] == r['reference'] for r in slots)); assert count == 144
                save_json(out/folder/(candidate+'-predictions.json'), p.tolist())
                retention.append({'candidate': candidate, 'fold': f['fold'], 'original_correct': 99, 'slots_correct': count, 'fit_rows': len(fit), 'anchors': len(chosen)-len(fit), 'strength': model.strength})
                for i in a['held']:
                    records.append({**examples[i], 'fold': f['fold'], 'candidate': candidate, 'prediction': int(p[i]), 'baseline': int(a['current'][i]), 'review': bool(a['actual'][i]), 'local_available': bool(a['actual'][i] and d['available'][i])})
        save_json(out/'predictions.json', records); save_json(out/'retention.json', retention); print({'fold': f['fold'], 'configs': len(CONFIGS)}, flush=True)
    results = {}
    for candidate in sorted({r['candidate'] for r in records}):
        rows = [r for r in records if r['candidate'] == candidate]
        results[candidate] = {'accuracy': accuracy(rows, 'prediction'), 'baseline': accuracy(rows, 'baseline'),
            'gains': sum(r['prediction'] == r['reference'] != r['baseline'] for r in rows), 'losses': sum(r['baseline'] == r['reference'] != r['prediction'] for r in rows),
            'coverage': sum(r['covered'] for r in rows), 'original_cases_retained': 99, 'original_slots_retained': 144, 'target_exceeded': accuracy(rows, 'prediction')['correct'] >= 235}
    save_json(out/'results.json', results); save_json(out/'manifest.json', {'code_sha256': {str(p): file_hash(p) for p in files}, 'cache_audit_manifest_sha256': file_hash(cache_audit/'manifest.json'),
        'targets_ref': digest(y.tolist()), 'protocol_ref': digest(protocol)})
    (out/'run.log').write_text('Completed8 source-held fitting configurations with score/guarded arms. No serving change.\n'); print(results, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--cache', type=Path, required=True); p.add_argument('--cache-audit', type=Path, required=True); p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args(); run(a.cache.resolve(), a.cache_audit.resolve(), a.output_dir.resolve())
