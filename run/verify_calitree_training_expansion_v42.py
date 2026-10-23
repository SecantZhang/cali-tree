"""Rebuild every request identity and evidence feature in the approved expansion.

Read-only independent audit; never imports credentials or performs model calls.
"""
import argparse
from collections import Counter
from pathlib import Path

from jsonschema import ValidationError

from critical.core.decision import bound_compiler_v3 as compiler
from critical.core.decision import bound_evidence_v2 as physical
from critical.core.decision import semantic_interpretation_v5 as meaning
from critical.core.decision.bound_evidence import EvidenceContractError
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.compiler import media_inputs
from critical.core.calibration import shared_regions_v27 as shared
from critical.core.optimization.prompt.calitree import task_coverage as task
from run import calitree_training_expansion_v42 as expansion
from run.calitree_accuracy_headroom_v37 import dataset
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint


def audit(out, audit_dir):
    if audit_dir.exists():
        raise ValueError('Fresh audit directory required')
    protocol = expansion.verify(out)
    seal = read(out / 'preflight_seal.json')
    for name, sha in seal['files'].items():
        archived = out / 'preflight_logs' / name
        original = archived if name in ('run.log', 'llm-histories.log') and archived.exists() else out / name
        assert fingerprint(original) == sha, name
    if (out / 'preflight_logs/llm-histories.log').exists():
        assert fingerprint(out / 'llm-histories.log') == fingerprint(out / 'ledger/llm-histories.log')
    for name, sha in seal['upstream_code_and_prompt_hashes'].items():
        assert fingerprint(name) == sha, name
    budget = read(out / 'ledger/budget.json')
    limits = budget['limits']
    assert limits['identity'] == expansion.IDENTITY
    assert limits['max_calls'] == protocol['max_requests'] == 544
    assert limits['max_completion_tokens'] == protocol['max_completion_tokens'] == 4784128
    assert limits['scope_limits'] == {'search': 3, 'final': 0}
    assert not budget['stopped']
    entries = {e['case']: e for e in read(out / 'inputs.json')}
    training = {e['case']: e for e in read(out / 'training_data.json')}
    references = read(out / 'references.json')
    assert set(entries) == set(training) == set(references) and len(entries) == 160
    local, recent, _ = dataset()
    reserved = read(expansion.RESERVED / 'inputs_without_labels.json')
    new_sources = {e['source_group'] for e in entries.values()}
    assert len(new_sources) == 32
    assert not new_sources & {e['source_group'] for e in local + recent + reserved}
    assert all('reference' not in e and 'human_score' not in e for e in entries.values())
    instructions = {digest(e['instruction']): e['instruction'] for e in entries.values()}
    jobs = [read(p) for p in sorted((out / 'ledger/jobs').glob('*.json'))]
    job_by_stage = {}
    for job in jobs:
        assert job['phase'] == 'search' and job['slot'] == 'once'
        key = (job['case_id'], job['stage'])
        assert key not in job_by_stage
        job_by_stage[key] = job
    input_tokens = completion_tokens = reservations = 0
    outcomes, stages, case_calls = Counter(), Counter(), Counter()
    for job in jobs:
        stage, case = job['stage'], job['case_id']
        media = []
        if stage.startswith('bound_instruction_v3'):
            assert case.startswith('compile-') and case[8:] in instructions
            instruction = instructions[case[8:]]
            payload = {'instruction': instruction, 'max_checks': physical.MAX_CHECKS}
            schema, template, cap = compiler.schema_for(instruction), compiler.TEMPLATE.read_text(), 8192
            if stage == 'bound_instruction_v3_repair':
                first = job_by_stage[(case, 'bound_instruction_v3')]
                assert first['outcome'] == 'completed'
                try:
                    compiler.checked_program(instruction, first['parsed'])
                except (ValidationError, EvidenceContractError) as exc:
                    failure = compiler.diagnostic(exc)
                else:
                    raise AssertionError('Unnecessary compiler repair')
                payload.update(draft=first['parsed'], validation_error=failure)
                template = compiler.REPAIR_TEMPLATE + template
            else:
                assert stage == 'bound_instruction_v3'
        else:
            assert case in entries
            e = entries[case]
            program = read(out / 'programs' / (digest(e['instruction']) + '.json'))['program']
            pair = physical.image_identity(e['evidence'])[1]
            if stage == 'flat_judge':
                payload, schema = {'instruction': e['instruction']}, task.SCHEMA
                template, cap = (task.TEMPLATES / 'regular.txt').read_text(), 2048
            elif stage == 'bound_visual_observation_v2':
                assert program is not None
                payload, schema = {'program': program, 'image_pair_ref': pair}, physical.observation_schema(program, pair)
                template, cap = (physical.TEMPLATES / 'observe.txt').read_text(), 16384
            else:
                assert stage == 'instruction_relative_interpretation' and program is not None
                observer = job_by_stage[(case, 'bound_visual_observation_v2')]
                assert observer['outcome'] == 'completed'
                physical.validate_observation(program, observer['parsed'], pair)
                payload = meaning.make_input(program, observer['parsed'], pair)
                schema, template, cap = meaning.schema(payload), meaning.PROMPT, 8192
            if stage != 'instruction_relative_interpretation':
                media = [{'type': 'image', 'sha256': fingerprint(m['path'])} if m['type'] == 'image' else m
                         for m in media_inputs(e['evidence'])]
        assert job['payload'] == payload and job['media_identity'] == media and job['max_tokens'] == cap
        expected = digest([limits['identity'], case, stage, payload, schema, template, media, 'once', cap])
        assert job['execution_ref'] == expected
        case_calls[case] += 1
        stages[stage] += 1
        outcomes[job['outcome']] += 1
        if 'response' in job:
            input_tokens += int(job['response']['promptTokens'])
            completion_tokens += int(job['response']['completionTokens'])
        else:
            reservations += cap
    assert set(budget['attempted_slots']) == {j['execution_ref'] for j in jobs}
    assert budget['calls'] == len(jobs) == len(budget['attempted_slots']) <= 544
    assert input_tokens == budget['input_tokens']
    assert completion_tokens + reservations == budget['completion_tokens_or_reserved'] <= 4784128
    assert stages['bound_instruction_v3'] == len(instructions) <= 32
    assert stages['bound_instruction_v3_repair'] <= 32
    for case, count in case_calls.items():
        assert count <= (2 if case.startswith('compile-') else 3)
        assert budget['cases'][case]['search'] == count and budget['cases'][case]['final'] == 0
    valid = correct = 0
    for key, instruction in instructions.items():
        saved = read(out / 'programs' / (key + '.json'))
        initial = job_by_stage[('compile-' + key, 'bound_instruction_v3')]
        last = job_by_stage.get(('compile-' + key, 'bound_instruction_v3_repair'), initial)
        if saved['program'] is not None:
            assert last['outcome'] == 'completed'
            assert saved['program'] == compiler.checked_program(instruction, last['parsed'])
        else:
            assert saved['error']
    for case, e in entries.items():
        saved = read(out / 'cases' / (case + '.json'))
        t = training[case]
        assert all(t[k] == v for k, v in e.items())
        assert t['reference'] == references[case]
        assert saved['program'] == t['program']
        regular = job_by_stage[(case, 'flat_judge')]
        judgment = saved['regular_judgment']
        if judgment is not None:
            assert regular['outcome'] == 'completed' and judgment == regular['parsed']
            assert saved['regular_execution_ref'] == regular['execution_ref']
            expansion.validate_regular(judgment)
            label = task.LABELS.index(judgment['label']) if judgment['label'] in task.LABELS else -1
        else:
            assert saved['regular_error']
            label = -1
        assert t['regular'] == label
        correct += label == t['reference']
        if saved['features'] is not None:
            assert saved['extraction_error'] is None
            observer = job_by_stage[(case, 'bound_visual_observation_v2')]
            interpretation = job_by_stage[(case, 'instruction_relative_interpretation')]
            assert observer['parsed'] == saved['observation']
            assert interpretation['parsed'] == saved['interpretation']
            assert saved['pair_ref'] == physical.image_identity(e['evidence'])[1]
            payload = meaning.make_input(saved['program'], saved['observation'], saved['pair_ref'])
            meaning.validate(payload, saved['interpretation'])
            rebuilt = shared.evidence.project(saved['program'], saved['observation'], saved['pair_ref'], saved['interpretation'])
            assert rebuilt == saved['features'] == t['features']
            valid += 1
        else:
            assert saved['extraction_error'] and t['features'] is None
    result = {'passed': True, 'cases': len(entries), 'new_sources': len(new_sources), 'reserved_sources_excluded': 80,
              'request_identities_rebuilt': len(jobs), 'stage_counts': dict(stages), 'outcomes': dict(outcomes),
              'input_tokens': input_tokens, 'completion_tokens': completion_tokens, 'failed_output_reservations': reservations,
              'completion_tokens_or_reserved': completion_tokens + reservations, 'valid_feature_cases': valid,
              'regular_training_correct': correct, 'new_model_calls_in_audit': 0,
              'recorded_usage_estimate_usd': input_tokens * .1 / 1e6 + completion_tokens * .5 / 1e6,
              'including_failed_output_reservations_usd': input_tokens * .1 / 1e6 + (completion_tokens + reservations) * .5 / 1e6,
              'scope': 'Training collection audit only; no unseen-generalization accuracy claimed.'}
    assert read(out / 'results.json')['valid_feature_cases'] == valid
    assert read(out / 'results.json')['regular_correct'] == correct
    audit_dir.mkdir(parents=True)
    save_json(audit_dir / 'verification.json', result)
    save_json(audit_dir / 'manifest.json', {'auditor_sha256': fingerprint(__file__),
              'budget_sha256': fingerprint(out / 'ledger/budget.json'), 'training_data_sha256': fingerprint(out / 'training_data.json')})
    (audit_dir / 'run.log').write_text('Independently rebuilt request identities, scopes, budgets, compiler bindings, features, label joins, and fitting-source exclusions.\n')
    (audit_dir / 'llm-histories.log').write_text('Zero model calls.\n')
    print(result, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--audit-dir', type=Path, required=True)
    args = parser.parse_args()
    audit(args.output_dir.resolve(), args.audit_dir.resolve())
