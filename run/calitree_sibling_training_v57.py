"""Prepare complete five-editor fitting coverage for the existing sampled tasks.

No new sources or compilation. Each of 540 outputs has its own three-call
durable budget, so four concurrent workers cannot race a shared request ledger.
The aggregate upper bound is the sum of those disjoint per-output allowances.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
from pathlib import Path
from threading import Lock

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence_v2 import validate_program
from critical.core.decision.compiler import media_inputs
from critical.core.optimization.prompt.calitree.evidence_covered_judge import BoundEvidencePipeline
from critical.core.optimization.prompt.calitree import task_coverage as task
from critical.core.calibration import shared_regions_v27 as shared
from run.calitree_continuous_policy_v43 import examples_and_scores, RESERVED
from run.calitree_fidelity_policy_v56 import evidence_metadata
from run.calitree_guarded_forward_v32 import SOURCE
from run.calitree_m0 import pixel_hash
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint, exact, IDENTITY
from run.collect_calitree_aurora_pilot_v29r1 import validate_regular

VERSION = 'matched-editor-sibling-training-v57'
SOURCE_ROOT = Path('/Users/zzhang/Documents/Projects/Adobe/calitree-mlsys')
CASE_CAP = 16384 + 8192 + 2048
CASES, MAX_CALLS, MAX_OUTPUT = 540, 540 * 3, 540 * CASE_CAP
WORKERS = 4


def prepare(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    local, recent, _, _ = examples_and_scores(True)
    examples = local + recent
    metadata = evidence_metadata()
    catalog_path = ROOT / 'logs/exps/261020-aurora-pilot80-v29/exposure/original/exposure_ledger.json'
    catalog = read(catalog_path)['tasks']
    bench = SOURCE_ROOT / 'data/aurora/bench'
    by_path = {str(bench / o['edited_path']): t['task_uid'] for t in catalog for o in t['outputs']}
    by_uid = {t['task_uid']: t for t in catalog}
    existing, programs, parent_cases = set(), {}, {}
    for e in examples:
        m = metadata[e['case']]
        uid = by_path[m['evidence']['edited_image']]
        existing.add((uid, fingerprint(m['evidence']['edited_image'])))
        if e['program'] is not None:
            validate_program(e['program'])
            programs.setdefault(uid, e['program'])
            parent_cases.setdefault(uid, e['case'])
    selected = []
    for uid in sorted(programs):
        t = by_uid[uid]
        for output in sorted(t['outputs'], key=lambda o: o['editor']):
            if (uid, output['edited_sha256']) not in existing:
                selected.append((t, output))
    assert len(selected) == CASES
    assert len({t['task_uid'] for t, o in selected}) == 135
    assert len({t['source_group'] for t, o in selected}) == 134
    reserved = {e['source_group'] for e in read(RESERVED / 'inputs_without_labels.json')}
    excluded = set(read(SOURCE / 'manifest.json')['excluded_groups'])
    assert not {t['source_group'] for t, o in selected} & (reserved | excluded)
    entries, refs, hashes, used_programs = [], {}, {}, {}
    for i, (t, output) in enumerate(selected, 1):
        uid, case = t['task_uid'], f'S{i:04}'
        p = programs[uid]
        assert p['instruction'] == output['instruction']
        source, edited = bench / t['source_path'], bench / output['edited_path']
        assert pixel_hash(source) == t['source_group']
        assert fingerprint(source) == t['source_sha256'] and fingerprint(edited) == output['edited_sha256']
        entries.append({'case': case, 'task_uid': uid, 'source_group': t['source_group'], 'instruction': output['instruction'],
                        'task': t['task'], 'editor': output['editor'], 'program_ref': p['program_ref'],
                        'evidence': {'source_image': str(source), 'edited_image': str(edited)}})
        refs[case] = {'reference': task.LABELS.index(output['reference']), 'human_score': output['human_score']}
        used_programs[uid] = {'program': p, 'parent_case': parent_cases[uid]}
        hashes[str(source)] = t['source_sha256']
        hashes[str(edited)] = output['edited_sha256']
    out.mkdir(parents=True)
    # Extrapolate completed Luna non-compiler stages, including failed output reservations.
    usage_root = ROOT / 'logs/exps/261020-training-expansion-v42/ledger/jobs'
    empirical_input = empirical_completion = 0
    for path in usage_root.glob('*.json'):
        job = read(path)
        if job['stage'].startswith('bound_instruction'):
            continue
        empirical_input += int(job.get('response', {}).get('promptTokens', 0))
        empirical_completion += int(job['response']['completionTokens']) if 'response' in job else job['max_tokens']
    estimate = CASES / 160 * (empirical_input * .1 + empirical_completion * .5) / 1e6
    protocol = {'version': VERSION, 'identity': IDENTITY, 'cases': CASES, 'existing_tasks': 135, 'existing_sources': 134,
                'new_source_groups': 0, 'compiler_calls': 0, 'max_requests': MAX_CALLS, 'max_completion_tokens': MAX_OUTPUT,
                'per_output_request_cap': 3, 'per_output_completion_cap': CASE_CAP, 'workers': WORKERS, 'transport_retries': 0,
                'budget_proof': '540 immutable, unique output jobs; separate durable ledger per output, each <=3 requests and <=26,624 completion tokens. Aggregate cannot exceed 1,620/14,376,960, regardless of concurrency.',
                'circuit_breaker': 'Shared stop latch after provider rejection or three consecutive transport failures. At most four in-flight requests; never retry a failed slot.',
                'scope': 'Complete four missing editors on the 135 existing single-editor tasks. Training only, no reserved-source access or serving changes.',
                'source_exclusions': 'All 80 reserved source groups and the original sampled-manifest excluded groups are absent.',
                'later_evaluation': 'Keep the primary 276-case source-held evaluation fixed. Exclude every new sibling of a held source from fitting, regardless of whether it is scored. Original 99/144 retention remains mandatory.',
                'cost': {'empirical_usd': estimate, 'expected_usd_range': [.8, 1.4], 'full_output_allowance_usd': MAX_OUTPUT * .5 / 1e6,
                         'input_charges_additional': True, 'basis': 'Scale completed v42 non-compiler Luna usage, including failed output reservation, from 160 to 540 outputs.',
                         'pricing_source': 'https://developers.openai.com/api/docs/models/gpt-6-luna'},
                'paid_authorization_required': True, 'new_model_calls': 0}
    save_json(out / 'protocol.json', protocol)
    save_json(out / 'inputs_without_labels.json', entries)
    save_json(out / 'references_training_only.json', refs)
    save_json(out / 'programs.json', used_programs)
    save_json(out / 'inventory.json', {'existing_pool': 375, 'expanded_pool': 915, 'existing_pool_tasks': 183,
              'expanded_pool_tasks': 183, 'existing_pool_sources': 182, 'expanded_pool_sources': 182,
              'original_training_editor_counts': dict(Counter(metadata[e['case']]['editing_model'] for e in local)),
              'new_editor_counts': dict(Counter(e['editor'] for e in entries)), 'new_task_counts': dict(Counter(e['task'] for e in entries))})
    code = [Path(__file__).resolve(), ROOT / 'critical/core/decision/calls.py', ROOT / 'critical/lm_engine/provider_api.py',
            ROOT / 'critical/lm_engine/openai_compat.py', ROOT / 'critical/lm_engine/lm_template/base.py',
            ROOT / 'critical/core/optimization/prompt/calitree/evidence_covered_judge.py',
            ROOT / 'critical/core/decision/bound_evidence_v2.py', ROOT / 'critical/core/decision/bound_evidence.py',
            ROOT / 'critical/core/decision/semantic_interpretation_v5.py', task.TEMPLATES / 'regular.txt']
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'input_ref': digest(entries), 'reference_ref': digest(refs),
              'programs_ref': digest(used_programs), 'image_hashes': hashes, 'code_hashes': {str(p): fingerprint(p) for p in code},
              'catalog_sha256': fingerprint(catalog_path), 'reserved_inputs_sha256': fingerprint(RESERVED / 'inputs_without_labels.json')})
    (out / 'run.log').write_text('Prepared 540 missing sibling outputs; no paid authorization or ledger. Existing source/task contexts, four other editors, frozen programs, no compiler calls.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')
    print({'cases': CASES, 'max_requests': MAX_CALLS, 'max_completion_tokens': MAX_OUTPUT, 'workers': WORKERS,
           'empirical_cost_usd': estimate, 'expected_usd': [.8, 1.4], 'full_output_allowance_usd': MAX_OUTPUT * .5 / 1e6}, flush=True)


def verify(out):
    p, m = read(out / 'protocol.json'), read(out / 'manifest.json')
    entries, refs, programs = read(out / 'inputs_without_labels.json'), read(out / 'references_training_only.json'), read(out / 'programs.json')
    assert digest(p) == m['protocol_ref'] and digest(entries) == m['input_ref']
    assert digest(refs) == m['reference_ref'] and digest(programs) == m['programs_ref']
    assert p['cases'] == 540 and p['max_requests'] == 1620 and p['max_completion_tokens'] == 14376960
    assert fingerprint(RESERVED / 'inputs_without_labels.json') == m['reserved_inputs_sha256']
    for path, expected in {**m['code_hashes'], **m['image_hashes']}.items():
        assert fingerprint(path) == expected, path
    assert len(entries) == len({e['case'] for e in entries}) == 540 and len(refs) == 540
    assert len({e['evidence']['edited_image'] for e in entries}) == 540
    reserved = {e['source_group'] for e in read(RESERVED / 'inputs_without_labels.json')}
    for e in entries:
        assert not {'reference', 'human_score'} & set(e)
        assert e['source_group'] not in reserved
        program = programs[e['task_uid']]['program']
        validate_program(program)
        assert program['program_ref'] == e['program_ref'] and program['instruction'] == e['instruction']
    return p


class StopCircuit:
    def __init__(self, path):
        self.path, self.lock, self.errors, self.stopped = Path(path), Lock(), 0, None
        if self.path.exists():
            self.stopped = read(self.path)['reason']

    def check(self):
        with self.lock:
            if self.stopped:
                raise RuntimeError('Global provider stop latch: ' + self.stopped)

    def success(self):
        with self.lock:
            self.errors = 0

    def failure(self, error):
        message = str(error).lower()
        with self.lock:
            self.errors += 1
            rejected = any(word in message for word in ('400', '401', '403', '404', 'model_not_found', 'invalid_api_key', 'permission'))
            if rejected or self.errors >= 3:
                self.stopped = 'provider_rejected' if rejected else 'three_consecutive_transport_failures'
                save_json(self.path, {'reason': self.stopped, 'consecutive_errors': self.errors})


def run_case(entry, program, calls, circuit):
    result = {'program': program, 'observation': None, 'interpretation': None, 'pair_ref': None, 'features': None,
              'regular_judgment': None, 'regular_execution_ref': None, 'extraction_error': None, 'regular_error': None}
    try:
        circuit.check()
        observation, interpretation, pair = BoundEvidencePipeline(calls).extract(program, entry['evidence'], case_id=entry['case'])
        result.update(observation=observation, interpretation=interpretation, pair_ref=pair,
                      features=shared.evidence.project(program, observation, pair, interpretation))
    except (ValueError, RuntimeError, KeyError, TypeError) as exc:
        result['extraction_error'] = type(exc).__name__
    circuit.check()
    try:
        value, ref = calls.call('flat_judge', {'instruction': entry['instruction']}, task.SCHEMA,
                                template=(task.TEMPLATES / 'regular.txt').read_text(), media=media_inputs(entry['evidence']),
                                case_id=entry['case'], slot='once', max_tokens=2048)
        validate_regular(value)
        result.update(regular_judgment=value, regular_execution_ref=ref)
    except (ValueError, RuntimeError, KeyError, TypeError) as exc:
        result['regular_error'] = type(exc).__name__
    return result


def collect(out, live=False):
    if not live or not (out / 'authorization.json').exists():
        raise ValueError('Separate explicit paid authorization and --live required')
    verify(out)
    authorization = read(out / 'authorization.json')
    assert authorization['protocol_sha256'] == fingerprint(out / 'protocol.json')
    if (out / 'preflight_seal.json').exists():
        for name, expected in read(out / 'preflight_seal.json')['files'].items():
            assert fingerprint(out / name) == expected, name
    circuit = StopCircuit(out / 'provider_stop.json')
    circuit.check()
    from critical import config
    from critical.core.decision.calls import DurableCalls
    from critical.lm_engine import load_creds, get_engine, require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True)
    config.PROJECT_ROOT, config.CREDENTIALS_FILE = SOURCE_ROOT, SOURCE_ROOT / '.env'
    creds = load_creds(provider='openai', engine='gpt')
    if creds.endpoints != ['https://api.openai.com/v1']:
        raise ValueError('Official endpoint required')
    entries, programs = read(out / 'inputs_without_labels.json'), read(out / 'programs.json')
    def work(e):
        path = out / 'cases' / (e['case'] + '.json')
        if path.exists():
            return
        circuit.check()
        directory = out / 'case_ledgers' / e['case']
        def factory(cap):
            engine = get_engine('gpt', creds=creds, model=IDENTITY['model'], temperature=0, max_tokens=cap,
                                timeout=180, max_http_attempts=1, history=LLMHistoryWriter(directory / 'llm-histories.log'))
            class GuardedEngine:
                def generate(self, *args, **kwargs):
                    circuit.check()
                    try:
                        value = engine.generate(*args, **kwargs)
                    except Exception as exc:
                        circuit.failure(exc)
                        raise
                    circuit.success()
                    return value
            return GuardedEngine()
        calls = DurableCalls(directory, factory, identity=IDENTITY, max_calls=3, max_completion_tokens=CASE_CAP,
                             scope_limits={'search': 3, 'final': 0})
        result = run_case(e, programs[e['task_uid']]['program'], calls, circuit)
        exact(path, result)
        print({'case': e['case'], 'extraction_error': result['extraction_error'], 'regular_error': result['regular_error']}, flush=True)
    with (out / 'collection.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        failures = []
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {pool.submit(work, e): e['case'] for e in entries}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    failures.append({'case': futures[future], 'error': type(exc).__name__})
        if failures:
            save_json(out / 'incomplete.json', {'worker_failures': failures, 'provider_stopped': circuit.stopped})
            raise RuntimeError('Collection incomplete; retain ledgers and inspect incomplete.json, never resample failed slots')
    report(out)


def report(out):
    verify(out)
    refs = read(out / 'references_training_only.json')
    rows = []
    for e in read(out / 'inputs_without_labels.json'):
        c = read(out / 'cases' / (e['case'] + '.json'))
        value = c['regular_judgment']
        regular = task.LABELS.index(value['label']) if value is not None and value['label'] in task.LABELS else -1
        rows.append({**e, 'program': c['program'], 'features': c['features'], 'regular': regular,
                     **refs[e['case']], 'extraction_error': c['extraction_error'], 'regular_error': c['regular_error']})
    budgets = [read(out / 'case_ledgers' / e['case'] / 'budget.json') for e in rows]
    calls = sum(b['calls'] for b in budgets)
    tokens = sum(b['completion_tokens_or_reserved'] for b in budgets)
    assert calls <= MAX_CALLS and tokens <= MAX_OUTPUT
    exact(out / 'training_data.json', rows)
    exact(out / 'results.json', {'cases': 540, 'requests': calls, 'completion_tokens_or_reserved': tokens,
          'valid_feature_cases': sum(e['features'] is not None for e in rows), 'regular_correct': sum(e['regular'] == e['reference'] for e in rows),
          'scope': 'Additional fitting data only; no model fitting, validation or generalization result in collection.'})
    print(read(out / 'results.json'), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    for name in ('prepare', 'verify', 'live', 'report'):
        mode.add_argument('--' + name, action='store_true')
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if args.prepare:
        prepare(out)
    elif args.verify:
        print(verify(out))
    elif args.live:
        collect(out, True)
    else:
        report(out)
