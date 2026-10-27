"""Separate genuinely source-excluded calibration residuals from fitting views.

This offline development ablation never reads the new v75 pilot responses.
"""
import argparse
from pathlib import Path
import shutil

import numpy as np

from critical.core.calibration.source_excluded_calibration_v89 import BoundaryCalibration, source_excluded_views
from critical.core.calibration.rubric_score_v82 import RubricScore
from critical.core.calibration.rubric_evidence_v73 import SPECS
from critical.core.calibration.judge_semantics_v60 import SPECS as LANGUAGE
from critical.core.calibration.semantic_rubric_runtime_v70 import SemanticRubricExecutor
from critical.core.calibration.independent_expert_v87 import ExpertGate
from critical.core.decision.artifacts import digest, save_json
from run.calitree_seeded_rubric_v73 import arrays, attach
from run.calitree_warranted_rubric_v71 import TEACHERS, INNER
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, read, fingerprint
from run.calitree_cached_sol_router_v85 import cached
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS
from run.calitree_accuracy_headroom_v37 import accuracy

RUBRICS = ROOT/'logs/exps/261023-verified-semantic-hybrid-v72-r1'
EXPERT = ROOT/'logs/exps/261023-verified-independent-expert-v87-r2'
CONFIGS = [(scope, 'boundary', warranted) for scope in ('mixed', 'source_excluded') for warranted in (False, True)]
CONFIGS += [(scope, 'semantic_score', reg) for scope in ('mixed', 'source_excluded') for reg in (.01, .1, 1.)]


def candidate_name(scope, kind, setting):
    return scope+'_'+kind+'_'+str(setting)


def baseline_predictions(folder, names, raw, semantic, ps, regular, sol, valid):
    """Keep v72/v87 rule context and precedence on the unchanged teacher."""
    rubric = read(RUBRICS/folder/'rubric.json'); executor = SemanticRubricExecutor(rubric)
    gate = ExpertGate(read(EXPERT/folder/'gate.json'))
    columns = {n: i for i, n in enumerate(names)}
    views = attach(raw, semantic, ps, sol)
    actual = np.argmax(ps, axis=1)
    current = actual.copy(); locked = np.zeros(len(ps), dtype=bool)
    for i in range(len(ps)):
        if not valid[i]:
            current[i] = regular[i]
            continue
        result = executor.select({n: bool(raw[i, columns[n]]) for n in rubric['feature_names']}, int(actual[i]))
        current[i] = result['prediction']; locked[i] = result['rule_index'] is not None
        if not locked[i] and sol[i] >= 0:
            result = gate.select({n: bool(views[i, columns[n]]) for n in gate.artifact['feature_names']}, int(actual[i]), int(sol[i]))
            if result is not None:
                current[i] = result['prediction']; locked[i] = True
    return current, locked


def run(out):
    if out.exists():
        raise ValueError('Fresh experiment directory required')
    examples, names, raw, semantic = arrays(); sol, _ = cached(examples)
    y = np.asarray([e['reference'] for e in examples]); groups = np.asarray([e['source_group'] for e in examples])
    regular = np.asarray([e['regular'] for e in examples]); valid = np.asarray([e['covered'] for e in examples])
    pos = {e['case']: i for i, e in enumerate(examples)}
    originals = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    old_groups = set(groups[:99]); prior = {r['case']: r for r in read(EXPERT/'predictions.json')}
    selected = [i for i, n in enumerate(names) if n in SPECS or n in LANGUAGE]
    feature_names = [names[i] for i in selected]; descriptions = {**SPECS, **LANGUAGE}
    warrants = np.asarray([[s['rubric_'+label+'_ready'] for label in ('no', 'partial', 'yes')] for s in semantic], dtype=bool)
    protocol = {
        'version': 'source-excluded-calibration-ablation-v89', 'configs': CONFIGS,
        'motivation': 'Previous correction learners mixed genuine source-excluded residuals with always-fitted original-source views. Compare fitting scopes without changing the teacher or evidence.',
        'scope': 'Same276 reviewed development cases,84 pixel sources and five outer source folds; all outer-held siblings excluded. Fold5 supplies an all-data artifact, not evaluation.',
        'selection': 'All candidate parameters use only outer-training labels and actual original99 protection. No held label enters feature, coefficient, strength or boundary selection.',
        'fitting_scopes': {'mixed': 'Every valid outer fitting row, retaining prior explicitly supervised original-source views.', 'source_excluded': 'Only valid rows whose pixel source was actually excluded by one of the five cached inner teachers; originals remain protected constraints, not calibration fit rows.'},
        'boundary': '49 fixed biases: No=0, Partial and Yes from[-1,-.5,0,.5,1,1.5,2]. Maximize equal-source fitting accuracy, then minimize bias norm and log loss, with a hard99-original veto. Compare unrestricted versus affirmative same-requirement grading warrants.',
        'semantic_score': 'Existing v82 additive equation, up to24 named rubric/claim terms, regularization .01/.1/1. Strength chosen on fitting data after actual-original veto. No captions, NLI, raw embeddings or identifiers.',
        'priority': 'Existing v72 and v87 rules keep their original v69 teacher context and precedence. Calibration only changes the remaining teacher decisions. Missing bound evidence keeps regular fallback.',
        'pilot': 'The new24-case v75 responses are never opened or fitted. Only the pre-existing915-case cached evidence and old generic expert cache are used.',
        'limits': 'Exploratory development comparison after repeated prior research, not untouched validation. Class biases are calibration controls, not factual confidence or standalone semantic rubrics.',
        'new_api_calls': 0, 'reserved_sources_used': 0, 'serving_changed': False,
    }
    out.mkdir(parents=True); save_json(out/'protocol.json', protocol)
    (out/'run.log').write_text('Separate calibration fitting-view scopes; source-held experiment started.\n')
    (out/'llm-histories.log').write_text('Zero API calls, uploads, new teacher fits or new v75 pilot response reads.\n')
    files = [Path(__file__), ROOT/'critical/core/calibration/source_excluded_calibration_v89.py', ROOT/'critical/core/calibration/rubric_score_v82.py']
    hashes = {str(p): fingerprint(p) for p in files}; source_hashes = {}
    for p in files:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    records, retention = [], []
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        folder = 'fold'+str(f['fold']); train = [pos[c] for c in f['train_cases']]; held = [pos[c] for c in f['held_cases']]
        teacher = TEACHERS/folder; saved = read(teacher/'predictions.json'); ps = np.asarray(saved['support'])
        inner_views = []
        for inner in range(5):
            path = INNER/folder/('inner'+str(inner)); membership = read(path/'membership.json')
            assert read(path/'teacher.json')['contract']['rows'] == membership['train']
            inner_views.append((membership, read(path/'predictions.json')['support']))
            for file in ('membership.json', 'predictions.json', 'teacher.json'):
                source_hashes[str(path/file)] = fingerprint(path/file)
        mixed_ps, excluded = source_excluded_views(ps, train, held, groups, inner_views)
        assert set(np.where(excluded)[0]) == {i for i in train if groups[i] not in old_groups}
        current, locked = baseline_predictions(folder, names, raw, semantic, ps, regular, sol, valid)
        assert np.all(current[:99] == y[:99])
        assert all(current[i] == prior[examples[i]['case']]['prediction'] for i in held)
        full = attach(raw, semantic, ps, regular)[:, selected]
        training = attach(raw, semantic, mixed_ps, regular)[:, selected]
        membership = {'train_cases': f['train_cases'], 'held_cases': f['held_cases'],
                      'genuinely_source_excluded_cases': [examples[i]['case'] for i in np.where(excluded)[0]],
                      'original_source_views': [examples[i]['case'] for i in train if not excluded[i]],
                      'inner_memberships': [m for m, _ in inner_views]}
        save_json(out/folder/'memberships.json', membership)
        all_predictions = {}
        for scope, kind, setting in CONFIGS:
            name = candidate_name(scope, kind, setting)
            fit = [i for i in train if valid[i] and (scope == 'mixed' or excluded[i])]
            if kind == 'boundary':
                model = BoundaryCalibration().fit(mixed_ps[fit], y[fit], groups[fit], protected_support=ps[:99], protected_y=y[:99],
                        warrants=warrants[fit] if setting else None, protected_warrants=warrants[:99] if setting else None)
                predicted = model.predict(ps, warrants=warrants if setting else None)
                artifact = model.artifact(); artifact['requires_grading_warrant'] = setting
            else:
                model = RubricScore(feature_names, regularization=setting).fit(training[fit], y[fit], support=mixed_ps[fit], groups=groups[fit],
                        protected_X=full[:99], protected_y=y[:99], protected_support=ps[:99])
                predicted = np.argmax(model.predict_proba(full, support=ps), axis=1)
                artifact = model.artifact(descriptions)
            proposed = predicted.copy(); predicted[locked] = current[locked]; predicted[~valid] = regular[~valid]
            assert np.all(predicted[:99] == y[:99])
            slots = int(sum(predicted[pos[r['case']]] == r['reference'] for r in originals)); assert slots == 144
            artifact.update({'teacher_ref': digest(read(teacher/'teacher.json')['contract']), 'scope': scope,
                             'fit_cases': [examples[i]['case'] for i in fit], 'fit_sources': sorted(set(groups[fit])),
                             'prior_rules_keep_context': True})
            save_json(out/folder/(name+'.json'), artifact)
            retention.append({'candidate': name, 'fold': f['fold'], 'original_correct': 99, 'slots_correct': slots,
                              'fit_rows': len(fit), 'fit_sources': len(set(groups[fit])),
                              'calibration_original_rows': sum(i < 99 for i in fit)})
            all_predictions[name] = predicted.tolist()
            for i in held:
                records.append({**examples[i], 'candidate': name, 'fold': f['fold'], 'prediction': int(predicted[i]),
                                'baseline': int(current[i]), 'teacher': int(np.argmax(ps[i])),
                                'uncorrected_proposal': int(proposed[i]), 'prior_rule_priority': bool(locked[i])})
        save_json(out/folder/'all_predictions.json', all_predictions)
        for path in (teacher/'predictions.json', teacher/'teacher.json', RUBRICS/folder/'rubric.json', EXPERT/folder/'gate.json'):
            source_hashes[str(path)] = fingerprint(path)
        save_json(out/'predictions.json', records); save_json(out/'retention.json', retention)
        print({'fold': f['fold'], 'held': len(held), 'true_oof_rows': int(excluded.sum()), 'mixed_rows': len(train)}, flush=True)
    results = {}
    for config in CONFIGS:
        name = candidate_name(*config); rows = [r for r in records if r['candidate'] == name]
        results[name] = {'accuracy': accuracy(rows, 'prediction'), 'baseline': accuracy(rows, 'baseline'),
                         'gains': sum(r['prediction'] == r['reference'] != r['baseline'] for r in rows),
                         'losses': sum(r['baseline'] == r['reference'] != r['prediction'] for r in rows),
                         'changes': sum(r['prediction'] != r['baseline'] for r in rows),
                         'upstream_evidence_coverage': sum(r['covered'] for r in rows),
                         'all_original_fits_retained': True, 'target_exceeded': accuracy(rows, 'prediction')['correct'] >= 235}
    assert all(r['baseline']['correct'] == 225 and r['upstream_evidence_coverage'] == 273 for r in results.values())
    assert all(fingerprint(p) == sha for p, sha in hashes.items())
    save_json(out/'results.json', results)
    save_json(out/'manifest.json', {'code_sha256': hashes, 'source_hashes': source_hashes, 'targets_ref': digest(y.tolist()),
                                 'matrix_ref': digest(raw.tolist()), 'protocol_ref': digest(protocol)})
    (out/'run.log').write_text('Completed ten calibration controls across both fitting scopes; all99 originals/144 slots and273/276 coverage retained. No serving change. See results.json.\n')
    print(results, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    run(p.parse_args().output_dir.resolve())
