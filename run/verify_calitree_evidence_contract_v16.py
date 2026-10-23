"""Verify the paired diagnostic and report changes without relabeling or fitting."""
import argparse
from collections import Counter
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence_v2 import image_identity, observation_schema, validate_observation, derive_record
from critical.core.decision.semantic_interpretation_v5 import FIELDS, make_input, schema, validate
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import project
from run import calitree_evidence_contract_v16 as runner


def audit(out):
    manifest = runner.prepare(out); protocol = runner.base.read(out / 'protocol.json')
    approval = runner.base.read(out / 'approval.json')
    assert approval['manifest_ref'] == manifest['artifact_ref']
    assert approval['max_requests'] == protocol['new_calls_max']
    assert approval['max_completion_tokens'] == protocol['completion_tokens_max']
    programs = runner.base.read(out / 'programs.json'); prompts = runner.base.read(out / 'prompts.json')
    saved = runner.base.read(out / 'observations.json'); lookup = {(r['case'], r['arm']): r for r in saved}
    expected = {(c['case'], arm) for c in manifest['cases'] for arm in runner.ARMS}
    assert len(saved) == len(expected) and set(lookup) == expected
    total_calls = tokens = 0; outcomes = Counter(); state_counts = {a: Counter() for a in runner.ARMS}
    source_map = {c['case']: c for c in manifest['cases']}
    for (case_id, arm), row in lookup.items():
        case = source_map[case_id]; program = programs[case_id]; pair = image_identity(case['evidence'])[1]
        folder = out / 'ledgers' / arm / case_id
        budget = runner.base.read(folder / 'budget.json'); jobs = [runner.base.read(p) for p in (folder / 'jobs').glob('*.json')]
        assert budget['limits']['identity'] == protocol['identity']
        assert budget['calls'] == len(jobs) == len(set(budget['attempted_slots'])) <= 2
        assert set(budget['attempted_slots']) == {j['execution_ref'] for j in jobs}
        assert budget['completion_tokens_or_reserved'] <= runner.base.CAPS['observe'] + runner.base.INTERPRET_CAP
        total_calls += budget['calls']; tokens += budget['completion_tokens_or_reserved']
        stages = {j['stage']: j for j in jobs}
        assert len(stages) == len(jobs)
        assert set(stages) <= {'bound_visual_observation_v2', 'instruction_relative_interpretation'}
        for stage, job in stages.items():
            assert job['outcome'] != 'interrupted'
            assert job['slot'] == 'once' and job['case_id'] == case_id
            outcomes[job['outcome']] += 1
            if stage == 'bound_visual_observation_v2':
                payload = {'program': program, 'image_pair_ref': pair}; contract = observation_schema(program, pair)
                media = [{'type': 'text', 'text': 'SOURCE image'}, {'type': 'image', 'sha256': case['image_hashes']['source_image']},
                         {'type': 'text', 'text': 'EDITED image'}, {'type': 'image', 'sha256': case['image_hashes']['edited_image']}]
                template, cap = prompts[arm]['observe'], runner.base.CAPS['observe']
            else:
                assert row['observation'] is not None
                payload = make_input(program, row['observation']['observation'], pair); contract = schema(payload)
                media = []; template, cap = prompts[arm]['interpret'], runner.base.INTERPRET_CAP
            assert job['payload'] == payload and job['media_identity'] == media and job['max_tokens'] == cap
            assert job['execution_ref'] == digest([protocol['identity'], case_id, stage, payload, contract, template, media, 'once', cap])
        if row['observation'] is not None:
            observation = row['observation']['observation']; validate_observation(program, observation, pair)
            observer_job = stages['bound_visual_observation_v2']
            assert observer_job['parsed'] == observation and observer_job['outcome'] == 'completed'
            assert observer_job['execution_ref'] == row['observation']['execution_ref']
            bound = derive_record(program, observation, pair)
            state_counts[arm].update(c['desired_state'] for c in bound['checks'].values())
            assert 'instruction_relative_interpretation' in stages
        else:
            assert row['interpretation'] is None and 'instruction_relative_interpretation' not in stages
        if row['interpretation'] is not None:
            value = row['interpretation']['value']; payload = make_input(program, row['observation']['observation'], pair)
            validate(payload, value); job = stages['instruction_relative_interpretation']
            assert job['outcome'] == 'completed' and job['parsed'] == value
            assert job['execution_ref'] == row['interpretation']['execution_ref']
            assert row['features'] == project(program, row['observation']['observation'], pair, value)
        else:
            assert row['features'] is None
    assert total_calls <= protocol['new_calls_max'] == 48
    assert tokens <= protocol['completion_tokens_max'] == 589824
    differences = []
    for case in manifest['cases']:
        original, clarified = (lookup[(case['case'], a)] for a in runner.ARMS)
        changes = []; meaning_changes = []
        if all(r['observation'] is not None for r in (original, clarified)):
            a, b = [derive_record(programs[case['case']], r['observation']['observation'], image_identity(case['evidence'])[1]) for r in (original, clarified)]
            for check in a['checks']:
                left, right = a['checks'][check], b['checks'][check]
                fields = {k: [left[k], right[k]] for k in ('state', 'desired_state') if left[k] != right[k]}
                for k in ('source_anchor', 'edited_coverage'):
                    if left['observation'][k] != right['observation'][k]:
                        fields[k] = [left['observation'][k], right['observation'][k]]
                if fields:
                    changes.append({'check': check, 'question': left['question'], 'changes': fields})
        if all(r['interpretation'] is not None for r in (original, clarified)):
            a, b = [r['interpretation']['value']['requirements'] for r in (original, clarified)]
            for requirement in a:
                changed = {k: [a[requirement][k], b[requirement][k]] for k in FIELDS if a[requirement][k] != b[requirement][k]}
                if changed:
                    meaning_changes.append({'requirement': requirement, 'changes': changed,
                        'original_explanation': a[requirement]['explanation'], 'clarified_explanation': b[requirement]['explanation']})
        differences.append({'case': case['case'], 'instruction': case['instruction'], 'checks': changes,
            'interpretations': meaning_changes, 'errors': {a: lookup[(case['case'], a)]['error'] for a in runner.ARMS}})
    result = {'passed': True, 'approval_bound': True, 'requests': total_calls, 'completion_tokens_or_reserved': tokens, 'outcomes': dict(outcomes),
        'effective_state_counts': {a: dict(v) for a, v in state_counts.items()}, 'cases': differences,
        'reference_labels_in_payloads': False, 'new_model_calls_in_audit': 0, 'final_set_access': False,
        'quality_improvement_claim': False, 'interpretation': 'Categorical changes require image/evidence review. Fresh paired prompts do not establish which arm is correct, and the diagnostic cohort is failure-selected.'}
    save_json(out / 'verification.json', result)
    lines = ['# Paired training evidence-contract diagnostic', '', result['interpretation'], '',
        f'{total_calls} requests, {tokens:,} conservatively charged completion tokens; caps 48 and 589,824. '
        'No label/reference feedback, fitting, relabeling, retries or final-set use.', '',
        '| Case | Instruction | Changed checks | Changed interpretations |', '|---|---|---:|---:|']
    for r in differences:
        lines.append(f"| {r['case']} | {r['instruction'].replace('|', '/')} | {len(r['checks'])} | {len(r['interpretations'])} |")
    lines += ['', 'Exact changed states, bindings, coverage flags and interpretation explanations are in verification.json. '
        'Original references remain in a separate file and are deliberately absent from this review table. '
        'Neither arm is automatically promoted.']
    (out / 'report.md').write_text('\n'.join(lines) + '\n')
    paths = sorted(p.relative_to(out).as_posix() for p in out.glob('**/*.json') if p.name not in ('completion_seal.json', 'review.json'))
    runner.base.exact(out / 'completion_seal.json', {'manifest_ref': manifest['artifact_ref'],
        'files': {name: runner.base.fingerprint(out / name) for name in paths}})
    print({k: v for k, v in result.items() if k != 'cases'})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    audit(parser.parse_args().output_dir.resolve())
