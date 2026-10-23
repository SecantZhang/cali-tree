"""Fresh Luna/Sol observer arms on the same twelve training examples.

Adds a fresh Luna control to v51's cached-control prototype. Only the observer
model differs between fresh arms. Compilation, interpretation and controllers
stay fixed; no fitting or reserved evaluation is performed.
"""
import argparse
from pathlib import Path

from critical.core.decision import bound_evidence_v2 as physical
from critical.core.decision import semantic_interpretation_v5 as meaning
from critical.core.calibration import shared_regions_v27 as shared
from critical.core.calibration.semantic_expert_policy_v49 import SemanticExpertPolicy
from critical.core.decision.artifacts import digest, save_json
from run import calitree_observer_diagnostic_v51 as base
from run.calitree_aurora_pilot_v29 import read, exact, fingerprint

MAX_CALLS = 48
MAX_OUTPUT = 12 * (2 * 16384 + 2 * 8192)


def prepare(out):
    base.prepare(out)
    p = read(out / 'protocol.json')
    p.update(version=base.VERSION + '-r1', design='paired_fresh_observer_arms', max_requests=MAX_CALLS,
             max_completion_tokens=MAX_OUTPUT,
             change='Fresh Luna observer + Luna interpretation versus fresh Sol observer + Luna interpretation. Same compiled questions, physical prompt/schema, cached regular labels, and frozen held-source controllers. Arm names enter slot accounting only, not prompts.',
             observer_arms={'luna': base.LUNA, 'sol': base.SOL}, interpreter_calls_per_case=2,
             failure_policy='Retain failed slots without retry; report both fresh-arm accuracies with failures incorrect and both safe-path accuracies falling back to the frozen cached prediction. All 12 stay counted.')
    p['cost'].update(expected_usd_range=[.45, 1.1],
                     full_output_allowance_usd=12 * 16384 * 10 / 1e6 + 12 * (16384 + 2 * 8192) * .5 / 1e6)
    save_json(out / 'protocol.json', p)
    m = read(out / 'manifest.json')
    m['protocol_ref'] = digest(p)
    m['code_hashes'][str(Path(__file__).resolve())] = fingerprint(__file__)
    save_json(out / 'manifest.json', m)
    (out / 'run.log').write_text('Prepared r1 fresh-paired Luna/Sol observer comparison, superseding the cached-only control prototype. Twelve training-only examples; five frozen controllers reproduce all 276 prior predictions and original retention. Zero API calls.\n')
    print({'final_design': p['design'], 'cases': 12, 'max_requests': MAX_CALLS, 'max_completion_tokens': MAX_OUTPUT,
           'expected_usd': p['cost']['expected_usd_range'], 'full_output_allowance_usd': p['cost']['full_output_allowance_usd']}, flush=True)


def verify(out):
    p = base.verify(out)
    assert p['design'] == 'paired_fresh_observer_arms'
    assert p['max_requests'] == MAX_CALLS and p['max_completion_tokens'] == MAX_OUTPUT
    assert p['observer_arms'] == {'luna': base.LUNA, 'sol': base.SOL}
    return p


def collect(out, live=False):
    if not live or not (out / 'authorization.json').exists():
        raise ValueError('Separate explicit paid authorization and --live required')
    verify(out)
    from critical import config
    from critical.core.decision.calls import DurableCalls, RoutedCalls, ProviderStopped, BudgetExhausted
    from critical.lm_engine import load_creds, get_engine, require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True)
    config.PROJECT_ROOT = Path('/Users/zzhang/Documents/Projects/Adobe/calitree-mlsys')
    config.CREDENTIALS_FILE = config.PROJECT_ROOT / '.env'
    creds = load_creds(provider='openai', engine='gpt')
    if creds.endpoints != ['https://api.openai.com/v1']:
        raise ValueError('Official endpoint required')
    history = LLMHistoryWriter(out / 'ledger/llm-histories.log')
    def sol_factory(cap):
        return get_engine('gpt', creds=creds, model=base.SOL['model'], temperature=None, reasoning_effort='medium',
                          max_tokens=cap, timeout=180, max_http_attempts=1, history=history)
    def luna_factory(cap):
        return get_engine('gpt', creds=creds, model=base.LUNA['model'], temperature=0, max_tokens=cap, timeout=180,
                          max_http_attempts=1, history=history)
    calls = DurableCalls(out / 'ledger', sol_factory, identity=base.SOL, max_calls=MAX_CALLS, max_completion_tokens=MAX_OUTPUT,
                         scope_limits={'search': 4, 'final': 0}, routes={'luna': {'identity': base.LUNA, 'engine_factory': luna_factory}})
    for e in read(out / 'inputs_without_labels.json'):
        for arm in ('luna', 'sol'):
            path = out / 'cases' / (e['case'] + '-' + arm + '.json')
            if path.exists():
                continue
            result = {'observation': None, 'interpretation': None, 'features': None, 'error': None}
            try:
                observer_calls = RoutedCalls(calls, 'luna') if arm == 'luna' else calls
                observation = physical.BoundVisualObserver(observer_calls).observe(e['program'], e['evidence'], case_id=e['case'], max_tokens=16384)
                result['observation'] = observation
                payload = meaning.make_input(e['program'], observation['observation'], e['pair_ref'])
                value, ref = calls.call('instruction_relative_interpretation', payload, meaning.schema(payload), template=meaning.PROMPT,
                                        slot=arm + '-interpretation', max_tokens=8192, case_id=e['case'], route='luna')
                meaning.validate(payload, value)
                result.update(interpretation=value, interpretation_execution_ref=ref,
                              features=shared.evidence.project(e['program'], observation['observation'], e['pair_ref'], value))
            except (ProviderStopped, BudgetExhausted):
                raise
            except (ValueError, RuntimeError, KeyError, TypeError) as exc:
                result['error'] = type(exc).__name__
            exact(path, result)
            print({'case': e['case'], 'arm': arm, 'error': result['error']}, flush=True)
    report(out)


def report(out):
    verify(out)
    references = read(out / 'references_training_only.json')
    rows = []
    for e in read(out / 'inputs_without_labels.json'):
        controller = SemanticExpertPolicy(read(out / f"controllers/fold{e['fold']}.json"))
        row = {'case': e['case'], 'reference': references[e['case']]['reference'], 'cached': e['baseline_prediction']}
        for arm in ('luna', 'sol'):
            value = read(out / 'cases' / (e['case'] + '-' + arm + '.json'))
            available = value['features'] is not None
            prediction = controller.resolve(e['program'], value['features'], e['regular'])['prediction'] if available else -1
            row[arm] = prediction
            row[arm + '_available'] = available
            row['safe_' + arm] = prediction if available else e['baseline_prediction']
        rows.append(row)
    exact(out / 'results.json', {'cases': 12, 'correct': {arm: sum(r[arm] == r['reference'] for r in rows) for arm in ('cached', 'luna', 'sol', 'safe_luna', 'safe_sol')},
          'failures': {arm: sum(not r[arm + '_available'] for r in rows) for arm in ('luna', 'sol')}, 'rows': rows,
          'scope': 'Selected training-only paired diagnostic, no fitting/deployment or generalization accuracy claim.'})


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
