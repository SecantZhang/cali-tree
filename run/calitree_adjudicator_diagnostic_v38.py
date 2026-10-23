"""Prepare/run a bounded paired Sol diagnostic on original training cases only.

Direct unchanged judge versus six source-excluded visual calibration examples.
No inference occurs without --live and separate paid-call authorization.
"""
import argparse
from collections import Counter
from pathlib import Path

from critical.core.optimization.prompt.calitree import adjudication_examples_v38 as cards
from critical.core.optimization.prompt.calitree import task_coverage as task
from critical.core.decision.artifacts import digest, save_json
from run.calitree_fallback_routing_v34 import old_examples
from run.calitree_guarded_forward_v32 import SOURCE
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint, exact
from run.collect_calitree_aurora_pilot_v29r1 import validate_regular

IDENTITY = {'provider': 'openai', 'model': 'gpt-6.1-sol', 'temperature': None, 'reasoning_effort': 'medium'}
TEMPLATE = ROOT / 'critical/core/prompts/templates/semantic_adjudicator_v38/calibrated.txt'
MAX_REQUESTS = 48
MAX_OUTPUT = 48 * 8192


def pool():
    metadata = {e['case']: e for e in read(SOURCE / 'manifest.json')['cases']}
    old = {}
    for bank in (1, 2, 3):
        for e in old_examples(bank):
            m = metadata[e['case']]
            assert m['group'] == e['source_group'] and task.LABELS.index(m['reference']) == e['reference']
            assert m['instruction'] == e['program']['instruction']
            old[e['case']] = {**e, 'instruction': m['instruction'], 'evidence': m['evidence'], 'image_hashes': m['image_hashes']}
    assert len(old) == 99
    return [old[k] for k in sorted(old)]


def prepare(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    out.mkdir(parents=True)
    training = pool()
    selected, seen = [], set()
    for label in (0, 1, 2):
        candidates = sorted((e for e in training if e['reference'] == label), key=lambda e: digest([cards.VERSION, label, e['case']]))
        count = 0
        for e in candidates:
            if e['source_group'] in seen:
                continue
            selected.append(e)
            seen.add(e['source_group'])
            count += 1
            if count == 8:
                break
        assert count == 8
    jobs = []
    for e in selected:
        examples = cards.select(training, e)
        for arm, chosen, template in (('direct', [], (task.TEMPLATES / 'regular.txt').read_text()),
                                      ('calibrated', examples, TEMPLATE.read_text())):
            req = cards.request(e, chosen)
            jobs.append({'case': e['case'], 'arm': arm, **req, 'template': template,
                         'example_cases': [x['case'] for x in chosen],
                         'example_source_groups': [x['source_group'] for x in chosen]})
    images = {str(Path(path).resolve()): fingerprint(path) for e in training for path in e['evidence'].values()}
    protocol = {'version': cards.VERSION, 'identity': IDENTITY, 'cases': 24, 'labels_per_class': 8, 'max_requests': MAX_REQUESTS,
                'max_completion_tokens': MAX_OUTPUT, 'max_tokens_per_request': 8192, 'retries': 0, 'new_extraction': False,
                'scope': 'Original training cases only; this is a diagnostic, not a generalization test.',
                'examples': 'Six labeled visual pairs from other training sources, two per label, ranked by coarse requested operation. Entire query source excluded.',
                'arms': ['direct', 'calibrated'], 'official_endpoint': 'https://api.openai.com/v1',
                'cost': {'input_per_million': 2.0, 'cache_write_per_million': 2.5, 'output_per_million': 10.0,
                         'pricing_source': 'https://developers.openai.com/api/docs/models/gpt-6.1-sol', 'checked_on': '2026-10-20',
                         'expected_usd_range': [1.0, 3.0], 'completion_cap_usd': MAX_OUTPUT * 10 / 1e6,
                         'input_note': 'Input charges additional; calibrated requests contain 14 images, direct requests 2. Forecast is not a hard input-token cap or invoice.'},
                'training_retention': 'No serving changes or tree refits in this diagnostic; later integration must retain all 144 original training slots.',
                'paid_authorization_required': True, 'new_model_calls': 0}
    save_json(out / 'protocol.json', protocol)
    save_json(out / 'training_pool.json', training)
    save_json(out / 'cases.json', selected)
    save_json(out / 'jobs.json', jobs)
    code = [Path(__file__).resolve(), Path(cards.__file__).resolve(), TEMPLATE,
            ROOT / 'critical/lm_engine/provider_api.py', ROOT / 'critical/core/decision/calls.py']
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'jobs_ref': digest(jobs),
              'cases_ref': digest(selected), 'pool_ref': digest(training), 'image_hashes': images,
              'code_hashes': {str(p): fingerprint(p) for p in code}})
    (out / 'run.log').write_text('Prepared training-only paired adjudicator diagnostic. No paid calls authorized yet.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')
    print({'prepared': True, 'cases': len(selected), 'requests': len(jobs), 'max_output_tokens': MAX_OUTPUT,
           'expected_cost_usd': [1, 3], 'completion_cap_usd': MAX_OUTPUT * 10 / 1e6}, flush=True)


def verify(out):
    p = read(out / 'protocol.json')
    m = read(out / 'manifest.json')
    assert digest(p) == m['protocol_ref'] and digest(read(out / 'jobs.json')) == m['jobs_ref']
    assert digest(read(out / 'cases.json')) == m['cases_ref'] and digest(read(out / 'training_pool.json')) == m['pool_ref']
    for path, expected in {**m['image_hashes'], **m['code_hashes']}.items():
        assert fingerprint(path) == expected, path
    cases = read(out / 'cases.json')
    assert len(cases) == len({e['source_group'] for e in cases}) == 24
    assert Counter(e['reference'] for e in cases) == {0: 8, 1: 8, 2: 8}
    by_case = {e['case']: e for e in cases}
    for j in read(out / 'jobs.json'):
        assert by_case[j['case']]['source_group'] not in j['example_source_groups']
        assert len(set(j['example_source_groups'])) == len(j['example_source_groups'])
        assert set(j['payload']) == ({'instruction'} if j['arm'] == 'direct' else {'instruction', 'calibration_examples'})
    return p


def collect(out, live=False):
    if not live:
        raise ValueError('Separate explicit paid authorization and --live required')
    verify(out)
    from critical import config
    from critical.core.decision.calls import DurableCalls, ProviderStopped, BudgetExhausted
    from critical.lm_engine import load_creds, get_engine, require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True)
    config.PROJECT_ROOT = Path('/Users/zzhang/Documents/Projects/Adobe/calitree-mlsys')
    config.CREDENTIALS_FILE = config.PROJECT_ROOT / '.env'
    creds = load_creds(provider='openai', engine='gpt')
    if creds.endpoints != ['https://api.openai.com/v1']:
        raise ValueError('Official endpoint required')
    def factory(cap):
        return get_engine('gpt', creds=creds, model=IDENTITY['model'], temperature=None, reasoning_effort='medium',
                          max_tokens=cap, timeout=180, max_http_attempts=1,
                          history=LLMHistoryWriter(out / 'ledger/llm-histories.log'))
    calls = DurableCalls(out / 'ledger', factory, identity=IDENTITY, max_calls=MAX_REQUESTS,
                         max_completion_tokens=MAX_OUTPUT, scope_limits={'search': 2, 'final': 0})
    for j in read(out / 'jobs.json'):
        target = out / 'responses' / (j['case'] + '-' + j['arm'] + '.json')
        if target.exists():
            continue
        try:
            value, ref = calls.call('semantic_adjudication_v38', j['payload'], task.SCHEMA, template=j['template'],
                                    media=j['media'], case_id=j['case'], slot=j['arm'], max_tokens=8192)
            validate_regular(value)
            result = {'judgment': value, 'execution_ref': ref, 'error': None}
        except (ProviderStopped, BudgetExhausted):
            raise
        except (ValueError, RuntimeError, KeyError, TypeError) as exc:
            result = {'judgment': None, 'execution_ref': None, 'error': type(exc).__name__}
        exact(target, result)
        print({'case': j['case'], 'arm': j['arm'], 'error': result['error']}, flush=True)
    report(out)


def report(out):
    verify(out)
    cases = read(out / 'cases.json')
    rows = []
    for e in cases:
        r = {'case': e['case'], 'reference': e['reference'], 'cached_luna': e['regular']}
        for arm in ('direct', 'calibrated'):
            v = read(out / 'responses' / (e['case'] + '-' + arm + '.json'))['judgment']
            r[arm] = task.LABELS.index(v['label']) if v is not None and v['label'] in task.LABELS else -1
        rows.append(r)
    result = {'cases': len(rows), 'scope': 'Training-only diagnostic; not generalization accuracy.',
              'correct': {a: sum(r[a] == r['reference'] for r in rows) for a in ('cached_luna', 'direct', 'calibrated')},
              'training_retention_of_serving_pipeline_not_tested': True, 'rows': rows}
    exact(out / 'results.json', result)
    print(result, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare', action='store_true')
    mode.add_argument('--verify', action='store_true')
    mode.add_argument('--live', action='store_true')
    mode.add_argument('--report', action='store_true')
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
