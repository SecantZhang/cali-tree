"""Three prospectively frozen 48/12 replications of the unchanged v11 pipeline.

The 36 evaluation sources are disjoint and globally excluded from training.
Training samples overlap because only 31 eligible Yes sources remain. Original
M0 train/development/final sources are excluded; historical exposure is disclosed.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import shutil
import time

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.calls import DurableCalls
from critical.core.decision.bound_evidence_v2 import (image_identity, BoundInstructionCompiler, BoundVisualObserver,
    derive_record, diagnostic_readout)
from critical.core.decision.semantic_interpretation_v5 import PROMPT, make_input, schema, validate
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import project, CONTRACT_REF
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import metrics
from critical.core.calibration.semantic_hierarchy.union_groups_v10 import original, split_balanced, semantic, validate_partition
from critical.core.calibration.semantic_hierarchy.union_learning_v10 import UnionFits, PROFILES
from critical.core.calibration.semantic_hierarchy.union_reuse_v11 import ReuseFits, REPAIR
from critical.core.calibration.semantic_hierarchy.union_merges_v10 import learn, LIMITS, rank, gate, predict
from critical.database.dl_aurora.loader import AURORA_MODELS, score_to_label
from run.calitree_bound_evidence_v2 import audit_payloads, usage, CAPS
from run.calitree_single_call import ROOT, read, fingerprint
from run.calitree_union_reuse import selection_key, merge_order

VERSION = 'three-sampled-splits-reuse-v11-20261018'
SEEDS = (2026101801, 2026101802, 2026101803)
LABELS = ('no', 'partial', 'yes')
M0 = ROOT / 'logs/exps/261014-semantic-hierarchy-m0-fifty-v1'
PREVIOUS = ROOT / 'logs/exps/261015-union-reuse-v11'
INTERPRET_CAP = 8192
IDENTITY = {'provider': 'openai', 'model': 'gpt-6-luna', 'reasoning_effort': 'none', 'temperature': 0}
METHODS = {'original4_reuse': original, 'split8_reuse': split_balanced, 'semantic8_reuse': semantic}


def exact(path, value):
    value = json.loads(json.dumps(value))
    if path.exists():
        if read(path) != value:
            raise ValueError('Frozen replication artifact changed: ' + str(path))
    else:
        save_json(path, value)


def select(rows, seed, per_class, excluded=()):
    """Fixed-seed source sampling with task-category spreading; no score ranking."""
    used, result, tasks = set(excluded), [], Counter()
    for _ in range(per_class):
        for label in LABELS:
            candidates = [r for r in rows if r['reference'] == label and r['group'] not in used]
            if not candidates:
                raise ValueError('Insufficient distinct sources for declared quota: ' + label)
            chosen = min(candidates, key=lambda r: (tasks[r['task']], digest([VERSION, seed, r['id']])))
            result.append(deepcopy(chosen)); used.add(chosen['group']); tasks[chosen['task']] += 1
    return result


def assert_splits(splits, excluded):
    eval_groups = [set(r['group'] for r in s['evaluation']) for s in splits]
    if sum(map(len, eval_groups)) != len(set().union(*eval_groups)):
        raise ValueError('Evaluation cohorts overlap')
    all_eval = set().union(*eval_groups)
    for s in splits:
        train, evaluation = s['train'], s['evaluation']
        train_groups = {r['group'] for r in train}
        if len(train) != len(train_groups) or len(train) != 48 or len(evaluation) != 12:
            raise ValueError('Changed full-denominator sample sizes')
        if train_groups & all_eval or (train_groups | {r['group'] for r in evaluation}) & set(excluded):
            raise ValueError('Training/evaluation/reserved source leakage')
        if Counter(r['reference'] for r in train) != dict.fromkeys(LABELS, 16):
            raise ValueError('Training class quotas changed')
        if Counter(r['reference'] for r in evaluation) != dict.fromkeys(LABELS, 4):
            raise ValueError('Evaluation class quotas changed')
        for batch in ('G1', 'G2', 'G3', 'G4'):
            if Counter(r['reference'] for r in train if r['batch'] == batch) != dict.fromkeys(LABELS, 4):
                raise ValueError('Original-four batch balance changed')


def prepare(out, reuse_collection_from=None):
    reuse_collection_from = Path(reuse_collection_from).resolve() if reuse_collection_from else None
    out.mkdir(parents=True, exist_ok=True)
    validate_settings()
    if (out / 'manifest.json').exists():
        manifest = read(out / 'manifest.json'); verify(out, manifest); return manifest
    inventory = read(M0 / 'exposure_ledger.json')
    by_uid = {r['task_uid']: r for r in inventory['tasks']}
    excluded = {r['group'] for part in ('train', 'validation', 'test') for r in read(M0 / 'splits' / (part + '.json'))['cases']}
    official = set(read(ROOT / 'data/aurora/bench/splits/seed_42.json')['test'])
    candidates = []
    for r in (json.loads(line) for line in (ROOT / 'data/aurora/bench/metadata.jsonl').read_text().splitlines()):
        t = by_uid[r['task_uid']]
        if r['model'] != AURORA_MODELS[0] or r['task_uid'] not in official or t['source_group'] in excluded:
            continue
        evidence = {'source_image': str(ROOT / 'data/aurora/bench' / r['source_path']),
                    'edited_image': str(ROOT / 'data/aurora/bench' / r['edited_path'])}
        candidates.append({'id': r['item_id'], 'task_uid': r['task_uid'], 'group': t['source_group'],
            'instruction': r['instruction'], 'task': r['task'], 'editing_model': r['model'],
            'reference': score_to_label(r['human_score'])[1], 'human_score': r['human_score'],
            'evidence': evidence, 'image_hashes': {k: fingerprint(p) for k, p in evidence.items()},
            'historical_exposure_status': t['status']})
    evaluations, all_eval = [], set()
    for seed in SEEDS:
        rows = select(candidates, seed, 4, all_eval)
        evaluations.append(rows); all_eval.update(r['group'] for r in rows)
    splits = []
    for i, seed in enumerate(SEEDS):
        train = select(candidates, seed + 100, 16, all_eval)
        # The original4 arm receives four balanced twelve-source batches.
        for j, row in enumerate(train):
            row['batch'] = 'G' + str((j // 3) % 4 + 1)
        splits.append({'name': 'split' + str(i + 1), 'seed': seed, 'train': train, 'evaluation': evaluations[i]})
    assert_splits(splits, excluded)
    unique = {r['id']: r for s in splits for part in ('train', 'evaluation') for r in s[part]}
    # Source pixels define leakage groups, while exact item IDs define cache
    # identity. Multiple instructions may legitimately share the same pixels.
    previous_ids = {}
    if reuse_collection_from:
        previous_manifest = read(Path(reuse_collection_from) / 'manifest.json')
        if previous_manifest['judge_identity'] != IDENTITY:
            raise ValueError('Cannot mix extraction models when reusing collection')
        previous_ids = {r['id']: r['case'] for r in previous_manifest['cases']}
        for split in splits:
            old = read(Path(reuse_collection_from) / 'splits' / (split['name'] + '.json'))
            assert all([r['id'] for r in old[part]] == [r['id'] for r in split[part]] for part in ('train', 'evaluation'))
    next_id = max((int(v[1:]) for v in previous_ids.values()), default=0) + 1
    cases = []
    for item_id, row in sorted(unique.items(), key=lambda pair: (pair[1]['group'], pair[0])):
        row = deepcopy(row)
        if item_id in previous_ids:
            row['case'] = previous_ids[item_id]
        else:
            row['case'] = f'N{next_id:03}'; next_id += 1
        row.pop('batch', None); cases.append(row)
    cases.sort(key=lambda row: row['case'])
    case_ids = {r['id']: r['case'] for r in cases}
    for s in splits:
        for part in ('train', 'evaluation'):
            for row in s[part]:
                row['case'] = case_ids[row['id']]
        exact(out / 'splits' / (s['name'] + '.json'), s)
    code = [Path(__file__).resolve(), ROOT / 'run/calitree_single_call.py', ROOT / 'run/calitree_bound_evidence_v2.py',
            ROOT / 'run/calitree_union_reuse.py', ROOT / 'run/calitree_union_merge.py',
            ROOT / 'critical/core/decision/calls.py', ROOT / 'critical/core/decision/compiler.py',
            ROOT / 'critical/lm_engine/provider_api.py', ROOT / 'critical/lm_engine/lm_template/__init__.py', ROOT / 'critical/lm_engine/lm_template/base.py',
            ROOT / 'critical/lm_engine/lm_gpt/engine.py',
            ROOT / 'critical/core/decision/artifacts.py', ROOT / 'critical/core/decision/bound_evidence.py',
            ROOT / 'critical/core/decision/bound_evidence_v2.py', ROOT / 'critical/core/decision/semantic_interpretation_v5.py']
    code += sorted((ROOT / 'critical/core/calibration/semantic_hierarchy').glob('*.py'))
    code += sorted((ROOT / 'critical/core/prompts/templates/bound_evidence_v2').glob('*.txt'))
    protocol = {'version': VERSION, 'seeds': SEEDS, 'identity': IDENTITY, 'caps': {**CAPS, 'interpret': INTERPRET_CAP},
        'workers': 8, 'train_per_split': 48, 'evaluation_per_split': 12, 'stratified': True,
        'seed_groups': {'original': '4 x 12, each 4/class', 'split_balanced': '8 x 6, each 2/class',
                        'semantic': '8 x 6, fixed label-blind semantic clustering'},
        'profiles': PROFILES, 'limits': LIMITS, 'repair': REPAIR, 'runs': list(METHODS),
        'selection': read(PREVIOUS / 'protocol.json')['selection'],
        'model_change': 'User requested gpt-6-luna instead of gpt-6.1-sol. Preserve original sampled splits; Luna reasoning=none and temperature=0 as supported by the existing adapter. Earlier Sol attempts are preserved separately and never reused.',
        'new_evidence': 'One compile, one ordered image-pair observation, one text interpretation per unique source. Shared sources reuse the identical label-blind observation; no retries or replacements.',
        'failure_policy': 'Missing observation/meaning remains unresolved in denominators. No qualifying complete root is a reported infeasibility; do not loosen gates or resample.',
        'evaluation': 'Three mutually source-disjoint 12-case cohorts; all 36 excluded from all training. Freeze each arm before scoring. No evaluation-driven fitting, threshold tuning, retries or root choice.',
        'comparison': 'Reuse-first M5-M7 versus direct full-grammar fit on the same 48, with compact/deep profile chosen by training rank only. Original frozen root is an additional reference.',
        'scope': 'New sampled sources relative to old 60 and reserved 50. Historical exposure ledger status is retained; no globally untouched-data claim. Training sets overlap and replicates are correlated.',
        'reserved_fifty_evaluated': False, 'max_new_calls': len(cases) * 3,
        'cache_identity': 'Exact dataset item ID, instruction and ordered image hashes; source pixels only define leakage groups.',
        'max_completion_tokens': len(cases) * (sum(CAPS.values()) + INTERPRET_CAP)}
    if reuse_collection_from:
        protocol['collection_reuse_from'] = str(Path(reuse_collection_from).resolve())
        protocol['input_identity_revision'] = 'Preserve exactly the same 180 selected item slots. Repair cache aliasing for shared source pixels; collect only previously missing exact inputs, retaining all failures without retry.'
    exact(out / 'protocol.json', protocol)
    sources = [M0 / 'exposure_ledger.json', PREVIOUS / 'protocol.json', PREVIOUS / 'deployment_policy.json',
               ROOT / 'data/aurora/bench/metadata.jsonl', ROOT / 'data/aurora/bench/splits/seed_42.json',
               ROOT / 'data/aurora/bench/manifest.json']
    if reuse_collection_from:
        sources += [Path(reuse_collection_from) / 'manifest.json', Path(reuse_collection_from) / 'collection_results.json']
        sources += [Path(reuse_collection_from) / 'splits' / (name + '.json') for name in ('split1', 'split2', 'split3')]
    sources += [M0 / 'splits' / (part + '.json') for part in ('train', 'validation', 'test')]
    manifest = {'version': VERSION, 'protocol_ref': digest(protocol), 'cases': cases,
        'splits': {s['name']: digest(s) for s in splits}, 'excluded_groups': sorted(excluded),
        'code_hashes': {str(p.relative_to(ROOT)): fingerprint(p) for p in dict.fromkeys(code)},
        'source_hashes': {str(p.relative_to(ROOT)): fingerprint(p) for p in sources},
        'pool_counts': dict(Counter(r['reference'] for r in candidates)),
        'unique_inputs': len(cases), 'unique_sources': len({r['group'] for r in cases}), 'workers': 8, 'judge_identity': IDENTITY, 'caps': CAPS,
        'max_calls': 2 * len(cases)}
    for rel, h in manifest['code_hashes'].items():
        dst = out / 'source_snapshot' / rel; dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dst)
    exact(out / 'manifest.json', manifest); exact(out / 'seal.json', {'manifest_ref': digest(manifest)})
    overlap = {a['name'] + '/' + b['name']: len({r['group'] for r in a['train']} & {r['group'] for r in b['train']})
               for i, a in enumerate(splits) for b in splits[i + 1:]}
    exact(out / 'estimate.json', {'unique_inputs': len(cases), 'unique_sources': len({r['group'] for r in cases}), 'source_slots': 180, 'training_pair_overlap': overlap,
        'globally_disjoint_evaluation_sources': 36, 'max_new_calls': protocol['max_new_calls'],
        'max_image_calls': len(cases), 'max_completion_tokens': protocol['max_completion_tokens'],
        'reserved_test_calls': 0, 'historical_exposure_statuses': dict(Counter(r['historical_exposure_status'] for r in cases)),
        'existing_evidence_cache': 0, 'model': IDENTITY})
    verify(out, manifest); return manifest


def verify(out, manifest):
    if digest(manifest) != read(out / 'seal.json')['manifest_ref'] or manifest['version'] != VERSION:
        raise ValueError('Changed replication manifest')
    if digest(read(out / 'protocol.json')) != manifest['protocol_ref']:
        raise ValueError('Changed replication protocol')
    for rel, h in manifest['code_hashes'].items():
        if fingerprint(ROOT / rel) != h or fingerprint(out / 'source_snapshot' / rel) != h:
            raise ValueError('Frozen implementation changed: ' + rel)
    for rel, h in manifest['source_hashes'].items():
        if fingerprint(ROOT / rel) != h:
            raise ValueError('Frozen source changed: ' + rel)
    splits = [read(out / 'splits' / (name + '.json')) for name in manifest['splits']]
    if any(digest(s) != manifest['splits'][s['name']] for s in splits):
        raise ValueError('Changed sampled split')
    assert_splits(splits, manifest['excluded_groups'])
    by_case = {row['case']: row for row in manifest['cases']}
    for split in splits:
        for part in ('train', 'evaluation'):
            for row in split[part]:
                cached = by_case[row['case']]
                assert all(row[k] == cached[k] for k in ('id', 'instruction', 'reference', 'group', 'image_hashes'))
    # Public release hashes and decoded source pixels protect source identity.
    from run.calitree_m0 import pixel_hash
    release = read(ROOT / 'data/aurora/bench/manifest.json')
    for row in manifest['cases']:
        if pixel_hash(row['evidence']['source_image']) != row['group']:
            raise ValueError('Source pixel identity changed')
        for role, path in row['evidence'].items():
            rel = str(Path(path).relative_to(ROOT / 'data/aurora/bench'))
            if fingerprint(path) != row['image_hashes'][role] or row['image_hashes'][role] != release['files'][rel]['sha256']:
                raise ValueError('Public image bytes changed')


def validate_settings():
    from critical.lm_engine.provider_api import chat_request
    _, body, _, _ = chat_request('https://api.openai.com/v1', 'not-a-key', IDENTITY['model'], [],
                                INTERPRET_CAP, IDENTITY['temperature'], provider='openai')
    if any(body.get(k) != IDENTITY[k] for k in ('model', 'temperature', 'reasoning_effort')):
        raise ValueError('Declared Luna profile differs from adapter wire settings')


def model_factory(directory, live):
    from critical import config
    from critical.lm_engine import get_engine, load_creds, require_live
    from critical.logging.llm_history import LLMHistoryWriter
    config.PROJECT_ROOT = ROOT; config.CREDENTIALS_FILE = ROOT / '.env'
    creds = None
    if live:
        require_live(True); creds = load_creds(provider='openai', engine='gpt')
        if creds.provider != 'openai' or creds.endpoints != ['https://api.openai.com/v1']:
            raise ValueError('Official OpenAI endpoint only')
    def factory(cap):
        if not live:
            raise AssertionError('Offline replay attempted a model call')
        # The adapter supplies reasoning=none for Luna; explicit effort is only
        # supported for Sol. validate_settings checks the actual wire profile.
        return get_engine('gpt', creds=creds, model=IDENTITY['model'], temperature=IDENTITY['temperature'],
            max_tokens=cap, timeout=180, max_http_attempts=1,
            history=LLMHistoryWriter(directory / 'llm-histories.log'))
    return factory


def collect_physical(output, manifest, live):
    def work(case):
        target = output / 'cases' / (case['case'] + '.json')
        if target.exists():
            return read(target)
        row = {'case': case['case'], 'compilation': None, 'observation': None, 'record': None,
               'error': None, 'diagnostic': {'prediction': -1, 'label': 'Unresolved', 'reason': 'missing_evidence'}}
        for stage in ('compile', 'observe'):
            directory = output / 'ledgers' / case['case'] / stage
            calls = DurableCalls(directory, model_factory(directory, live), identity=IDENTITY,
                max_calls=1, max_completion_tokens=CAPS[stage], scope_limits={'search': 1, 'final': 1})
            try:
                if stage == 'compile':
                    row['compilation'] = BoundInstructionCompiler(calls).compile(case['instruction'],
                        case_id=case['id'], max_tokens=CAPS[stage])
                else:
                    program = row['compilation']['program']
                    row['observation'] = BoundVisualObserver(calls).observe(program, case['evidence'],
                        case_id=case['id'], max_tokens=CAPS[stage])
                    row['record'] = derive_record(program, row['observation']['observation'], image_identity(case['evidence'])[1])
                    row['diagnostic'] = diagnostic_readout(row['record'])
            except (RuntimeError, ValueError, KeyError, TypeError) as exc:
                row['error'] = {'stage': stage, 'code': getattr(exc, 'code', type(exc).__name__), 'message': str(exc)}
                jobs = list((directory / 'jobs').glob('*.json'))
                if jobs and (job := read(jobs[0]))['outcome'] != 'completed':
                    row['error'] = {'stage': stage, 'code': job['outcome'], 'message': job.get('error') or job['outcome']}
                break
        exact(target, row)
        print({'case': case['case'], 'compiled': row['compilation'] is not None,
               'observed': row['record'] is not None, 'error': row['error']}, flush=True)
        return row
    with ThreadPoolExecutor(max_workers=manifest['workers']) as pool:
        return list(pool.map(work, manifest['cases']))


def interpret_one(out, row, observed, live):
    target = out / 'interpretations' / (row['case'] + '.json')
    if target.exists():
        return read(target)
    if not observed['record']:
        value = {'case': row['case'], 'interpretation': None, 'error': 'missing_original_observation', 'execution_ref': None}
        exact(target, value); return value
    directory = out / 'interpretation_ledgers' / row['case']
    factory = model_factory(directory, live)
    payload = make_input(observed['compilation']['program'], observed['observation']['observation'], image_identity(row['evidence'])[1])
    calls = DurableCalls(directory, factory, identity=IDENTITY, max_calls=1, max_completion_tokens=INTERPRET_CAP,
                         scope_limits={'search': 1, 'final': 1})
    try:
        result, ref = calls.call('instruction_relative_interpretation', payload, schema(payload), template=PROMPT,
            slot='once', max_tokens=INTERPRET_CAP, case_id=row['case'])
        validate(payload, result)
        value = {'case': row['case'], 'interpretation': result, 'error': None, 'execution_ref': ref}
    except Exception as exc:
        value = {'case': row['case'], 'interpretation': None, 'error': type(exc).__name__ + ': ' + str(exc), 'execution_ref': None}
    exact(target, value)
    print({'case': row['case'], 'interpreted': value['interpretation'] is not None}, flush=True)
    return value


def collect_all(out, manifest, live):
    extraction = out / 'extraction'
    if (extraction / 'observations.json').exists():
        observations = read(extraction / 'observations.json')
    else:
        # The first durable slot verifies provider availability before dispatching
        # the batch. An upstream/network/auth failure ends the run, with no retries.
        if live:
            first = collect_physical(extraction, {**manifest, 'cases': manifest['cases'][:1], 'workers': 1}, True)[0]
            if not first['compilation'] or (first.get('error') or {}).get('code') in ('failed', 'interrupted'):
                raise RuntimeError('First collection slot did not establish provider availability; inspect its saved error before continuing')
        observations = collect_physical(extraction, manifest, live)
        exact(extraction / 'observations.json', observations)
    audit = audit_payloads(extraction, manifest, observations)
    by_case = {r['case']: r for r in observations}
    with ThreadPoolExecutor(max_workers=manifest['workers']) as pool:
        interpretations = list(pool.map(lambda row: interpret_one(out, row, by_case[row['case']], live), manifest['cases']))
    exact(out / 'interpretations.json', interpretations)
    meanings = {r['case']: r for r in interpretations}
    records = {}
    for row in manifest['cases']:
        obs = by_case[row['case']]; interpretation = meanings[row['case']]['interpretation']
        feature = project(obs['compilation']['program'], obs['observation']['observation'],
            image_identity(row['evidence'])[1], interpretation) if obs['record'] else None
        records[row['case']] = {'case': row['case'], 'source_group': row['group'], 'instruction': row['instruction'],
            'reference': LABELS.index(row['reference']), 'features': feature}
    exact(out / 'portable_records.json', records)
    jobs = [read(p) for p in out.glob('interpretation_ledgers/*/jobs/*.json')]
    # Inspect every interpretation payload against its label-free expected input.
    for row in manifest['cases']:
        obs = by_case[row['case']]
        found = [j for j in jobs if j['case_id'] == row['case']]
        if obs['record']:
            expected = make_input(obs['compilation']['program'], obs['observation']['observation'], image_identity(row['evidence'])[1])
            assert len(found) == 1 and found[0]['payload'] == expected and not found[0]['media_identity']
        else:
            assert not found
    summary = {'physical': usage(extraction), 'physical_payload_audit': audit,
        'semantic': {'attempts': len(jobs), 'valid': sum(r['interpretation'] is not None for r in interpretations),
            'input_tokens': sum((j.get('response') or {}).get('promptTokens', 0) or 0 for j in jobs),
            'completion_tokens': sum((j.get('response') or {}).get('completionTokens', 0) or 0 for j in jobs)},
        'unique_inputs': len(records), 'unique_sources': len({r['group'] for r in manifest['cases']}), 'missing_portable_records': sum(r['features'] is None for r in records.values()),
        'unresolved_records': sum(r['features'] is None or not r['features']['features']['meaning_available'] for r in records.values()),
        'attempts': sum(v['attempts'] for v in usage(extraction).values()) + len(jobs),
        'max_calls': 3 * len(records), 'reference_labels_in_payload': False, 'reserved_test_calls': 0}
    exact(out / 'collection_results.json', summary); verify(out, manifest); return records


def fit_one(out, name, replay=False):
    manifest = prepare(out)
    split = read(out / 'splits' / (name + '.json')); records = read(out / 'portable_records.json')
    train = [{**records[r['case']], 'batch': r['batch']} for r in split['train']]
    directory = out / name
    exact(directory / 'training_data.json', train)
    fits = ReuseFits(directory, replay); runs = {}
    for run_name, method in METHODS.items():
        groups = method(train); validate_partition(groups, train)
        exact(directory / run_name / 'groups.json', groups)
        started = time.monotonic()
        try:
            result = learn(train, groups, 'reuse', fits,
                lambda key, value: exact(directory / run_name / (key + '.json'), value))
            exact(directory / run_name / 'result.json', result)
            runs[run_name] = result
        except ValueError as exc:
            # Preserve failed runs under the original limits; no resampling.
            exact(directory / run_name / 'failure.json', {'error': str(exc), 'limits': LIMITS})
            runs[run_name] = None
        print({'split': name, 'run': run_name, 'seconds': round(time.monotonic() - started, 1),
               'complete_root': bool(runs[run_name] and runs[run_name]['root_candidates'])}, flush=True)
    alternatives = [(run_name, result['registry'][k]) for run_name, result in runs.items() if result
                    for k in result['root_candidates']]
    chosen = min(alternatives, key=lambda pair: (*selection_key(pair[0], {'root': pair[1]}), pair[1]['node_id'])) if alternatives else None
    # Fit the direct control and choose its depth from training metrics only.
    flat_fits = UnionFits(directory / 'direct_control', replay)
    cold = [flat_fits.cold(train, 'constrained', profile) for profile in ('compact', 'deep')]
    direct = min((r['result'] for r in cold if r['result'] and r['result']['portable']), key=rank, default=None)
    frozen = {'merged': chosen[1]['runtime'] if chosen else None, 'direct': direct['runtime'] if direct else None,
              'original_v11': read(PREVIOUS / 'deployment_policy.json')}
    exact(directory / 'frozen_policies.json', frozen)
    selection = {'selected_run': chosen[0] if chosen else None, 'node_id': chosen[1]['node_id'] if chosen else None,
        'training': chosen[1]['metrics'] if chosen else None, 'root_mode': chosen[1]['reuse']['kind'] if chosen else None,
        'training_sources': [r['source_group'] for r in train], 'selection_used_evaluation': False,
        'frozen_policies_ref': digest(frozen), 'feature_contract_ref': CONTRACT_REF}
    exact(directory / 'selected_training_root.json', selection)
    if chosen:
        selected_result = runs[chosen[0]]; order = merge_order(selected_result, chosen[1])
        steps = []
        for i, node_id in enumerate(order, 1):
            n = selected_result['registry'][node_id]
            cohort = [r for r in train if r['source_group'] in set(n['fit_sources'])]
            decision = gate(n, [selected_result['registry'][k] for k in n['children']], cohort)
            assert decision['status'] == 'accepted'
            steps.append({'step': i, 'node_id': node_id, 'sources': len(cohort), 'correct': n['metrics']['correct'],
                          'mode': n['reuse']['kind'], 'rules': n['complexity']['rules'], 'decision': decision})
        exact(directory / 'selected_merge_table.json', steps)
    # Evaluation references are accessed only after frozen artifacts were saved.
    evaluation = [{**records[r['case']], 'batch': 'evaluation'} for r in split['evaluation']]
    arm_results = {}
    for arm, policy in frozen.items():
        ps = PortableRuleExecutor(policy).predict_records([r['features'] for r in evaluation]) if policy else [
            {'prediction': -1, 'trace': [], 'reason': 'no_qualifying_complete_policy'} for r in evaluation]
        arm_results[arm] = {'available': policy is not None,
            'metrics': metrics([r['prediction'] for r in ps], [r['reference'] for r in evaluation]),
            'cases': [{'case': r['case'], 'source_group': r['source_group'], 'instruction': r['instruction'],
                       'reference': r['reference'], **p} for r, p in zip(evaluation, ps)],
            'rules': None}
        if policy:
            def leaves(n):
                return leaves(n['true']) + leaves(n['false']) if 'feature' in n else 1
            arm_results[arm]['rules'] = leaves(policy['tree'])
    result = {'split': name, 'seed': split['seed'], 'selection': selection, 'arms': arm_results,
        'direct_training': direct['metrics'] if direct else None,
        'runs': {key: {'complete': bool(value and value['root_candidates']),
            'root_candidates': len(value['root_candidates']) if value else 0,
            'candidate_pairs': value['proposal_count'] if value else None,
            'accepted_candidates': value['accepted_proposals'] if value else None} for key, value in runs.items()},
        'missing_training': sum(r['features'] is None for r in train),
        'missing_evaluation': sum(r['features'] is None for r in evaluation),
        'reserved_test_predictions': 0, 'selection_used_evaluation': False}
    exact(directory / 'results.json', result)
    print({'split': name, 'selected_run': selection['selected_run'], 'local_correct': (selection['training'] or {}).get('correct'),
           'evaluation': {arm: v['metrics']['correct'] for arm, v in arm_results.items()}}, flush=True)
    return result


def summarize(out):
    manifest = prepare(out); results = [read(out / ('split' + str(i)) / 'results.json') for i in (1, 2, 3)]
    merged_rows = [row for result in results for row in result['arms']['merged']['cases']]
    assert len(merged_rows) == 36 and len({r['source_group'] for r in merged_rows}) == 36
    pooled = {}
    for arm in ('merged', 'direct', 'original_v11'):
        rows = [r for result in results for r in result['arms'][arm]['cases']]
        pooled[arm] = metrics([r['prediction'] for r in rows], [r['reference'] for r in rows])
    paired = Counter()
    for result in results:
        for a, b in zip(result['arms']['merged']['cases'], result['arms']['direct']['cases']):
            assert a['case'] == b['case'] and a['reference'] == b['reference']
            ca, cb = a['prediction'] == a['reference'], b['prediction'] == b['reference']
            paired['both_correct' if ca and cb else 'merged_only' if ca else 'direct_only' if cb else 'both_wrong'] += 1
    report = {'version': VERSION, 'replications': results, 'pooled_evaluation': pooled,
        'paired_merge_vs_direct': dict(paired), 'completed_hierarchies': sum(r['selection']['node_id'] is not None for r in results),
        'estimate': read(out / 'estimate.json'), 'collection': read(out / 'collection_results.json'),
        'reserved_test_predictions': 0, 'evaluation_sources_globally_excluded_from_training': True,
        'caveat': 'Three correlated training samples and small balanced evaluation cohorts, with historical exposure disclosed. No evaluation-guided retries or selection.'}
    exact(out / 'results.json', report)
    lines = ['# Three sampled CaliTree pipeline replications', '',
        'Same M1 v2 / interpretation v5 / portable v8 / reuse-first M5–M7 v11 pipeline. '
        'Three new 48-training / 12-evaluation samples; source-disjoint from the original 60 and reserved 50. '
        'All 36 evaluation sources are mutually disjoint and excluded from every training sample. '
        'Training cohorts overlap; cached source evidence is shared consistently. Historical exposure is disclosed.', '',
        '| Split | Merged training | Merged evaluation | Direct training | Direct evaluation | Root mode | Rules merge/direct |',
        '|---|---|---|---|---|---|---|']
    for r in results:
        m = r['selection']['training']; d = r['direct_training']
        lines.append(f"| {r['split']} | {str(m['correct']) + '/48' if m else 'No complete root'} | "
            f"{r['arms']['merged']['metrics']['correct']}/12 | {str(d['correct']) + '/48' if d else 'Unavailable'} | "
            f"{r['arms']['direct']['metrics']['correct']}/12 | {r['selection']['root_mode']} | "
            f"{r['arms']['merged']['rules']} / {r['arms']['direct']['rules']} |")
    lines += ['', 'Pooled across 36 distinct evaluation sources:', '']
    for arm, metric in pooled.items():
        lines.append(f"- {arm}: {metric['correct']}/36 ({metric['accuracy']:.1%}); macro-F1 {metric['macro_f1']:.3f}; unresolved {metric['unresolved']}.")
    lines += ['', 'Paired merge versus direct: ' + json.dumps(dict(paired)) + '.', '',
        'Original frozen v11 is a reference arm trained on different data, not a matched-training comparison. '
        'No final-fifty predictions, resampling after failures, relaxed acceptance gates, or evaluation-based root choice.', '',
        '## Sampling and cost accounting', '', '```json', json.dumps(read(out / 'estimate.json'), indent=2), '```', '',
        '```json', json.dumps(read(out / 'collection_results.json'), indent=2), '```', '',
        '## Interpretation', '', report['caveat'], '',
        'The paired merged/direct comparison evaluates the complete learning procedures, including their '
        'selection policies and bounded searches. It does not isolate one individual merge operation. '
        'Keep fitting agreement, hierarchy feasibility, rule reuse/compression, and evaluation agreement separate.']
    (out / 'report.md').write_text('\n'.join(lines) + '\n')
    print({'completed_hierarchies': report['completed_hierarchies'],
           'pooled_correct': {k: v['correct'] for k, v in pooled.items()}, 'paired': dict(paired)}, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--mode', choices=('preflight', 'collect', 'train', 'summary', 'all'), default='preflight')
    parser.add_argument('--split', choices=('split1', 'split2', 'split3'))
    parser.add_argument('--reuse-collection-from', type=Path)
    parser.add_argument('--live', action='store_true'); parser.add_argument('--replay', action='store_true')
    args = parser.parse_args(); out = args.output_dir.resolve(); manifest = prepare(out, args.reuse_collection_from)
    if args.mode == 'preflight':
        print(read(out / 'estimate.json')); return
    if args.mode in ('collect', 'all'):
        if not (args.live or args.replay):
            parser.error('Collection requires --live or --replay')
        collect_all(out, manifest, args.live)
    if args.mode in ('train', 'all'):
        for name in (args.split,) if args.split else ('split1', 'split2', 'split3'):
            fit_one(out, name, args.replay)
    if args.mode in ('summary', 'all'):
        summarize(out)


if __name__ == '__main__':
    main()
