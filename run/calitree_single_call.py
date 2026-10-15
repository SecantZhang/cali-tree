"""Benchmark one shared evidence call + fixed policy against a saved flat run.

Preflight freezes cases, code, prompt and policy; live permits one attempt per
case; replay verifies saved observations and predictions without provider access.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from math import comb, sqrt
from pathlib import Path
import shutil
import sys

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.calls import DurableCalls
from critical.core.decision.single_call import (
    POLICY, SCHEMA, TEMPLATE, VERSION, SingleCallEvidenceJudge, prompt,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = ROOT / 'logs/exps/261013-flat-sol-high-balanced12'
IDENTITY = {'provider': 'openai', 'model': 'gpt-6.1-sol',
            'reasoning_effort': 'high', 'temperature': None}
CAP = 16384


def read(path):
    return json.loads(Path(path).read_text())


def fingerprint(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def verify_baseline(directory):
    manifest = read(directory / 'manifest.json')
    result = read(directory / 'results.json')
    if digest(manifest) != read(directory / 'seal.json')['manifest_ref']:
        raise ValueError('Flat manifest seal changed')
    if (manifest['judge_identity'] != IDENTITY or result['model'] != IDENTITY
            or manifest['presentation'] != 'source_first' or manifest['draws_per_case'] != 1
            or manifest['http_attempts_per_slot'] != 1 or manifest['max_completion_tokens_per_case'] != CAP):
        raise ValueError('Flat judge settings do not match the comparison protocol')
    cases = manifest['cases']
    if (len(cases) != 12 or Counter(c['reference'] for c in cases) != {'no': 4, 'partial': 4, 'yes': 4}
            or len({c['group'] for c in cases}) != 12):
        raise ValueError('Expected twelve source-independent class-balanced cases')
    if [r['id'] for r in result['cases']] != [c['id'] for c in cases]:
        raise ValueError('Flat result cases differ from the manifest')
    if fingerprint(directory / 'prompt.txt') != manifest['prompt_sha256']:
        raise ValueError('Flat prompt changed')
    if fingerprint(directory / 'run_benchmark.py') != manifest['runner_sha256']:
        raise ValueError('Flat runner changed')
    for case, row in zip(cases, result['cases']):
        if any(case[k] != row[k] for k in ('case', 'id', 'instruction', 'human_score', 'reference')):
            raise ValueError('Flat result metadata changed')
        job = read(directory / 'ledgers' / case['case'] / 'jobs' / (row['execution_ref'] + '.json'))
        if (job['outcome'] != 'completed' or job['parsed']['label'] != row['prediction']
                or job['payload'] != {'instruction': case['instruction']}):
            raise ValueError('Flat result does not match its saved response')
    if result['correct'] != sum(r['prediction'] == r['reference'] for r in result['cases']):
        raise ValueError('Invalid flat accuracy')
    return manifest, result


def prepare(output, baseline):
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'manifest.json').exists():
        manifest = read(output / 'manifest.json')
        if manifest['baseline_directory'] != str(baseline):
            raise ValueError('Changed comparison baseline')
        verify(output, manifest)
        return manifest
    flat, _ = verify_baseline(baseline)
    code = [p for p in (ROOT / 'critical').rglob('*')
            if p.is_file() and p.suffix in ('.py', '.txt', '.json')]
    code.append(Path(__file__).resolve())
    hashes = {}
    for source in code:
        rel = str(source.relative_to(ROOT))
        target = output / 'source_snapshot' / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        hashes[rel] = fingerprint(source)
    shutil.copyfile(TEMPLATE, output / 'prompt.txt')
    save_json(output / 'policy.json', POLICY)
    baseline_paths = [baseline / name for name in ('manifest.json', 'seal.json', 'results.json', 'prompt.txt', 'run_benchmark.py')]
    baseline_paths += list((baseline / 'ledgers').glob('*/jobs/*.json'))
    manifest = {
        'version': VERSION, 'judge_identity': IDENTITY, 'cases': flat['cases'],
        'baseline_directory': str(baseline), 'baseline_files': {str(p): fingerprint(p) for p in baseline_paths},
        'presentation': 'source_first', 'draws_per_case': 1, 'http_attempts_per_slot': 1,
        'max_calls': 12, 'workers': 4, 'max_completion_tokens_per_case': CAP,
        'prompt_sha256': fingerprint(output / 'prompt.txt'), 'schema_ref': digest(SCHEMA),
        'policy_ref': digest(POLICY), 'code_hashes': hashes,
        'authorization': 'Implement the single-call explicit evidence checks with a fixed label policy, and benchmark it against the flat judge on the same 12 cases using the same model and one presentation per case.',
        'comparison': 'Reuse the twelve saved flat judgments; twelve new evidence calls, no repeats or optimization.',
        'scope': 'Previously inspected diagnostic cases; human references are aggregate-mean classes. Not an untouched or repeat-robustness test.',
        'runtime': {'python': sys.version},
    }
    save_json(output / 'manifest.json', manifest)
    save_json(output / 'seal.json', {'manifest_ref': digest(manifest)})
    save_json(output / 'estimate.json', {
        'new_api_calls_max': 12, 'reused_flat_calls': 12,
        'max_completion_tokens': 12 * CAP,
        'output_token_cost_ceiling_usd': 12 * CAP * 10 / 1_000_000,
        'input_cost': 'Additional input text/image tokens; actual usage reported after execution.',
        'pricing_source': 'https://developers.openai.com/api/docs/models/gpt-6.1-sol',
    })
    verify(output, manifest)
    return manifest


def verify(output, manifest):
    if digest(manifest) != read(output / 'seal.json')['manifest_ref']:
        raise ValueError('Evidence manifest seal changed')
    if (manifest['version'] != VERSION or manifest['judge_identity'] != IDENTITY
            or manifest['schema_ref'] != digest(SCHEMA) or manifest['policy_ref'] != digest(POLICY)
            or read(output / 'policy.json') != POLICY
            or fingerprint(output / 'prompt.txt') != manifest['prompt_sha256']
            or prompt() != (output / 'prompt.txt').read_text()):
        raise ValueError('Changed frozen evidence judge protocol')
    flat, _ = verify_baseline(Path(manifest['baseline_directory']))
    if manifest['cases'] != flat['cases']:
        raise ValueError('Changed benchmark cases')
    for path, expected in manifest['baseline_files'].items():
        if fingerprint(path) != expected:
            raise ValueError('Changed saved flat baseline artifact')
    for case in manifest['cases']:
        for name, path in case['evidence'].items():
            if fingerprint(path) != case['image_hashes'][name]:
                raise ValueError('Changed benchmark image')
    for rel, expected in manifest['code_hashes'].items():
        if (fingerprint(ROOT / rel) != expected
                or fingerprint(output / 'source_snapshot' / rel) != expected):
            raise ValueError('Changed frozen implementation: ' + rel)


def metrics(rows):
    n = len(rows)
    correct = sum(r['prediction'] == r['reference'] for r in rows)
    resolved = sum(r['prediction'] is not None for r in rows)
    recalls = {label: sum(r['prediction'] == label for r in rows if r['reference'] == label)
               / sum(r['reference'] == label for r in rows) for label in ('no', 'partial', 'yes')}
    z = 1.96; proportion = correct / n; denominator = 1 + z*z/n
    center = (proportion + z*z/(2*n)) / denominator
    radius = z*sqrt(proportion*(1-proportion)/n + z*z/(4*n*n)) / denominator
    return {'correct': correct, 'total': n, 'accuracy': correct/n, 'resolved': resolved,
            'coverage': resolved/n, 'per_class_recall': recalls,
            'macro_recall': sum(recalls.values())/3,
            'confusion': {label: dict(Counter(r['prediction'] or 'unresolved' for r in rows
                                            if r['reference'] == label)) for label in recalls},
            'wilson_95_interval': [center-radius, center+radius]}


def paired_comparison(flat, rows):
    if [r['id'] for r in rows] != [r['id'] for r in flat['cases']]:
        raise ValueError('Unpaired cases')
    wins, losses, changed = [], [], []
    for old, new in zip(flat['cases'], rows):
        before = old['prediction'] == old['reference']
        after = new['prediction'] == new['reference']
        if after and not before: wins.append(new['case'])
        if before and not after: losses.append(new['case'])
        if old['prediction'] != new['prediction']: changed.append(new['case'])
    discordant = len(wins) + len(losses)
    p = min(1., 2*sum(comb(discordant, k) for k in range(min(len(wins), len(losses))+1))
            / 2**discordant) if discordant else 1.
    return {'wins': wins, 'losses': losses, 'changed_predictions': changed,
            'accuracy_difference': (len(wins)-len(losses))/len(rows),
            'mcnemar_exact_two_sided_p': p}


def run(output, manifest, live):
    from critical import config
    from critical.lm_engine import get_engine, load_creds, require_live
    from critical.logging.llm_history import LLMHistoryWriter
    config.PROJECT_ROOT = ROOT; config.CREDENTIALS_FILE = ROOT / '.env'
    creds = None
    if live:
        require_live(True)
        creds = load_creds(provider='openai', engine='gpt')
        if creds.provider != 'openai' or creds.endpoints != ['https://api.openai.com/v1']:
            raise ValueError('Official OpenAI only')

    def work(case):
        directory = output / 'ledgers' / case['case']
        if not live and not list((directory / 'jobs').glob('*.json')):
            raise ValueError('Replay requires an existing durable observation')

        def factory(cap):
            if not live: raise AssertionError('Replay attempted a provider call')
            return get_engine('gpt', creds=creds, model=IDENTITY['model'], reasoning_effort='high',
                              temperature=None, max_tokens=cap, timeout=180, max_http_attempts=1,
                              history=LLMHistoryWriter(directory / 'llm-histories.log'))
        calls = DurableCalls(directory, factory, identity=IDENTITY, max_calls=1,
                             max_completion_tokens=CAP, scope_limits={'search': 1, 'final': 1})
        row = {k: case[k] for k in ('case', 'id', 'instruction', 'human_score', 'reference')}
        row.update(prediction=None, error=None, decision=None)
        try:
            decision = SingleCallEvidenceJudge(calls).judge(
                case['instruction'], case['evidence'], case_id=case['id'], max_tokens=CAP)
            row.update(prediction=decision['label'], decision=decision)
        except (RuntimeError, ValueError, KeyError, TypeError) as exc:
            row['error'] = type(exc).__name__ + ': ' + str(exc)
            jobs = list((directory / 'jobs').glob('*.json'))
            if jobs and (job := read(jobs[0]))['outcome'] != 'completed':
                row['error'] = job.get('error') or job['outcome']
        print(json.dumps({k: row[k] for k in ('case', 'reference', 'prediction', 'error')}), flush=True)
        return row

    with ThreadPoolExecutor(max_workers=manifest['workers']) as pool:
        rows = list(pool.map(work, manifest['cases']))
    jobs = [read(p) for p in sorted((output / 'ledgers').glob('*/jobs/*.json'))]
    responses = [j['response'] for j in jobs if j.get('response')]
    flat = read(Path(manifest['baseline_directory']) / 'results.json')
    return {'version': VERSION, 'model': IDENTITY, 'policy': POLICY, 'metrics': metrics(rows),
            'flat_metrics': metrics(flat['cases']), 'paired': paired_comparison(flat, rows), 'cases': rows,
            'api_attempts': len(jobs), 'call_outcomes': dict(Counter(j['outcome'] for j in jobs)),
            'input_tokens': sum(r.get('promptTokens', 0) for r in responses),
            'completion_tokens': sum(r.get('completionTokens', 0) for r in responses),
            'returned_models': sorted({r.get('model', 'unknown') for r in responses}),
            'flat_input_tokens': flat['input_tokens'], 'flat_completion_tokens': flat['completion_tokens'],
            'scope': manifest['scope']}


def write_report(output, result, manifest):
    flat = read(Path(manifest['baseline_directory']) / 'results.json')
    lines = ['# Single-call evidence checks versus flat judge', '',
             'GPT-6.1 Sol, high reasoning; same twelve AURORA-editor cases, four per class.',
             'One SOURCE-first presentation and one response per case in each arm.',
             'Flat responses are reused from the preceding benchmark. No new flat calls.', '',
             '| Method | Correct | No recall | Partial recall | Yes recall | Resolved |',
             '|---|---:|---:|---:|---:|---:|']
    for name, m in [('Flat', result['flat_metrics']), ('Explicit evidence + fixed policy', result['metrics'])]:
        rates = ' | '.join(f"{m['per_class_recall'][label]:.0%}" for label in ('no', 'partial', 'yes'))
        lines.append(f"| {name} | {m['correct']}/12 ({m['accuracy']:.1%}) | {rates} | {m['resolved']}/12 |")
    p = result['paired']
    lines += ['', f"Paired improvements: {p['wins']}; regressions: {p['losses']}; net accuracy change: {p['accuracy_difference']:+.1%}.",
              f"Exact two-sided McNemar p: {p['mcnemar_exact_two_sided_p']:.3f}.", '',
              '## Frozen policy', '',
              '- No: wrong target, destroyed source meaning, or every core requirement absent.',
              '- Yes: every material requirement complete, matched target, relevant source meaning preserved.',
              '- Partial: some core fulfillment with a material shortfall/deviation.',
              '- Unknown evidence: enumerate possible states; resolve only if the label cannot change.',
              '- Invalid records remain unresolved; no retries, votes, fitting, or model readout.', '',
              '| Case | Instruction | Reference | Flat | Evidence + policy |', '|---|---|---|---|---|']
    for old, new in zip(flat['cases'], result['cases']):
        lines.append(f"| {new['case']} | {new['instruction'].replace('|', '/')} | {new['reference']} | {old['prediction']} | {new['prediction'] or 'unresolved'} |")
    lines += ['', '## Evidence records', '']
    for row in result['cases']:
        lines += [f"### {row['case']}: {row['instruction']}", '',
                  f"Reference: {row['reference']}; prediction: {row['prediction'] or 'unresolved'}.", '']
        if row['decision']:
            obs = row['decision']['observations']
            lines += [f"Scope: {obs['instruction_scope']}", '',
                      f"Target: **{obs['target']['state']}** — {obs['target']['evidence']}", '',
                      f"Source integrity: **{obs['source_integrity']['state']}** — {obs['source_integrity']['evidence']}", '']
            lines += [f"- {r['id']} ({r['role']}, **{r['state']}**): {r['question']} {r['evidence']}" for r in obs['requirements']]
            lines += ['', f"Policy: {row['decision']['reason']}.", '']
        else: lines += [row['error'] or 'No valid record.', '']
    lo, hi = result['metrics']['wilson_95_interval']
    lines += ['## Usage and interpretation', '',
              f"New API attempts: {result['api_attempts']}; outcomes: {json.dumps(result['call_outcomes'])}.",
              f"Evidence input/output tokens: {result['input_tokens']}/{result['completion_tokens']}; flat: {result['flat_input_tokens']}/{result['flat_completion_tokens']}.",
              f"Evidence accuracy Wilson 95% interval: {lo:.1%}–{hi:.1%}.", '',
              'This is a previously inspected twelve-case diagnostic, not an untouched generalization test.',
              'One response per case cannot establish repeat robustness. Checks within a call share model errors.',
              'Requirement selection, core/constraint roles, scope, and evidence interpretation remain model judgments.',
              'Code validates structure and exact instruction quotes, not semantic completeness or visual truth.',
              'The evidence prompt and policy were frozen before these calls; no case-specific examples or labels were supplied.',
              'Prompt wording, evidence representation and deterministic aggregation change together; this does not isolate decomposition alone.',
              'Both arms request the same model alias/settings, but separate calls need not use identical backend snapshots.',
              'The existing fulfillment optimizer and default pipeline are unchanged.', '']
    (output / 'report.md').write_text('\n'.join(lines))
    (output / 'llm-histories.log').write_text(''.join(p.read_text() for p in sorted((output / 'ledgers').glob('*/llm-histories.log'))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-dir', type=Path, default=DEFAULT_BASELINE)
    parser.add_argument('--output-dir', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight', action='store_true')
    mode.add_argument('--live', action='store_true')
    mode.add_argument('--replay', action='store_true')
    args = parser.parse_args()
    output, baseline = args.output_dir.resolve(), args.baseline_dir.resolve()
    if output == baseline:
        raise ValueError('Use a new directory; never overwrite the flat baseline')
    if args.replay and not (output / 'results.json').exists():
        raise ValueError('Replay requires completed saved results')
    manifest = prepare(output, baseline)
    if args.preflight:
        print(json.dumps({'ready': True, 'new_calls_max': 12, 'flat_calls_reused': 12,
                          'identity': IDENTITY, 'classes': dict(Counter(c['reference'] for c in manifest['cases']))}))
        return
    result = run(output, manifest, args.live)
    verify(output, manifest)
    if args.replay:
        if result != read(output / 'results.json'):
            raise ValueError('Replay changed saved results')
        save_json(output / 'verification.json', {'exact_replay': True, 'new_api_calls': 0,
                  'manifest_ref': digest(manifest), 'results_sha256': fingerprint(output / 'results.json'),
                  'baseline_unchanged': True, 'same_cases_images_model_settings': True})
        print(json.dumps({'exact_replay': True, 'new_api_calls': 0}))
    else:
        if (output / 'results.json').exists() and read(output / 'results.json') != result:
            raise ValueError('Refusing to overwrite different results')
        save_json(output / 'results.json', result)
        write_report(output, result, manifest)
        print(json.dumps({'metrics': result['metrics'], 'paired': result['paired']}))


if __name__ == '__main__':
    main()
