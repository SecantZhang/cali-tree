"""Frozen local comparison of explicit schema and evidence-first facet prompts."""
import argparse
import fcntl
import json
from pathlib import Path
import shutil

from critical.core.decision import facet_policy_v150 as facets
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.lm_engine.local_mlx_large_v128 import LargeMLXEngine, MEMORY_LIMIT
from critical.lm_engine.local_qwen_v94 import file_hash
from critical.logging.llm_history import LLMHistoryWriter
from run.calitree_facet_probe_v150 import CHECKPOINT, ROOT, read

GUIDE = ROOT/'critical/core/prompts/templates/facet_policy_v150/field_guide_v153.txt'
ARMS = ('explicit_fields_first', 'explicit_evidence_first')


def prepare(prior, out):
    if out.exists():
        raise ValueError('Fresh explicit-facet probe required')
    assert read(prior/'results.json')['complete']
    profile = read(prior/'profile.json'); jobs = []
    for old in read(prior/'jobs.json'):
        if old['arm'] != 'facets':
            continue
        for arm in ARMS:
            keys = list(facets.schema()['properties'])
            if arm.endswith('evidence_first'):
                keys = ['evidence', 'material_gap']+list(facets.FIELDS)
            schema = facets.schema()
            schema['properties'] = {k: schema['properties'][k] for k in keys}; schema['required'] = keys
            guide = GUIDE.read_text().replace('{schema}', json.dumps(schema)).replace('{field_order}', ', '.join(keys))
            prompt = old['prompt']+'\n\n'+guide
            job = {k: v for k, v in old.items() if k not in ('request_ref', 'arm', 'prompt', 'prompt_ref', 'schema')}
            job.update(arm=arm, prompt=prompt, prompt_ref=digest(prompt), schema=schema)
            job['request_ref'] = digest(job); jobs.append(job)
    assert len(jobs) == 48
    protocol = {'version': 'explicit-facet-contract-and-order-v153', 'prior_probe': str(prior),
        'cases': 24, 'arms': list(ARMS), 'training_only': True,
        'hypothesis': 'v150 omitted the literal schema/value guide from its model prompt. Explicit value semantics and observation-before-state ordering may reduce categorical/evidence contradictions.',
        'adaptation': 'Designed after the v150/v151 fitting-only diagnostic and v152 grammar reachability audit. Same protected fitting sources; not an unseen validation or a repeated failed-slot retry.',
        'readouts': ['unchanged v150 strict semantic policy', 'cached v150 regular and facet controls'],
        'admission_rule': {'accepted_min': 23, 'correct_min': 18, 'each_grade_correct_min': 5,
                           'literal_gap_contradictions_max': 2},
        'budget': {'max_attempts': 48, 'max_emitted_tokens': 24576, 'max_tokens': 512, 'workers': 1, 'retries': 0},
        'stop': 'First backend error or three consecutive invalid/truncated outputs; no resumes or repairs.',
        'reserved_sources_used': 0, 'paid_requests': 0, 'serving_changed': False}
    sources = [Path(__file__), GUIDE, ROOT/'critical/core/decision/facet_policy_v150.py',
        ROOT/'critical/lm_engine/local_mlx_large_v128.py', ROOT/'critical/lm_engine/local_mlx_v118.py']
    out.mkdir(parents=True)
    for p in sources:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    save_json(out/'profile.json', profile); save_json(out/'protocol.json', protocol); save_json(out/'jobs.json', jobs)
    shutil.copyfile(prior/'references.json', out/'references.json')
    save_json(out/'manifest.json', {'profile_ref': digest(profile), 'protocol_ref': digest(protocol), 'jobs_ref': digest(jobs),
        'prior_manifest_sha256': file_hash(prior/'manifest.json'), 'checkpoint_sha256': file_hash(CHECKPOINT),
        'references_sha256': file_hash(out/'references.json'), 'code_sha256': {str(p): file_hash(p) for p in sources}})
    (out/'run.log').write_text('Prepared48 new local observations under two explicit facet contracts.\n')
    (out/'llm-histories.log').touch()
    print({'prepared': True, 'jobs': len(jobs), 'new_paid_calls': 0}, flush=True)


def collect(out):
    from importlib.metadata import version
    if (out/'results.json').exists() or (out/'attempts').exists():
        raise ValueError('No resume/retry of terminal or partially attempted profile')
    manifest = read(out/'manifest.json'); profile = read(out/'profile.json'); jobs = read(out/'jobs.json')
    assert digest(jobs) == manifest['jobs_ref'] and digest(profile) == manifest['profile_ref']
    assert digest(read(out/'protocol.json')) == manifest['protocol_ref']
    assert file_hash(CHECKPOINT) == manifest['checkpoint_sha256']
    for path, sha in manifest['code_sha256'].items():
        assert file_hash(path) == sha
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
            assert mx.get_peak_memory() <= MEMORY_LIMIT
            save_json(out/'preflight.json', {'passed': True, 'peak_memory_bytes': mx.get_peak_memory()})
        finally:
            mx.set_memory_limit(old)
        (out/'attempts').mkdir(); (out/'responses').mkdir(); consecutive = 0
        for job in jobs:
            key = job['case']+'-'+job['arm']
            assert digest({k: v for k, v in job.items() if k != 'request_ref'}) == job['request_ref']
            hashes, pair = image_identity(job['evidence']); assert hashes == job['image_hashes'] and pair == job['image_pair_ref']
            save_json(out/'attempts'/(key+'.json'), {'request_ref': job['request_ref'], 'status': 'attempted'})
            result = {'case': job['case'], 'arm': job['arm'], 'request_ref': job['request_ref'], 'accepted': False, 'error': None}
            try:
                response = engine.generate(job['prompt'], [{'type': 'text', 'text': 'SOURCE image'},
                    {'type': 'image', 'path': job['evidence']['source_image']}, {'type': 'text', 'text': 'EDITED image'},
                    {'type': 'image', 'path': job['evidence']['edited_image']}], job['schema'])
                result['response'] = response
                if response['finishReason'] != 'stop':
                    raise ValueError('Native output reached fixed token cap')
                value = facets.validate(json.loads(response['content']))
                result.update(accepted=True, value=value)
            except Exception as exc:
                result['error'] = type(exc).__name__+': '+str(exc)
            save_json(out/'responses'/(key+'.json'), result)
            consecutive = 0 if result['accepted'] else consecutive+1
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
        result = {'planned_jobs': 48, 'attempts': attempts, 'responses': len(rows), 'accepted': sum(r['accepted'] for r in rows),
            'emitted_tokens': emitted, 'reserved_tokens': reserved, 'complete': len(rows) == 48,
            'new_paid_calls': 0, 'reserved_sources_used': 0, 'serving_changed': False}
        save_json(out/'results.json', result); print(result, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--prior-probe', type=Path); modes = p.add_mutually_exclusive_group(required=True)
    modes.add_argument('--prepare', action='store_true'); modes.add_argument('--collect', action='store_true')
    a = p.parse_args()
    if a.prepare:
        if a.prior_probe is None:
            p.error('--prior-probe required for preparation')
        prepare(a.prior_probe.resolve(), a.output_dir.resolve())
    else:
        collect(a.output_dir.resolve())
