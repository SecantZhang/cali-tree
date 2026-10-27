"""Test an explicit weighted rubric on the completed local task/preservation view.

The score is a statistical human-grade correction, not a factual certificate.
Only the frozen review region executes it; original-case vetoes apply to that
actual flow rather than irrelevant hypothetical corrections outside the region.
"""
import argparse
from pathlib import Path
import shutil

import numpy as np

from critical.core.calibration.rubric_score_v82 import RubricScore
from critical.core.calibration import local_warranted_rubric_v97 as local
from critical.core.calibration.source_excluded_calibration_v89 import source_excluded_views
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_seeded_rubric_v73 import arrays, attach
from run.calitree_source_excluded_calibration_v89 import baseline_predictions
from run.calitree_warranted_rubric_v71 import TEACHERS, INNER
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, FROZEN, read
from run.calitree_cached_sol_router_v85 import cached
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS
from run.calitree_accuracy_headroom_v37 import accuracy
from run.verify_calitree_local_review_cache_v98 import validate_response

CONFIGS = [(family, reg) for family in ('local', 'contextual') for reg in (.01, .1, 1.)]
SUPPORT_DESCRIPTIONS = {'teacher_support_'+label: 'The existing teacher assigns this model support to '+label+'; it is not calibrated correctness.' for label in ('no', 'partial', 'yes')}


def admissible(flags, teacher, regular, proposed):
    if flags['local_'+local.LABELS[proposed]+'_ready']:
        return True
    views = local.view_flags(flags, teacher, regular)
    reason = (flags['local_any_uncertainty'] or flags['local_claim_conflict'] or flags['local_progress_witness'] or
              (views['local_view_teacher_unwarranted'] and views['local_view_regular_warranted']))
    return proposed == regular and regular != teacher and reason


def run(cache, cache_audit, out, *, method='additive'):
    if method not in ('additive', 'tree_residual'):
        raise ValueError('Unknown semantic score method')
    if out.exists():
        raise ValueError('Fresh score-study output required')
    audit = read(cache_audit/'verification.json'); audit_manifest = read(cache_audit/'manifest.json')
    assert audit['passed'] and audit['complete'] and not audit['snapshot_only']
    assert audit_manifest['cache_manifest_sha256'] == file_hash(cache/'manifest.json')
    for file, sha in audit_manifest['source_hashes'].items():
        assert file_hash(file) == sha
    examples, old_names, raw, semantic = arrays(); y = np.asarray([e['reference'] for e in examples])
    groups = np.asarray([e['source_group'] for e in examples]); regular = np.asarray([e['regular'] for e in examples]); valid = np.asarray([e['covered'] for e in examples]); sol, _ = cached(examples)
    pos = {e['case']: i for i, e in enumerate(examples)}; profile = read(cache/'identity.json'); jobs = read(cache/'jobs.json')
    extra_names = list(local.SPECS); names = old_names+extra_names+(list(SUPPORT_DESCRIPTIONS) if method == 'tree_residual' else [])
    descriptions = {**local.DESCRIPTIONS, **SUPPORT_DESCRIPTIONS}
    configs = CONFIGS if method == 'additive' else [(family, depth) for family in ('local', 'contextual') for depth in (2, 3)]
    extra = np.zeros((len(examples), len(extra_names))); available = np.zeros(len(examples), dtype=bool); values_by_row = {}
    for job in jobs:
        response = read(cache/'responses'/(job['case']+'.json'))
        if validate_response(job, response, profile):
            i = pos[job['case']]; flags = local.project(job['program'], job['image_pair_ref'], job['identity_ref'], job['prompt_ref'], response['record'])
            extra[i] = [int(flags[n]) for n in extra_names]; available[i] = True; values_by_row[i] = flags
    memberships = read(cache/'memberships.json')
    protocol = {'version': 'local-weighted-semantic-rubric-v102' if method == 'additive' else 'local-semantic-residual-v103', 'configs': configs, 'method': method,
                'equation': 'Existing v82 explicit teacher-logit offset with at most24 normalized terms.' if method == 'additive' else '128 depth2/3 semantic trees fit onehot(human grade)-teacher support. Normalize the nonnegative sum of teacher support and strength*residual. Source-weighted fitting; strength0/.25/.5/.75/1 vetoed by actual original decisions.',
                'flow': 'Execute only in the same .8 review region after v72/v87 priority, and only with a valid bound local observation. All other/failed cases keep the existing decision.',
                'fitting': 'Each fold genuine source-excluded review rows with available local facts. No other-fold union membership as a feature, no held-source sibling fitting.',
                'protection': 'Strength is vetoed using every actual original input where the score head can execute. Remaining originals are structurally unchanged. All99/144 are checked after real flow assembly.',
                'families': {'local': 'New local task/preservation concepts and existing named judge-view cues only.', 'contextual': 'Also existing named meaning/task/intent/requirement/rationale fields. No vision vectors, source IDs or object-name features.'},
                'arms': 'Score-only weighted rubric versus an additional affirmative-grade/independent-judge admissibility guard. Both are measured; neither is silently substituted.',
                'limits': 'A statistical rubric for human-grade prediction, not proof of physical failure or calibrated correctness. Same reviewed276-case development denominator.',
                'new_api_calls': 0, 'new_observer_calls': 0, 'reserved_sources_used': 0, 'serving_changed': False}
    out.mkdir(parents=True); save_json(out/'protocol.json', protocol)
    (out/'run.log').write_text('Completed local cache and strict audit accepted; weighted rubric comparison started.\n'); (out/'llm-histories.log').write_text('Zero API/local-observer/encoder calls. Cached semantic claims and supports only.\n')
    files = [Path(__file__), ROOT/'critical/core/calibration/rubric_score_v82.py', ROOT/'critical/core/calibration/local_warranted_rubric_v97.py']
    if method == 'tree_residual':
        files.append(ROOT/'critical/core/calibration/semantic_residual_v103.py')
    for file in files:
        dest = out/'source_snapshot'/file.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(file, dest)
    records = []; retention = []; slots = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        folder = 'fold'+str(f['fold']); train = [pos[c] for c in f['train_cases']]; held = [pos[c] for c in f['held_cases']]
        ps = np.asarray(read(TEACHERS/folder/'predictions.json')['support']); current, locked = baseline_predictions(folder, old_names, raw, semantic, ps, regular, sol, valid)
        actual = valid & ~locked & (ps.max(axis=1) < .8)
        inner = [(read(INNER/folder/('inner'+str(k))/'membership.json'), read(INNER/folder/('inner'+str(k))/'predictions.json')['support']) for k in range(5)]
        oof, genuine = source_excluded_views(ps, train, held, groups, inner); fitting = valid & genuine & (oof.max(axis=1) < .8)
        expected = next(m for m in memberships if m['fold'] == f['fold'])
        assert expected['actual_review_cases'] == [examples[i]['case'] for i in np.flatnonzero(actual)]
        assert expected['fit_review_cases'] == [examples[i]['case'] for i in np.flatnonzero(fitting)]
        full_parts = []; teacher = np.argmax(ps, axis=1); oof_teacher = np.argmax(oof, axis=1)
        for probabilities, mask, context in ((ps, actual, teacher), (oof, fitting, oof_teacher)):
            local_matrix = extra*mask[:, None]
            for i in np.flatnonzero(mask & available):
                for key, value in local.view_flags(values_by_row[i], int(context[i]), int(regular[i])).items():
                    local_matrix[i, extra_names.index(key)] = int(value)
            blocks = [attach(raw, semantic, probabilities, regular), local_matrix]
            if method == 'tree_residual':
                blocks.append(probabilities)
            full_parts.append(np.concatenate(blocks, axis=1))
        full, T = full_parts; fit = np.flatnonzero(fitting & available).tolist(); protected = [i for i in range(99) if actual[i] and available[i]]
        for family, reg in configs:
            columns = [i for i, n in enumerate(names) if n in local.SPECS or n in SUPPORT_DESCRIPTIONS or n.startswith('view_') or
                       (family == 'contextual' and n.startswith(('meaning_', 'task_', 'intent_', 'requires_', 'rationale_', 'rubric_')))]
            feature_names = [names[i] for i in columns]
            if method == 'additive':
                model = RubricScore(feature_names, regularization=reg)
            else:
                from critical.core.calibration.semantic_residual_v103 import SemanticResidual
                model = SemanticResidual(feature_names, depth=reg)
            model.fit(T[fit][:, columns], y[fit], support=oof[fit], groups=groups[fit],
                    protected_X=full[protected][:, columns], protected_y=y[protected], protected_support=ps[protected])
            proposed = np.argmax(model.predict_proba(full[:, columns], support=ps), axis=1)
            base_name = family+('_reg' if method == 'additive' else '_depth')+str(reg); artifact = model.artifact(descriptions)
            artifact.update(teacher_ref=digest(read(TEACHERS/folder/'teacher.json')['contract']), observer_identity_ref=digest(profile),
                            fit_cases=[examples[i]['case'] for i in fit], protected_review_cases=[examples[i]['case'] for i in protected])
            save_json(out/folder/(base_name+'.json'), artifact)
            if method == 'tree_residual':
                model.model.save_model(str(out/folder/(base_name+'.cbm')))
                model.model.save_model(str(out/folder/(base_name+'-native.json')), format='json')
            for guarded in (False, True):
                candidate = base_name+('_guarded' if guarded else '_score')
                p = current.copy()
                for i in np.flatnonzero(actual & available):
                    if not guarded or admissible(values_by_row[i], int(teacher[i]), int(regular[i]), int(proposed[i])):
                        p[i] = proposed[i]
                assert np.all(p[:99] == y[:99]) and np.array_equal(p[~(actual & available)], current[~(actual & available)])
                correct_slots = int(sum(p[pos[r['case']]] == r['reference'] for r in slots)); assert correct_slots == 144
                retention.append({'candidate': candidate, 'fold': f['fold'], 'original_correct': 99, 'slots_correct': 144, 'strength': model.strength,
                                  'terms': len(model.columns) if method == 'additive' else None, 'protected_review_originals': len(protected),
                                  'input_features': len(feature_names), 'method': method})
                save_json(out/folder/(candidate+'-predictions.json'), p.tolist())
                for i in held:
                    records.append({**examples[i], 'candidate': candidate, 'fold': f['fold'], 'prediction': int(p[i]), 'baseline': int(current[i]),
                                    'review': bool(actual[i]), 'local_available': bool(actual[i] and available[i])})
        save_json(out/'predictions.json', records); save_json(out/'retention.json', retention)
        print({'fold': f['fold'], 'fit_rows': len(fit), 'protected_original_review': len(protected)}, flush=True)
    results = {}
    for r in records:
        results.setdefault(r['candidate'], None)
    for candidate in results:
        rows = [r for r in records if r['candidate'] == candidate]
        results[candidate] = {'accuracy': accuracy(rows, 'prediction'), 'baseline': accuracy(rows, 'baseline'),
            'gains': sum(r['prediction'] == r['reference'] != r['baseline'] for r in rows), 'losses': sum(r['baseline'] == r['reference'] != r['prediction'] for r in rows),
            'coverage': sum(r['covered'] for r in rows), 'original_cases_retained': 99, 'original_slots_retained': 144,
            'target_exceeded': accuracy(rows, 'prediction')['correct'] >= 235}
    assert all(v['baseline']['correct'] == 225 and v['coverage'] == 273 for v in results.values())
    save_json(out/'results.json', results); save_json(out/'manifest.json', {'code_sha256': {str(p): file_hash(p) for p in files},
        'cache_audit_manifest_sha256': file_hash(cache_audit/'manifest.json'), 'targets_ref': digest(y.tolist()), 'protocol_ref': digest(protocol)})
    (out/'run.log').write_text('Completed weighted local-rubric score/guard comparison. All original cases/slots and outside-region decisions retained; no serving change.\n')
    print(results, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--cache', type=Path, required=True); p.add_argument('--cache-audit', type=Path, required=True); p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--method', choices=('additive', 'tree_residual'), default='additive')
    a = p.parse_args(); run(a.cache.resolve(), a.cache_audit.resolve(), a.output_dir.resolve(), method=a.method)
