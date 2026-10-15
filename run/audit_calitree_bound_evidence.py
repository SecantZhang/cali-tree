"""Independent structural/metric audit and adversarial M1 contract probes."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence import EvidenceContractError
from critical.core.decision import bound_evidence_v2 as implementation
from run.calitree_single_call import ROOT, read, fingerprint


def independent_prediction(program, record):
    checks = record['checks']; outcomes = {c['id'] for c in program['checks'] if c['role'] == 'outcome'}
    partial = outcomes | {c['id'] for c in program['checks'] if c['role'] == 'intermediate'}
    required = set(k for r in program['requirements'] for k in r['check_ids'])
    answers = []
    for unknown_value in (False, True):
        memo = {}
        def satisfied(k):
            if k not in memo:
                c = checks[k]; state = c['state']
                if state == 'not_applicable' and k not in required:
                    value = False
                elif state in ('unknown', 'not_applicable'):
                    value = unknown_value
                else:
                    value = state == c['expected_state']
                memo[k] = value and all(satisfied(d) for d in c['dependencies'])
            return memo[k]
        complete = all(satisfied(k) for k in required)
        collateral_ok = all(satisfied(k) for k, c in checks.items()
                            if c['role'].startswith('collateral_') and c['state'] != 'not_applicable')
        answers.append(2 if complete and collateral_ok else 1 if any(satisfied(k) for k in partial) else 0)
    return answers[0] if answers[0] == answers[1] else -1


def audit(output):
    m, result = read(output / 'manifest.json'), read(output / 'results.json')
    rows = read(output / 'observations.json')
    assert m['evidence_version'] == 'bound-physical-evidence-v2'
    m0 = ROOT / 'logs/exps/261014-semantic-hierarchy-m0-fifty-v1'
    allowed = read(m0 / 'splits/validation.json')['cases']
    assert m['cases'] == allowed and len(rows) == 12
    reserved = {c['group'] for c in read(m0 / 'splits/test.json')['cases']}
    assert not {c['group'] for c in allowed} & reserved
    for path, ref in m['pinned_files'].items():
        assert fingerprint(path) == ref
    for rel, ref in m['code_hashes'].items():
        assert fingerprint(ROOT / rel) == fingerprint(output / 'source_snapshot' / rel) == ref
    checked, absence_probes, bindings_rejected, predictions = 0, 0, 0, []
    temporal_coverage, diagnostics = {}, []
    for case, row in zip(allowed, rows):
        assert case['case'] == row['case']
        if row['record'] is None:
            predictions.append(-1); continue
        p = row['compilation']['program']; obs = row['observation']['observation']; record = row['record']
        plain = {k: deepcopy(v) for k, v in p.items() if k != 'program_ref'}
        assert digest(plain) == p['program_ref']
        context = [p['version'], p['instruction'], p['contract'], p['requirements']]
        assert p['instruction'] == case['instruction']
        ordered = [p['version'], 'source_first', case['image_hashes']['source_image'], case['image_hashes']['edited_image']]
        assert obs['image_pair_ref'] == digest(ordered)
        assert obs['program_ref'] == p['program_ref'] == record['program_ref']
        assert set(obs['checks']) == {c['id'] for c in p['checks']}
        temporal_coverage[case['case']] = []
        for r in p['requirements']:
            assert set(r['check_ids']) == {c['id'] for c in p['checks'] if c['role'] in ('outcome', 'identity', 'preservation') and r['id'] in c['requirement_ids']}
            assert any(c['role'] == 'outcome' and c['id'] in r['check_ids'] for c in p['checks'])
            temporal = any(c['role'] == 'outcome' and c['kind'] in implementation.TEMPORAL_KINDS and r['id'] in c['requirement_ids'] for c in p['checks'])
            if temporal:
                support = [c['id'] for c in p['checks'] if c['role'] == 'intermediate' and r['id'] in c['requirement_ids']]
                assert support
                temporal_coverage[case['case']].append({'requirement': r['id'], 'intermediates': support})
        for c in p['checks']:
            checked += 1
            check_body = {k: v for k, v in c.items() if k != 'check_ref'}
            assert c['check_ref'] == digest([context, check_body])
            answer = obs['checks'][c['id']]
            assert answer['check_ref'] == c['check_ref'] and answer['question'] == c['question']
            assert c['source_quote'] in p['instruction']
            # Independent normalization, including both absence polarities.
            expected = answer['state']
            if answer['applicability'] == 'unknown':
                expected = 'unknown'
            elif answer['applicability'] == 'not_applicable' or expected == 'not_applicable':
                expected = 'unknown' if c['role'] in ('outcome', 'identity', 'preservation') else 'not_applicable'
            if c['absence_when'] != 'never' and expected == c['absence_when']:
                if c['absence_source_anchor'] == 'required' and answer['source_anchor'] != 'identified' or answer['edited_coverage'] != 'adequate':
                    expected = 'unknown'
            assert record['checks'][c['id']]['state'] == expected
            if c['absence_when'] != 'never':
                probe = deepcopy(obs)
                probe['checks'][c['id']].update(state=c['absence_when'], applicability='applicable', edited_coverage='cropped')
                altered = implementation.derive_record(p, probe, obs['image_pair_ref'])
                assert altered['checks'][c['id']]['state'] == 'unknown'
                absence_probes += 1
                if c['absence_source_anchor'] == 'required':
                    probe['checks'][c['id']].update(edited_coverage='adequate', source_anchor='ambiguous')
                    altered = implementation.derive_record(p, probe, obs['image_pair_ref'])
                    assert altered['checks'][c['id']]['state'] == 'unknown'
                    absence_probes += 1
        bad = deepcopy(obs); first = p['checks'][0]['id']; bad['checks'][first]['question'] = 'A different physical question'
        try:
            implementation.derive_record(p, bad, obs['image_pair_ref'])
        except EvidenceContractError as exc:
            assert exc.code == 'check_binding_mismatch'; bindings_rejected += 1
        else:
            raise AssertionError('Mismatched question was accepted')
        expected = independent_prediction(p, record)
        assert expected == row['diagnostic']['prediction']; predictions.append(expected)
        diagnostics.extend({'case': case['case'], **d} for d in record['diagnostics'])
        compile_job = read(next((output / 'ledgers' / case['case'] / 'compile/jobs').glob('*.json')))
        visual_job = read(next((output / 'ledgers' / case['case'] / 'observe/jobs').glob('*.json')))
        assert compile_job['payload'] == {'instruction': case['instruction'], 'max_checks': 16}
        assert not compile_job['media_identity']
        assert visual_job['payload'] == {'program': p, 'image_pair_ref': obs['image_pair_ref']}
        assert visual_job['parsed'] == obs
        assert visual_job['media_identity'] == [
            {'type': 'text', 'text': 'SOURCE image'}, {'type': 'image', 'sha256': case['image_hashes']['source_image']},
            {'type': 'text', 'text': 'EDITED image'}, {'type': 'image', 'sha256': case['image_hashes']['edited_image']}]
    labels = ('no', 'partial', 'yes'); target = [labels.index(c['reference']) for c in allowed]
    metric = result['evaluation']['bound_exact_diagnostic']
    assert metric['correct'] == sum(p == y for p, y in zip(predictions, target))
    assert metric['unresolved'] == predictions.count(-1)
    f1 = []
    for k, name in enumerate(labels):
        tp = sum(p == y == k for p, y in zip(predictions, target))
        assert metric['per_class'][name]['recall'] == tp / 4
        f1.append(2 * tp / (4 + predictions.count(k)))
    assert abs(metric['macro_f1'] - sum(f1) / 3) < 1e-12
    assert not (m0 / 'predictions.json').exists() and not list(m0.glob('ledgers/**/jobs/*.json'))
    data = {'passed': True, 'valid_observed_cases': result['observed'], 'bound_questions_checked': checked,
            'mismatched_question_probes_rejected': bindings_rejected, 'absence_safeguard_probes': absence_probes,
            'temporal_requirement_coverage': temporal_coverage, 'normalization_diagnostics': diagnostics,
            'independent_predictions': predictions, 'reserved_test_overlap': 0, 'reserved_test_calls': 0,
            'new_model_calls': 0, 'limitation': 'Structural identity, uncertainty, and metric audit; not a guarantee of visual truth.'}
    path = output / 'independent_audit.json'
    if path.exists():
        assert read(path) == data
    else:
        save_json(path, data)
    print({k: v for k, v in data.items() if k not in ('temporal_requirement_coverage', 'normalization_diagnostics')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('output_dir', type=Path)
    audit(parser.parse_args().output_dir.resolve())
