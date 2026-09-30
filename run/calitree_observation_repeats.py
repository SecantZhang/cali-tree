"""Extend the frozen 50-case study from two to five draws, without resampling failures."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from run.calitree_observation50 import MODEL, check_once
from run.calitree_observation_reliability import label_from_statuses
from tests.unit.calitree.assumption3_probe import (
    ROOT, BudgetedEngine, BudgetExhausted, apply_pilot_reviews, save,
)
from critical.lm_engine import get_engine, load_creds, require_live
from critical.logging.llm_history import LLMHistoryWriter

KNOWN = {'complete', 'partial', 'absent'}
VALID = KNOWN | {'unknown'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jobs(directory):
    records = {}
    for path in sorted((directory / 'jobs').glob('*.json')):
        record = json.loads(path.read_text())
        if record['job_id'] in records:
            raise ValueError('Duplicate job: ' + record['job_id'])
        records[record['job_id']] = record
    return records


def prepare(source, out):
    source = source.resolve()
    if source == out.resolve():
        raise ValueError('Extension must use a separate directory')
    original = json.loads((source / 'manifest.json').read_text())
    for relative, expected in original['source_sha256'].items():
        if sha(ROOT / relative) != expected:
            raise ValueError('Original checker dependency changed: ' + relative)
    templates = {p.name: p.read_text() for p in
                 (ROOT / 'critical/core/prompts/templates/calitree_decomposition_casewise_v1').glob('*.txt')}
    if templates != original['checker_templates']:
        raise ValueError('Original checker templates changed')
    rows = json.loads((source / 'frozen_plans.json').read_text())
    if len(rows) != 50 or set(rows) != set(original['rows']):
        raise ValueError('Expected original 50 cases')
    old_jobs = read_jobs(source)
    for case, row in rows.items():
        for key, value in original['rows'][case].items():
            if key != 'plan' and row[key] != value:
                raise ValueError('Changed case identity: ' + case)
        expected_plan = original['rows'][case]['plan']
        if expected_plan is None:
            expected_plan = old_jobs['compile/' + case]['plan']
        if row['plan'] != expected_plan:
            raise ValueError('Changed frozen criteria: ' + case)
        for image in row['images']:
            if sha(image['path']) != image['sha256']:
                raise ValueError('Changed image: ' + case)
        for condition in row['plan']['conditions']:
            for rep in range(2):
                if f'check/{rep}/{case}/{condition["id"]}' not in old_jobs:
                    raise ValueError('Missing original attempted slot')
    apply_pilot_reviews(rows)
    count = sum(len(row['plan']['conditions']) for row in rows.values())
    source_files = [source / 'manifest.json', source / 'frozen_plans.json', *sorted((source / 'jobs').glob('*.json'))]
    manifest = {'version': 'calitree-five-repeats-v1', 'source': str(source),
                'source_files': {str(p): sha(p) for p in source_files}, 'driver_sha256': sha(__file__),
                'model': MODEL, 'temperature': 0, 'reasoning_effort': 'none',
                'repeats': 5, 'new_repeat_indices': [2, 3, 4], 'max_calls': count * 3,
                'completion_budget': count * 3 * 1024, 'max_tokens': 1024,
                'schema_retries': 0, 'http_attempts_per_call': 1, 'rows': rows,
                'agreement_definition': 'modal known final prediction or exact known vector, divided by five'}
    out.mkdir(parents=True, exist_ok=True)
    path = out / 'manifest.json'
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise ValueError('Extension protocol changed; use another directory')
    save(path, manifest)
    return manifest, old_jobs


def modal(values):
    counts = Counter(v for v in values if v is not None)
    size = max(counts.values(), default=0)
    return {'count': size, 'fraction': size / 5,
            'modes': [v for v, n in counts.items() if n == size]}


def summarize(rows, records):
    cases, conditions = {}, []
    for case, row in rows.items():
        vectors = [[] for _ in range(5)]
        condition_counts = []
        for c in row['plan']['conditions']:
            statuses = []
            for rep in range(5):
                r = records.get(f'check/{rep}/{case}/{c["id"]}', {})
                status = r.get('check', {}).get('status') if r.get('outcome') == 'completed' else r.get('outcome', 'not_run')
                statuses.append(status)
                vectors[rep].append(status)
            agreement = modal([s if s in KNOWN else None for s in statuses])
            condition_counts.append(agreement['count'])
            conditions.append({'case': case, 'id': c['id'], 'statuses': statuses, 'known_agreement': agreement})
        predictions = [label_from_statuses(v) for v in vectors]
        prediction_agreement = modal([p if p != 'unresolved' else None for p in predictions])
        vector_agreement = modal([tuple(v) if v and all(s in KNOWN for s in v) else None for v in vectors])
        cases[case] = {'instruction': row['instruction'], 'predictions': predictions,
                       'vectors': vectors, 'final_agreement': prediction_agreement,
                       'vector_agreement': vector_agreement,
                       'minimum_condition_agreement_count': min(condition_counts, default=0),
                       'resolved_draws': sum(p != 'unresolved' for p in predictions),
                       'model_unknown_draws': sum('unknown' in v for v in vectors),
                       'incomplete_draws': sum(any(s not in VALID for s in v) for v in vectors)}
    metrics = {}
    for name, counts in {
        'final_prediction': [c['final_agreement']['count'] for c in cases.values()],
        'exact_condition_vector': [c['vector_agreement']['count'] for c in cases.values()],
        'every_condition_individually': [c['minimum_condition_agreement_count'] for c in cases.values()],
        'individual_conditions': [c['known_agreement']['count'] for c in conditions],
    }.items():
        metrics[name] = {'denominator': len(counts), 'exact_counts': dict(Counter(counts)),
                         'at_least': {str(k): {'count': sum(n >= k for n in counts),
                                              'percent': 100 * sum(n >= k for n in counts) / len(counts)}
                                      for k in (3, 4, 5)}}
    return {'cases': cases, 'conditions': conditions, 'metrics': metrics,
            'outcomes': dict(Counter(r['outcome'] for key, r in records.items() if key.startswith('check/')))}


def execute(out, manifest, prior, engine):
    records = dict(prior)
    new = read_jobs(out)
    if records.keys() & new.keys():
        raise ValueError('Extension overlaps original jobs')
    records.update(new)
    (out / 'jobs').mkdir(exist_ok=True)
    budget = BudgetedEngine(engine, out / 'budget.json', manifest['max_calls'], manifest['completion_budget'])
    stop_reason = 'complete'
    consecutive_errors = 0
    try:
        for rep in manifest['new_repeat_indices']:
            for case, row in manifest['rows'].items():
                for condition in row['plan']['conditions']:
                    key = f'check/{rep}/{case}/{condition["id"]}'
                    if key in records:
                        continue
                    path = out / 'jobs' / (hashlib.sha256(key.encode()).hexdigest() + '.json')
                    record = {'job_id': key, 'outcome': 'interrupted_or_pending'}
                    records[key] = record
                    save(path, record)
                    try:
                        record = {'job_id': key, **check_once(budget, row, condition)}
                    except BudgetExhausted:
                        record = {'job_id': key, 'outcome': 'budget_exhausted'}
                        records[key] = record
                        save(path, record)
                        raise
                    records[key] = record
                    save(path, record)
                    message = json.dumps({'job': key, 'outcome': record['outcome'], 'usage': budget.usage})
                    print(message, flush=True)
                    with (out / 'run.log').open('a') as log:
                        log.write(message + '\n')
                    consecutive_errors = consecutive_errors + 1 if record['outcome'] == 'transport_error' else 0
                    if consecutive_errors >= 3:
                        raise RuntimeError('Three consecutive transport failures; no further calls')
            save(out / 'progress.json', summarize(manifest['rows'], records))
    except (BudgetExhausted, RuntimeError) as exc:
        stop_reason = str(exc)
    result = {'stop_reason': stop_reason, 'usage': budget.usage, 'summary': summarize(manifest['rows'], records)}
    save(out / 'results.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'logs/exps/260929-22:30:00-exps')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    manifest, prior = prepare(args.source, args.output_dir)
    print(json.dumps({k: manifest[k] for k in ('model', 'repeats', 'max_calls', 'completion_budget')}), flush=True)
    if not args.live:
        return
    require_live(args.live, context='User requested three additional repeats of the same 50 cases')
    creds = load_creds(model=MODEL)
    if creds.provider != 'openai' or creds.endpoints != ['https://api.openai.com/v1']:
        raise ValueError('Official OpenAI only')
    engine = get_engine('gpt', model=MODEL, creds=creds, temperature=0, max_tokens=1024, timeout=60,
                        history=LLMHistoryWriter(args.output_dir / 'llm-histories.log'))
    result = execute(args.output_dir, manifest, prior, engine)
    print(json.dumps({'stop_reason': result['stop_reason'], 'usage': result['usage'],
                      'metrics': result['summary']['metrics']}), flush=True)


if __name__ == '__main__':
    main()
