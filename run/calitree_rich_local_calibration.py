"""Extract richer label-blind evidence, then fit reusable rules on the same 12 cases."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil

from critical.core.calibration.local_evidence_rules import LocalEvidenceRuleCalibrator
from critical.core.calibration.rich_local_rules import (
    VERSION, FEATURES, LIMITS, PREDICATES, RichLocalRuleCalibrator, conflicts,
)
from critical.core.calibration.registry import CalibrationRegistry
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.calls import DurableCalls
from critical.core.decision.rich_evidence import SCHEMA, RichEvidenceExtractor, base_observation, prompt
from run.calitree_single_call import CAP, IDENTITY, ROOT, fingerprint, metrics, paired_comparison, read
from run.calitree_local_calibration import rule_text, verify as verify_previous

DEFAULT_LOCAL = ROOT / 'logs/exps/261013-local-reusable-rules-v1'
LABELS = ('no', 'partial', 'yes')


def prepare(output, previous):
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'manifest.json').exists():
        m = read(output / 'manifest.json')
        if m['previous_directory'] != str(previous): raise ValueError('Changed previous local fit')
        verify(output, m); return m
    old = read(previous / 'manifest.json'); verify_previous(previous, old)
    if len(old['cases']) != 12 or len({r['group'] for r in old['cases']}) != 12:
        raise ValueError('Expected original source-distinct twelve cases')
    paths = [previous / name for name in ('manifest.json', 'seal.json', 'results.json', 'policy_seal.json')]
    paths += [Path(old['evidence_directory']) / name for name in ('manifest.json', 'seal.json', 'results.json')]
    paths += [Path(old['flat_directory']) / 'results.json']
    files = [p for p in (ROOT / 'critical').rglob('*') if p.is_file() and p.suffix in ('.py', '.txt', '.json')]
    files += [Path(__file__).resolve(), ROOT / 'run/calitree_single_call.py', ROOT / 'run/calitree_local_calibration.py']
    code = {}
    for path in files:
        rel = str(path.relative_to(ROOT)); dst = output / 'source_snapshot' / rel
        dst.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, dst); code[rel] = fingerprint(path)
    (output / 'prompt.txt').write_text(prompt())
    m = {'version': VERSION, 'previous_directory': str(previous), 'cases': old['cases'],
         'evidence_directory': old['evidence_directory'], 'flat_directory': old['flat_directory'],
         'cached_files': {str(p): fingerprint(p) for p in paths}, 'code_hashes': code,
         'judge_identity': IDENTITY, 'workers': 4, 'max_calls': 12, 'http_attempts_per_slot': 1,
         'draws_per_case': 1, 'presentation': 'source_first', 'max_completion_tokens_per_case': CAP,
         'prompt_ref': digest(prompt()), 'schema_ref': digest(SCHEMA), 'predicates': PREDICATES,
         'features': list(FEATURES), 'limits': LIMITS,
         'controls': ['Original cached v1 local result', 'Frozen v1 policy on fresh base projection',
                      'Refitted v1 grammar on fresh base projection', 'Rich grammar on fresh rich evidence'],
         'scope': 'Local fit on the same twelve labels. Schema designed after prior error analysis; extraction payloads are label-blind, not an untouched evaluation.',
         'authorization': 'Implement the richer label-blind evidence extraction on the same 12 cases, then rerun the constrained local calibration. Keep the rules reusable and compare with the current 10/12 result.'}
    save_json(output / 'manifest.json', m); save_json(output / 'seal.json', {'manifest_ref': digest(m)})
    save_json(output / 'estimate.json', {'max_new_image_calls': 12, 'fitting_api_calls': 0,
              'max_completion_tokens': 12*CAP, 'output_token_cost_ceiling_usd': 12*CAP*10/1_000_000,
              'input_cost': 'Additional text/image input tokens; actual usage reported.',
              'pricing_source': 'https://developers.openai.com/api/docs/models/gpt-6.1-sol'})
    verify(output, m); return m


def verify(output, m):
    if (digest(m) != read(output / 'seal.json')['manifest_ref'] or m['version'] != VERSION
            or m['judge_identity'] != IDENTITY or m['predicates'] != PREDICATES or m['limits'] != LIMITS
            or m['prompt_ref'] != digest(prompt()) or m['schema_ref'] != digest(SCHEMA)
            or (output / 'prompt.txt').read_text() != prompt()): raise ValueError('Changed rich experiment protocol')
    if Counter(r['reference'] for r in m['cases']) != {'no': 4, 'partial': 4, 'yes': 4}:
        raise ValueError('Changed class-balanced sample')
    for name, expected in m['cached_files'].items():
        if fingerprint(name) != expected: raise ValueError('Changed prior result/cache')
    for row in m['cases']:
        for key, path in row['evidence'].items():
            if fingerprint(path) != row['image_hashes'][key]: raise ValueError('Changed images')
    for rel, expected in m['code_hashes'].items():
        if fingerprint(ROOT / rel) != expected or fingerprint(output / 'source_snapshot' / rel) != expected:
            raise ValueError('Changed frozen code: ' + rel)


def extract(output, manifest, live):
    from critical import config
    from critical.lm_engine import get_engine, load_creds, require_live
    from critical.logging.llm_history import LLMHistoryWriter
    config.PROJECT_ROOT = ROOT; config.CREDENTIALS_FILE = ROOT / '.env'
    creds = None
    if live:
        require_live(True); creds = load_creds(provider='openai', engine='gpt')
        if creds.provider != 'openai' or creds.endpoints != ['https://api.openai.com/v1']:
            raise ValueError('Official OpenAI only')
    def work(case):
        directory = output / 'ledgers' / case['case']
        if not live and not list((directory / 'jobs').glob('*.json')):
            raise ValueError('Replay needs existing extraction slots')
        def factory(cap):
            if not live: raise AssertionError('Replay attempted a new API call')
            return get_engine('gpt', creds=creds, model=IDENTITY['model'], reasoning_effort='high',
                              temperature=None, max_tokens=cap, timeout=180, max_http_attempts=1,
                              history=LLMHistoryWriter(directory / 'llm-histories.log'))
        calls = DurableCalls(directory, factory, identity=IDENTITY, max_calls=1,
                             max_completion_tokens=CAP, scope_limits={'search': 1, 'final': 1})
        row = {'case': case['case'], 'id': case['id'], 'instruction': case['instruction'],
               'extraction': None, 'error': None}
        try:
            row['extraction'] = RichEvidenceExtractor(calls).extract(case['instruction'], case['evidence'],
                                                                    case_id=case['id'], max_tokens=CAP)
        except (RuntimeError, ValueError, KeyError, TypeError) as exc:
            row['error'] = type(exc).__name__ + ': ' + str(exc)
            jobs = list((directory / 'jobs').glob('*.json'))
            if jobs and (job := read(jobs[0]))['outcome'] != 'completed': row['error'] = job.get('error') or job['outcome']
        print({'case': case['case'], 'observed': row['extraction'] is not None, 'error': row['error']}, flush=True)
        return row
    with ThreadPoolExecutor(max_workers=manifest['workers']) as pool:
        return list(pool.map(work, manifest['cases']))


def score(rows):
    value = metrics(rows); value.pop('wilson_95_interval', None); return value


def paired(old, rows):
    value = paired_comparison({'cases': old}, rows); value.pop('mcnemar_exact_two_sided_p', None); return value


def fit_and_compare(extractions, cases, previous):
    """Labels become available only here, after the extraction stage completes."""
    valid = [i for i, r in enumerate(extractions) if r['extraction'] is not None]
    rich_inputs = [{'instruction': extractions[i]['instruction'],
                    'observations': extractions[i]['extraction']['observations']} for i in valid]
    base_inputs = [{**x, 'observations': base_observation(x['observations'])} for x in rich_inputs]
    targets = [LABELS.index(cases[i]['reference']) for i in valid]; groups = [cases[i]['group'] for i in valid]
    old_model = LocalEvidenceRuleCalibrator.restore(previous['policy'])
    old_refit = LocalEvidenceRuleCalibrator().fit(base_inputs, targets, source_groups=groups)
    new_model = RichLocalRuleCalibrator().fit(rich_inputs, targets, source_groups=groups)
    values = {'old_policy_fresh': old_model.predict_records(base_inputs),
              'old_grammar_refit_fresh': old_refit.predict_records(base_inputs),
              'rich_local': new_model.predict_records(rich_inputs)}
    indexed = {name: dict(zip(valid, rows)) for name, rows in values.items()}
    rows = []
    for i, (case, extraction) in enumerate(zip(cases, extractions)):
        row = {k: case[k] for k in ('case', 'id', 'instruction', 'reference')}
        row.update(extraction=extraction['extraction'], error=extraction['error'])
        for name in values:
            value = indexed[name].get(i); row[name] = value
        row['prediction'] = row['rich_local']['label'] if row['rich_local'] else None
        rows.append(row)
    collision = conflicts(rich_inputs, targets)
    for c in collision['identical_feature_conflicts']:
        c['cases'] = [cases[valid[i]]['case'] for i in c['indices']]
    return rows, {'rich': new_model.metadata(), 'old_refit': old_refit.metadata()}, collision


def execute(output, manifest, live):
    extractions = extract(output, manifest, live)
    path = output / 'extractions.json'
    if path.exists() and read(path) != extractions: raise ValueError('Changed frozen extraction records')
    if not path.exists():
        if not live: raise ValueError('Replay requires saved extraction records')
        save_json(path, extractions)
    old = read(Path(manifest['previous_directory']) / 'results.json')
    rows, policies, collision = fit_and_compare(extractions, manifest['cases'], old)
    artifact = {'policies': policies, 'extractions_ref': digest(extractions),
                'local_training_case_ids': [r['id'] for r in manifest['cases']]}
    seal_path = output / 'policy_seal.json'
    if live:
        version, path = CalibrationRegistry(output / 'registry').publish(artifact)
        seal = {'version': version, 'path': str(path.relative_to(output)), 'artifact_ref': digest(artifact)}
        if seal_path.exists() and read(seal_path) != seal: raise ValueError('Refusing changed frozen policy')
        save_json(seal_path, seal)
    else:
        seal = read(seal_path)
        if digest(read(output / seal['path'])) != seal['artifact_ref'] or read(output / seal['path']) != artifact:
            raise ValueError('Exact refitting changed policies')
    controls = {}
    for name in ('old_policy_fresh', 'old_grammar_refit_fresh', 'rich_local'):
        controls[name] = score([{**r, 'prediction': r[name]['label'] if r[name] else None} for r in rows])
    jobs = [read(p) for p in sorted((output / 'ledgers').glob('*/jobs/*.json'))]
    responses = [j['response'] for j in jobs if j.get('response')]
    return {'version': VERSION, 'scope': manifest['scope'], 'model': IDENTITY,
            'old_cached_local': old['local_metrics'], 'controls': controls, 'cases': rows,
            'vs_old_cached': paired(old['cases'], rows),
            'vs_old_grammar_fresh': paired([{**r, 'prediction': r['old_grammar_refit_fresh']['label'] if r['old_grammar_refit_fresh'] else None} for r in rows], rows),
            'policies': policies, 'registry': seal, 'conflicts': collision,
            'api_attempts': len(jobs), 'call_outcomes': dict(Counter(j['outcome'] for j in jobs)),
            'input_tokens': sum(r.get('promptTokens', 0) for r in responses),
            'completion_tokens': sum(r.get('completionTokens', 0) for r in responses)}


def report(output, result, manifest):
    lines = ['# Rich label-blind evidence and constrained local calibration', '',
             '**All calibrated scores are same-case fitting results, not held-out accuracy.**',
             'Same twelve AURORA cases, GPT-6.1 Sol high, SOURCE-first, one new response per case.',
             'The extractor receives instruction and images only. The schema was designed after prior error analysis.', '',
             '| Method | Correct | No | Partial | Yes |', '|---|---:|---:|---:|---:|---:|']
    arms = [('Original cached v1 local fit', result['old_cached_local']),
            ('Frozen old policy on fresh base evidence', result['controls']['old_policy_fresh']),
            ('Refitted old grammar on fresh base evidence', result['controls']['old_grammar_refit_fresh']),
            ('Rich grammar on fresh rich evidence', result['controls']['rich_local'])]
    for name, m in arms:
        recall = ' | '.join(f"{round(m['per_class_recall'][k]*4)}/4" for k in LABELS)
        lines.append(f"| {name} | {m['correct']}/12 ({m['accuracy']:.1%}) | {recall} |")
    lines += ['', '## Learned rich policy', '', 'Keep decisive No and unresolved evidence guards; otherwise:',
              '', '```text', *rule_text(result['policies']['rich']['tree']), '```', '',
              f"Leaf source support: {result['policies']['rich']['leaf_support']}.",
              'Depth <=2; split nodes <=3; >=2 distinct source cases per learned leaf; monotone across all 162 anonymous evidence summaries.',
              'Rules cannot use object names, instructions, case IDs, evidence words, task labels or exact condition counts.',
              'Appearance changes alone do not reduce collateral continuity; unrequested entity/relation changes do. Visibility is recorded as evidence, not a universal crop penalty.', '',
              '| Case | Reference | Old cached | Old policy/fresh | Old refit/fresh | Rich local |',
              '|---|---|---|---|---|---|']
    old = read(Path(manifest['previous_directory']) / 'results.json') if result.get('cases') else None
    for i, row in enumerate(result['cases']):
        values = [row[k]['label'] if row[k] else 'unresolved' for k in ('old_policy_fresh', 'old_grammar_refit_fresh', 'rich_local')]
        lines.append(f"| {row['case']} | {row['reference']} | {old['cases'][i]['prediction'] if old else ''} | {' | '.join(v or 'unresolved' for v in values)} |")
    lines += ['', '## Extracted facts', '']
    for row in result['cases']:
        lines += [f"### {row['case']}: {row['instruction']}", '']
        if row['extraction']:
            o = row['extraction']['observations']
            lines += [f"Source integrity: {o['source_integrity']['state']} — {o['source_integrity']['evidence']}", '']
            for name, fact in {**o['collateral'], 'verification_visibility': o['verification_visibility']}.items():
                lines.append(f"- {name}: **{fact['state']}** — {fact['evidence']}")
            lines += ['', f"Rule summary: {row['rich_local']}", '']
        else: lines += [row['error'] or 'No valid evidence.', '']
    lines += ['## Limits', '',
              'Label-blind extraction does not mean the schema design was blind to previous cases. The same labels select and score the rules.',
              'Fresh observations can differ from cached observations. The fresh-base controls help distinguish that effect from richer predicates.',
              'Generic syntax, support and monotonicity do not establish semantic truth or generalization. There are no repeat/robustness calls.',
              f"New API attempts: {result['api_attempts']}; outcomes {result['call_outcomes']}; input/completion tokens {result['input_tokens']}/{result['completion_tokens']}.", '']
    (output / 'report.md').write_text('\n'.join(lines))
    (output / 'llm-histories.log').write_text(''.join(p.read_text() for p in sorted((output / 'ledgers').glob('*/llm-histories.log'))))


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--previous-dir', type=Path, default=DEFAULT_LOCAL)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight', action='store_true'); mode.add_argument('--live', action='store_true'); mode.add_argument('--replay', action='store_true')
    args = p.parse_args(); output, previous = args.output_dir.resolve(), args.previous_dir.resolve()
    if output == previous: raise ValueError('Use a new output directory')
    if args.replay and not (output / 'results.json').exists(): raise ValueError('Replay needs saved results')
    manifest = prepare(output, previous)
    if args.preflight:
        print({'ready': True, 'new_calls_max': 12, 'label_blind_payload': ['instruction'], 'limits': LIMITS}); return
    result = execute(output, manifest, args.live); verify(output, manifest)
    if args.replay:
        if read(output / 'results.json') != result: raise ValueError('Replay changed results')
        save_json(output / 'verification.json', {'exact_refit_and_replay': True, 'new_api_calls': 0,
                  'original_caches_unchanged': True, 'results_sha256': fingerprint(output / 'results.json')})
        print({'exact_refit_and_replay': True, 'new_api_calls': 0})
    else:
        if (output / 'results.json').exists() and read(output / 'results.json') != result: raise ValueError('Different saved results')
        save_json(output / 'results.json', result); report(output, result, manifest)
        print({'controls': result['controls'], 'vs_old_cached': result['vs_old_cached'], 'rich_policy': result['policies']['rich']})


if __name__ == '__main__': main()
