"""Fit compact task/preservation rules only after the local cache completes."""
import argparse
from dataclasses import asdict
from pathlib import Path
import shutil

import numpy as np

from critical.core.calibration.local_warranted_rubric_v97 import LocalWarrantedRubric, SPECS, CONTRACT_REF, project, view_flags
from critical.core.calibration.seeded_rubric_v73 import Search
from critical.core.calibration.source_excluded_calibration_v89 import source_excluded_views
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision import local_rubric_evidence_v94 as facts
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_seeded_rubric_v73 import arrays, attach
from run.calitree_source_excluded_calibration_v89 import baseline_predictions
from run.calitree_warranted_rubric_v71 import TEACHERS, INNER
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, FROZEN, read
from run.calitree_cached_sol_router_v85 import cached
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS
from run.calitree_accuracy_headroom_v37 import accuracy

CONFIGS = [Search(family=family, mode=mode, max_rules=8, max_guards=2, max_features=192 if family == 'semantic' else 256,
                  min_sources=support, loss_cost=2.) for mode in ('grades', 'hybrid') for family in ('semantic', 'auxiliary') for support in (1, 2)]


def name(config):
    return config.family+'_'+config.mode+'_sources'+str(config.min_sources)


def run(cache, out):
    # Fail before fitting or creating output if collection is still in flight.
    if not (cache/'results.json').exists() or not read(cache/'results.json')['complete']:
        raise ValueError('The frozen local observation cache must be complete before fitting')
    if out.exists():
        raise ValueError('Fresh fitting experiment directory required')
    examples, old_names, raw, semantic = arrays(); y = np.asarray([e['reference'] for e in examples])
    groups = np.asarray([e['source_group'] for e in examples]); regular = np.asarray([e['regular'] for e in examples]); valid = np.asarray([e['covered'] for e in examples]); sol, _ = cached(examples)
    pos = {e['case']: i for i, e in enumerate(examples)}; inputs = {r['case']: r for r in read(FROZEN/'replay_inputs_without_references.json')}
    manifest = read(cache/'manifest.json'); profile = read(cache/'identity.json'); jobs = read(cache/'jobs.json')
    assert digest(jobs) == manifest['jobs_ref'] and digest(profile) == manifest['identity_ref']
    assert profile['contract_ref'] == facts.CONTRACT_REF
    for file, sha in manifest['code_sha256'].items():
        assert file_hash(cache/'source_snapshot'/Path(file).relative_to(ROOT)) == sha
    for file, sha in manifest['source_hashes'].items():
        assert file_hash(file) == sha
    template = (cache/'source_snapshot/critical/core/prompts/templates/local_rubric_v94/observe.txt').read_text()
    membership = read(cache/'memberships.json'); assert digest(membership) == manifest['memberships_ref']
    threshold = read(cache/'protocol.json')['review_threshold']; assert threshold == .8
    extra_names = list(SPECS); local = np.zeros((len(examples), len(extra_names)), dtype=np.float32); source_hashes = {}
    available = np.zeros(len(examples), dtype=bool)
    for job in jobs:
        path = cache/'responses'/(job['case']+'.json'); response = read(path); source_hashes[str(path)] = file_hash(path)
        assert response['request_ref'] == job['request_ref'] and job['program'] == inputs[job['case']]['program']
        assert digest({k: v for k, v in job.items() if k != 'request_ref'}) == job['request_ref']
        assert job['identity_ref'] == manifest['identity_ref'] and digest(job['prompt']) == job['prompt_ref']
        assert job['prompt'] == facts.prompt(job['program'], template)
        if 'cache_origin' in response:
            assert file_hash(response['cache_origin']) == response['cache_origin_sha256']
        if response['record'] is not None:
            flags = project(job['program'], job['image_pair_ref'], manifest['identity_ref'], job['prompt_ref'], response['record'])
            i = pos[job['case']]; local[i] = [int(flags[n]) for n in extra_names]; available[i] = True
    names = old_names+extra_names
    protocol = {'version': LocalWarrantedRubric.version, 'configs': [asdict(c) for c in CONFIGS], 'review_threshold': threshold,
                'scope': 'Same276 primary cases/five source-held folds; all held-source siblings excluded. Fold5 all-data artifacts are not evaluated.',
                'fitting': 'Only each fold genuine inner-source-excluded rows meeting the fixed .8 review cue can fit rules. Cache-union membership and other-fold review masks are never fitting features.',
                'warrants': 'Each concrete grade starts from a positive bound local-model warrant. Hybrid review clauses may select the already available independent regular visual judgment when local claims challenge the teacher; they never invent a grade from uncertainty. Separate collateral relevance from its type and explicit preservation.',
                'protection': 'All99 actual original inputs veto harmful rules in every fit. Existing v72/v87 rules preserve their original full-teacher context and priority; outside review/failed observations retain the prior decision.',
                'comparison': 'All276 cases, failed local observations included via unchanged prior fallback. Preserve144 local slots and273/276 upstream coverage; >85% needs235/276.',
                'selection': 'Highest primary correct count, then fewer all-data clauses/conditions, then greater positive-source support, then lexical candidate. A selected candidate still needs independent audit and real bound-runtime replay; no automatic serving change.',
                'limits': 'Learned rules use model claims, not certified facts. These are reviewed development cases; no untouched-test claim.',
                'new_paid_calls': 0, 'new_local_inferences': 0, 'reserved_sources_used': 0, 'serving_changed': False}
    out.mkdir(parents=True); save_json(out/'protocol.json', protocol)
    (out/'run.log').write_text('Completed local cache validated; source-held compact-rule fitting started.\n'); (out/'llm-histories.log').write_text('Zero model calls/inference/uploads during fitting. Cached local observations only; no v75 response reads.\n')
    files = [Path(__file__), ROOT/'critical/core/calibration/local_warranted_rubric_v97.py', ROOT/'critical/core/calibration/seeded_rubric_v73.py']
    for file in files:
        dest = out/'source_snapshot'/file.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(file, dest)
    records = []; retention = []; original_slots = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        folder = 'fold'+str(f['fold']); train = [pos[c] for c in f['train_cases']]; held = [pos[c] for c in f['held_cases']]
        ps = np.asarray(read(TEACHERS/folder/'predictions.json')['support']); current, locked = baseline_predictions(folder, old_names, raw, semantic, ps, regular, sol, valid)
        actual = valid & ~locked & (ps.max(axis=1) < threshold)
        inner_views = [(read(INNER/folder/('inner'+str(k))/'membership.json'), read(INNER/folder/('inner'+str(k))/'predictions.json')['support']) for k in range(5)]
        oof_ps, genuine = source_excluded_views(ps, train, held, groups, inner_views)
        fitting = valid & genuine & (oof_ps.max(axis=1) < threshold)
        expected = next(r for r in membership if r['fold'] == f['fold'])
        assert [examples[i]['case'] for i in np.where(actual)[0]] == expected['actual_review_cases']
        assert [examples[i]['case'] for i in np.where(fitting)[0]] == expected['fit_review_cases']
        assert set(np.where(fitting)[0]) <= set(train) and not set(groups[np.where(fitting)[0]]) & set(groups[held])
        base = np.argmax(ps, axis=1); base[~valid] = regular[~valid]
        oof_base = np.argmax(oof_ps, axis=1); oof_base[~valid] = regular[~valid]
        local_actual = local*actual[:, None]; local_oof = local*fitting[:, None]
        for matrix, mask, teacher_grades in ((local_actual, actual, base), (local_oof, fitting, oof_base)):
            for i in np.where(mask & available)[0]:
                dynamic = view_flags({n: bool(local[i, j]) for j, n in enumerate(extra_names)}, int(teacher_grades[i]), int(regular[i]))
                for feature, value in dynamic.items():
                    matrix[i, extra_names.index(feature)] = int(value)
        full = np.concatenate([attach(raw, semantic, ps, regular), local_actual], axis=1)
        fitting_views = np.concatenate([attach(raw, semantic, oof_ps, regular), local_oof], axis=1)
        fit = np.where(fitting)[0].tolist(); priority = {n: (5000. if n in ('local_no_ready', 'local_partial_ready', 'local_yes_ready') else 2500. if n in SPECS else 1000. if n.startswith('meaning_') else 0.) for n in names}
        all_predictions = {}
        for config in CONFIGS:
            candidate = name(config)
            model = LocalWarrantedRubric(names, config).fit(fitting_views[fit], y[fit], groups=groups[fit].tolist(), base=oof_base[fit], regular=regular[fit],
                protected_X=full[:99], protected_y=y[:99], protected_base=base[:99], protected_regular=regular[:99], priority=priority)
            p = np.asarray(model.predict(full, base=base, regular=regular)); p[~actual] = current[~actual]
            assert np.all(p[:99] == y[:99]) and np.array_equal(p[~actual], current[~actual])
            slots = int(sum(p[pos[r['case']]] == r['reference'] for r in original_slots)); assert slots == 144
            artifact = model.artifact(digest(read(TEACHERS/folder/'teacher.json')['contract']))
            artifact = {k: v for k, v in artifact.items() if k != 'artifact_ref'}
            artifact.update(review_threshold=threshold, observer_identity_ref=manifest['identity_ref'], local_fact_contract_ref=CONTRACT_REF,
                            observer_template_ref=digest(template), prior_rules_keep_original_context=True, fit_cases=[examples[i]['case'] for i in fit])
            artifact['artifact_ref'] = digest(artifact); save_json(out/folder/(candidate+'.json'), artifact); (out/folder/(candidate+'.txt')).write_text(model.render())
            all_predictions[candidate] = p.tolist()
            retention.append({'candidate': candidate, 'fold': f['fold'], 'original_correct': 99, 'slots_correct': slots,
                              'fit_rows': len(fit), 'fit_sources': len(set(groups[fit])), 'rules': len(model.rules), 'conditions': sum(len(r['conditions']) for r in model.rules)})
            for i in held:
                records.append({**examples[i], 'candidate': candidate, 'fold': f['fold'], 'prediction': int(p[i]), 'baseline': int(current[i]),
                                'review': bool(actual[i]), 'local_available': bool(available[i] and actual[i])})
        save_json(out/folder/'all_predictions.json', all_predictions); save_json(out/'predictions.json', records); save_json(out/'retention.json', retention)
        print({'fold': f['fold'], 'fit_rows': len(fit), 'held': len(held), 'rules': {r['candidate']: r['rules'] for r in retention if r['fold'] == f['fold']}}, flush=True)
    results = {}
    for config in CONFIGS:
        candidate = name(config); rows = [r for r in records if r['candidate'] == candidate]
        results[candidate] = {'accuracy': accuracy(rows, 'prediction'), 'baseline': accuracy(rows, 'baseline'),
                'gains': sum(r['prediction'] == r['reference'] != r['baseline'] for r in rows), 'losses': sum(r['baseline'] == r['reference'] != r['prediction'] for r in rows),
                'review_cases': sum(r['review'] for r in rows), 'valid_local_review_cases': sum(r['local_available'] for r in rows),
                'coverage': sum(r['covered'] for r in rows), 'original_cases_retained': 99, 'original_slots_retained': 144,
                'target_exceeded': accuracy(rows, 'prediction')['correct'] >= 235}
    assert all(r['baseline']['correct'] == 225 and r['coverage'] == 273 for r in results.values())
    full = {r['candidate']: r for r in retention if r['fold'] == 5}
    config_by_name = {name(config): config for config in CONFIGS}
    selected = min(results, key=lambda candidate: (-results[candidate]['accuracy']['correct'], full[candidate]['rules'],
                    full[candidate]['conditions'], -config_by_name[candidate].min_sources, candidate))
    save_json(out/'selection.json', {'candidate': selected, 'accuracy': results[selected]['accuracy'],
                'target_exceeded': results[selected]['target_exceeded'], 'verified': False, 'serving_changed': False,
                'needs_independent_audit': results[selected]['accuracy']['correct'] > 225})
    save_json(out/'results.json', results); save_json(out/'manifest.json', {'protocol_ref': digest(protocol), 'cache_manifest_sha256': file_hash(cache/'manifest.json'),
                'cache_result_sha256': file_hash(cache/'results.json'), 'code_sha256': {str(p): file_hash(p) for p in files}, 'source_hashes': source_hashes, 'targets_ref': digest(y.tolist())})
    (out/'run.log').write_text('Completed eight source-held compact local grading/review policies; originals/slots/coverage retained. No serving change; see measured results.json.\n')
    print(results, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--cache', type=Path, required=True); p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args(); run(a.cache.resolve(), a.output_dir.resolve())
