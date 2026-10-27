"""Prepare a bounded Sol facet cache for all276 evaluation and99 local cases."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
from pathlib import Path
import random
import shutil
import threading

from PIL import Image

from critical.core.decision import facet_policy_v150 as facets
from critical.core.decision import outcome_policy_v160 as outcome
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence_v2 import image_identity, validate_program
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_facet_probe_v150 import ROOT, FROZEN, TEMPLATE, read
from run.calitree_explicit_facet_probe_v153 import GUIDE
from run.calitree_paid_facet_probe_v155 import MODELS, CAPS, ENDPOINT
from run.calitree_paid_facet_credentials_v157 import resolve_credentials
from run.verify_calitree_paid_facet_v158 import execution_ref

PILOT = ROOT/'logs/exps/261025-paid-facet-probe-v155-r1'
PILOT_AUDIT = ROOT/'logs/exps/261025-paid-facet-audit-v158-r3'
RECONSTRUCTION = ROOT/'logs/exps/261025-outcome-primary-v160-r1'
PRIMARY = ROOT/'logs/exps/261023-verified-semantic-compression-v112-r2/predictions.json'
META = ROOT/'logs/exps/261021-paired-vision-v63/inputs_without_labels.json'
RESERVED = ROOT/'logs/exps/261020-validation-reservation-v39/inputs_without_labels.json'
WORKERS = 4
WORKER_TOKEN_CAP = 131072
MAX_CALLS = 351
MAX_TOKENS = WORKERS*WORKER_TOKEN_CAP
PER_REQUEST = CAPS['sol']


def prompt_and_schema(instruction):
    spec = facets.schema(); order = ['evidence', 'material_gap']+list(facets.FIELDS)
    spec['properties'] = {k: spec['properties'][k] for k in order}; spec['required'] = order
    guide = GUIDE.read_text().replace('{schema}', json.dumps(spec)).replace('{field_order}', ', '.join(order))
    prompt = TEMPLATE.read_text().replace('{instruction}', json.dumps(instruction))+'\n\n'+guide
    return prompt, spec


def make_job(raw, metadata):
    hashes, pair = image_identity(raw['evidence'])
    prompt, spec = prompt_and_schema(raw['program']['instruction'])
    job = {'case': raw['case'], 'source_group': metadata['source_group'], 'instruction': raw['program']['instruction'],
        'program_ref': raw['program']['program_ref'], 'evidence': raw['evidence'], 'image_hashes': hashes,
        'image_pair_ref': pair, 'prompt': prompt, 'schema': spec, 'arm': 'sol', 'identity': MODELS['sol'],
        'max_tokens': PER_REQUEST, 'wire_prompt_ref': digest(prompt+'\nINPUT_JSON: {}')}
    job['request_ref'] = digest(job)
    return job


def prepare(out):
    if out.exists():
        raise ValueError('Fresh375-case facet collection required')
    assert read(PILOT_AUDIT/'verification.json')['passed'] and read(PILOT_AUDIT/'verification.json')['complete']
    assert read(RECONSTRUCTION/'results.json')['adapted_collection_screen']['sol']
    raw = {r['case']: r for r in read(FROZEN/'replay_inputs_without_references.json')}
    refs = {r['case']: r['reference'] for r in read(FROZEN/'fitting_replay.json')}
    originals = [r['case'] for r in read(FROZEN/'fitting_replay.json')[:99]]
    primary = [r['case'] for r in read(PRIMARY)]
    assert len(set(originals)) == 99 and len(set(primary)) == 276 and not set(originals)&set(primary)
    metadata = {r['case']: r for r in read(META)}; reserved = {r['source_group'] for r in read(RESERVED)}
    assert not {metadata[c]['source_group'] for c in originals}&{metadata[c]['source_group'] for c in primary}
    cases = originals+primary; jobs = []; membership = []; inventory = {}
    for case in cases:
        assert metadata[case]['source_group'] not in reserved
        validate_program(raw[case]['program'])
        job = make_job(raw[case], metadata[case]); jobs.append(job)
        membership.append({'case': case, 'role': 'protected_original' if case in originals else 'source_held_development',
                           'source_group': metadata[case]['source_group']})
    by_case = {j['case']: j for j in jobs}
    reused = {}
    for prior in [j for j in read(PILOT/'jobs.json') if j['arm'] == 'sol']:
        case = prior['case']; assert prior == by_case[case]
        path = PILOT/'responses'/(case+'-sol.json'); result = read(path)
        if result['accepted']:
            facets.validate(result['value'])
        reused[case] = {'case': case, 'request_ref': prior['request_ref'], 'source_response': str(path),
            'source_response_sha256': file_hash(path), 'accepted': result['accepted'],
            'value': result.get('value'), 'status': 'reused' if result['accepted'] else 'retained_failed_slot'}
    assert len(reused) == 24 and sum(r['accepted'] for r in reused.values()) == 23
    pending = sorted(set(cases)-set(reused)); assert len(pending) == MAX_CALLS
    random.Random(20261025).shuffle(pending)
    assignments = {str(w): pending[w::WORKERS] for w in range(WORKERS)}
    assert sum(map(len, assignments.values())) == MAX_CALLS
    for case in pending:
        for field, path in by_case[case]['evidence'].items():
            with Image.open(path) as image:
                size = list(image.size)
            inventory[path] = {'sha256': file_hash(path), 'dimensions': size, 'role': field}
    observed = read(PILOT/'reported_usage_cost.json')['usage']['sol']
    expected = MAX_CALLS/observed['valid_responses']*observed['estimated_reported_usage_usd']
    protocol = {'version': 'source-bound-facet-collection-v161', 'target_cases': 375, 'protected_originals': 99,
        'development_evaluation_cases': 276, 'reused_valid': 23, 'retained_failed': 1,
        'model': MODELS['sol'], 'endpoint': ENDPOINT, 'per_request_completion_cap': PER_REQUEST,
        'max_new_requests': MAX_CALLS, 'max_new_completion_tokens': MAX_TOKENS,
        'workers': WORKERS, 'worker_completion_cap': WORKER_TOKEN_CAP,
        'allocation': 'Disjoint fixed request queues and independent durable ledgers. Token budgets sum to524288; no borrowing. A worker stops before a reservation exceeding its cap.',
        'failure_policy': 'One HTTP attempt per slot, no retries/repair. Preserve pilot N108 failure. Provider rejection or three consecutive invalid results in a worker stop new work globally; already-reserved in-flight requests finish. Worker budget exhaustion stops that worker.',
        'observer_profile': 'Exact unchanged v155 Sol evidence-first prompt/schema, low reasoning, temperature omitted,8192 completion-token ceiling. No reference labels or compiled check text uploaded.',
        'readout': outcome.VERSION, 'outcome_contract_ref': outcome.CONTRACT_REF,
        'adaptation': 'Sol selected by the adapted24-fitting-case outcome-primary reconstruction; original strict screens failed. This collection covers the full276 development evaluation and99 protection set, not an untouched final test.',
        'selector_study': {'primary': {'priority': 'learned_semantic_precedence', 'guards': 2, 'loss_cost': 2., 'max_rules': 4, 'min_sources': 3},
            'candidates': [{'priority': p, 'guards': g, 'loss_cost': loss, 'max_rules': 4, 'min_sources': 3}
                for p in ('retain_prior_priority', 'learned_semantic_precedence') for g in (1, 2) for loss in (1., 2.)],
            'fitting': 'Only genuine fold-training views under existing five source folds; hard actual-original99/144 veto. Existing915-case teacher training data remain intact. Unmeasured540 sibling outputs keep V112 fallback. No outer-held source or label may choose a rule.',
            'coverage': 'New expert requires valid bound observations, a positive outcome-grade witness and the existing covered/valid input route. Missing/unresolved observations retain V112. Recompute coverage and predictions on every276 case; compare strict prior priority with selective learned precedence under the same local veto.'},
        'cost': {'verified_rates_date': '2026-10-25', 'input_usd_per_million': 2., 'output_usd_per_million': 10.,
            'expected_usd_from_pilot_mean': expected, 'expected_usd_range': [1.5, 4.],
            'full_output_allowance_usd': MAX_TOKENS*10/1e6,
            'limits': 'Completion-token hard cap only; input charges are additional. Expected range assumes pilot input/output averages transfer; it is not a total-charge cap.',
            'source': 'https://developers.openai.com/api/docs/models/gpt-6.1-sol'},
        'new_api_calls_during_preparation': 0, 'reserved_sources_used': 0, 'serving_changed': False}
    upload = {'destination': ENDPOINT, 'unique_image_files': len(inventory),
        'unique_image_hashes': len({v['sha256'] for v in inventory.values()}), 'image_upload_occurrences': 2*MAX_CALLS,
        'files': inventory, 'text': 'Edit instructions, generic reconstructed observation rubric, literal field guide and JSON schema. No human labels, source IDs or compiled programs are uploaded.'}
    out.mkdir(parents=True)
    save_json(out/'protocol.json', protocol); save_json(out/'jobs.json', jobs); save_json(out/'memberships.json', membership)
    save_json(out/'worker_assignments.json', assignments); save_json(out/'reused_observations.json', reused)
    save_json(out/'upload_inventory.json', upload); save_json(out/'references_not_uploaded.json', {c: refs[c] for c in cases})
    files = [Path(__file__), TEMPLATE, GUIDE, ROOT/'critical/core/decision/facet_policy_v150.py',
        ROOT/'critical/core/decision/outcome_policy_v160.py', ROOT/'critical/core/decision/calls.py',
        ROOT/'critical/lm_engine/lm_template/base.py', ROOT/'critical/lm_engine/openai_compat.py',
        ROOT/'critical/lm_engine/provider_api.py', ROOT/'run/calitree_paid_facet_credentials_v157.py']
    for path in files:
        dest = out/'source_snapshot'/path.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, dest)
    save_json(out/'manifest.json', {'protocol_ref': digest(protocol), 'jobs_ref': digest(jobs),
        'assignments_ref': digest(assignments), 'memberships_ref': digest(membership), 'reused_ref': digest(reused),
        'upload_inventory_ref': digest(upload), 'references_sha256': file_hash(out/'references_not_uploaded.json'),
        'pilot_audit_manifest_sha256': file_hash(PILOT_AUDIT/'manifest.json'),
        'reconstruction_manifest_sha256': file_hash(RECONSTRUCTION/'manifest.json'),
        'code_sha256': {str(p): file_hash(p) for p in files},
        'data_sha256': {str(p): file_hash(p) for p in (FROZEN/'replay_inputs_without_references.json', FROZEN/'fitting_replay.json', PRIMARY, META, RESERVED)}})
    (out/'run.log').write_text('Prepared375-case Sol facet scope offline;351 new slots,23 cached successes,one retained failure. No API calls.\n')
    (out/'llm-histories.log').write_text('Live request histories, if authorized, are isolated per worker in workers/workerN/llm-histories.log.\n')
    result = verify(out)
    print({'prepared': True, **result, 'expected_usd': expected, 'full_output_allowance_usd': MAX_TOKENS*10/1e6}, flush=True)


def verify(out):
    m = read(out/'manifest.json'); protocol = read(out/'protocol.json'); jobs = read(out/'jobs.json')
    assert digest(protocol) == m['protocol_ref'] and digest(jobs) == m['jobs_ref']
    assignments, membership, reused, upload = [read(out/name) for name in ('worker_assignments.json', 'memberships.json', 'reused_observations.json', 'upload_inventory.json')]
    for key, value in (('assignments', assignments), ('memberships', membership), ('reused', reused), ('upload_inventory', upload)):
        assert digest(value) == m[key+'_ref']
    assert file_hash(out/'references_not_uploaded.json') == m['references_sha256']
    for path, sha in {**m['code_sha256'], **m['data_sha256']}.items():
        assert file_hash(path) == sha
    for path, sha in m['code_sha256'].items():
        assert file_hash(out/'source_snapshot'/Path(path).relative_to(ROOT)) == sha
    assert m['pilot_audit_manifest_sha256'] == file_hash(PILOT_AUDIT/'manifest.json')
    assert m['reconstruction_manifest_sha256'] == file_hash(RECONSTRUCTION/'manifest.json')
    assert protocol['max_new_requests'] == MAX_CALLS and protocol['max_new_completion_tokens'] == MAX_TOKENS
    assert protocol['workers'] == WORKERS and protocol['worker_completion_cap'] == WORKER_TOKEN_CAP
    assert protocol['per_request_completion_cap'] == PER_REQUEST and protocol['model'] == MODELS['sol']
    raw = {r['case']: r for r in read(FROZEN/'replay_inputs_without_references.json')}
    metadata = {r['case']: r for r in read(META)}; reserved = {r['source_group'] for r in read(RESERVED)}
    original = {r['case'] for r in read(FROZEN/'fitting_replay.json')[:99]}
    primary = {r['case'] for r in read(PRIMARY)}; expected = original|primary
    assert len(jobs) == len({j['case'] for j in jobs}) == len(expected) == 375
    assert {j['case'] for j in jobs} == expected
    assert len(membership) == 375 and {r['case'] for r in membership} == expected
    assert sum(r['role'] == 'protected_original' for r in membership) == 99
    for record in membership:
        assert record['source_group'] == metadata[record['case']]['source_group']
        assert record['role'] == ('protected_original' if record['case'] in original else 'source_held_development')
    by_case = {j['case']: j for j in jobs}
    for job in jobs:
        case = job['case']; assert metadata[case]['source_group'] not in reserved
        assert make_job(raw[case], metadata[case]) == job
    assigned = [c for w in range(WORKERS) for c in assignments[str(w)]]
    assert len(assigned) == len(set(assigned)) == MAX_CALLS and set(assigned) == expected-set(reused)
    assert len(reused) == 24 and sum(r['accepted'] for r in reused.values()) == 23
    for case, record in reused.items():
        assert file_hash(record['source_response']) == record['source_response_sha256']
        source = read(record['source_response']); assert source['request_ref'] == record['request_ref'] == by_case[case]['request_ref']
        assert source['accepted'] == record['accepted'] and source.get('value') == record['value']
    for path, spec in upload['files'].items():
        assert file_hash(path) == spec['sha256']
    result = {'passed': True, 'target_cases': 375, 'new_requests': MAX_CALLS, 'reused_valid': 23, 'retained_failed': 1,
        'worker_jobs': {w: len(q) for w, q in assignments.items()}, 'completion_cap': MAX_TOKENS,
        'new_image_files': upload['unique_image_files'], 'image_upload_occurrences': 2*MAX_CALLS,
        'reserved_sources_used': 0, 'new_api_calls': 0}
    save_json(out/'preflight_verification.json', result)
    return result


def stop_globally(out, event, reason):
    event.set()
    try:
        with (out/'stop.json').open('x') as f:
            json.dump({'reason': reason}, f)
    except FileExistsError:
        pass


def collect_worker(out, worker, creds, event):
    from critical.core.decision.calls import DurableCalls, ProviderStopped, BudgetExhausted
    from critical.lm_engine import get_engine
    from critical.logging.llm_history import LLMHistoryWriter
    queue = read(out/'worker_assignments.json')[str(worker)]
    jobs = {j['case']: j for j in read(out/'jobs.json')}
    directory = out/'workers'/('worker'+str(worker)); directory.mkdir(parents=True, exist_ok=True)
    history = LLMHistoryWriter(directory/'llm-histories.log')
    def factory(cap):
        return get_engine('gpt', creds=creds, model=MODELS['sol']['model'], temperature=None, reasoning_effort='low',
            max_tokens=cap, timeout=240, max_http_attempts=1, history=history)
    calls = DurableCalls(directory/'ledger', factory, identity=MODELS['sol'], max_calls=len(queue),
        max_completion_tokens=WORKER_TOKEN_CAP, scope_limits={'search': 1, 'final': 0})
    consecutive = 0
    for case in queue:
        if event.is_set() or (out/'stop.json').exists():
            break
        path = out/'responses'/(case+'.json')
        if path.exists():
            continue
        job = jobs[case]
        result = {'case': case, 'request_ref': job['request_ref'], 'execution_ref': execution_ref(job),
                  'worker': worker, 'accepted': False, 'error': None}
        try:
            media = [{'type': 'text', 'text': 'SOURCE image'}, {'type': 'image', 'path': job['evidence']['source_image']},
                     {'type': 'text', 'text': 'EDITED image'}, {'type': 'image', 'path': job['evidence']['edited_image']}]
            value, ref = calls.call('explicit_semantic_facets_v155', {}, job['schema'], template=job['prompt'], media=media,
                slot='sol', case_id=case, max_tokens=PER_REQUEST)
            assert ref == result['execution_ref']
            result.update(accepted=True, value=facets.validate(value))
        except BudgetExhausted:
            return {'worker': worker, 'status': 'budget_exhausted_before_next_reservation'}
        except ProviderStopped as exc:
            result['error'] = type(exc).__name__; save_json(path, result)
            stop_globally(out, event, 'Provider rejected a request or durable transport stop occurred')
            break
        except (ValueError, RuntimeError, TypeError, KeyError) as exc:
            result['error'] = type(exc).__name__
        save_json(path, result)
        consecutive = 0 if result['accepted'] else consecutive+1
        print({'worker': worker, 'case': case, 'accepted': result['accepted'], 'error': result['error']}, flush=True)
        if consecutive >= 3:
            stop_globally(out, event, 'Three consecutive invalid results in one worker'); break
    return {'worker': worker, 'status': 'stopped' if event.is_set() else 'terminal_queue'}


def aggregate(out):
    assignments = read(out/'worker_assignments.json'); summaries = []; total_calls = 0; total_tokens = 0; input_tokens = 0
    for w in range(WORKERS):
        path = out/'workers'/('worker'+str(w))/'ledger/budget.json'
        if not path.exists():
            continue
        b = read(path)
        assert b['limits']['max_calls'] == len(assignments[str(w)]) and b['limits']['max_completion_tokens'] == WORKER_TOKEN_CAP
        assert b['calls'] <= len(assignments[str(w)]) and b['completion_tokens_or_reserved'] <= WORKER_TOKEN_CAP
        total_calls += b['calls']; total_tokens += b['completion_tokens_or_reserved']; input_tokens += b['input_tokens']
    for path in (out/'responses').glob('*.json'):
        summaries.append(read(path))
    assert len({r['case'] for r in summaries}) == len(summaries) <= MAX_CALLS
    assert total_calls <= MAX_CALLS and total_tokens <= MAX_TOKENS
    result = {'planned_new_slots': MAX_CALLS, 'new_attempts': total_calls, 'new_responses': len(summaries),
        'new_valid_observations': sum(r['accepted'] for r in summaries), 'reused_valid': 23, 'retained_failed': 1,
        'completion_tokens_or_reserved': total_tokens, 'input_tokens': input_tokens,
        'complete': len(summaries) == MAX_CALLS, 'global_stop': (out/'stop.json').exists(),
        'new_fits': 0, 'reserved_sources_used': 0, 'serving_changed': False}
    save_json(out/'collection_status.json', result)
    print(result, flush=True)
    return result


def collect(out, *, live=False, credential_path=None):
    if not live or not (out/'authorization.json').exists():
        raise ValueError('New351-request paid-call/upload approval and --live required')
    verify(out)
    authorization = read(out/'authorization.json')
    assert authorization['approved'] is True and authorization['upload_approved'] is True
    assert authorization['manifest_sha256'] == file_hash(out/'manifest.json')
    assert authorization['max_requests'] == MAX_CALLS and authorization['max_completion_tokens'] == MAX_TOKENS
    if (out/'collection_status.json').exists() or (out/'stop.json').exists():
        raise ValueError('Terminal/stopped collection requires explicit recovery, never automatic restart')
    from critical.lm_engine import require_live
    require_live(True)
    with (out/'execution.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        creds, resolution = resolve_credentials(credential_path)
        save_json(out/'credential_resolution.json', resolution)
        (out/'responses').mkdir(exist_ok=True)
        event = threading.Event()
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            results = list(executor.map(lambda w: collect_worker(out, w, creds, event), range(WORKERS)))
        save_json(out/'worker_status.json', results)
        aggregate(out)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--credential-path', type=Path); mode = p.add_mutually_exclusive_group(required=True)
    for name in ('prepare', 'verify', 'live', 'report'):
        mode.add_argument('--'+name, action='store_true')
    a = p.parse_args(); out = a.output_dir.resolve()
    if a.prepare:
        prepare(out)
    elif a.verify:
        print(verify(out))
    elif a.live:
        collect(out, live=True, credential_path=a.credential_path)
    else:
        aggregate(out)
