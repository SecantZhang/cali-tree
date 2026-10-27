"""Prepare/collect a bounded local task-versus-preservation observation probe."""
import argparse
from importlib.metadata import version
import json
from pathlib import Path
import shutil

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision import local_rubric_evidence_v94 as facts
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.lm_engine.local_qwen_v94 import LocalQwenEngine, file_hash
from critical.logging.llm_history import LLMHistoryWriter

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT/'logs/exps/261021-frozen-visual-policy-v69'
TEMPLATE = ROOT/'critical/core/prompts/templates/local_rubric_v94/observe.txt'
DOWNLOAD = ROOT/'logs/exps/261023-local-vlm-download-v94-r1/identity.json'


def read(path):
    return json.loads(Path(path).read_text())


def prepare(out, *, engine_type=LocalQwenEngine, extra_profile=None, extra_sources=()):
    if out.exists():
        raise ValueError('Fresh local probe directory required')
    checkpoint = read(DOWNLOAD); assert checkpoint['status'] == 'complete'
    raw = read(FROZEN/'replay_inputs_without_references.json')[:99]
    references = {r['case']: r['reference'] for r in read(FROZEN/'fitting_replay.json')}
    chosen = []
    for label in range(3):
        for cached_error in (False, True):
            pool = [r for r in raw if references[r['case']] == label and
                    (r['judgment']['label'] != ('no', 'partial', 'yes')[label]) == cached_error]
            pool.sort(key=lambda r: digest(['local-v94-smoke', r['case']]))
            assert len(pool) >= 2
            chosen += pool[:2]
    chosen.sort(key=lambda r: r['case']); assert len(chosen) == 12
    identity = {'checkpoint_ref': digest(checkpoint), 'model': checkpoint['model'], 'revision': checkpoint['revision'],
                'engine': engine_type.name, 'device': 'mps', 'dtype': 'float16', 'attention': 'sdpa',
                'max_new_tokens': 256, 'max_pixels_per_image': 256*32*32, 'min_pixels_per_image': 64*32*32,
                'do_sample': False, 'transformers': '4.57.6', 'torch': '2.9.0', 'torchvision': '0.24.0',
                'image_processor': 'torchvision_fast', 'contract_ref': facts.CONTRACT_REF}
    identity.update(extra_profile or {})
    identity_ref = digest(identity); template = TEMPLATE.read_text(); jobs = []
    for r in chosen:
        hashes, pair = image_identity(r['evidence']); prompt = facts.prompt(r['program'], template)
        job = {'case': r['case'], 'program': r['program'], 'evidence': r['evidence'], 'image_hashes': hashes,
               'image_pair_ref': pair, 'prompt': prompt, 'prompt_ref': digest(prompt), 'schema': facts.schema(), 'identity_ref': identity_ref}
        job['request_ref'] = digest(job); jobs.append(job)
    protocol = {'version': 'local-observer-smoke-v94', 'cases': 12, 'case_scope': 'Original99 training only; four per reference class, half cached regular errors. Balanced diagnostic, not population accuracy.',
                'sampling': 'Reference/error status used only for training-diagnostic sampling, never sent to the observer. Fixed digest ordering.',
                'semantics': 'Observe target correspondence, endpoint, directional progress, visible collateral type, instruction-explicit preservation, collateral goal relevance and essential identity separately; no satisfaction grade or automatic penalty.',
                'bounds': {'max_local_inferences': 12, 'max_new_tokens': 3072, 'workers': 1, 'retries': 0},
                'exclusions': 'No fitting, reserved images, new v75 response reads, compiler/observer API calls or uploads. All inference is local with network disabled.',
                'limits': 'A local model claim is not a physical certificate or a verified accuracy improvement. Failures remain failed; no response repair or resampling.',
                'new_paid_calls': 0, 'reserved_sources_used': 0, 'serving_changed': False}
    out.mkdir(parents=True); save_json(out/'protocol.json', protocol); save_json(out/'identity.json', identity); save_json(out/'jobs.json', jobs)
    save_json(out/'references.json', {r['case']: references[r['case']] for r in chosen})
    files = [Path(__file__), TEMPLATE, ROOT/'critical/lm_engine/local_qwen_v94.py', ROOT/'critical/core/decision/local_rubric_evidence_v94.py', *extra_sources]
    for file in files:
        destination = out/'source_snapshot'/file.relative_to(ROOT); destination.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(file, destination)
    save_json(out/'manifest.json', {'protocol_ref': digest(protocol), 'identity_ref': identity_ref, 'jobs_ref': digest(jobs),
                                  'code_sha256': {str(p): file_hash(p) for p in files}, 'checkpoint_identity_sha256': file_hash(DOWNLOAD)})
    (out/'run.log').write_text('Prepared twelve original-training local observations; zero inference or uploads.\n')
    (out/'llm-histories.log').touch()
    print({'prepared_cases': [r['case'] for r in chosen], 'model': identity['model'], 'identity_ref': identity_ref}, flush=True)


def collect(out, *, engine_type=LocalQwenEngine):
    manifest = read(out/'manifest.json'); profile = read(out/'identity.json'); checkpoint = read(DOWNLOAD); jobs = read(out/'jobs.json')
    assert digest(profile) == manifest['identity_ref'] and digest(jobs) == manifest['jobs_ref'] and len(jobs) == 12
    assert file_hash(DOWNLOAD) == manifest['checkpoint_identity_sha256'] and digest(checkpoint) == profile['checkpoint_ref']
    assert all(version(package) == profile[package] for package in ('torch', 'transformers', 'torchvision'))
    assert profile['engine'] == engine_type.name
    assert all(version(package) == expected for package, expected in profile.get('extra_requirements', {}).items())
    for file, sha in manifest['code_sha256'].items():
        assert file_hash(file) == sha
    engine = engine_type(checkpoint['destination'], checkpoint, history=LLMHistoryWriter(out/'llm-histories.log'), max_tokens=256)
    (out/'responses').mkdir(exist_ok=True); (out/'attempts').mkdir(exist_ok=True)
    for job in jobs:
        case = job['case']; response = out/'responses'/(case+'.json'); attempt = out/'attempts'/(case+'.json')
        assert digest({k: v for k, v in job.items() if k != 'request_ref'}) == job['request_ref']
        if response.exists() or attempt.exists():
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
            value = facts.validate(result['response']['parsed'])
            record = facts.bind(job['program'], pair, job['identity_ref'], job['prompt_ref'], value)
            facts.project(job['program'], pair, job['identity_ref'], job['prompt_ref'], record)
            result.update(observation=value, record=record)
        except Exception as exc:
            result['error'] = type(exc).__name__+': '+str(exc)
        save_json(response, result)
        with (out/'run.log').open('a') as f:
            f.write(case+' '+('accepted' if result['record'] else result['error'])+'\n')
        print({'case': case, 'accepted': result['record'] is not None, 'error': result['error'],
               'latency_s': result.get('response', {}).get('latencySeconds')}, flush=True)
        # Stop a broken runtime without automatically reattempting failed slots.
        recent = sorted((out/'responses').glob('*.json'), key=lambda p: p.stat().st_mtime)[-3:]
        if len(recent) == 3 and all(read(p)['error'] for p in recent):
            break
    observed = [read(out/'responses'/(job['case']+'.json')) for job in jobs if (out/'responses'/(job['case']+'.json')).exists()]
    tokens = sum(r.get('response', {}).get('completionTokens', 0) for r in observed)
    assert len(list((out/'attempts').glob('*.json'))) <= 12 and tokens <= 3072
    save_json(out/'results.json', {'cases': 12, 'attempted': len(list((out/'attempts').glob('*.json'))), 'responses': len(observed),
                  'accepted': sum(r['record'] is not None for r in observed), 'completion_tokens': tokens,
                  'new_paid_calls': 0, 'reserved_sources_used': 0, 'scope': 'Local observation smoke only; no fitting or pipeline accuracy result.'})
    print(read(out/'results.json'), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--prepare', action='store_true'); p.add_argument('--collect', action='store_true'); a = p.parse_args()
    if a.prepare == a.collect:
        p.error('Choose exactly one of --prepare / --collect')
    (prepare if a.prepare else collect)(a.output_dir.resolve())
