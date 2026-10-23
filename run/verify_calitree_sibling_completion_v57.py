"""Independently rebuild the matched-editor collection's requests and features.

Reads durable records only. No credentials, model calls, fitting, or reserved
labels. Failed outputs stay in the accounting and training-data denominator.
"""
import argparse
from collections import Counter
from pathlib import Path

from critical.core.decision import bound_evidence_v2 as physical
from critical.core.decision import semantic_interpretation_v5 as meaning
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.compiler import media_inputs
from critical.core.calibration import shared_regions_v27 as shared
from critical.core.optimization.prompt.calitree import task_coverage as task
from critical.database.dl_aurora.loader import score_to_label
from run import calitree_sibling_training_v57 as sibling
from run.calitree_continuous_policy_v43 import examples_and_scores, RESERVED
from run.calitree_guarded_forward_v32 import SOURCE
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint


def audit(out, audit_dir):
    if audit_dir.exists():
        raise ValueError('Fresh audit directory required')
    protocol = sibling.verify(out)
    auth = read(out / 'authorization.json')
    assert auth['authorized'] is True
    assert auth['protocol_sha256'] == fingerprint(out / 'protocol.json')
    assert auth['preflight_sha256'] == fingerprint(out / 'preflight_seal.json')
    assert (auth['max_requests'], auth['max_completion_tokens'], auth['workers']) == (1620, 14376960, 4)
    if (out / 'provider_stop.json').exists():
        recovery = out / 'continuation_r1'
        plan = read(recovery / 'plan.json')
        assert read(out / 'provider_stop.json')['reason'] == 'three_consecutive_transport_failures'
        assert read(recovery / 'preflight.json')['passed'] is True
        assert read(recovery / 'completion.json')['completed'] is True
        assert not (recovery / 'provider_stop.json').exists() and not (recovery / 'incomplete.json').exists()
        assert plan['maximum_total_slots'] <= auth['max_requests']
        assert plan['original_authorization_sha256'] == fingerprint(out / 'authorization.json')
        for name, sha in plan['old_immutable_hashes'].items():
            assert fingerprint(out / name) == sha, name
        for name, sha in plan['code_hashes'].items():
            assert fingerprint(name) == sha, name
    else:
        assert not (out / 'incomplete.json').exists()
    for name, sha in read(out / 'preflight_seal.json')['files'].items():
        archived = out / 'preflight_logs' / name
        original = archived if name in ('run.log', 'llm-histories.log') and archived.exists() else out / name
        assert fingerprint(original) == sha, name
    entries = read(out / 'inputs_without_labels.json')
    references = read(out / 'references_training_only.json')
    programs = read(out / 'programs.json')
    training = {e['case']: e for e in read(out / 'training_data.json')}
    assert len(training) == len(entries) == 540 and set(training) == set(references)
    local, recent, _, _ = examples_and_scores(True)
    parents = {e['case']: e for e in local + recent}
    old_groups = {e['source_group'] for e in local + recent}
    excluded = {e['source_group'] for e in read(RESERVED / 'inputs_without_labels.json')}
    excluded |= set(read(SOURCE / 'manifest.json')['excluded_groups'])
    groups = {e['source_group'] for e in entries}
    assert len(groups) == 134 and groups <= old_groups and not groups & excluded
    catalog_path = ROOT / 'logs/exps/261020-aurora-pilot80-v29/exposure/original/exposure_ledger.json'
    assert fingerprint(catalog_path) == read(out / 'manifest.json')['catalog_sha256']
    selected_tasks = {e['task_uid'] for e in entries}
    catalog = {t['task_uid']: t for t in read(catalog_path)['tasks'] if t['task_uid'] in selected_tasks}
    assert len(catalog) == 135
    for item in programs.values():
        assert item['program'] == parents[item['parent_case']]['program']
    totals, stages, outcomes = Counter(), Counter(), Counter()
    combined_history = []
    for e in entries:
        case = e['case']
        source = catalog[e['task_uid']]
        released = next(o for o in source['outputs'] if o['edited_sha256'] == fingerprint(e['evidence']['edited_image']))
        assert source['source_group'] == e['source_group'] and released['editor'] == e['editor']
        assert references[case]['human_score'] == released['human_score']
        assert references[case]['reference'] == task.LABELS.index(released['reference']) == score_to_label(float(released['human_score']))[0]
        directory = out / 'case_ledgers' / case
        budget = read(directory / 'budget.json')
        limits = budget['limits']
        assert limits['identity'] == sibling.IDENTITY and not budget['stopped']
        assert (limits['max_calls'], limits['max_completion_tokens']) == (3, sibling.CASE_CAP)
        assert limits['scope_limits'] == {'search': 3, 'final': 0}
        jobs = [read(p) for p in sorted((directory / 'jobs').glob('*.json'))]
        by_stage = {j['stage']: j for j in jobs}
        assert len(by_stage) == len(jobs) and 2 <= len(jobs) <= 3
        assert 'bound_visual_observation_v2' in by_stage and 'flat_judge' in by_stage
        assert set(budget['attempted_slots']) == {j['execution_ref'] for j in jobs}
        assert budget['calls'] == len(jobs) == len(budget['attempted_slots'])
        p = programs[e['task_uid']]['program']
        pair = physical.image_identity(e['evidence'])[1]
        counts = Counter()
        for j in jobs:
            stage = j['stage']
            assert j['case_id'] == case and j['phase'] == 'search' and j['slot'] == 'once'
            media = []
            if stage == 'bound_visual_observation_v2':
                payload = {'program': p, 'image_pair_ref': pair}
                schema, template, cap = physical.observation_schema(p, pair), (physical.TEMPLATES / 'observe.txt').read_text(), 16384
            elif stage == 'instruction_relative_interpretation':
                observer = by_stage['bound_visual_observation_v2']
                assert observer['outcome'] == 'completed'
                physical.validate_observation(p, observer['parsed'], pair)
                payload = meaning.make_input(p, observer['parsed'], pair)
                schema, template, cap = meaning.schema(payload), meaning.PROMPT, 8192
            else:
                assert stage == 'flat_judge'
                payload = {'instruction': e['instruction']}
                schema, template, cap = task.SCHEMA, (task.TEMPLATES / 'regular.txt').read_text(), 2048
            if stage != 'instruction_relative_interpretation':
                media = [{'type': 'image', 'sha256': fingerprint(m['path'])} if m['type'] == 'image' else m
                         for m in media_inputs(e['evidence'])]
            assert j['payload'] == payload and j['media_identity'] == media and j['max_tokens'] == cap
            assert j['execution_ref'] == digest([limits['identity'], case, stage, payload, schema, template, media, 'once', cap])
            stages[stage] += 1
            outcomes[j['outcome']] += 1
            if 'response' in j:
                counts['input_tokens'] += int(j['response']['promptTokens'])
                counts['completion_tokens'] += int(j['response']['completionTokens'])
            else:
                counts['failed_output_reservations'] += cap
        reserved = counts['completion_tokens'] + counts['failed_output_reservations']
        assert counts['input_tokens'] == budget['input_tokens']
        assert reserved == budget['completion_tokens_or_reserved'] <= sibling.CASE_CAP
        assert set(budget['cases']) == {case}
        case_budget = budget['cases'][case]
        assert (case_budget['search'], case_budget['final'], case_budget['completion_tokens_or_reserved']) == (len(jobs), 0, reserved)
        assert case_budget.get('input_tokens', 0) == counts['input_tokens']
        saved = read(out / 'cases' / (case + '.json'))
        t = training[case]
        assert all(t[k] == v for k, v in e.items())
        assert all(t[k] == v for k, v in references[case].items())
        assert saved['program'] == t['program'] == p
        regular = saved['regular_judgment']
        if regular is None:
            assert saved['regular_error'] and t['regular'] == -1
        else:
            sibling.validate_regular(regular)
            assert by_stage['flat_judge']['outcome'] == 'completed'
            assert regular == by_stage['flat_judge']['parsed']
            assert saved['regular_execution_ref'] == by_stage['flat_judge']['execution_ref']
            assert t['regular'] == (task.LABELS.index(regular['label']) if regular['label'] in task.LABELS else -1)
        totals['regular_correct'] += t['regular'] == t['reference']
        assert t['regular_error'] == saved['regular_error'] and t['extraction_error'] == saved['extraction_error']
        if saved['features'] is None:
            assert saved['extraction_error'] and t['features'] is None
        else:
            assert saved['extraction_error'] is None and saved['pair_ref'] == pair
            assert by_stage['bound_visual_observation_v2']['outcome'] == by_stage['instruction_relative_interpretation']['outcome'] == 'completed'
            assert saved['observation'] == by_stage['bound_visual_observation_v2']['parsed']
            assert saved['interpretation'] == by_stage['instruction_relative_interpretation']['parsed']
            meaning.validate(meaning.make_input(p, saved['observation'], pair), saved['interpretation'])
            rebuilt = shared.evidence.project(p, saved['observation'], pair, saved['interpretation'])
            assert rebuilt == saved['features'] == t['features']
            totals['valid_feature_cases'] += 1
        totals.update(counts)
        totals['requests'] += len(jobs)
        combined_history.append((directory / 'llm-histories.log').read_text())
    assert totals['requests'] <= protocol['max_requests']
    assert totals['completion_tokens'] + totals['failed_output_reservations'] <= protocol['max_completion_tokens']
    results = read(out / 'results.json')
    for key in ('requests', 'regular_correct', 'valid_feature_cases'):
        assert results[key] == totals[key]
    assert results['cases'] == 540
    assert results['completion_tokens_or_reserved'] == totals['completion_tokens'] + totals['failed_output_reservations']
    if (out / 'preflight_logs/llm-histories.log').exists():
        assert (out / 'llm-histories.log').read_text() == ''.join(combined_history)
    result = {'passed': True, 'cases': 540, 'existing_sources': len(groups), 'new_source_groups': 0,
              'reserved_sources_excluded': 80, 'stage_counts': dict(stages), 'outcomes': dict(outcomes), **totals,
              'completion_tokens_or_reserved': results['completion_tokens_or_reserved'],
              'recorded_usage_estimate_usd': (totals['input_tokens'] * .1 + totals['completion_tokens'] * .5) / 1e6,
              'including_failed_output_reservations_usd': (totals['input_tokens'] * .1 + results['completion_tokens_or_reserved'] * .5) / 1e6,
              'new_model_calls_in_audit': 0, 'scope': 'Training collection only; no unseen-generalization accuracy claimed.'}
    audit_dir.mkdir(parents=True)
    save_json(audit_dir / 'verification.json', result)
    save_json(audit_dir / 'manifest.json', {'auditor_sha256': fingerprint(__file__),
              'training_data_sha256': fingerprint(out / 'training_data.json'), 'authorization_sha256': fingerprint(out / 'authorization.json')})
    (audit_dir / 'run.log').write_text('Rebuilt every per-output request, bound evidence projection, reused program, scope, token budget and reference join.\n')
    (audit_dir / 'llm-histories.log').write_text('Zero model calls.\n')
    print(result, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--audit-dir', type=Path, required=True)
    args = parser.parse_args()
    audit(args.output_dir.resolve(), args.audit_dir.resolve())
