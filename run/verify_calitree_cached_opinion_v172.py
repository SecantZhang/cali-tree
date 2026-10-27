"""Re-induce the cached-expert study and independently verify its negative result."""
import argparse
from pathlib import Path
import shutil

import numpy as np

from critical.core.calibration.cached_opinion_selector_v170 import CachedOpinionSelector, SPECS, SEEDS, allowed, project
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_compact_balance_v143 import contexts, CACHE, CACHE_AUDIT, VERIFIED
from run.verify_calitree_semantic_residual_v105 import load
from run.calitree_cached_opinion_selector_v170 import CONFIGS, name_of
from run.calitree_semantic_context_projection_v171 import project_context
from run.verify_calitree_facet_selector_v164 import scalar, check_boolean_union
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, FROZEN, read
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS
from run.verify_calitree_facet_probe_v151 import classification_metrics


def audit(study, out):
    if out.exists():
        raise ValueError('Fresh cached-opinion verification required')
    manifest, protocol = read(study/'manifest.json'), read(study/'protocol.json')
    assert digest(protocol) == manifest['protocol_ref']
    for path, sha in manifest['code_sha256'].items():
        assert file_hash(path) == file_hash(study/'source_snapshot'/Path(path).relative_to(ROOT)) == sha
    assert manifest['cache_audit_manifest_sha256'] == file_hash(CACHE_AUDIT/'manifest.json')
    d = load(CACHE, CACHE_AUDIT); raw = {r['case']: r for r in read(FROZEN/'replay_inputs_without_references.json')}
    legacy = [n for n in d['names'] if allowed(n)]; extra_names = list(SPECS); names = legacy+extra_names
    extra = []
    for e in d['examples']:
        r = raw[e['case']]; pair = r['observation']['image_pair_ref'] if r['observation'] else None
        v = project(r['program'], r['observation'], pair, r['interpretation'], r['judgment'])
        extra.append([v[n] for n in extra_names])
    extra = np.asarray(extra, dtype=bool)
    slots = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    members = {r['fold']: r for r in read(study/'memberships.json')}
    published = {r['case']: r for r in read(VERIFIED/'predictions.json')}
    stored_rows = {(r['candidate'], r['case']): r for r in read(study/'predictions.json')}
    rows = []; checks = []; scalars = 0; booleans = 0
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        a, c, fit = contexts(d, f); full, fitting = c['actual'], c['fitting']
        assert members[f['fold']]['fit_cases'] == [d['examples'][i]['case'] for i in fit]
        assert set(members[f['fold']]['fit_source_groups']) == set(d['groups'][fit])
        assert not set(d['groups'][fit])&set(d['groups'][a['held']])
        actual, T, projection = project_context(d, a, legacy)
        assert members[f['fold']]['projection_changed_rows'] == projection['changed_fitting_rows']
        assert members[f['fold']]['projection_changed_indicators'] == projection['changed_fitting_indicators']
        actual_X = np.c_[actual, extra]; fitting_X = np.c_[T, extra]
        for priority, guards, loss in CONFIGS:
            name = name_of(priority, guards, loss); folder = study/a['folder']
            eligible = d['valid'] & (~full['locked'] if priority == 'retain_prior_priority' else True)
            fit_eligible = d['valid'] & (~fitting['locked'] if priority == 'retain_prior_priority' else True)
            model = CachedOpinionSelector(names, guards=guards, loss_cost=loss).fit(fitting_X[fit], d['y'][fit],
                base=fitting['base'][fit], eligible=fit_eligible[fit], groups=d['groups'][fit],
                protected_X=actual_X[:99], protected_y=d['y'][:99], protected_base=full['base'][:99], protected_eligible=eligible[:99])
            artifact = read(folder/(name+'.json')); native = read(folder/(name+'-native.json'))['rules']
            assert artifact == model.artifact() and native == model.native_rules
            for rule in artifact['rules']:
                assert (SEEDS[rule['grade']], True) in {(t['feature'], t['value']) for t in rule['conditions']}
            truth_rows = check_boolean_union(native, artifact['rules']); booleans += truth_rows
            p = model.predict(actual_X, base=full['base'], eligible=eligible)
            for i in range(len(p)):
                values = {n: bool(actual_X[i, j]) for j, n in enumerate(names)}
                assert scalar(native, values, int(full['base'][i]), bool(eligible[i])) == p[i]
                assert scalar(artifact['rules'], values, int(full['base'][i]), bool(eligible[i])) == p[i]
            assert p.tolist() == read(folder/(name+'-predictions.json'))
            assert np.all(p[:99] == d['y'][:99])
            assert sum(p[d['pos'][r['case']]] == r['reference'] for r in slots) == 144
            assert np.array_equal(p[~eligible], full['base'][~eligible])
            scalars += len(p)
            checks.append({'fold': f['fold'], 'candidate': name, 'scalar_rows': len(p), 'boolean_rows': truth_rows,
                           'original_correct': 99, 'local_slots_correct': 144})
            for i in a['held']:
                e = d['examples'][i]; assert full['base'][i] == published[e['case']]['prediction']
                row = {**e, 'candidate': name, 'fold': f['fold'], 'prediction': int(p[i]), 'baseline': int(full['base'][i])}
                saved = stored_rows[(name, e['case'])]
                for field in ('prediction', 'baseline', 'reference', 'source_group', 'covered', 'fold'):
                    assert row[field] == saved[field]
                rows.append(row)
    declared = read(study/'results.json'); metrics = {}
    for config in CONFIGS:
        name = name_of(*config); rr = [r for r in rows if r['candidate'] == name]
        assert len(rr) == len({r['case'] for r in rr}) == 276
        metric = classification_metrics(rr, 'prediction'); metrics[name] = metric
        for field in ('correct', 'total', 'accuracy', 'balanced_accuracy', 'unresolved'):
            assert np.isclose(metric[field], declared[name]['metrics'][field], atol=1e-12)
        assert sum(r['covered'] for r in rr) == declared[name]['coverage'] == 273
        assert classification_metrics(rr, 'baseline')['correct'] == 227
    assert scalars == manifest['scalar_replays'] == 43920
    result = {'passed': True, 'reinduced_selectors': len(checks), 'portable_scalar_rows': scalars,
        'exhaustive_boolean_rows': booleans, 'metrics': metrics, 'original99_and_local144_retained': True,
        'coverage': 273, 'new_api_calls': 0, 'selected_version_changed': False,
        'scope': 'All276 source-held development cases including fallback. Negative comparison; not a target completion.'}
    out.mkdir(parents=True); save_json(out/'verification.json', result); save_json(out/'checks.json', checks)
    save_json(out/'manifest.json', {'auditor_sha256': file_hash(__file__), 'study_manifest_sha256': file_hash(study/'manifest.json')})
    (out/'run.log').write_text('48 cached-opinion selectors re-induced; all scalar/merged/native predictions, local vetoes and full metrics match.\n')
    (out/'llm-histories.log').write_text('Zero new API/observer/encoder calls.\n')
    dest = out/'source_snapshot/run'/Path(__file__).name; dest.parent.mkdir(parents=True); shutil.copyfile(__file__, dest)
    print({'passed': True, 'selectors': len(checks), 'scalar_rows': scalars, 'boolean_rows': booleans,
        'metrics': {n: (m['correct'], m['balanced_accuracy']) for n, m in metrics.items()}}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--study', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True); a = p.parse_args()
    audit(a.study.resolve(), a.output_dir.resolve())
