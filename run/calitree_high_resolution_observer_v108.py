"""Frozen higher-resolution local evidence view over the existing224 inputs.

This is a new decoding/image profile, not a repair of earlier failures. Its
responses remain separate and no previously collected observation is replaced.
"""
import argparse
from copy import deepcopy
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
from run.calitree_local_observer_v94 import ROOT, DOWNLOAD, read

MAX_PIXELS = 1024*32*32
MAX_TOKENS = 512


def prepare(previous, out):
    if out.exists():
        raise ValueError('Fresh high-resolution cache required')
    old = read(previous/'manifest.json'); jobs = deepcopy(read(previous/'jobs.json')); profile = deepcopy(read(previous/'identity.json'))
    assert len(jobs) == 224 and digest(jobs) == old['jobs_ref'] and digest(profile) == old['identity_ref']
    assert read(previous/'results.json')['complete']
    profile.update(max_pixels_per_image=MAX_PIXELS, max_new_tokens=MAX_TOKENS,
                   prior_probe='New v108 high-resolution512-output profile; all v96 successes/failures retained unchanged. No response repair or retry.')
    identity_ref = digest(profile)
    for job in jobs:
        job.pop('request_ref'); job['identity_ref'] = identity_ref; job['request_ref'] = digest(job)
    memberships = read(previous/'memberships.json'); assert digest(memberships) == old['memberships_ref']
    protocol = {'version': 'high-resolution-local-review-cache-v108', 'cases': 224, 'review_threshold': .8,
        'selection': 'Exactly the frozen v96 actual/OOS review union and fold memberships. No label/error-dependent selection or new sources.',
        'fold_control': 'Each downstream fold uses only its own actual/OOS mask. Other-fold union membership cannot become a feature or fitting selector.',
        'change': 'Same pinned Qwen3-VL8B checkpoint, seven-field task/preservation contract, prompt and greedy constrained decoding. Increase image budget from256 to1024 visual tokens/image and output allowance256 to512, in a separate cache.',
        'bounds': {'workers': 1, 'max_fresh_local_inferences': 224, 'max_new_tokens': 224*MAX_TOKENS, 'retries': 0},
        'failures': 'A durable attempted slot is never automatically repeated. Stop after three consecutive failures; all failures remain unavailable and in the full276 denominator.',
        'scope': 'Local computation over existing fitting/development images only. No API, uploads, reserved sources, prompt optimization or fitting during collection.',
        'previous_manifest_sha256': file_hash(previous/'manifest.json'), 'serving_changed': False, 'new_paid_calls': 0}
    out.mkdir(parents=True); save_json(out/'protocol.json', protocol); save_json(out/'identity.json', profile); save_json(out/'jobs.json', jobs); save_json(out/'memberships.json', memberships)
    files = [Path(__file__), ROOT/'run/calitree_local_observer_v94.py', ROOT/'critical/core/decision/local_rubric_evidence_v94.py', ROOT/'critical/lm_engine/local_qwen_v94.py', ROOT/'critical/lm_engine/local_qwen_grammar_v95.py']
    for p in files:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    template = Path('critical/core/prompts/templates/local_rubric_v94/observe.txt'); dest = out/'source_snapshot'/template; dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(previous/'source_snapshot'/template, dest); files.append(ROOT/template)
    assert file_hash(dest) == file_hash(ROOT/template)
    source_hashes = {**old['source_hashes'], str(previous/'manifest.json'): file_hash(previous/'manifest.json'), str(previous/'jobs.json'): file_hash(previous/'jobs.json'),
                     str(previous/'memberships.json'): file_hash(previous/'memberships.json'), str(previous/'identity.json'): file_hash(previous/'identity.json')}
    save_json(out/'manifest.json', {'protocol_ref': digest(protocol), 'identity_ref': identity_ref, 'jobs_ref': digest(jobs), 'memberships_ref': digest(memberships),
        'code_sha256': {str(p): file_hash(p) for p in files}, 'source_hashes': source_hashes, 'checkpoint_identity_sha256': file_hash(DOWNLOAD)})
    (out/'run.log').write_text('Frozen224-case high-resolution observation profile prepared; no inference or fitting.\n'); (out/'llm-histories.log').touch()
    print({'prepared': len(jobs), 'max_pixels_per_image': MAX_PIXELS, 'max_fresh_tokens': 224*MAX_TOKENS, 'new_api_calls': 0}, flush=True)


def collect(out):
    manifest = read(out/'manifest.json'); profile = read(out/'identity.json'); checkpoint = read(DOWNLOAD); jobs = read(out/'jobs.json'); protocol = read(out/'protocol.json')
    assert digest(profile) == manifest['identity_ref'] and digest(jobs) == manifest['jobs_ref'] and digest(protocol) == manifest['protocol_ref']
    assert profile['max_pixels_per_image'] == MAX_PIXELS and profile['max_new_tokens'] == MAX_TOKENS
    assert digest(read(out/'memberships.json')) == manifest['memberships_ref'] and digest(checkpoint) == profile['checkpoint_ref'] and file_hash(DOWNLOAD) == manifest['checkpoint_identity_sha256']
    for package in ('torch', 'transformers', 'torchvision'):
        assert version(package) == profile[package]
    for package, expected in profile['extra_requirements'].items():
        assert version(package) == expected
    for file, sha in {**manifest['code_sha256'], **manifest['source_hashes']}.items():
        assert file_hash(file) == sha, file
    engine = LocalQwenGrammarEngine(checkpoint['destination'], checkpoint, history=LLMHistoryWriter(out/'llm-histories.log'), max_tokens=MAX_TOKENS, max_pixels=MAX_PIXELS)
    (out/'responses').mkdir(exist_ok=True); (out/'attempts').mkdir(exist_ok=True); errors = 0
    for job in jobs:
        case = job['case']; destination = out/'responses'/(case+'.json'); attempt = out/'attempts'/(case+'.json')
        assert digest({k: v for k, v in job.items() if k != 'request_ref'}) == job['request_ref']
        if destination.exists() or attempt.exists():
            continue
        hashes, pair = image_identity(job['evidence']); assert hashes == job['image_hashes'] and pair == job['image_pair_ref']
        with attempt.open('x') as f:
            json.dump({'case': case, 'request_ref': job['request_ref'], 'status': 'attempted'}, f)
        result = {'case': case, 'request_ref': job['request_ref'], 'observation': None, 'record': None, 'error': None}
        try:
            result['response'] = engine.generate(job['prompt'], [
                {'type': 'text', 'text': 'SOURCE image'}, {'type': 'image', 'path': job['evidence']['source_image']},
                {'type': 'text', 'text': 'EDITED image'}, {'type': 'image', 'path': job['evidence']['edited_image']}], job['schema'])
            if result['response']['finishReason'] != 'stop':
                raise ValueError('High-resolution observation reached its frozen token cap')
            value = facts.validate(result['response']['parsed']); record = facts.bind(job['program'], pair, job['identity_ref'], job['prompt_ref'], value)
            facts.project(job['program'], pair, job['identity_ref'], job['prompt_ref'], record); result.update(observation=value, record=record)
        except Exception as exc:
            result['error'] = type(exc).__name__+': '+str(exc)
        save_json(destination, result); errors = errors+1 if result['error'] else 0
        with (out/'run.log').open('a') as f:
            f.write(case+' '+('accepted' if result['record'] else result['error'])+'\n')
        print({'case': case, 'accepted': result['record'] is not None, 'saved': len(list((out/'responses').glob('*.json'))), 'latency_s': result.get('response', {}).get('latencySeconds'), 'error': result['error']}, flush=True)
        if errors >= 3:
            break
    responses = [read(p) for p in (out/'responses').glob('*.json')]; tokens = sum(r.get('response', {}).get('completionTokens', 0) for r in responses)
    attempted = len(list((out/'attempts').glob('*.json'))); missing_native = sum(r.get('response') is None for r in responses); reservations = (attempted-len(responses)+missing_native)*MAX_TOKENS
    assert attempted <=224 and tokens+reservations <=224*MAX_TOKENS
    result = {'cases':224, 'responses':len(responses), 'fresh_attempts':attempted, 'reused':0, 'accepted':sum(r['record'] is not None for r in responses),
        'fresh_completion_tokens':tokens, 'reserved_completion_tokens':reservations, 'new_paid_calls':0, 'reserved_sources_used':0, 'fitting_performed':False,
        'complete':len(responses)==224, 'scope':'New local high-resolution evidence profile; not a policy accuracy result.'}
    save_json(out/'results.json', result); print(result, flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--previous-cache',type=Path); p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--prepare',action='store_true'); p.add_argument('--collect',action='store_true'); a=p.parse_args()
    if a.prepare == a.collect or (a.prepare and a.previous_cache is None):
        p.error('Choose --prepare with --previous-cache, or --collect')
    prepare(a.previous_cache.resolve(),a.output_dir.resolve()) if a.prepare else collect(a.output_dir.resolve())
