"""Independent support, bound-input, expert-selection and local-retention audit."""
import argparse
import json
from pathlib import Path

from critical.core.calibration import evidence_coverage_v20 as base, complete_evidence_coverage as completion
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.core.optimization.prompt.calitree.task_coverage import LABELS
from run.calitree_evidence_coverage_v20 import CachedRegularCalls, baseline_prediction, scores
from run.calitree_task_coverage import ROOT, read, fingerprint, exact


def audit(out):
    manifest = read(out / 'manifest.json'); protocol = read(out / 'protocol.json')
    assert digest(protocol) == manifest['protocol_ref']
    for name, expected in manifest['source_hashes'].items():
        assert fingerprint(name) == expected, name
    for name, expected in manifest['code_hashes'].items():
        assert fingerprint(ROOT / name) == expected, name
    previous = Path(manifest['base_run']); root = Path(manifest['source_root'])
    prior = Path(manifest['prior_directory']); meta = read(prior / 'manifest.json')['cases']
    calls = CachedRegularCalls(prior); evidence = root / 'logs/exps/261018-three-sampled-splits-luna-compiler-v3'
    local_count = transfer_count = guards = envelope_checks = bound_checks = fallback_checks = 0
    rebuilt = []; all_records = []; local_batches = 0
    for i in (1, 2, 3):
        data = read(previous / f'split{i}/training_data.json')
        programs = {r['source_group']: read(evidence / 'extraction/cases' / (r['case']+'.json'))['compilation']['program'] for r in data}
        source = root / f'logs/exps/261018-local-compression-v18-r1/split{i}'
        old = read(source / 'result.json'); models = [old['registry'][k] for k in old['forest']]
        original, fit_report = base.build(models, data, programs)
        assert original.export() == read(previous / f'split{i}/gate.json')
        filtered, completion_report = completion.complete(original, list(old['registry'].values()), data, programs)
        assert completion_report == read(out / f'split{i}/completion.json')
        original = filtered.base
        artifact = read(out / f'split{i}/gate.json')
        assert filtered.export() == artifact
        text = json.dumps(artifact)
        assert all(r['source_group'] not in text and r['instruction'] not in text for r in data)
        for rule in original.artifact['rules']:
            cohort = []
            for row in data:
                values = base.feature_values(programs[row['source_group']], row['features'])
                prediction = original.experts[rule['expert_ref']].predict_records([row['features']])[0]['prediction']
                if values is not None and prediction == rule['expert_prediction'] and all(values[c['feature']] == c['value'] for c in rule['guards']):
                    cohort.append(row)
            assert all(r['reference'] == rule['expert_prediction'] for r in cohort)
            assert rule['support'] == {'sources': len(cohort), 'instructions': len({r['instruction'] for r in cohort}), 'batches': len({r['batch'] for r in cohort})}
            assert len(cohort) >= 2 and len({r['instruction'] for r in cohort}) >= 2
            constants = [{'feature': f, 'value': cohort[0]['features']['features'][f]} for f in completion.supported.SEMANTIC
                         if all(r['features']['features'][f] == cohort[0]['features']['features'][f] for r in cohort)]
            assert artifact['envelopes'][digest(rule)]['conditions'] == constants
            guards += 1; envelope_checks += len(constants)
        local_sources = {r['source_group'] for r in data}; split = {'split': i}
        for scope in ('local', 'outside_training_sources'):
            records = read(out / f'split{i}/{scope}_predictions.json')
            before = {r['case']: r for r in read(previous / f'split{i}/{scope}_predictions.json')}
            for recorded in records:
                c = meta[recorded['case']]
                assert recorded['reference'] == c['reference'] and recorded['source_group'] == c['source_group']
                assert (c['source_group'] in local_sources) == (scope == 'local')
                extracted = read(evidence / 'extraction/cases' / (c['case']+'.json'))
                meaning = read(evidence / 'interpretations' / (c['case']+'.json'))['interpretation']
                p = extracted['compilation']['program']; pair = image_identity(c['evidence'])[1]
                record = base.project(p, extracted['observation']['observation'], pair, meaning)
                assert p['instruction'] == c['instruction']; bound_checks += 1
                values = base.feature_values(p, record); matching = []
                if values is not None and digest(base.task_scope(p)) in original.task_profiles:
                    for rule in original.artifact['rules']:
                        prediction = original.experts[rule['expert_ref']].predict_records([record])[0]['prediction']
                        if prediction == rule['expert_prediction'] and all(values[q['feature']] == q['value'] for q in rule['guards']):
                            matching.append((rule, prediction))
                labels = {prediction for _, prediction in matching}
                matching = [(rule, prediction) for rule, prediction in matching
                            if all(record['features'][q['feature']] == q['value'] for q in artifact['envelopes'][digest(rule)]['conditions'])] if len(labels) == 1 else []
                accepted = bool(matching); predicted = matching[0][1] if accepted else -1
                route = filtered.select_bound(p, extracted['observation']['observation'], pair, meaning)
                assert route == recorded['route'] and (route['covered'], route['prediction']) == (accepted, predicted)
                assert recorded['extraction_error'] is None
                regular = baseline_prediction(calls, c)
                assert recorded['regular'] == regular
                assert recorded['evidence_gate_tree'] == (predicted if accepted else regular)
                if accepted:
                    base_route = original.select(p, record)
                    assert base_route['covered'] and predicted == base_route['prediction']
                    assert recorded['served_by'] == 'frozen_tree' and recorded['fallback_execution_ref'] is None
                else:
                    assert recorded['served_by'] == 'regular_judge'
                    assert recorded['fallback_execution_ref'] == calls.requests[-1]['execution_ref']; fallback_checks += 1
                if scope == 'local':
                    assert recorded['evidence_gate_tree'] == recorded['reference']
                    local_count += 1
                else:
                    transfer_count += 1
            split[scope] = scores(records)
            split[scope]['semantic_support_deferrals'] = sum(r['route']['reason'] == 'outside_semantic_support' for r in records)
            if scope == 'local':
                split['children'] = {b: scores([r for r in records if r['batch'] == b]) for b in sorted({r['batch'] for r in records})}
                split['preserves_all_original_children'] = all(v['evidence_gate_tree_correct'] == v['total'] for v in split['children'].values())
                local_batches += len(split['children'])
            all_records.extend(records)
        rebuilt.append(split)
    result = read(out / 'results.json')
    assert result['splits'] == rebuilt
    assert result['local'] == scores([r for r in all_records if r['scope'] == 'local'])
    assert result['transfer'] == scores([r for r in all_records if r['scope'] != 'local'])
    assert result['preserves_all_original_children'] and result['new_model_calls'] == result['reserved_final_predictions'] == 0
    checks = {'passed': True, 'local_predictions_replayed': local_count, 'transfer_predictions_replayed': transfer_count,
              'original_child_batches_preserved': local_batches, 'completed_guard_regions_checked': guards,
              'semantic_support_conditions_checked': envelope_checks, 'bound_inputs_checked': bound_checks,
              'exact_fallback_responses_checked': fallback_checks, 'gate_refits_reproduced': 3,
              'no_case_membership_in_runtime': True, 'frozen_expert_outputs_preserved': True,
              'new_model_calls': 0, 'reserved_final_predictions': 0}
    exact(out / 'verification.json', checks)
    exact(out / 'completion_seal.json', {'files': {str(p.relative_to(out)): fingerprint(p) for p in sorted(out.rglob('*'))
                                                 if p.is_file() and p.name != 'completion_seal.json'},
                                        'auditor_sha256': fingerprint(__file__)})
    print(checks)
    return checks


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    audit(parser.parse_args().output_dir.resolve())
