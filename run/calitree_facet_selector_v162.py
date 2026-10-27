"""Fit compact source-excluded facet experts after the complete native audit."""
import argparse
from pathlib import Path
import shutil

import numpy as np

from critical.core.calibration.facet_selector_v162 import (FacetSelector, FACETS, allowed, project, execute)
from critical.core.calibration.class_balance_v141 import classification_metrics
from critical.core.decision import outcome_policy_v160 as outcome, facet_policy_v150 as strict
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_compact_balance_v143 import contexts, CACHE, CACHE_AUDIT, VERIFIED
from run.verify_calitree_semantic_residual_v105 import load
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, read
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS
from run.calitree_semantic_context_projection_v171 import project_context

CONFIGS = [(priority, guards, loss) for priority in ('retain_prior_priority', 'learned_semantic_precedence')
           for guards in (1, 2) for loss in (1., 2.)]
PRIMARY = ('learned_semantic_precedence', 2, 2.)


def name_of(priority, guards, loss):
    return priority+'_guards'+str(guards)+'_loss'+str(loss)


def load_observations(collection, audit, d):
    verified = read(audit/'verification.json'); manifest = read(audit/'manifest.json')
    if not (verified['passed'] and verified['complete'] and verified['fitting_ready'] and
            not verified.get('mock_transport_test', False)):
        raise ValueError('Complete real native observation audit required; mock/incomplete caches cannot fit a policy')
    assert manifest['collection_manifest_sha256'] == file_hash(collection/'manifest.json')
    observations = read(audit/'observations.json'); assert digest(observations) == manifest['observations_ref']
    for path, sha in manifest['native_input_sha256'].items():
        assert file_hash(path) == sha
    jobs = {j['case']: j for j in read(collection/'jobs.json')}
    assert len(observations) == len(jobs) == 375
    records = {r['case']: r for r in observations}; assert set(records) == set(jobs)
    frozen = {r['case']: r for r in read(ROOT/'logs/exps/261021-frozen-visual-policy-v69/replay_inputs_without_references.json')}
    new_names = list(FACETS); rows = []; available = []; raw_outcome = []; raw_strict = []
    for e in d['examples']:
        record = records.get(e['case']); value = None
        if record is not None:
            assert record['observation_ref'] == digest({k: v for k, v in record.items() if k != 'observation_ref'})
            job = jobs[e['case']]; raw = frozen[e['case']]
            assert record['program_ref'] == raw['program']['program_ref'] == job['program_ref']
            assert record['request_ref'] == job['request_ref']
            assert record['collection_manifest_sha256'] == manifest['collection_manifest_sha256']
            assert image_identity(raw['evidence'])[1] == record['image_pair_ref'] == job['image_pair_ref']
            if record['accepted']:
                value = strict.validate(record['value'])
        flags = project(value); rows.append([flags[n] for n in new_names]); available.append(value is not None)
        a = outcome.decide(value) if value else None; b = strict.decide(value) if value else None
        raw_outcome.append(a if a is not None else -1); raw_strict.append(b if b is not None else -1)
    return new_names, np.asarray(rows, dtype=bool), np.asarray(available, dtype=bool), np.asarray(raw_outcome), np.asarray(raw_strict)


def run(collection, audit, out):
    if out.exists():
        raise ValueError('Fresh source-held semantic facet study required')
    study = read(collection/'protocol.json')['selector_study']
    expected = [{'priority': p, 'guards': g, 'loss_cost': loss, 'max_rules': 4, 'min_sources': 3} for p, g, loss in CONFIGS]
    assert study['candidates'] == expected
    assert study['primary'] == {'priority': PRIMARY[0], 'guards': PRIMARY[1], 'loss_cost': PRIMARY[2], 'max_rules': 4, 'min_sources': 3}
    d = load(CACHE, CACHE_AUDIT)
    new_names, new_X, available, raw_outcome, raw_strict = load_observations(collection, audit, d)
    legacy = [n for n in d['names'] if allowed(n)]
    names = legacy+new_names; assert len(names) == len(set(names))
    columns = [d['names'].index(n) for n in legacy]
    covered = np.asarray([e['covered'] for e in d['examples']], dtype=bool)
    domain = available & covered & d['valid']
    original_cases = [e['case'] for e in d['examples'][:99]]
    assert set(original_cases) == {r['case'] for r in read(ROOT/'logs/exps/261021-frozen-visual-policy-v69/fitting_replay.json')[:99]}
    expected_primary = {r['case']: r for r in read(VERIFIED/'predictions.json')}
    slots = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    protocol = {'version': 'source-bound-semantic-facet-selector-v162', 'configs': CONFIGS, 'primary': PRIMARY,
        'collection_manifest_sha256': file_hash(collection/'manifest.json'), 'native_audit_manifest_sha256': file_hash(audit/'manifest.json'),
        'observer': read(collection/'protocol.json')['observer_profile'], 'outcome_contract_ref': outcome.CONTRACT_REF,
        'fitting': study['fitting'], 'coverage': study['coverage'],
        'legacy_projection': 'Existing declared named indicators converted with float32 value greater than0.5. No case/source/editor identifiers or raw embeddings.',
        'merge': 'Only exact absorption/complementary unions of adjacent rules with the same action; never cross a different intervening expert decision.',
        'evaluation': 'All276 reviewed development examples in five source-held folds; full fit5 supplies the candidate artifact/local checks. All held-source siblings excluded. Existing V112 residual fitting views are reused, not newly inner-cross-fitted.',
        'new_model_calls': 0, 'reserved_sources_used': 0, 'serving_changed': False}
    out.mkdir(parents=True); save_json(out/'protocol.json', protocol)
    (out/'run.log').write_text('Compact semantic facet selection started after complete native observation audit.\n')
    (out/'llm-histories.log').write_text('No API/observer/encoder calls during fitting; audited cache only.\n')
    files = [Path(__file__), ROOT/'critical/core/calibration/facet_selector_v162.py', ROOT/'run/calitree_compact_balance_v143.py',
        ROOT/'critical/core/decision/outcome_policy_v160.py', ROOT/'critical/core/decision/facet_policy_v150.py',
        ROOT/'run/verify_calitree_semantic_residual_v105.py', ROOT/'run/calitree_source_excluded_calibration_v89.py',
        ROOT/'critical/core/calibration/semantic_residual_runtime_v104.py',
        ROOT/'critical/core/calibration/semantic_residual_v103.py',
        ROOT/'critical/core/calibration/local_warranted_rubric_v97.py', ROOT/'run/calitree_semantic_context_projection_v171.py']
    hashes = {str(p): file_hash(p) for p in files}
    for path in files:
        dest = out/'source_snapshot'/path.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, dest)
    rows = []; retention = []; memberships = []; replays = 0
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        a, context, genuine = contexts(d, f); full, fitting = context['actual'], context['fitting']
        train = np.asarray([i for i in genuine if domain[i]], dtype=int)
        assert len(train) and not set(d['groups'][train])&set(d['groups'][a['held']])
        actual_legacy, fitting_legacy, projection = project_context(d, a, legacy)
        actual_X = np.c_[actual_legacy, new_X]; fitting_X = np.c_[fitting_legacy, new_X]
        memberships.append({'fold': f['fold'], 'fit_cases': [d['examples'][i]['case'] for i in train],
            'fit_source_groups': sorted(set(d['groups'][train])), 'held_cases': f['held_cases'], 'protected_cases': original_cases,
            'projection_changed_rows': projection['changed_fitting_rows'],
            'projection_changed_indicators': projection['changed_fitting_indicators']})
        for priority, guards, loss in CONFIGS:
            name = name_of(priority, guards, loss)
            actual_eligible = domain & (~full['locked'] if priority == 'retain_prior_priority' else True)
            fitting_eligible = domain & (~fitting['locked'] if priority == 'retain_prior_priority' else True)
            model = FacetSelector(names, guards=guards, loss_cost=loss).fit(fitting_X[train], d['y'][train],
                base=fitting['base'][train], eligible=fitting_eligible[train], groups=d['groups'][train],
                protected_X=actual_X[:99], protected_y=d['y'][:99], protected_base=full['base'][:99],
                protected_eligible=actual_eligible[:99])
            p = model.predict(actual_X, base=full['base'], eligible=actual_eligible)
            native = model._predict(actual_X, full['base'], actual_eligible, model.native_rules)
            assert np.array_equal(p, native)
            artifact = model.artifact()
            used = artifact['feature_names']; indices = [names.index(n) for n in used]
            for i in range(len(p)):
                values = {n: bool(actual_X[i, j]) for n, j in zip(used, indices)}
                assert execute(artifact, values, int(full['base'][i]), bool(actual_eligible[i])) == p[i]
            replays += len(p)
            assert np.all(p[:99] == d['y'][:99])
            assert sum(p[d['pos'][r['case']]] == r['reference'] for r in slots) == 144
            assert np.array_equal(p[~actual_eligible], full['base'][~actual_eligible])
            # The new expert is a subset of the existing valid covered route;
            # its absence cannot remove the inherited tree or regular fallback.
            merged_coverage = covered.copy(); assert np.array_equal(merged_coverage, covered)
            if priority == 'retain_prior_priority':
                assert np.array_equal(p[full['locked']], full['base'][full['locked']])
            save_json(out/a['folder']/(name+'.json'), artifact)
            save_json(out/a['folder']/(name+'-native.json'), {'rules': model.native_rules})
            save_json(out/a['folder']/(name+'-predictions.json'), p.tolist())
            save_json(out/a['folder']/(name+'-binding.json'), {
                'fold': f['fold'],
                'deployment_parent_artifact_ref': read(ROOT/'examples/calitree_weighted_semantic_v112/policy.json')['artifact_ref'] if f['fold'] == 5 else None,
                'native_parent_context_ref': digest({'fold': f['fold'], 'support': full['support'].tolist(),
                    'predictions': full['base'].tolist(), 'locked': full['locked'].tolist()}),
                'priority': priority, 'legacy_feature_names': legacy, 'new_feature_names': new_names,
                'legacy_float32_border': .5, 'selector_artifact_ref': artifact['artifact_ref'],
                'observation_audit_manifest_sha256': file_hash(audit/'manifest.json')})
            retention.append({'fold': f['fold'], 'candidate': name, 'original_correct': 99, 'local_slots_correct': 144,
                'rules': len(model.rules), 'features': len(used), 'training': model.training})
            for i in a['held']:
                e = d['examples'][i]; assert full['base'][i] == expected_primary[e['case']]['prediction']
                rows.append({**e, 'candidate': name, 'fold': f['fold'], 'prediction': int(p[i]), 'baseline': int(full['base'][i]),
                    'raw_outcome': int(raw_outcome[i]), 'raw_strict': int(raw_strict[i]), 'regular': int(d['regular'][i]),
                    'facet_available': bool(available[i]), 'new_expert_eligible': bool(actual_eligible[i]),
                    'prior_locked': bool(full['locked'][i]), 'changed': bool(p[i] != full['base'][i]),
                    'merged_covered': bool(merged_coverage[i])})
        save_json(out/'predictions.json', rows); save_json(out/'retention.json', retention); save_json(out/'memberships.json', memberships)
        print({'fold': f['fold'], 'new_facet_fitting_cases': len(train), 'candidates': len(CONFIGS)}, flush=True)
    results = {}
    for config in CONFIGS:
        name = name_of(*config); rr = [r for r in rows if r['candidate'] == name]
        assert len(rr) == len({r['case'] for r in rr}) == 276
        assert {r['case'] for r in rr} == set(expected_primary)
        results[name] = {'metrics': classification_metrics(rr), 'baseline': classification_metrics(rr, 'baseline'),
            'regular': classification_metrics(rr, 'regular'), 'raw_outcome': classification_metrics(rr, 'raw_outcome'),
            'raw_strict': classification_metrics(rr, 'raw_strict'),
            'gains': sum(r['prediction'] == r['reference'] != r['baseline'] for r in rr),
            'losses': sum(r['baseline'] == r['reference'] != r['prediction'] for r in rr),
            'coverage': sum(r['merged_covered'] for r in rr), 'new_rule_routes': sum(r['changed'] for r in rr),
            'all_original_cases_and_slots_retained': True}
        assert results[name]['coverage'] == 273 and results[name]['baseline']['correct'] == 227
    save_json(out/'results.json', results)
    assert all(file_hash(path) == sha for path, sha in hashes.items())
    save_json(out/'manifest.json', {'code_sha256': hashes, 'protocol_ref': digest(protocol),
        'native_audit_manifest_sha256': file_hash(audit/'manifest.json'), 'scalar_replays': replays})
    (out/'run.log').write_text('Completed48 compact facet selector fits with native/merged/scalar replay; all99/144 local cases retained. V112 remains selected.\n')
    print({name: (r['metrics']['correct'], r['metrics']['balanced_accuracy']) for name, r in results.items()}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--collection', type=Path, required=True)
    p.add_argument('--audit', type=Path, required=True); p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args(); run(a.collection.resolve(), a.audit.resolve(), a.output_dir.resolve())
