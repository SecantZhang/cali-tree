"""Audit local observation bindings, budgets and fold-specific review masks.

Partial audits are explicitly snapshots of collection, never fitting approval or
an accuracy result. --require-complete additionally reconciles the terminal
collector summary before permitting downstream experiment checks.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np
from catboost import CatBoostClassifier

from critical.core.decision import local_rubric_evidence_v94 as facts
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.core.calibration.source_excluded_calibration_v89 import source_excluded_views
from critical.lm_engine.local_qwen_v94 import MODEL, REVISION, file_hash, parse_json
from run.calitree_semantic_rubric_v70 import ROOT, FROZEN, VISION, STUDY, data, read
from run.calitree_seeded_rubric_v73 import arrays
from run.calitree_source_excluded_calibration_v89 import baseline_predictions
from run.calitree_cached_sol_router_v85 import cached
from run.calitree_warranted_rubric_v71 import TEACHERS, INNER


def validate_response(job, response, profile):
    if response.get('case') != job['case'] or response.get('request_ref') != job['request_ref']:
        raise ValueError('Local response belongs to a different request')
    if digest({k: v for k, v in job.items() if k != 'request_ref'}) != job['request_ref']:
        raise ValueError('Changed prepared local request')
    if job['identity_ref'] != digest(profile) or job['schema'] != facts.schema() or job['prompt_ref'] != digest(job['prompt']):
        raise ValueError('Changed local identity/schema/prompt')
    raw = response.get('response')
    if raw is not None:
        if raw['engine'] != profile['engine'] or raw['model'] != profile['model'] or raw['endpointHost'] != 'local-mps':
            raise ValueError('A different or remote model supplied the observation')
        for key in ('promptTokens', 'completionTokens', 'totalTokens'):
            if type(raw[key]) is not int or raw[key] < 0:
                raise ValueError('Nonnegative native token counts required')
        if raw['promptTokens']+raw['completionTokens'] != raw['totalTokens'] or raw['completionTokens'] > profile['max_new_tokens']:
            raise ValueError('Local token accounting mismatch')
        if parse_json(raw['content']) != raw['parsed']:
            raise ValueError('Parsed local observation differs from the unmodified raw output')
    if response.get('record') is not None:
        if response.get('error') is not None or raw is None or raw['finishReason'] != 'stop':
            raise ValueError('Failed or truncated observations cannot be accepted')
        if response['observation'] != raw['parsed'] or response['record']['observation'] != raw['parsed']:
            raise ValueError('Accepted local observation was repaired or replaced')
        facts.project(job['program'], job['image_pair_ref'], job['identity_ref'], job['prompt_ref'], response['record'])
        return True
    if response.get('observation') is not None or not isinstance(response.get('error'), str) or not response['error']:
        raise ValueError('Rejected local slots must remain explicitly failed')
    return False


def history_key(prompt, raw):
    return (prompt, raw['content'], raw['promptTokens'], raw['completionTokens'], raw['model'])


def audit(cache, out, require_complete=False, *, expected_profile=None):
    if out.exists():
        raise ValueError('Fresh audit directory required')
    manifest = read(cache/'manifest.json'); profile = read(cache/'identity.json'); jobs = read(cache/'jobs.json'); memberships = read(cache/'memberships.json')
    protocol = read(cache/'protocol.json')
    assert digest(protocol) == manifest['protocol_ref'] and digest(profile) == manifest['identity_ref']
    assert digest(jobs) == manifest['jobs_ref'] and digest(memberships) == manifest['memberships_ref']
    assert profile['contract_ref'] == facts.CONTRACT_REF and profile['decoder'] == 'native-json-schema-prefix'
    assert profile['model'] == MODEL and profile['revision'] == REVISION and profile['engine'] == 'local_qwen_grammar_v95'
    assert profile['device'] == 'mps' and profile['dtype'] == 'float16' and profile['attention'] == 'sdpa' and profile['do_sample'] is False
    if expected_profile is None:
        assert profile['max_new_tokens'] == 256 and profile['max_pixels_per_image'] == 256*32*32
    else:
        # The v109 wrapper supplies the full frozen profile, not arbitrary
        # per-field exceptions. The historical CLI/default stays unchanged.
        assert profile == expected_profile
        assert profile['max_new_tokens'] == 512 and profile['max_pixels_per_image'] == 1024*32*32
        assert protocol['version'] == 'high-resolution-local-review-cache-v108'
    assert protocol['review_threshold'] == .8 and protocol['bounds'] == {'workers': 1, 'max_fresh_local_inferences': 224, 'max_new_tokens': 224*profile['max_new_tokens'], 'retries': 0}
    checkpoint_path = ROOT/'logs/exps/261023-local-vlm-download-v94-r1/identity.json'
    assert file_hash(checkpoint_path) == manifest['checkpoint_identity_sha256'] and digest(read(checkpoint_path)) == profile['checkpoint_ref']
    assert len(jobs) == protocol['cases'] == 224 and len({j['case'] for j in jobs}) == len(jobs)
    for file, sha in manifest['code_sha256'].items():
        assert file_hash(cache/'source_snapshot'/Path(file).relative_to(ROOT)) == sha
    for file, sha in manifest['source_hashes'].items():
        assert file_hash(file) == sha
    out.mkdir(parents=True); (out/'run.log').write_text('Independent review-region and local-request audit started.\n')
    (out/'llm-histories.log').write_text('Zero model/API calls or fits. Local collector request/response history is audited in the source cache.\n')
    snapshot = out/'source_snapshot/run'/Path(__file__).name; snapshot.parent.mkdir(parents=True); snapshot.write_bytes(Path(__file__).read_bytes())
    examples, teacher_names, X = data(); same, names, raw, semantic = arrays(); assert examples == same
    groups = np.asarray([e['source_group'] for e in examples]); valid = np.asarray([e['covered'] for e in examples]); y = np.asarray([e['reference'] for e in examples])
    regular = np.asarray([e['regular'] for e in examples]); sol, _ = cached(examples); pos = {e['case']: i for i, e in enumerate(examples)}
    reserved_metadata = ROOT/'logs/exps/261020-validation-reservation-v39/inputs_without_labels.json'
    assert not set(groups) & {r['source_group'] for r in read(reserved_metadata)}
    selected = set(); native_count = 0; mask_checks = []; source_hashes = {}
    for path in (cache/'manifest.json', cache/'identity.json', cache/'jobs.json', cache/'memberships.json', cache/'protocol.json', checkpoint_path):
        source_hashes[str(path)] = file_hash(path)
    for path in (FROZEN/'fitting_replay.json', FROZEN/'replay_inputs_without_references.json', VISION/'inputs_without_labels.json', STUDY/'folds.json'):
        source_hashes[str(path)] = file_hash(path)
    source_hashes[str(reserved_metadata)] = file_hash(reserved_metadata)
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        folder = 'fold'+str(f['fold']); train = [pos[c] for c in f['train_cases']]; held = [pos[c] for c in f['held_cases']]
        assert not set(groups[train]) & set(groups[held])
        meta = read(TEACHERS/folder/'teacher.json')['contract']; columns = [teacher_names.index(n) for n in meta['columns']]
        assert meta['rows'] == train and digest(X[train][:, columns].tolist()) == meta['matrix_ref'] and digest(y[train].tolist()) == meta['targets_ref']
        model = CatBoostClassifier(); model.load_model(str(TEACHERS/folder/'teacher.cbm')); ps = model.predict_proba(X[:, columns], thread_count=2); native_count += 1
        assert np.allclose(ps, read(TEACHERS/folder/'predictions.json')['support'], atol=1e-12, rtol=0)
        for name in ('teacher.cbm', 'teacher.json', 'predictions.json'):
            path = TEACHERS/folder/name; source_hashes[str(path)] = file_hash(path)
        _, locked = baseline_predictions(folder, names, raw, semantic, ps, regular, sol, valid)
        actual = valid & ~locked & (ps.max(axis=1) < protocol['review_threshold']); inner_views = []
        for k in range(5):
            path = INNER/folder/('inner'+str(k)); membership = read(path/'membership.json'); inner_meta = read(path/'teacher.json')['contract']
            cols = [teacher_names.index(n) for n in inner_meta['columns']]; indices = membership['train']
            assert inner_meta['rows'] == indices and digest(X[indices][:, cols].tolist()) == inner_meta['matrix_ref'] and digest(y[indices].tolist()) == inner_meta['targets_ref']
            model = CatBoostClassifier(); model.load_model(str(path/'teacher.cbm')); p = model.predict_proba(X[:, cols], thread_count=2); native_count += 1
            assert np.allclose(p, read(path/'predictions.json')['support'], atol=1e-12, rtol=0)
            inner_views.append((membership, p))
            for name in ('teacher.cbm', 'teacher.json', 'predictions.json', 'membership.json'):
                source_hashes[str(path/name)] = file_hash(path/name)
        oof, genuine = source_excluded_views(ps, train, held, groups, inner_views)
        fit = valid & genuine & (oof.max(axis=1) < protocol['review_threshold'])
        selected.update(np.where(actual | fit)[0].tolist())
        saved = next(m for m in memberships if m['fold'] == f['fold'])
        assert saved['train_cases'] == f['train_cases'] and saved['held_cases'] == f['held_cases']
        assert saved['actual_review_cases'] == [examples[i]['case'] for i in np.where(actual)[0]]
        assert saved['fit_review_cases'] == [examples[i]['case'] for i in np.where(fit)[0]]
        assert saved['inner_memberships'] == [m for m, _ in inner_views]
        mask_checks.append({'fold': f['fold'], 'actual_review': int(actual.sum()), 'fit_review': int(fit.sum())})
    assert [j['case'] for j in jobs] == [examples[i]['case'] for i in sorted(selected)]
    raw_inputs = {r['case']: r for r in read(FROZEN/'replay_inputs_without_references.json')}
    template = (cache/'source_snapshot/critical/core/prompts/templates/local_rubric_v94/observe.txt').read_text()
    template_path = cache/'source_snapshot/critical/core/prompts/templates/local_rubric_v94/observe.txt'
    source_hashes[str(template_path)] = file_hash(template_path)
    response_paths = {p.stem: p for p in (cache/'responses').glob('*.json')}; attempt_paths = {p.stem: p for p in (cache/'attempts').glob('*.json')}
    assert set(response_paths) <= {j['case'] for j in jobs} and set(attempt_paths) <= {j['case'] for j in jobs}
    histories = []
    for line in (cache/'llm-histories.log').read_text().splitlines(keepends=True):
        if not line.endswith('\n'):
            continue  # In-flight writer may not have completed its last line.
        entry = json.loads(line)
        assert entry['engine'] == profile['engine'] and entry['model'] == profile['model'] and entry['endpoint_host'] == 'local-mps' and entry['remote_calls'] == 0
        assert entry['checkpoint_revision'] == profile['revision'] and entry['do_sample'] is False
        assert entry['max_new_tokens'] == profile['max_new_tokens'] and entry['max_pixels_per_image'] == profile['max_pixels_per_image']
        histories.append(entry)
    history = Counter((h['prompt'], h.get('response'), h['prompt_tokens'], h['completion_tokens'], h['model']) for h in histories)
    slots = []; completed_tokens = reserved_tokens = fresh_tokens = reused = accepted = 0
    for job in jobs:
        r = raw_inputs[job['case']]; assert job['program'] == r['program'] and job['evidence'] == r['evidence']
        assert job['prompt'] == facts.prompt(job['program'], template)
        hashes, pair = image_identity(r['evidence']); assert hashes == job['image_hashes'] and pair == job['image_pair_ref']
        case = job['case']; path = response_paths.get(case); attempt = attempt_paths.get(case)
        if attempt is not None:
            a = read(attempt); assert a['case'] == case and a['request_ref'] == job['request_ref'] and a['status'] == 'attempted'
            source_hashes[str(attempt)] = file_hash(attempt)
        if path is None:
            if attempt is not None:
                reserved_tokens += profile['max_new_tokens']
            slots.append({'case': case, 'status': 'pending', 'attempted': attempt is not None}); continue
        response = read(path); passed = validate_response(job, response, profile); source_hashes[str(path)] = file_hash(path)
        accepted += passed; raw_response = response.get('response')
        tokens = raw_response['completionTokens'] if raw_response is not None else 0
        completed_tokens += tokens
        if 'cache_origin' in response:
            assert attempt is None and file_hash(response['cache_origin']) == response['cache_origin_sha256']
            origin = Path(response['cache_origin']); original = read(origin)
            assert origin == ROOT/'logs/exps/261023-local-grammar-v95-smoke-r1/responses'/(case+'.json')
            source_cache = origin.parent.parent; source_manifest = read(source_cache/'manifest.json')
            source_jobs = read(source_cache/'jobs.json'); assert digest(source_jobs) == source_manifest['jobs_ref']
            assert source_manifest['identity_ref'] == manifest['identity_ref'] and next(j for j in source_jobs if j['case'] == case) == job
            assert {k: v for k, v in response.items() if k not in ('cache_origin', 'cache_origin_sha256')} == original
            reused += 1
        else:
            assert attempt is not None
            fresh_tokens += tokens
            if raw_response is None:
                reserved_tokens += profile['max_new_tokens']
            else:
                key = history_key(job['prompt'], raw_response); assert history[key] >= 1; history[key] -= 1
        slots.append({'case': case, 'status': 'accepted' if passed else 'failed', 'reused': 'cache_origin' in response, 'tokens': tokens})
    complete = len(response_paths) == len(jobs)
    assert len(attempt_paths) <= len(jobs) and len(histories) <= len(attempt_paths)
    assert fresh_tokens+reserved_tokens <= protocol['bounds']['max_new_tokens']
    if require_complete:
        assert complete, 'Observation collection is incomplete'
        terminal = read(cache/'results.json'); assert terminal['complete'] and terminal['responses'] == len(jobs)
        assert terminal['fresh_attempts'] == len(attempt_paths) and terminal['accepted'] == accepted and terminal['reused'] == reused and terminal['fresh_completion_tokens'] == fresh_tokens
    verification = {'passed': True, 'complete': complete, 'snapshot_only': not require_complete,
        'native_models_checked': native_count, 'masks_checked': mask_checks, 'cases': len(jobs), 'responses_checked': len(response_paths),
        'accepted': accepted, 'reused': reused, 'fresh_attempts': len(attempt_paths), 'completed_tokens_including_reuse': completed_tokens,
        'fresh_completion_tokens': fresh_tokens, 'reserved_completion_tokens': reserved_tokens,
        'fresh_tokens_plus_reservations': fresh_tokens+reserved_tokens, 'max_fresh_tokens': protocol['bounds']['max_new_tokens'],
        'new_llm_calls': 0, 'new_paid_calls': 0, 'new_fits': 0, 'reserved_sources_used': 0, 'no_accuracy_claim': True}
    save_json(out/'verification.json', verification); save_json(out/'slots.json', slots)
    save_json(out/'manifest.json', {'auditor_sha256': file_hash(__file__), 'cache_manifest_sha256': file_hash(cache/'manifest.json'), 'source_hashes': source_hashes})
    (out/'run.log').write_text('Native review masks, source exclusions, local bindings and accounting verified. This snapshot grants no fitting/accuracy claim unless collection is complete.\n')
    print(verification, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--cache', type=Path, required=True); p.add_argument('--output-dir', type=Path, required=True); p.add_argument('--require-complete', action='store_true')
    a = p.parse_args(); audit(a.cache.resolve(), a.output_dir.resolve(), a.require_complete)
