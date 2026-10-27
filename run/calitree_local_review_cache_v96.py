"""Collect local facts only where fixed teacher review regions require them."""
import argparse
from importlib.metadata import version
import json
from pathlib import Path
import shutil

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision import local_rubric_evidence_v94 as facts
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.lm_engine.local_qwen_grammar_v95 import LocalQwenGrammarEngine
from critical.lm_engine.local_qwen_v94 import file_hash
from critical.logging.llm_history import LLMHistoryWriter
from run.calitree_local_observer_v94 import ROOT, FROZEN, TEMPLATE, DOWNLOAD, read

SMOKE = ROOT/'logs/exps/261023-local-grammar-v95-smoke-r1'
THRESHOLD = .8


def prepare(out):
    # CatBoost/main-runtime helpers are needed for preparation only. The vision
    # environment collecting observations never imports them.
    import numpy as np
    from run.calitree_semantic_rubric_v70 import data, STUDY
    from run.calitree_warranted_rubric_v71 import TEACHERS, INNER
    from critical.core.calibration.source_excluded_calibration_v89 import source_excluded_views
    from run.calitree_seeded_rubric_v73 import arrays
    from run.calitree_cached_sol_router_v85 import cached
    from run.calitree_source_excluded_calibration_v89 import baseline_predictions
    if out.exists():
        raise ValueError('Fresh observation-cache directory required')
    examples, _, _ = data(); same, names, raw, semantic = arrays(); assert examples == same
    groups = np.asarray([e['source_group'] for e in examples]); valid = np.asarray([e['covered'] for e in examples])
    regular = np.asarray([e['regular'] for e in examples]); sol, _ = cached(examples); pos = {e['case']: i for i, e in enumerate(examples)}
    selected = set(); memberships = []; source_hashes = {}
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        folder = 'fold'+str(f['fold']); train = [pos[c] for c in f['train_cases']]; held = [pos[c] for c in f['held_cases']]
        teacher = TEACHERS/folder; ps = np.asarray(read(teacher/'predictions.json')['support'])
        _, locked = baseline_predictions(folder, names, raw, semantic, ps, regular, sol, valid)
        actual = valid & ~locked & (ps.max(axis=1) < THRESHOLD)
        inner = []; trace = []
        for k in range(5):
            path = INNER/folder/('inner'+str(k)); membership = read(path/'membership.json')
            inner.append((membership, read(path/'predictions.json')['support'])); trace.append(membership)
            for file in ('membership.json', 'predictions.json'):
                source_hashes[str(path/file)] = file_hash(path/file)
        oof, genuine = source_excluded_views(ps, train, held, groups, inner)
        fit = valid & genuine & (oof.max(axis=1) < THRESHOLD)
        selected.update(np.where(actual | fit)[0].tolist())
        memberships.append({'fold': f['fold'], 'train_cases': f['train_cases'], 'held_cases': f['held_cases'],
                    'actual_review_cases': [examples[i]['case'] for i in np.where(actual)[0]],
                    'fit_review_cases': [examples[i]['case'] for i in np.where(fit)[0]], 'inner_memberships': trace})
        source_hashes[str(teacher/'predictions.json')] = file_hash(teacher/'predictions.json')
    checkpoint = read(DOWNLOAD); profile = read(SMOKE/'identity.json'); assert profile['checkpoint_ref'] == digest(checkpoint)
    identity_ref = digest(profile); template = TEMPLATE.read_text(); inputs = read(FROZEN/'replay_inputs_without_references.json'); jobs = []
    for i in sorted(selected):
        r = inputs[i]; hashes, pair = image_identity(r['evidence']); prompt = facts.prompt(r['program'], template)
        job = {'case': r['case'], 'program': r['program'], 'evidence': r['evidence'], 'image_hashes': hashes,
               'image_pair_ref': pair, 'prompt': prompt, 'prompt_ref': digest(prompt), 'schema': facts.schema(), 'identity_ref': identity_ref}
        job['request_ref'] = digest(job); jobs.append(job)
    assert len(jobs) == 224 and sum(i < 99 for i in selected) == 10
    protocol = {'version': 'local-task-preservation-review-cache-v96', 'cases': len(jobs), 'review_threshold': THRESHOLD,
                'selection': 'Fixed bound-evidence review region: no earlier v72/v87 rule fires and full-teacher top support<.8; also cache every genuine inner-source-excluded fitting view meeting .8. Support is a model cue, not truth confidence.',
                'fold_control': 'Each fitted controller may use only its own actual/OOS review membership. The cache union is an inference optimization; union membership or observations outside that fold region must not become predictor features or fitting rows.',
                'original_protection': 'Ten original inputs occur in at least one actual review region; collect them for actual99-case vetoes. Nonreview originals retain their existing decision without a new observation.',
                'semantics': 'Frozen v95 native-JSON observer with separate task, identity, collateral type, explicit preservation and goal relevance; no automatic collateral cap.',
                'cache': 'Exact compatible smoke requests may be copied with recorded source path/SHA. Failed compatible smoke slots remain failed; no resampling.',
                'bounds': {'workers': 1, 'max_fresh_local_inferences': len(jobs), 'max_new_tokens': len(jobs)*256, 'retries': 0},
                'scope': 'Unchanged915 fitting/development inputs. All276 primary cases remain the future scoring denominator, including cases outside review or with failed observations. No reserved-source access, new v75 response reads, uploads, API calls or fitting during collection.',
                'serving_changed': False, 'new_paid_calls': 0}
    out.mkdir(parents=True); save_json(out/'protocol.json', protocol); save_json(out/'identity.json', profile); save_json(out/'jobs.json', jobs); save_json(out/'memberships.json', memberships)
    files = [Path(__file__), ROOT/'run/calitree_local_observer_v94.py', TEMPLATE,
             ROOT/'critical/core/decision/local_rubric_evidence_v94.py', ROOT/'critical/lm_engine/local_qwen_v94.py', ROOT/'critical/lm_engine/local_qwen_grammar_v95.py']
    for p in files:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    save_json(out/'manifest.json', {'protocol_ref': digest(protocol), 'identity_ref': identity_ref, 'jobs_ref': digest(jobs),
              'memberships_ref': digest(memberships), 'code_sha256': {str(p): file_hash(p) for p in files},
              'source_hashes': source_hashes, 'checkpoint_identity_sha256': file_hash(DOWNLOAD)})
    (out/'run.log').write_text('Prepared224 local observations covering each fixed actual and genuine OOS review region. No inference/fitting/uploads.\n'); (out/'llm-histories.log').touch()
    print({'prepared_cases': len(jobs), 'original_cases': 10, 'max_fresh_tokens': len(jobs)*256}, flush=True)


def collect(out):
    manifest = read(out/'manifest.json'); profile = read(out/'identity.json'); checkpoint = read(DOWNLOAD); jobs = read(out/'jobs.json')
    assert digest(profile) == manifest['identity_ref'] and digest(jobs) == manifest['jobs_ref']
    assert digest(read(out/'memberships.json')) == manifest['memberships_ref']
    assert digest(checkpoint) == profile['checkpoint_ref'] and file_hash(DOWNLOAD) == manifest['checkpoint_identity_sha256']
    for package in ('torch', 'transformers', 'torchvision'):
        assert version(package) == profile[package]
    for package, expected in profile['extra_requirements'].items():
        assert version(package) == expected
    for file, sha in manifest['code_sha256'].items():
        assert file_hash(file) == sha
    for file, sha in manifest['source_hashes'].items():
        assert file_hash(file) == sha
    smoke_manifest = read(SMOKE/'manifest.json'); smoke_jobs = {r['case']: r for r in read(SMOKE/'jobs.json')}
    assert smoke_manifest['identity_ref'] == manifest['identity_ref']
    engine = LocalQwenGrammarEngine(checkpoint['destination'], checkpoint, history=LLMHistoryWriter(out/'llm-histories.log'), max_tokens=256)
    (out/'responses').mkdir(exist_ok=True); (out/'attempts').mkdir(exist_ok=True); errors = 0
    for job in jobs:
        case = job['case']; destination = out/'responses'/(case+'.json'); attempt = out/'attempts'/(case+'.json')
        assert digest({k: v for k, v in job.items() if k != 'request_ref'}) == job['request_ref']
        if destination.exists() or attempt.exists():
            continue
        prior = SMOKE/'responses'/(case+'.json')
        if prior.exists():
            assert smoke_jobs[case] == job
            result = read(prior); assert result['request_ref'] == job['request_ref']
            result.update(cache_origin=str(prior), cache_origin_sha256=file_hash(prior)); save_json(destination, result)
            continue
        hashes, pair = image_identity(job['evidence']); assert hashes == job['image_hashes'] and pair == job['image_pair_ref']
        with attempt.open('x') as f:
            json.dump({'case': case, 'request_ref': job['request_ref'], 'status': 'attempted'}, f)
        result = {'case': case, 'request_ref': job['request_ref'], 'observation': None, 'record': None, 'error': None}
        try:
            result['response'] = engine.generate(job['prompt'], [
                {'type': 'text', 'text': 'SOURCE image'}, {'type': 'image', 'path': job['evidence']['source_image']},
                {'type': 'text', 'text': 'EDITED image'}, {'type': 'image', 'path': job['evidence']['edited_image']}], job['schema'])
            if result['response']['finishReason'] == 'length':
                raise ValueError('Local observation reached its frozen token cap')
            value = facts.validate(result['response']['parsed']); record = facts.bind(job['program'], pair, job['identity_ref'], job['prompt_ref'], value)
            facts.project(job['program'], pair, job['identity_ref'], job['prompt_ref'], record); result.update(observation=value, record=record)
        except Exception as exc:
            result['error'] = type(exc).__name__+': '+str(exc)
        save_json(destination, result)
        errors = errors+1 if result['error'] else 0
        with (out/'run.log').open('a') as f:
            f.write(case+' '+('accepted' if result['record'] else result['error'])+'\n')
        print({'case': case, 'accepted': result['record'] is not None, 'saved': len(list((out/'responses').glob('*.json'))),
               'latency_s': result.get('response', {}).get('latencySeconds'), 'error': result['error']}, flush=True)
        if errors >= 3:
            break
    responses = [read(p) for p in (out/'responses').glob('*.json')]
    fresh = [r for r in responses if 'cache_origin' not in r]; tokens = sum(r.get('response', {}).get('completionTokens', 0) for r in fresh)
    assert len(list((out/'attempts').glob('*.json'))) <= len(jobs) and tokens <= len(jobs)*256
    result = {'cases': len(jobs), 'responses': len(responses), 'fresh_attempts': len(list((out/'attempts').glob('*.json'))),
              'reused': sum('cache_origin' in r for r in responses), 'accepted': sum(r['record'] is not None for r in responses),
              'fresh_completion_tokens': tokens, 'new_paid_calls': 0, 'reserved_sources_used': 0, 'fitting_performed': False,
              'complete': len(responses) == len(jobs), 'scope': 'Local review-region evidence cache; not an accuracy result or a deployed policy.'}
    save_json(out/'results.json', result); print(result, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--prepare', action='store_true'); p.add_argument('--collect', action='store_true'); a = p.parse_args()
    if a.prepare == a.collect:
        p.error('Choose exactly one of --prepare / --collect')
    (prepare if a.prepare else collect)(a.output_dir.resolve())
