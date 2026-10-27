"""Re-induce and independently execute all compact balanced-policy studies."""
import argparse
import math
from pathlib import Path
import shutil

import numpy as np
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score

from critical.core.calibration.compact_balance_v143 import CompactBalance
from critical.core.calibration.balanced_semantic_patches_v144 import BalancedSemanticPatches
from critical.core.calibration.balanced_semantic_experts_v146 import BalancedSemanticExperts, EXPERT_SPECS, REVIEW_REASONS
from critical.core.calibration.class_balance_v141 import classification_metrics
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_compact_balance_v143 import contexts, CACHE, CACHE_AUDIT
from run.verify_calitree_semantic_residual_v105 import load
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, read
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS

STUDIES = [(ROOT/'logs/exps/261025-compact-balanced-v143-r1', 'calibration'),
           (ROOT/'logs/exps/261025-balanced-patches-v144-r1', 'patches'),
           (ROOT/'logs/exps/261025-balanced-experts-v146-r1', 'experts')]


def scalar_calibration(artifact, support, grade, locked, warrants):
    selected = artifact['selected']; family = selected['family']
    if locked or family == 'identity':
        return grade
    first, second = selected['parameters']
    if family == 'bias':
        score = [math.log(max(float(v), 1e-9))+b for v, b in zip(support, (0., first, second))]
        proposed = max(range(3), key=lambda i: (score[i], -i))
    else:
        z = float(support[1])+2*float(support[2])
        proposed = 0 if z < first else (1 if z < second else 2)
    return proposed if not artifact['warranted'] or proposed == grade or warrants[proposed] else grade


def scalar_rules(artifact, values, grade, locked, regular):
    if locked:
        return grade
    for rule in artifact['rules']:
        if grade != rule['from_grade']:
            continue
        if all(values[t['feature']] == t['value'] for t in rule['conditions']):
            label = ('no', 'partial', 'yes')[rule['grade']]
            positive = {t['feature'] for t in rule['conditions'] if t['value']}
            if rule.get('role') == 'regular':
                assert 'expert_'+label+'_review_ready' in positive and regular == rule['grade']
            else:
                assert {'rubric_'+label+'_ready', 'local_'+label+'_ready'} & positive
            return rule['grade']
    return grade


def audit(out):
    if out.exists():
        raise ValueError('Fresh balanced-search audit required')
    studies = []
    for path, kind in STUDIES:
        manifest = read(path/'manifest.json'); protocol = read(path/'protocol.json')
        assert manifest['protocol_ref'] == digest(protocol)
        assert manifest['cache_audit_manifest_sha256'] == file_hash(CACHE_AUDIT/'manifest.json')
        for source, sha in manifest['code_sha256'].items():
            assert file_hash(source) == file_hash(path/'source_snapshot'/Path(source).relative_to(ROOT)) == sha
        studies.append((path, kind, protocol))
    d = load(CACHE, CACHE_AUDIT)
    warrants = np.asarray([[s['rubric_'+label+'_ready'] for label in ('no', 'partial', 'yes')] for s in d['semantic']], dtype=bool)
    slots = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    out.mkdir(parents=True); (out/'run.log').write_text('Re-induce all frozen balanced-search arms and replay scalar execution.\n')
    (out/'llm-histories.log').write_text('Zero API/encoder/observer calls or reserved inputs.\n')
    rows_by_study = {str(p): [] for p, _, _ in studies}; checks = []; oracle = []
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        a, c, fit = contexts(d, f); full, fitting = c['actual'], c['fitting']; folder = a['folder']
        assert set(fit) <= set(a['train'])
        assert not set(d['groups'][fit]) & set(d['groups'][a['held']])
        for path, kind, protocol in studies:
            candidates = sorted(read(path/'results.json'))
            if kind != 'calibration':
                membership = read(path/folder/'memberships.json'); names = membership['features']
                assert membership['fit_cases'] == [d['examples'][i]['case'] for i in fit]
                assert membership['held_cases'] == f['held_cases']
                X = {}
                if kind == 'patches':
                    columns = [d['names'].index(n) for n in names]
                    X = {'actual': a['full'][:, columns].astype(bool), 'fitting': a['T'][:, columns].astype(bool)}
                else:
                    old_names = names[:-len(EXPERT_SPECS)]
                    assert names[-len(EXPERT_SPECS):] == list(EXPERT_SPECS)
                    columns = [d['names'].index(n) for n in old_names]
                    for key, source in (('actual', a['full']), ('fitting', a['T'])):
                        base_values = source[:, columns].astype(bool); extra = []
                        for i in range(len(source)):
                            v = dict(zip(old_names, map(bool, base_values[i])))
                            review = any(v.get(n, False) for n in REVIEW_REASONS)
                            regular, current = int(d['regular'][i]), int(c[key]['base'][i])
                            extra.append([bool(review and current != regular and regular == k) for k in range(3)])
                        X[key] = np.concatenate([base_values, np.asarray(extra, dtype=bool)], axis=1)
            for candidate in candidates:
                artifact = read(path/folder/(candidate+'.json'))
                if kind == 'calibration':
                    model = CompactBalance(family=artifact['family'], warranted=artifact['warranted'], pareto=artifact['pareto_fitting_recalls']).fit(
                        fitting['support'][fit], d['y'][fit], fitting['base'][fit], fitting['locked'][fit], warrants[fit],
                        protected_support=full['support'][:99], protected_y=d['y'][:99],
                        protected_base=full['base'][:99], protected_locked=full['locked'][:99], protected_warrants=warrants[:99])
                    clean = {k: v for k, v in artifact.items() if k not in ('fit_cases', 'fit_support_ref', 'fit_base_ref', 'fit_locks_ref')}
                    assert model.artifact() == clean
                    assert artifact['fit_cases'] == [d['examples'][i]['case'] for i in fit]
                    p = model.predict(full['support'], full['base'], full['locked'], warrants)
                    scalar = [scalar_calibration(artifact, full['support'][i], int(full['base'][i]), bool(full['locked'][i]), warrants[i]) for i in range(len(p))]
                else:
                    cls = BalancedSemanticPatches if kind == 'patches' else BalancedSemanticExperts
                    kwargs = {'partial_only': artifact['partial_only']} if kind == 'patches' else {'style': artifact['style']}
                    model = cls(names, **kwargs, loss_cost=artifact['loss_cost'], guards=artifact['max_guards']).fit(
                        X['fitting'][fit], d['y'][fit], fitting['base'][fit], ~fitting['locked'][fit], d['groups'][fit],
                        protected_X=X['actual'][:99], protected_y=d['y'][:99],
                        protected_base=full['base'][:99], protected_eligible=~full['locked'][:99])
                    assert model.artifact() == artifact
                    p = model.predict(X['actual'], full['base'], ~full['locked'])
                    scalar = [scalar_rules(artifact, dict(zip(names, map(bool, X['actual'][i]))),
                        int(full['base'][i]), bool(full['locked'][i]), int(d['regular'][i])) for i in range(len(p))]
                    assert len(artifact['rules']) <= 4
                    assert all(r['support']['gain_sources'] >= 2 for r in artifact['rules'])
                assert p.tolist() == scalar == read(path/folder/(candidate+'-predictions.json'))
                assert np.all(p[:99] == d['y'][:99])
                assert np.array_equal(p[full['locked']], full['base'][full['locked']])
                assert sum(p[d['pos'][r['case']]] == r['reference'] for r in slots) == 144
                for i in a['held']:
                    rows_by_study[str(path)].append({**d['examples'][i], 'candidate': candidate, 'fold': f['fold'],
                        'prediction': int(p[i]), 'baseline': int(full['base'][i]), 'changed': bool(p[i] != full['base'][i])})
                checks.append({'study': path.name, 'candidate': candidate, 'fold': f['fold'], 'portable_rows': len(p),
                               'original_correct': 99, 'slots_correct': 144})
        for i in a['held']:
            grade = int(d['y'][i]); current = int(full['base'][i]); target = ('no', 'partial', 'yes')[grade]
            allowed = not full['locked'][i]
            warrant = bool(d['semantic'][i]['rubric_'+target+'_ready'] or a['full'][i, d['names'].index('local_'+target+'_ready')])
            regular = int(d['regular'][i]) == grade
            oracle.append({**d['examples'][i], 'prediction': current,
                'warrant_oracle': grade if allowed and warrant else current,
                'regular_oracle': grade if allowed and regular else current,
                'union_oracle': grade if allowed and (regular or warrant) else current})
        print({'fold': f['fold'], 'calibrations_or_rules_reinduced': len(checks)}, flush=True)
    results = {}
    for path, kind, protocol in studies:
        rr = rows_by_study[str(path)]
        assert sorted(rr, key=lambda r: (r['candidate'], r['case'])) == sorted(read(path/'predictions.json'), key=lambda r: (r['candidate'], r['case']))
        results[path.name] = read(path/'results.json')
        for candidate, measured in results[path.name].items():
            selected = [r for r in rr if r['candidate'] == candidate]
            assert len(selected) == 276 and len({r['case'] for r in selected}) == 276
            score = classification_metrics(selected)
            assert measured['metrics'] == score and measured['baseline'] == classification_metrics(selected, 'baseline')
            y, p = [r['reference'] for r in selected], [r['prediction'] for r in selected]
            assert abs(score['accuracy']-accuracy_score(y, p)) < 1e-14
            assert abs(score['balanced_accuracy']-balanced_accuracy_score(y, p)) < 1e-14
            assert abs(score['macro_f1']-f1_score(y, p, labels=[0, 1, 2], average='macro')) < 1e-14
            assert measured['coverage'] == 273
            assert measured['gains'] == sum(r['prediction'] == r['reference'] != r['baseline'] for r in selected)
            assert measured['losses'] == sum(r['baseline'] == r['reference'] != r['prediction'] for r in selected)
    diagnostic = {'uses_reference_labels': True, 'deployable_policy': False,
        'scope': 'Perfect label-informed correction availability under existing priority/gating; only diagnoses headroom, never reported as learned accuracy.',
        'metrics': {field: classification_metrics(oracle, field) for field in ('prediction', 'warrant_oracle', 'regular_oracle', 'union_oracle')}}
    save_json(out/'oracle_diagnostics.json', diagnostic)
    save_json(out/'oracle_cases.json', oracle); save_json(out/'checks.json', checks)
    result = {'passed': True, 'studies': results, 'reinduced_calibrations_or_rule_models': len(checks),
        'portable_rows': sum(r['portable_rows'] for r in checks), 'original_cases_per_fit': 99,
        'original_slots_per_fit': 144, 'coverage': 273, 'new_api_or_neural_calls': 0,
        'reserved_sources_used': 0, 'selected_default_changed': False}
    save_json(out/'verification.json', result)
    save_json(out/'manifest.json', {'auditor_sha256': file_hash(__file__),
        'studies': {str(p): file_hash(p/'manifest.json') for p, _, _ in studies},
        'selected_pipeline_sha256': file_hash(ROOT/'critical/core/calibration/artifacts/calitree_current.json')})
    dest = out/'source_snapshot/run'/Path(__file__).name; dest.parent.mkdir(parents=True); shutil.copyfile(__file__, dest)
    (out/'run.log').write_text('All168 compact calibrations/semantic models re-induced;153,720 scalar/native rows match. Original99/144 and273 coverage retained.\n')
    print({'passed': True, 'models': len(checks), 'portable_rows': result['portable_rows']}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    audit(p.parse_args().output_dir.resolve())
