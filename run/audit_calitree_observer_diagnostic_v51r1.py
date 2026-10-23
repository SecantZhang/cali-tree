"""Reconstruct paid request identities, budgets, projections and paired changes."""
import argparse
from collections import Counter
from pathlib import Path

from critical.core.decision import bound_evidence_v2 as physical
from critical.core.decision import semantic_interpretation_v5 as meaning
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.compiler import media_inputs
from critical.core.calibration import shared_regions_v27 as shared
from critical.core.calibration.semantic_expert_policy_v49 import SemanticExpertPolicy
from run import calitree_observer_diagnostic_v51r1 as diagnostic
from run.calitree_aurora_pilot_v29 import read, fingerprint


def audit(prepared, out):
    if out.exists():
        raise ValueError('Fresh audit directory required')
    protocol = diagnostic.verify(prepared)
    seal = read(prepared / 'preflight_seal.json')
    for name, expected in seal['files'].items():
        archived = prepared / 'preflight_logs' / name
        original = archived if name in ('run.log', 'llm-histories.log') and archived.exists() else prepared / name
        assert fingerprint(original) == expected, name
    if (prepared / 'preflight_logs/llm-histories.log').exists():
        assert fingerprint(prepared / 'llm-histories.log') == fingerprint(prepared / 'ledger/llm-histories.log')
    for name, expected in seal['upstream_code_hashes'].items():
        assert fingerprint(name) == expected, name
    authorization = read(prepared / 'authorization.json')
    assert authorization['max_requests'] == 48 and authorization['max_completion_tokens'] == 589824
    assert authorization['protocol_sha256'] == fingerprint(prepared / 'protocol.json')
    assert authorization['preflight_sha256'] == fingerprint(prepared / 'preflight_seal.json')
    entries = {e['case']: e for e in read(prepared / 'inputs_without_labels.json')}
    references = read(prepared / 'references_training_only.json')
    budget = read(prepared / 'ledger/budget.json')
    assert not budget['stopped']
    assert budget['limits']['identity'] == diagnostic.base.SOL
    assert budget['limits']['routes'] == {'luna': diagnostic.base.LUNA}
    assert budget['limits']['scope_limits'] == {'search': 4, 'final': 0}
    assert budget['limits']['max_calls'] == 48 and budget['limits']['max_completion_tokens'] == 589824
    jobs = [read(p) for p in (prepared / 'ledger/jobs').glob('*.json')]
    assert len(jobs) == budget['calls'] == len(set(budget['attempted_slots'])) <= 48
    by_key = {j['execution_ref']: j for j in jobs}
    assert set(by_key) == set(budget['attempted_slots'])
    outcomes, stage_counts, case_counts = Counter(), Counter(), Counter()
    inputs = completions = reservations = 0
    known_cost = reservation_cost = 0.
    for job in jobs:
        assert job['case_id'] in entries and job['phase'] == 'search'
        e = entries[job['case_id']]
        route = job.get('route')
        identity = diagnostic.base.SOL if route is None else diagnostic.base.LUNA
        assert route in (None, 'luna')
        if route is not None:
            assert job['requested_identity'] == identity
        media = []
        if job['stage'] == 'bound_visual_observation_v2':
            arm = 'sol' if route is None else 'luna'
            assert job['slot'] == 'once'
            cap = 16384
            payload = {'program': e['program'], 'image_pair_ref': e['pair_ref']}
            schema = physical.observation_schema(e['program'], e['pair_ref'])
            template = (physical.TEMPLATES / 'observe.txt').read_text()
            media = [{'type': 'image', 'sha256': fingerprint(m['path'])} if m['type'] == 'image' else m for m in media_inputs(e['evidence'])]
        else:
            assert job['stage'] == 'instruction_relative_interpretation' and route == 'luna'
            assert job['slot'] in ('luna-interpretation', 'sol-interpretation')
            arm = job['slot'].split('-')[0]
            cap = 8192
            saved = read(prepared / 'cases' / (e['case'] + '-' + arm + '.json'))
            assert saved['observation'] is not None
            payload = meaning.make_input(e['program'], saved['observation']['observation'], e['pair_ref'])
            schema, template = meaning.schema(payload), meaning.PROMPT
        assert job['payload'] == payload and job['max_tokens'] == cap and job['media_identity'] == media
        key = digest([identity, e['case'], job['stage'], payload, schema, template, media, job['slot'], cap])
        if route is not None:
            key = digest([key, route])
        assert key == job['execution_ref']
        outcomes[job['outcome']] += 1
        stage_counts[arm + '/' + job['stage']] += 1
        case_counts[e['case']] += 1
        input_price, output_price = (2., 10.) if identity == diagnostic.base.SOL else (.1, .5)
        if 'response' in job:
            in_count = int(job['response']['promptTokens'])
            out_count = int(job['response']['completionTokens'])
            inputs += in_count
            completions += out_count
            known_cost += (in_count * input_price + out_count * output_price) / 1e6
        else:
            reservations += cap
            reservation_cost += cap * output_price / 1e6
    assert inputs == budget['input_tokens']
    assert completions + reservations == budget['completion_tokens_or_reserved'] <= 589824
    for case, count in case_counts.items():
        assert count <= 4 and budget['cases'][case]['search'] == count and budget['cases'][case]['final'] == 0
    assert stage_counts['sol/bound_visual_observation_v2'] == 12
    assert stage_counts['luna/bound_visual_observation_v2'] == 12
    rows, changes = [], []
    for e in entries.values():
        controller = SemanticExpertPolicy(read(prepared / f"controllers/fold{e['fold']}.json"))
        row = {'case': e['case'], 'reference': references[e['case']]['reference'], 'cached': e['baseline_prediction']}
        saved_arms = {}
        for arm in ('luna', 'sol'):
            saved = read(prepared / 'cases' / (e['case'] + '-' + arm + '.json'))
            saved_arms[arm] = saved
            available = saved['features'] is not None
            if available:
                observation = saved['observation']
                assert by_key[observation['execution_ref']]['outcome'] == 'completed'
                assert by_key[saved['interpretation_execution_ref']]['outcome'] == 'completed'
                assert by_key[observation['execution_ref']]['parsed'] == observation['observation']
                assert by_key[saved['interpretation_execution_ref']]['parsed'] == saved['interpretation']
                physical.validate_observation(e['program'], observation['observation'], e['pair_ref'])
                payload = meaning.make_input(e['program'], observation['observation'], e['pair_ref'])
                meaning.validate(payload, saved['interpretation'])
                record = shared.evidence.project(e['program'], observation['observation'], e['pair_ref'], saved['interpretation'])
                assert record == saved['features']
                prediction = controller.resolve(e['program'], record, e['regular'])['prediction']
            else:
                assert saved['error']
                prediction = -1
            row[arm], row[arm + '_available'] = prediction, available
            row['safe_' + arm] = prediction if available else e['baseline_prediction']
        rows.append(row)
        change = {'case': e['case'], 'instruction': e['program']['instruction'], 'reference': row['reference'],
                  'cached_prediction': row['cached'], 'luna_prediction': row['luna'], 'sol_prediction': row['sol'],
                  'physical_changes': [], 'semantic_changes': []}
        change['predicate_changes_vs_cache'] = {
            arm: [{'feature': name, 'cached': old, 'fresh': saved_arms[arm]['features']['features'][name]}
                  for name, old in e['cached_features']['features'].items()
                  if old != saved_arms[arm]['features']['features'][name]]
            if saved_arms[arm]['features'] is not None else None for arm in ('luna', 'sol')}
        if all(saved_arms[a]['features'] is not None for a in ('luna', 'sol')):
            for check in e['program']['checks']:
                a, b = [saved_arms[arm]['observation']['observation']['checks'][check['id']] for arm in ('luna', 'sol')]
                different = {k: {'luna': a[k], 'sol': b[k]} for k in ('state', 'source_anchor', 'edited_coverage', 'applicability') if a[k] != b[k]}
                if different:
                    change['physical_changes'].append({'check': check['id'], 'role': check['role'], 'kind': check['kind'],
                        'question': check['question'], 'differences': different,
                        'luna_edited_evidence': a['edited_evidence'], 'sol_edited_evidence': b['edited_evidence']})
            for requirement in e['program']['requirements']:
                a, b = [saved_arms[arm]['interpretation']['requirements'][requirement['id']] for arm in ('luna', 'sol')]
                different = {field: {'luna': a[field], 'sol': b[field]} for field in meaning.FIELDS if a[field] != b[field]}
                if different:
                    change['semantic_changes'].append({'requirement': requirement['id'], 'differences': different,
                                                        'luna_explanation': a['explanation'], 'sol_explanation': b['explanation']})
        changes.append(change)
    result = read(prepared / 'results.json')
    for arm in ('cached', 'luna', 'sol', 'safe_luna', 'safe_sol'):
        assert sum(r[arm] == r['reference'] for r in rows) == result['correct'][arm]
    comparable = [r for r in rows if r['luna_available'] and r['sol_available']]
    summary = {'passed': True, 'cases': 12, 'request_identities_rebuilt': len(jobs), 'outcomes': dict(outcomes),
               'stage_counts': dict(stage_counts), 'known_input_tokens': inputs, 'known_completion_tokens': completions,
               'completion_tokens_or_reserved': completions + reservations, 'known_usage_estimate_usd': known_cost,
               'including_failed_output_reservations_usd': known_cost + reservation_cost,
               'correct': result['correct'], 'failures': result['failures'], 'both_available': len(comparable),
               'sol_fixes_vs_fresh_luna': sum(r['sol'] == r['reference'] and r['luna'] != r['reference'] for r in comparable),
               'sol_losses_vs_fresh_luna': sum(r['luna'] == r['reference'] and r['sol'] != r['reference'] for r in comparable),
               'fresh_luna_prediction_changes_vs_cache': sum(r['luna_available'] and r['luna'] != r['cached'] for r in rows),
               'fresh_luna_cases_with_predicate_changes_vs_cache': sum(bool(c['predicate_changes_vs_cache']['luna']) for c in changes),
               'new_model_calls_in_audit': 0, 'fitting': False, 'reserved_sources_used': 0,
               'scope': 'Selected training-only paired diagnostic; no generalization or factual-oracle claim.'}
    out.mkdir(parents=True)
    save_json(out / 'verification.json', summary)
    save_json(out / 'paired_evidence_changes.json', changes)
    save_json(out / 'predictions.json', rows)
    save_json(out / 'manifest.json', {'auditor_sha256': fingerprint(__file__),
              'prepared_manifest_sha256': fingerprint(prepared / 'manifest.json'), 'budget_sha256': fingerprint(prepared / 'ledger/budget.json')})
    (out / 'run.log').write_text('Independently rebuilt request hashes/media/schemas, model routes, token/call totals, bound projections and all paired fixed-controller decisions. No new calls or fitting.\n')
    (out / 'llm-histories.log').write_text('Zero model calls in audit.\n')
    print(summary, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    audit(args.prepared_dir.resolve(), args.output_dir.resolve())
