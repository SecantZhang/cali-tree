"""Matched 36-case flat versus frozen rich-evidence CaliTree evaluation.

CaliTree here is the latest rich-evidence + constrained-policy experiment, not
the separate legacy weighted-fulfillment per-case optimizer or a merged hierarchy.
No labels from these evaluation sources enter fitting or inference.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
import json
import shutil

from critical.core.calibration.rich_local_rules import RichLocalRuleCalibrator
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.calls import DurableCalls
from critical.core.decision.compiler import media_inputs
from critical.core.decision.rich_evidence import RichEvidenceExtractor, SCHEMA as RICH_SCHEMA, prompt as rich_prompt
from critical.database.dl_aurora.loader import AURORA_MODELS, score_to_label
from run.calitree_single_call import CAP, IDENTITY, ROOT, fingerprint, metrics, paired_comparison, read


VERSION = 'flat-vs-frozen-rich-calitree-balanced36-v1'
POLICY_DIRECTORY = ROOT / 'logs/exps/261013-rich-local-evidence-v2'
FLAT_DIRECTORY = ROOT / 'logs/exps/261013-flat-sol-high-balanced12'
CALIBRATION_DIRECTORY = ROOT / 'logs/exps/261013-batch-evidence-calibration-v1'
SEED = 20261013
PER_CLASS = 12
FLAT_SCHEMA = {'type': 'object', 'properties': {
    'rationale': {'type': 'string'},
    'label': {'type': 'string', 'enum': ['no', 'partial', 'yes', 'unresolved']}},
    'required': ['rationale', 'label'], 'additionalProperties': False}


def load_policy():
    seal = read(POLICY_DIRECTORY / 'policy_seal.json')
    artifact = read(POLICY_DIRECTORY / seal['path'])
    if digest(artifact) != seal['artifact_ref']: raise ValueError('Changed original frozen policy artifact')
    model = RichLocalRuleCalibrator.restore(artifact['policies']['rich'])
    return model, artifact, seal


def select_cases(candidates, excluded, *, per_class=PER_CLASS):
    selected, used, tasks = [], set(), Counter()
    for _ in range(per_class):
        for label in ('no', 'partial', 'yes'):
            available = [r for r in candidates if r['reference'] == label and r['group'] not in used | set(excluded)]
            if not available: raise ValueError('Insufficient distinct-source cases for ' + label)
            row = min(available, key=lambda r: (tasks[r['task']], digest([VERSION, SEED, r['id']])))
            selected.append({**row, 'case': f'E{len(selected)+1:02d}'})
            used.add(row['group']); tasks[row['task']] += 1
    return selected


def sample():
    from PIL import Image
    flat = read(FLAT_DIRECTORY / 'manifest.json')
    calibration = read(CALIBRATION_DIRECTORY / 'manifest.json')
    excluded = set(flat['excluded_groups']) | {r['group'] for r in flat['cases']}
    excluded |= {r['group'] for r in calibration['calibration_cases']}
    official_test = set(read(ROOT / 'data/aurora/bench/splits/seed_42.json')['test'])
    candidates, groups = [], {}
    for row in map(json.loads, (ROOT / 'data/aurora/bench/metadata.jsonl').read_text().splitlines()):
        if row['model'] != AURORA_MODELS[0] or row['task_uid'] not in official_test: continue
        source = ROOT / 'data/aurora/bench' / row['source_path']
        if str(source) not in groups:
            with Image.open(source) as image:
                rgb = image.convert('RGB'); groups[str(source)] = sha256(str(rgb.size).encode()+rgb.tobytes()).hexdigest()
        group = groups[str(source)]
        if group in excluded: continue
        images = {'source_image': str(source), 'edited_image': str(ROOT / 'data/aurora/bench' / row['edited_path'])}
        candidates.append({'id': row['item_id'], 'task_uid': row['task_uid'], 'group': group,
                           'instruction': row['instruction'], 'task': row['task'], 'editing_model': row['model'],
                           'human_score': row['human_score'], 'reference': score_to_label(row['human_score'])[1],
                           'evidence': images, 'image_hashes': {k: fingerprint(p) for k, p in images.items()}})
    return select_cases(candidates, excluded), sorted(excluded)


def prepare(output):
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'manifest.json').exists():
        m = read(output / 'manifest.json'); verify(output, m); return m
    _, artifact, seal = load_policy()
    if rich_prompt() != (POLICY_DIRECTORY / 'prompt.txt').read_text():
        raise ValueError('Current extractor differs from frozen fitted extractor')
    previous_manifest = read(POLICY_DIRECTORY / 'manifest.json')
    if previous_manifest['judge_identity'] != IDENTITY or previous_manifest['schema_ref'] != digest(RICH_SCHEMA):
        raise ValueError('Changed rich extraction identity/schema')
    flat_manifest = read(FLAT_DIRECTORY / 'manifest.json')
    if fingerprint(FLAT_DIRECTORY / 'prompt.txt') != flat_manifest['prompt_sha256']:
        raise ValueError('Changed fixed flat baseline prompt')
    cases, excluded = sample()
    files = [p for p in (ROOT / 'critical').rglob('*') if p.is_file() and p.suffix in ('.py', '.txt', '.json')]
    files += [Path(__file__).resolve(), ROOT / 'run/calitree_single_call.py']
    code = {}
    for source in files:
        rel = str(source.relative_to(ROOT)); dst = output / 'source_snapshot' / rel
        dst.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, dst); code[rel] = fingerprint(source)
    (output / 'flat_prompt.txt').write_text((FLAT_DIRECTORY / 'prompt.txt').read_text())
    (output / 'rich_prompt.txt').write_text(rich_prompt())
    save_json(output / 'frozen_policy.json', artifact)
    pinned = [POLICY_DIRECTORY / 'manifest.json', POLICY_DIRECTORY / 'policy_seal.json',
              POLICY_DIRECTORY / seal['path'], POLICY_DIRECTORY / 'results.json',
              FLAT_DIRECTORY / 'manifest.json', FLAT_DIRECTORY / 'prompt.txt',
              CALIBRATION_DIRECTORY / 'manifest.json']
    m = {'version': VERSION, 'cases': cases, 'excluded_groups': excluded, 'seed': SEED,
         'judge_identity': IDENTITY, 'workers': 4, 'max_calls': 72, 'max_completion_tokens_per_call': CAP,
         'presentation': 'source_first', 'draws_per_arm_per_case': 1, 'http_attempts_per_slot': 1,
         'policy_seal': seal, 'policy_ref': digest(artifact), 'code_hashes': code,
         'pinned_files': {str(p): fingerprint(p) for p in pinned},
         'flat_prompt_ref': digest((output / 'flat_prompt.txt').read_text()), 'flat_schema_ref': digest(FLAT_SCHEMA),
         'rich_prompt_ref': digest(rich_prompt()), 'rich_schema_ref': digest(RICH_SCHEMA),
         'metadata_sha256': fingerprint(ROOT / 'data/aurora/bench/metadata.jsonl'),
         'split_sha256': fingerprint(ROOT / 'data/aurora/bench/splits/seed_42.json'),
         'pipeline': 'Rich label-blind evidence v2 + frozen constrained rule policy, learned on original twelve sources; no refitting, leaf repair or hierarchy merging.',
         'sampling': '12/class, official seed-42 test tasks, AURORA editor only, unique source pixels, category spreading + deterministic hash ties. Exclude original twelve, earlier fitting sources, reserved fifty and calibration thirty-six.',
         'scope': 'Source-disjoint from listed fitting sets; historically queried project examples may remain. Not a globally untouched benchmark. One draw per case does not establish repeat robustness.',
         'authorization': 'Check the current pipeline on 36 cases baseline vs CaliTree comparison',
         'interpretation': 'Latest experimental rich-evidence pipeline; separate evaluation sources and frozen policy selected after optional clarification window.'}
    save_json(output / 'manifest.json', m); save_json(output / 'seal.json', {'manifest_ref': digest(m)})
    save_json(output / 'estimate.json', {'max_new_calls': 72, 'calls_per_arm': 36,
              'max_completion_tokens': 72*CAP, 'output_token_cost_ceiling_usd': 72*CAP*10/1_000_000,
              'input_cost': 'Additional text/image input usage, reported after execution.',
              'pricing_source': 'https://developers.openai.com/api/docs/models/gpt-6.1-sol'})
    verify(output, m); return m


def verify(output, m):
    if (digest(m) != read(output / 'seal.json')['manifest_ref'] or m['version'] != VERSION
            or m['judge_identity'] != IDENTITY or digest(read(output / 'frozen_policy.json')) != m['policy_ref']
            or m['rich_prompt_ref'] != digest(rich_prompt()) or m['rich_schema_ref'] != digest(RICH_SCHEMA)
            or m['flat_schema_ref'] != digest(FLAT_SCHEMA)
            or m['flat_prompt_ref'] != digest((output / 'flat_prompt.txt').read_text())
            or rich_prompt() != (output / 'rich_prompt.txt').read_text()):
        raise ValueError('Changed frozen benchmark protocol')
    cases = m['cases']; groups = {r['group'] for r in cases}
    if (len(cases) != 36 or len(groups) != 36 or groups & set(m['excluded_groups'])
            or Counter(r['reference'] for r in cases) != {'no': 12, 'partial': 12, 'yes': 12}):
        raise ValueError('Changed balanced/source-disjoint sample')
    test = set(read(ROOT / 'data/aurora/bench/splits/seed_42.json')['test'])
    for r in cases:
        if r['task_uid'] not in test or r['editing_model'] != AURORA_MODELS[0] or score_to_label(r['human_score'])[1] != r['reference']:
            raise ValueError('Changed source/reference semantics')
        for key, path in r['evidence'].items():
            if fingerprint(path) != r['image_hashes'][key]: raise ValueError('Changed image')
    for path, expected in m['pinned_files'].items():
        if fingerprint(path) != expected: raise ValueError('Changed original policy/prompt/fit manifest')
    for rel, expected in m['code_hashes'].items():
        if fingerprint(ROOT / rel) != expected or fingerprint(output / 'source_snapshot' / rel) != expected:
            raise ValueError('Changed frozen source: ' + rel)
    if (fingerprint(ROOT / 'data/aurora/bench/metadata.jsonl') != m['metadata_sha256']
            or fingerprint(ROOT / 'data/aurora/bench/splits/seed_42.json') != m['split_sha256']):
        raise ValueError('Changed dataset')


def infer_arm(case, arm, calls, *, policy, flat_prompt):
    """Only instruction and image inputs reach either model call."""
    if arm == 'flat':
        value, ref = calls.call('flat_judge', {'instruction': case['instruction']}, FLAT_SCHEMA,
                                template=flat_prompt, media=media_inputs(case['evidence']),
                                case_id=case['id'], slot='once', max_tokens=CAP)
        if value.get('label') not in ('no', 'partial', 'yes', 'unresolved') or not isinstance(value.get('rationale'), str):
            raise ValueError('Invalid flat response')
        return {'prediction': None if value['label'] == 'unresolved' else value['label'],
                'rationale': value['rationale'], 'execution_ref': ref}
    if arm != 'calitree': raise ValueError('Unknown benchmark arm')
    extraction = RichEvidenceExtractor(calls).extract(case['instruction'], case['evidence'], case_id=case['id'], max_tokens=CAP)
    decision = policy.predict_records([{'instruction': case['instruction'], 'observations': extraction['observations']}])[0]
    return {'prediction': decision['label'], 'extraction': extraction, 'decision': decision,
            'execution_ref': extraction['execution_ref']}


def run(output, m, live):
    from critical import config
    from critical.lm_engine import get_engine, load_creds, require_live
    from critical.logging.llm_history import LLMHistoryWriter
    config.PROJECT_ROOT = ROOT; config.CREDENTIALS_FILE = ROOT / '.env'
    policy = RichLocalRuleCalibrator.restore(read(output / 'frozen_policy.json')['policies']['rich'])
    creds = None
    if live:
        require_live(True); creds = load_creds(provider='openai', engine='gpt')
        if creds.provider != 'openai' or creds.endpoints != ['https://api.openai.com/v1']: raise ValueError('Official OpenAI required')
    tasks = []
    for i, case in enumerate(m['cases']):
        tasks += [(case, arm) for arm in (('flat', 'calitree') if i % 2 == 0 else ('calitree', 'flat'))]
    def work(task):
        case, arm = task; directory = output / 'ledgers' / case['case'] / arm
        if not live and not list((directory / 'jobs').glob('*.json')): raise ValueError('Missing replay slot')
        def factory(cap):
            if not live: raise AssertionError('Replay called the provider')
            return get_engine('gpt', creds=creds, model=IDENTITY['model'], reasoning_effort='high',
                              temperature=None, max_tokens=cap, timeout=180, max_http_attempts=1,
                              history=LLMHistoryWriter(directory / 'llm-histories.log'))
        calls = DurableCalls(directory, factory, identity=IDENTITY, max_calls=1,
                             max_completion_tokens=CAP, scope_limits={'search': 1, 'final': 1})
        row = {k: case[k] for k in ('case', 'id', 'instruction', 'reference')}
        row.update(arm=arm, prediction=None, error=None)
        try: row.update(infer_arm(case, arm, calls, policy=policy, flat_prompt=(output / 'flat_prompt.txt').read_text()))
        except (RuntimeError, ValueError, KeyError, TypeError) as exc:
            row['error'] = type(exc).__name__ + ': ' + str(exc)
            jobs = list((directory / 'jobs').glob('*.json'))
            if jobs and (job := read(jobs[0]))['outcome'] != 'completed': row['error'] = job.get('error') or job['outcome']
        print({k: row[k] for k in ('case', 'arm', 'prediction', 'error')}, flush=True)
        return row
    with ThreadPoolExecutor(max_workers=m['workers']) as pool: values = list(pool.map(work, tasks))
    rows = {arm: [next(r for r in values if r['id'] == c['id'] and r['arm'] == arm) for c in m['cases']]
            for arm in ('flat', 'calitree')}
    jobs = {arm: [read(p) for p in sorted((output / 'ledgers').glob('*/'+arm+'/jobs/*.json'))] for arm in rows}
    usage = {}
    for arm in rows:
        responses = [j['response'] for j in jobs[arm] if j.get('response')]
        usage[arm] = {'attempts': len(jobs[arm]), 'outcomes': dict(Counter(j['outcome'] for j in jobs[arm])),
                      'input_tokens': sum(r.get('promptTokens', 0) for r in responses),
                      'completion_tokens': sum(r.get('completionTokens', 0) for r in responses),
                      'returned_models': sorted({r.get('model', 'unknown') for r in responses})}
    return {'version': VERSION, 'model': IDENTITY, 'pipeline': m['pipeline'], 'scope': m['scope'],
            'flat_metrics': metrics(rows['flat']), 'calitree_metrics': metrics(rows['calitree']),
            'paired': paired_comparison({'cases': rows['flat']}, rows['calitree']), 'cases': rows,
            'usage': usage, 'policy_ref': m['policy_ref'], 'refitted_on_evaluation': False}


def report(output, result, m):
    lines = ['# Flat versus current rich-evidence CaliTree: 36-case comparison', '',
             'CaliTree means the latest experimental rich evidence v2 extractor plus the frozen constrained policy from the original twelve sources.',
             'This does not run the separate canonical weighted-fulfillment leaf optimizer or hierarchy merging.',
             'Same 36 AURORA-editor outputs, 12 per class; same GPT-6.1 Sol/high profile, one SOURCE-first response per arm/case.',
             'Policy frozen before sampling/calls; no evaluation-label fitting or prompt tuning.', '',
             '| Arm | Correct | No recall | Partial recall | Yes recall | Resolved |', '|---|---:|---:|---:|---:|---:|']
    for name, key in [('Flat', 'flat_metrics'), ('CaliTree frozen rich policy', 'calitree_metrics')]:
        v = result[key]; recalls = ' | '.join(f"{v['per_class_recall'][k]:.1%}" for k in ('no','partial','yes'))
        lines.append(f"| {name} | {v['correct']}/36 ({v['accuracy']:.1%}) | {recalls} | {v['resolved']}/36 |")
    p = result['paired']
    lines += ['', f"Paired improvements: {p['wins']}; regressions: {p['losses']}; net difference {p['accuracy_difference']:+.1%}.",
              f"Exact paired McNemar p={p['mcnemar_exact_two_sided_p']:.3f}.", '',
              '| Case | Task | Instruction | Reference | Flat | CaliTree |', '|---|---|---|---|---|---|']
    for c, a, b in zip(m['cases'], result['cases']['flat'], result['cases']['calitree']):
        lines.append(f"| {c['case']} | {c['task']} | {c['instruction'].replace('|','/')} | {c['reference']} | {a['prediction'] or 'unresolved'} | {b['prediction'] or 'unresolved'} |")
    lines += ['', '## Scope and accounting', '',
              'Evaluation sources are disjoint from original twelve, previous fitting sources, reserved fifty-case holdout, and the separate calibration thirty-six. Historically queried project examples may remain; this is not globally untouched data.',
              'Human classes come from aggregate means discretized at 0.5/1.5, not individual-vote majorities.',
              'Failed and unresolved records stay in the 36-case denominator. One draw per arm/case does not measure repeat robustness.',
              'Both arms request the same model alias/settings; separate calls need not share an identical provider backend snapshot.',
              'The original 10/12 was local fitting; this source-disjoint frozen-policy result measures a different question.', '',
              f"Usage: {result['usage']}", '', '## Case evidence', '']
    for a, b in zip(result['cases']['flat'], result['cases']['calitree']):
        lines += [f"### {a['case']}: {a['instruction']}", '',
                  f"Reference: {a['reference']}; flat: {a['prediction']}; CaliTree: {b['prediction']}.", '',
                  'Flat rationale: '+(a.get('rationale') or a.get('error') or 'No rationale.'), '']
        if b.get('extraction'):
            o = b['extraction']['observations']; lines += [f"CaliTree decision: {b['decision']}", '']
            lines += [f"- {name}: {fact['state']} — {fact['evidence']}" for name, fact in {**o['collateral'], 'visibility': o['verification_visibility']}.items()]
            lines += ['']
        else: lines += [b.get('error') or 'No valid evidence.', '']
    (output / 'report.md').write_text('\n'.join(lines))
    (output / 'llm-histories.log').write_text(''.join(p.read_text() for p in sorted((output / 'ledgers').glob('*/*/llm-histories.log'))))


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output-dir', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight', action='store_true'); mode.add_argument('--live', action='store_true'); mode.add_argument('--replay', action='store_true')
    args = parser.parse_args(); output = args.output_dir.resolve()
    if args.replay and not (output / 'results.json').exists(): raise ValueError('Replay requires saved results')
    m = prepare(output)
    if args.preflight:
        print({'ready': True, 'cases': 36, 'classes': dict(Counter(r['reference'] for r in m['cases'])),
               'tasks': dict(Counter(r['task'] for r in m['cases'])), 'max_calls': 72, 'policy_ref': m['policy_ref']}); return
    result = run(output, m, args.live); verify(output, m)
    if args.replay:
        if read(output / 'results.json') != result: raise ValueError('Replay changed benchmark results')
        save_json(output / 'verification.json', {'exact_replay': True, 'new_api_calls': 0,
                  'policy_and_old_caches_unchanged': True, 'results_sha256': fingerprint(output / 'results.json')})
        print({'exact_replay': True, 'new_api_calls': 0})
    else:
        if (output / 'results.json').exists() and read(output / 'results.json') != result: raise ValueError('Different saved results')
        save_json(output / 'results.json', result); report(output, result, m)
        print({k: result[k] for k in ('flat_metrics', 'calitree_metrics', 'paired', 'usage')})


if __name__ == '__main__': main()
