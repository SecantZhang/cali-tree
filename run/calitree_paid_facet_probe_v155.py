"""Prepare or explicitly authorize a bounded training-only Luna/Sol facet probe."""
import argparse
from pathlib import Path
import json
import shutil

from PIL import Image

from critical.core.decision import facet_policy_v150 as facets
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.lm_engine.local_qwen_v94 import file_hash
from critical.lm_engine.provider_api import chat_request
from run.calitree_facet_probe_v150 import ROOT, FROZEN, PRIOR, read
from run.verify_calitree_facet_probe_v151 import classification_metrics, scalar_grade

MODELS = {
    'luna': {'model': 'gpt-6-luna', 'provider': 'openai', 'temperature': 0., 'reasoning_effort': 'none'},
    'sol': {'model': 'gpt-6.1-sol', 'provider': 'openai', 'temperature': None, 'reasoning_effort': 'low'},
}
CAPS = {'luna': 2048, 'sol': 8192}
MAX_CALLS = 48
MAX_TOKENS = 24*sum(CAPS.values())
ENDPOINT = 'https://api.openai.com/v1'


def prepare(prior, out):
    if out.exists():
        raise ValueError('Fresh paid facet protocol required')
    selected = [j for j in read(prior/'jobs.json') if j['arm'] == 'explicit_evidence_first']
    assert len(selected) == 24
    references = read(prior/'references.json')
    assert len(references) == 24 and [list(references.values()).count(k) for k in range(3)] == [8, 8, 8]
    jobs = []
    for old in selected:
        for arm, identity in MODELS.items():
            job = {k: old[k] for k in ('case', 'source_group', 'instruction', 'program_ref', 'evidence', 'image_hashes', 'image_pair_ref', 'prompt', 'schema')}
            job.update(arm=arm, identity=identity, max_tokens=CAPS[arm], wire_prompt_ref=digest(old['prompt']+'\nINPUT_JSON: {}'))
            job['request_ref'] = digest(job); jobs.append(job)
    protocol = {'version': 'explicit-facet-observer-comparison-v155', 'prior_profile': str(prior),
        'cases': 24, 'arms': MODELS, 'max_requests': MAX_CALLS, 'max_completion_tokens': MAX_TOKENS,
        'per_request_completion_caps': CAPS, 'endpoint': ENDPOINT,
        'reasoning': 'Luna none at temperature0; Sol low with temperature omitted. Reasoning tokens count within the completion allowance.',
        'scope': 'Adapted training-only diagnostic on the same24 protected original fitting sources. No276 held-source evaluation or reserved80 sources; no compilation, fitting, retries or deployment.',
        'hypothesis': 'An explicit semantic facet contract may recover meaningful partial progress while stronger visual reasoning separates full completion from material gaps.',
        'readout': 'Unchanged v150 strict executable tree. Missing/invalid/unresolved outputs remain incorrect over all24. Literal gap contradictions and per-class recall reported.',
        'collection_admission': {'accepted_min': 23, 'correct_min': 18, 'each_grade_correct_min': 5, 'literal_gap_contradictions_max': 2},
        'failure_policy': 'Durable single-attempt slots, no transport retries or model substitution. Provider rejection or three consecutive transport failures stop collection. Failed slots are never repaired or resampled.',
        'cost': {'verified_date': '2026-10-25', 'input_usd_per_million': {'luna': .1, 'sol': 2.},
            'output_usd_per_million': {'luna': .5, 'sol': 10.},
            'full_output_allowance_usd': 24*(CAPS['luna']*.5+CAPS['sol']*10)/1e6,
            'expected_usd_range': [.5, 1.5],
            'expected_assumptions': 'Estimated ~4000-8000 total input tokens/request including images and ~1000-4000 Sol completion tokens. An estimate, not a total-charge cap; the full output allowance is $1.990656 plus input charges. Official fetched vision guide does not establish a patch multiplier for these exact aliases.',
            'sources': ['https://developers.openai.com/api/docs/models/gpt-6-luna', 'https://developers.openai.com/api/docs/models/gpt-6.1-sol', 'https://developers.openai.com/api/docs/guides/images-vision']},
        'authorization': 'Explicit new paid-call and upload approval for this frozen manifest is required before --live.',
        'serving_changed': False, 'reserved_sources_used': 0}
    images = {}
    for job in selected:
        for field, path in job['evidence'].items():
            with Image.open(path) as image:
                dimensions = list(image.size)
            images[path] = {'sha256': file_hash(path), 'dimensions': dimensions, 'role': field}
    inventory = {'destination': ENDPOINT, 'image_files': images, 'unique_images': len(images),
        'image_upload_occurrences': len(jobs)*2,
        'text': 'Edit instructions, generic rubric/value guide and its schema; no human reference grades or example labels.',
        'image_resize': 'Original cached image bytes. Provider auto preprocessing; no derived image uploads.'}
    files = [Path(__file__), ROOT/'critical/core/decision/facet_policy_v150.py', ROOT/'critical/core/decision/calls.py',
             ROOT/'critical/lm_engine/provider_api.py', ROOT/'critical/lm_engine/openai_compat.py', ROOT/'critical/lm_engine/lm_template/base.py']
    out.mkdir(parents=True)
    for path in files:
        dest = out/'source_snapshot'/path.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, dest)
    save_json(out/'jobs.json', jobs); save_json(out/'protocol.json', protocol); save_json(out/'upload_inventory.json', inventory)
    save_json(out/'references_training_only.json', references)
    save_json(out/'manifest.json', {'protocol_ref': digest(protocol), 'jobs_ref': digest(jobs),
        'inventory_ref': digest(inventory), 'references_sha256': file_hash(out/'references_training_only.json'),
        'prior_manifest_sha256': file_hash(prior/'manifest.json'), 'code_sha256': {str(p): file_hash(p) for p in files}})
    (out/'run.log').write_text('Prepared offline48-request training-only facet comparison. No authorization or API requests.\n')
    (out/'llm-histories.log').touch()
    verified = verify(out)
    print({'prepared': True, 'verified': verified['passed'], 'cases': 24, 'unique_images': len(images),
        'max_requests': MAX_CALLS, 'max_completion_tokens': MAX_TOKENS,
        'full_output_allowance_usd': protocol['cost']['full_output_allowance_usd']}, flush=True)


def verify(out):
    protocol, jobs, manifest = read(out/'protocol.json'), read(out/'jobs.json'), read(out/'manifest.json')
    assert digest(protocol) == manifest['protocol_ref'] and digest(jobs) == manifest['jobs_ref']
    assert digest(read(out/'upload_inventory.json')) == manifest['inventory_ref']
    assert file_hash(out/'references_training_only.json') == manifest['references_sha256']
    assert protocol['arms'] == MODELS and protocol['max_requests'] == MAX_CALLS and protocol['max_completion_tokens'] == MAX_TOKENS
    for path, sha in manifest['code_sha256'].items():
        assert file_hash(path) == file_hash(out/'source_snapshot'/Path(path).relative_to(ROOT)) == sha
    prior = Path(protocol['prior_profile'])
    assert file_hash(prior/'manifest.json') == manifest['prior_manifest_sha256']
    originals = {r['case']: r for r in read(FROZEN/'fitting_replay.json')[:99]}
    raw = {r['case']: r for r in read(FROZEN/'replay_inputs_without_references.json')}
    meta = {r['case']: r for r in read(ROOT/'logs/exps/261021-paired-vision-v63/inputs_without_labels.json')}
    excluded = {meta[j['case']]['source_group'] for j in read(PRIOR/'jobs.json')}
    primary = {r['source_group'] for r in read(ROOT/'logs/exps/261023-verified-semantic-compression-v112-r2/predictions.json')}
    reserved = {r['source_group'] for r in read(ROOT/'logs/exps/261020-validation-reservation-v39/inputs_without_labels.json')}
    references = read(out/'references_training_only.json')
    assert references == read(prior/'references.json') and len(jobs) == 48
    assert [list(references.values()).count(k) for k in range(3)] == [8, 8, 8]
    old = {j['case']: j for j in read(prior/'jobs.json') if j['arm'] == 'explicit_evidence_first'}
    for job in jobs:
        case, arm = job['case'], job['arm']
        assert references[case] == originals[case]['reference']
        assert meta[case]['source_group'] not in excluded|primary|reserved
        assert digest({k: v for k, v in job.items() if k != 'request_ref'}) == job['request_ref']
        for key in ('source_group', 'instruction', 'program_ref', 'evidence', 'image_hashes', 'image_pair_ref', 'prompt', 'schema'):
            assert job[key] == old[case][key]
        assert job['instruction'] == raw[case]['program']['instruction'] and job['program_ref'] == raw[case]['program']['program_ref']
        assert job['identity'] == MODELS[arm] and job['max_tokens'] == CAPS[arm]
        assert digest(job['prompt']+'\nINPUT_JSON: {}') == job['wire_prompt_ref']
        assert image_identity(job['evidence']) == (job['image_hashes'], job['image_pair_ref'])
        options = {'reasoning_effort': 'low'} if arm == 'sol' else {}
        # Compile wire settings with a public fixture token. No credential load,
        # network request or image encoding occurs during preparation/verification.
        url, payload, _, dialect = chat_request(ENDPOINT, 'public-fixture', MODELS[arm]['model'], [], CAPS[arm], MODELS[arm]['temperature'], 'openai', {'type': 'json_schema', 'json_schema': {'name': 'facet_probe', 'strict': True, 'schema': job['schema']}}, **options)
        assert url == ENDPOINT+'/chat/completions' and dialect == 'openai'
        assert payload['max_completion_tokens'] == CAPS[arm] and payload['reasoning_effort'] == MODELS[arm]['reasoning_effort']
        if arm == 'sol':
            assert 'temperature' not in payload
    report = {'passed': True, 'jobs': len(jobs), 'cases': len(references), 'primary_and_reserved_sources': 0,
        'max_requests': MAX_CALLS, 'max_completion_tokens': MAX_TOKENS, 'new_paid_calls': 0}
    save_json(out/'preflight_verification.json', report)
    return report


def collect(out, *, live=False):
    if not live or not (out/'authorization.json').exists():
        raise ValueError('Explicit new paid-call/upload authorization and --live required')
    verify(out)
    authorization = read(out/'authorization.json')
    assert authorization.get('approved') is True and authorization.get('upload_approved') is True
    assert authorization['manifest_sha256'] == file_hash(out/'manifest.json')
    assert authorization['max_requests'] == MAX_CALLS and authorization['max_completion_tokens'] == MAX_TOKENS
    from critical import config
    from critical.core.decision.calls import DurableCalls, ProviderStopped, BudgetExhausted
    from critical.lm_engine import get_engine, load_creds, require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True)
    config.PROJECT_ROOT = Path('/Users/zzhang/Documents/Projects/Adobe/calitree-mlsys')
    config.CREDENTIALS_FILE = config.PROJECT_ROOT/'.env'
    creds = load_creds(provider='openai', engine='gpt')
    if creds.endpoints != [ENDPOINT]:
        raise ValueError('Exact official endpoint required; no mirrors/substitution')
    history = LLMHistoryWriter(out/'llm-histories.log')
    def factory(arm):
        def create(cap):
            options = {'reasoning_effort': 'low'} if arm == 'sol' else {}
            return get_engine('gpt', creds=creds, model=MODELS[arm]['model'], temperature=MODELS[arm]['temperature'],
                max_tokens=cap, timeout=240, max_http_attempts=1, history=history, **options)
        return create
    calls = DurableCalls(out/'ledger', factory('sol'), identity=MODELS['sol'], max_calls=MAX_CALLS,
        max_completion_tokens=MAX_TOKENS, scope_limits={'search': 2, 'final': 0},
        routes={'luna': {'identity': MODELS['luna'], 'engine_factory': factory('luna')}})
    for job in read(out/'jobs.json'):
        path = out/'responses'/(job['case']+'-'+job['arm']+'.json')
        if path.exists():
            continue
        result = {'case': job['case'], 'arm': job['arm'], 'request_ref': job['request_ref'], 'accepted': False, 'error': None}
        try:
            media = [{'type': 'text', 'text': 'SOURCE image'}, {'type': 'image', 'path': job['evidence']['source_image']},
                     {'type': 'text', 'text': 'EDITED image'}, {'type': 'image', 'path': job['evidence']['edited_image']}]
            value, ref = calls.call('explicit_semantic_facets_v155', {}, job['schema'], template=job['prompt'], media=media,
                slot=job['arm'], case_id=job['case'], max_tokens=job['max_tokens'], route='luna' if job['arm'] == 'luna' else None)
            result.update(value=facets.validate(value), execution_ref=ref, accepted=True)
        except (ProviderStopped, BudgetExhausted) as exc:
            result['error'] = type(exc).__name__+': '+str(exc); save_json(path, result)
            (out/'run.log').open('a').write('Stopped: '+result['error']+'\n')
            raise
        except (ValueError, RuntimeError, TypeError, KeyError) as exc:
            result['error'] = type(exc).__name__+': '+str(exc)
        save_json(path, result)
        print({'case': job['case'], 'arm': job['arm'], 'accepted': result['accepted'], 'error': result['error']}, flush=True)
    report(out)


def report(out):
    verify(out); refs = read(out/'references_training_only.json'); rows = []; accepted = {a: 0 for a in MODELS}
    gaps = {a: 0 for a in MODELS}
    for case, reference in refs.items():
        row = {'case': case, 'reference': reference}
        for arm in MODELS:
            path = out/'responses'/(case+'-'+arm+'.json'); result = read(path) if path.exists() else None
            v = facets.validate(result['value']) if result and result['accepted'] else None
            pred = scalar_grade(v) if v else None; row[arm] = pred if pred is not None else -1
            if v:
                accepted[arm] += 1
                assert pred == facets.decide(v)
                gap = (v['all_material_facets'] == 'no' or v['operation_fidelity'] == 'unfaithful' or
                       v['source_entity_fidelity'] == 'material_unrequested_change' or v['scope_coverage'] == 'partial')
                gaps[arm] += int(gap and v['material_gap'].strip().lower().rstrip('.') == 'none')
        rows.append(row)
    metrics = {a: classification_metrics(rows, a) for a in MODELS}; rule = read(out/'protocol.json')['collection_admission']
    admission = {a: accepted[a] >= rule['accepted_min'] and metrics[a]['correct'] >= rule['correct_min'] and
        min(v['correct'] for v in metrics[a]['per_class'].values()) >= rule['each_grade_correct_min'] and
        gaps[a] <= rule['literal_gap_contradictions_max'] for a in MODELS}
    result = {'cases': 24, 'metrics': metrics, 'accepted': accepted, 'literal_gap_contradictions': gaps,
        'larger_collection_admission': admission, 'scope': 'Adapted protected-fitting diagnostic, not source-held or final performance.',
        'serving_changed': False, 'reserved_sources_used': 0}
    save_json(out/'predictions.json', rows); save_json(out/'results.json', result); print(result, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--prior-profile', type=Path); modes = p.add_mutually_exclusive_group(required=True)
    for name in ('prepare', 'verify', 'live', 'report'):
        modes.add_argument('--'+name, action='store_true')
    a = p.parse_args(); out = a.output_dir.resolve()
    if a.prepare:
        if a.prior_profile is None:
            p.error('--prior-profile required')
        prepare(a.prior_profile.resolve(), out)
    elif a.verify:
        print(verify(out))
    elif a.live:
        collect(out, live=True)
    else:
        report(out)
