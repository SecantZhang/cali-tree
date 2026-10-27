"""Re-induce facet selectors and independently replay every exported decision."""
import argparse
from itertools import product
from pathlib import Path
import shutil

import numpy as np

from critical.core.calibration.facet_selector_v162 import FacetSelector, allowed
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_compact_balance_v143 import contexts, CACHE, CACHE_AUDIT, VERIFIED
from run.verify_calitree_semantic_residual_v105 import load
from run.calitree_facet_selector_v162 import CONFIGS, name_of, load_observations
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, read
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS
from run.verify_calitree_facet_probe_v151 import classification_metrics
from run.calitree_semantic_context_projection_v171 import project_context


def scalar(rules, flags, current, eligible):
    if eligible:
        for row in rules:
            if current == row['from_grade'] and all(flags[t['feature']] == t['value'] for t in row['conditions']):
                return row['grade']
    return current


def check_boolean_union(native, merged):
    features = sorted({t['feature'] for r in native+merged for t in r['conditions']})
    assert len(features) <= 12, 'The frozen four-rule/three-literal budget permits at most12 distinct predicates'
    checked = 0
    for values in product((False, True), repeat=len(features)):
        flags = dict(zip(features, values))
        for grade, eligible in product((-1, 0, 1, 2), (False, True)):
            assert scalar(native, flags, grade, eligible) == scalar(merged, flags, grade, eligible)
            checked += 1
    return checked


def audit(collection, observation_audit, study, out):
    if out.exists():
        raise ValueError('Fresh facet-selector verification required')
    source_manifest, source_protocol = read(study/'manifest.json'), read(study/'protocol.json')
    assert digest(source_protocol) == source_manifest['protocol_ref']
    for path, sha in source_manifest['code_sha256'].items():
        assert file_hash(path) == file_hash(study/'source_snapshot'/Path(path).relative_to(ROOT)) == sha
    assert source_manifest['native_audit_manifest_sha256'] == file_hash(observation_audit/'manifest.json')
    d = load(CACHE, CACHE_AUDIT)
    new_names, new_X, available, raw_outcome, raw_strict = load_observations(collection, observation_audit, d)
    legacy = [n for n in d['names'] if allowed(n)]; names = legacy+new_names
    columns = [d['names'].index(n) for n in legacy]
    domain = available & d['valid'] & np.asarray([e['covered'] for e in d['examples']], dtype=bool)
    reference = {r['case']: r for r in read(VERIFIED/'predictions.json')}
    original = d['y'][:99]
    slots = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    saved_memberships = {r['fold']: r for r in read(study/'memberships.json')}
    rows = []; checks = []; scalar_rows = 0; boolean_rows = 0
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        a, context, genuine = contexts(d, f); full, fitting = context['actual'], context['fitting']
        train = np.asarray([i for i in genuine if domain[i]], dtype=int)
        membership = saved_memberships[f['fold']]
        assert membership['fit_cases'] == [d['examples'][i]['case'] for i in train]
        assert set(membership['fit_source_groups']) == set(d['groups'][train])
        assert not set(d['groups'][train])&set(d['groups'][a['held']])
        assert membership['protected_cases'] == [e['case'] for e in d['examples'][:99]]
        assert membership['held_cases'] == f['held_cases']
        actual_legacy, fitting_legacy, projection = project_context(d, a, legacy)
        actual_X = np.c_[actual_legacy, new_X]; fitting_X = np.c_[fitting_legacy, new_X]
        assert membership['projection_changed_rows'] == projection['changed_fitting_rows']
        assert membership['projection_changed_indicators'] == projection['changed_fitting_indicators']
        for priority, guards, loss in CONFIGS:
            name = name_of(priority, guards, loss); folder = study/a['folder']
            eligible = domain & (~full['locked'] if priority == 'retain_prior_priority' else True)
            fit_eligible = domain & (~fitting['locked'] if priority == 'retain_prior_priority' else True)
            model = FacetSelector(names, guards=guards, loss_cost=loss).fit(fitting_X[train], d['y'][train],
                base=fitting['base'][train], eligible=fit_eligible[train], groups=d['groups'][train],
                protected_X=actual_X[:99], protected_y=original, protected_base=full['base'][:99],
                protected_eligible=eligible[:99])
            artifact = read(folder/(name+'.json')); native = read(folder/(name+'-native.json'))['rules']
            binding = read(folder/(name+'-binding.json'))
            expected_parent = read(ROOT/'examples/calitree_weighted_semantic_v112/policy.json')['artifact_ref'] if f['fold'] == 5 else None
            assert binding['fold'] == f['fold'] and binding['deployment_parent_artifact_ref'] == expected_parent
            assert binding['native_parent_context_ref'] == digest({'fold': f['fold'], 'support': full['support'].tolist(),
                'predictions': full['base'].tolist(), 'locked': full['locked'].tolist()})
            assert binding['selector_artifact_ref'] == artifact['artifact_ref'] and binding['priority'] == priority
            assert binding['legacy_feature_names'] == legacy and binding['new_feature_names'] == new_names
            assert binding['legacy_float32_border'] == .5
            assert binding['observation_audit_manifest_sha256'] == file_hash(observation_audit/'manifest.json')
            assert artifact == model.artifact() and native == model.native_rules
            assert artifact['artifact_ref'] == digest({k: v for k, v in artifact.items() if k != 'artifact_ref'})
            assert artifact['native_rules_ref'] == digest(native)
            exhaustive = check_boolean_union(native, artifact['rules']); boolean_rows += exhaustive
            predicted = model.predict(actual_X, base=full['base'], eligible=eligible)
            scalar_predictions = []
            for i in range(len(predicted)):
                flags = {n: bool(actual_X[i, j]) for j, n in enumerate(names)}
                p = scalar(artifact['rules'], flags, int(full['base'][i]), bool(eligible[i]))
                assert p == scalar(native, flags, int(full['base'][i]), bool(eligible[i])) == predicted[i]
                scalar_predictions.append(p)
            assert scalar_predictions == read(folder/(name+'-predictions.json'))
            assert np.array_equal(predicted[:99], original)
            assert sum(predicted[d['pos'][r['case']]] == r['reference'] for r in slots) == 144
            assert np.array_equal(predicted[~eligible], full['base'][~eligible])
            scalar_rows += len(predicted)
            checks.append({'fold': f['fold'], 'candidate': name, 'original_correct': 99, 'local_slots_correct': 144,
                           'scalar_rows': len(predicted), 'exhaustive_boolean_rows': exhaustive})
            for i in a['held']:
                e = d['examples'][i]; assert full['base'][i] == reference[e['case']]['prediction']
                rows.append({**e, 'candidate': name, 'fold': f['fold'], 'prediction': scalar_predictions[i],
                    'baseline': int(full['base'][i]), 'regular': int(d['regular'][i]),
                    'raw_outcome': int(raw_outcome[i]), 'raw_strict': int(raw_strict[i])})
    saved = read(study/'predictions.json'); assert len(saved) == len(rows)
    lookup = {(r['candidate'], r['case']): r for r in saved}; results = read(study/'results.json')
    metrics = {}
    for row in rows:
        stored = lookup[(row['candidate'], row['case'])]
        for field in ('prediction', 'baseline', 'regular', 'raw_outcome', 'raw_strict', 'reference', 'fold'):
            assert row[field] == stored[field]
        assert stored['merged_covered'] == stored['covered']
    for config in CONFIGS:
        name = name_of(*config); rr = [r for r in rows if r['candidate'] == name]
        assert len(rr) == len({r['case'] for r in rr}) == 276
        result = classification_metrics(rr, 'prediction'); metrics[name] = result
        for field, label in (('prediction', 'metrics'), ('baseline', 'baseline'), ('regular', 'regular'),
                             ('raw_outcome', 'raw_outcome'), ('raw_strict', 'raw_strict')):
            actual = classification_metrics(rr, field)
            for key in ('correct', 'total', 'accuracy', 'balanced_accuracy', 'unresolved'):
                assert np.isclose(actual[key], results[name][label][key], atol=1e-12)
        assert sum(r['covered'] for r in rr) == results[name]['coverage'] == 273
        assert results[name]['baseline']['correct'] == 227
    assert scalar_rows == source_manifest['scalar_replays']
    report = {'passed': True, 'reinduced_selectors': len(checks), 'portable_scalar_rows': scalar_rows,
        'exhaustive_boolean_rows': boolean_rows, 'metrics': metrics, 'original99_retained_in_every_fit': True,
        'local144_slots_retained_in_every_fit': True, 'coverage': 273, 'new_api_calls': 0,
        'scope': 'Complete276-case source-held development replay. This does not turn repeated development data into an untouched final test.'}
    out.mkdir(parents=True); save_json(out/'verification.json', report); save_json(out/'checks.json', checks)
    save_json(out/'manifest.json', {'auditor_sha256': file_hash(__file__), 'study_manifest_sha256': file_hash(study/'manifest.json'),
        'observation_audit_manifest_sha256': file_hash(observation_audit/'manifest.json')})
    (out/'run.log').write_text('Re-induced selectors; exact merged/native Boolean truth tables and all915-row predictions independently replayed.\n')
    (out/'llm-histories.log').write_text('No neural/API calls during selector verification.\n')
    dest = out/'source_snapshot/run'/Path(__file__).name; dest.parent.mkdir(parents=True); shutil.copyfile(__file__, dest)
    print({'passed': True, 'selectors': len(checks), 'scalar_rows': scalar_rows, 'boolean_rows': boolean_rows,
        'metrics': {n: (m['correct'], m['balanced_accuracy']) for n, m in metrics.items()}}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--collection', type=Path, required=True)
    p.add_argument('--observation-audit', type=Path, required=True); p.add_argument('--study', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True); a = p.parse_args()
    audit(a.collection.resolve(), a.observation_audit.resolve(), a.study.resolve(), a.output_dir.resolve())
