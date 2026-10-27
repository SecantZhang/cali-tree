"""Local training-only paired rubric reconstruction diagnostic; no API calls."""
import argparse
import fcntl
import json
from importlib.metadata import version
from pathlib import Path
import random
import shutil

from critical.core.decision import facet_policy_v150 as facets
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.lm_engine.local_mlx_large_v128 import LargeMLXEngine, MEMORY_LIMIT
from critical.lm_engine.local_qwen_v94 import file_hash
from critical.logging.llm_history import LLMHistoryWriter

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT/'logs/exps/261021-frozen-visual-policy-v69'
PRIOR = ROOT/'logs/exps/261023-bounded-large-probe-v131-r1'
CHECKPOINT = ROOT/'logs/exps/261023-large-mlx-download-v127-r1/identity.json'
TEMPLATE = ROOT/'critical/core/prompts/templates/facet_policy_v150/observe.txt'
REGULAR = ROOT/'critical/core/prompts/templates/task_coverage_v19/regular.txt'


def read(path):
    return json.loads(Path(path).read_text())


def prepare(out):
    if out.exists():
        raise ValueError('Fresh facet-policy probe required')
    checkpoint = read(CHECKPOINT); assert checkpoint['status'] == 'complete'
    all_inputs = read(FROZEN/'replay_inputs_without_references.json')
    references = read(FROZEN/'fitting_replay.json'); original = references[:99]
    metadata = {r['case']: r for r in read(ROOT/'logs/exps/261021-paired-vision-v63/inputs_without_labels.json')}
    raw = {r['case']: r for r in all_inputs}
    excluded = {metadata[r['case']]['source_group'] for r in read(PRIOR/'jobs.json')}
    primary_sources = {r['source_group'] for r in read(ROOT/'logs/exps/261023-verified-semantic-compression-v112-r2/predictions.json')}
    assert not {metadata[r['case']]['source_group'] for r in original} & primary_sources
    rng = random.Random(20261025); chosen = []
    for grade in range(3):
        candidates = sorted([r for r in original if r['reference'] == grade and metadata[r['case']]['source_group'] not in excluded], key=lambda r: r['case'])
        rng.shuffle(candidates); distinct = []; seen = set()
        for r in candidates:
            group = metadata[r['case']]['source_group']
            if group not in seen:
                seen.add(group); distinct.append(r)
        assert len(distinct) >= 8
        chosen.extend(distinct[:8])
    rng.shuffle(chosen)
    regular_schema = {'type': 'object', 'additionalProperties': False,
        'properties': {'rationale': {'type': 'string', 'minLength': 1, 'maxLength': 400},
                       'label': {'type': 'string', 'enum': ['no', 'partial', 'yes', 'unresolved']}},
        'required': ['rationale', 'label']}
    profile = {'model': checkpoint['model'], 'revision': checkpoint['revision'], 'checkpoint_ref': digest(checkpoint),
        'engine': LargeMLXEngine.name, 'max_tokens': 512, 'max_pixels': 256*32*32,
        'memory_limit_bytes': MEMORY_LIMIT, 'greedy': True, 'remote_calls': 0,
        'packages': {p: version(p) for p in ('mlx', 'mlx-vlm', 'transformers', 'torch', 'lm-format-enforcer')}}
    jobs = []
    for row in chosen:
        r = raw[row['case']]; hashes, pair = image_identity(r['evidence'])
        for arm in ('regular', 'facets'):
            prompt = ((REGULAR.read_text()+'\n\nExact edit instruction: '+json.dumps(r['program']['instruction'])) if arm == 'regular' else
                      TEMPLATE.read_text().replace('{instruction}', json.dumps(r['program']['instruction'])))
            job = {'case': r['case'], 'arm': arm, 'source_group': metadata[r['case']]['source_group'],
                'program_ref': r['program']['program_ref'], 'instruction': r['program']['instruction'],
                'evidence': r['evidence'], 'image_hashes': hashes, 'image_pair_ref': pair,
                'prompt': prompt, 'prompt_ref': digest(prompt), 'schema': regular_schema if arm == 'regular' else facets.schema(),
                'profile_ref': digest(profile)}
            job['request_ref'] = digest(job); jobs.append(job)
    protocol = {'version': 'reconstructed-facet-policy-probe-v150', 'cases': 24, 'arms': ['regular', 'facets'],
        'scope': 'Eight cases per grade from the protected original99, excluding all twelve previous diagnostic pixel sources. No276 evaluation or reserved sources. Rubric induction used only protected fit examples N017/N059/N065/N084; those sources are excluded.',
        'hypothesis': 'Separate newly realized requested subgoals from complete source-faithful operations. Wrong destination/count/duplication and partial global-style coverage can yield Partial when meaningful requested content newly appears.',
        'readouts': ['strict semantic tree', 'cautious some-progress/unknown-completion ablation'],
        'budget': {'max_attempts': 48, 'max_emitted_tokens': 24576, 'per_request_tokens': 512, 'workers': 1, 'retries': 0},
        'stop': 'First backend error or three consecutive invalid/truncated results; terminal runs are not resumed.',
        'new_paid_calls': 0, 'reserved_sources_used': 0, 'fitting': False, 'serving_changed': False,
        'limits': 'Paired training diagnostic excluding induction sources, not pipeline population accuracy or a completion claim.'}
    out.mkdir(parents=True); save_json(out/'profile.json', profile); save_json(out/'protocol.json', protocol)
    save_json(out/'jobs.json', jobs); save_json(out/'references.json', {r['case']: r['reference'] for r in chosen})
    sources = [Path(__file__), TEMPLATE, REGULAR, ROOT/'critical/core/decision/facet_policy_v150.py',
               ROOT/'critical/lm_engine/local_mlx_large_v128.py', ROOT/'critical/lm_engine/local_mlx_v118.py']
    for p in sources:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    save_json(out/'manifest.json', {'profile_ref': digest(profile), 'protocol_ref': digest(protocol), 'jobs_ref': digest(jobs),
        'checkpoint_sha256': file_hash(CHECKPOINT), 'code_sha256': {str(p): file_hash(p) for p in sources}})
    (out/'run.log').write_text('Prepared frozen24-case training-only paired facet-policy diagnostic.\n')
    (out/'llm-histories.log').touch()
    print({'prepared_cases': 24, 'local_attempts_cap': 48}, flush=True)


def collect(out):
    if (out/'results.json').exists():
        raise ValueError('Terminal probe cannot be resumed')
    manifest = read(out/'manifest.json'); profile = read(out/'profile.json'); jobs = read(out/'jobs.json')
    assert digest(profile) == manifest['profile_ref'] and digest(jobs) == manifest['jobs_ref']
    assert file_hash(CHECKPOINT) == manifest['checkpoint_sha256']
    for p, sha in manifest['code_sha256'].items():
        assert file_hash(p) == sha
    for package, v in profile['packages'].items():
        assert version(package) == v
    with Path('/tmp/calitree-local-gpu-experiment.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        engine = LargeMLXEngine(read(CHECKPOINT)['destination'], read(CHECKPOINT),
            history=LLMHistoryWriter(out/'llm-histories.log'), max_tokens=512, max_pixels=profile['max_pixels'])
        import mlx.core as mx
        old = mx.set_memory_limit(MEMORY_LIMIT)
        try:
            engine._load()
            if mx.get_peak_memory() > MEMORY_LIMIT:
                raise RuntimeError('Preflight memory exceeds the24GiB bound')
            save_json(out/'preflight.json', {'passed': True, 'active_memory_bytes': mx.get_active_memory(),
                'peak_memory_bytes': mx.get_peak_memory(), 'neural_calls': 0})
        finally:
            mx.set_memory_limit(old)
        (out/'attempts').mkdir(exist_ok=True); (out/'responses').mkdir(exist_ok=True)
        consecutive = 0
        for job in jobs:
            key = job['case']+'-'+job['arm']; destination = out/'responses'/(key+'.json'); attempt = out/'attempts'/(key+'.json')
            if destination.exists() or attempt.exists():
                raise ValueError('Partial execution requires a new protocol, not a resumed/retried slot')
            assert digest({k: v for k, v in job.items() if k != 'request_ref'}) == job['request_ref']
            hashes, pair = image_identity(job['evidence']); assert hashes == job['image_hashes'] and pair == job['image_pair_ref']
            with attempt.open('x') as f:
                json.dump({'request_ref': job['request_ref'], 'status': 'attempted'}, f)
            result = {'case': job['case'], 'arm': job['arm'], 'request_ref': job['request_ref'], 'accepted': False, 'error': None}
            try:
                response = engine.generate(job['prompt'], [{'type': 'text', 'text': 'SOURCE image'},
                    {'type': 'image', 'path': job['evidence']['source_image']}, {'type': 'text', 'text': 'EDITED image'},
                    {'type': 'image', 'path': job['evidence']['edited_image']}], job['schema'])
                result['response'] = response
                if response['finishReason'] != 'stop':
                    raise ValueError('Native output reached its fixed token cap')
                value = json.loads(response['content'])
                if job['arm'] == 'facets':
                    facets.validate(value)
                elif (set(value) != {'rationale', 'label'} or value['label'] not in ('no', 'partial', 'yes', 'unresolved') or
                      not isinstance(value['rationale'], str) or not 1 <= len(value['rationale']) <= 400):
                    raise ValueError('Invalid regular control judgment')
                result.update(accepted=True, value=value)
            except Exception as exc:
                result['error'] = type(exc).__name__+': '+str(exc)
            save_json(destination, result); consecutive = 0 if result['accepted'] else consecutive+1
            with (out/'run.log').open('a') as log:
                log.write(key+' '+('accepted' if result['accepted'] else result['error'])+'\n')
            print({'case': job['case'], 'arm': job['arm'], 'accepted': result['accepted'],
                'tokens': result.get('response', {}).get('completionTokens'), 'error': result['error']}, flush=True)
            if consecutive >= 3 or (result['error'] or '').startswith('RuntimeError:'):
                break
        rows = [read(p) for p in (out/'responses').glob('*.json')]
        attempts = len(list((out/'attempts').glob('*.json')))
        emitted = sum(r.get('response', {}).get('completionTokens', 0) for r in rows)
        reserved = sum('response' not in r for r in rows)*512
        assert attempts <= 48 and emitted+reserved <= 24576
        result = {'planned_cases': 24, 'planned_jobs': 48, 'attempts': attempts, 'responses': len(rows),
            'accepted': sum(r['accepted'] for r in rows), 'emitted_tokens': emitted, 'reserved_tokens': reserved,
            'complete': len(rows) == 48, 'new_paid_calls': 0, 'serving_changed': False}
        save_json(out/'results.json', result); print(result, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    mode = p.add_mutually_exclusive_group(required=True); mode.add_argument('--prepare', action='store_true'); mode.add_argument('--collect', action='store_true')
    a = p.parse_args(); (prepare if a.prepare else collect)(a.output_dir.resolve())
