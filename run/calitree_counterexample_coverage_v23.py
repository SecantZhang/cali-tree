"""Review false acceptances and calibrate rejection without changing verdicts.

All former transfer examples used here are explicitly development/calibration
data. Protect every local route and every previously correct accepted transfer
route; send reviewed errors to the unchanged regular judge. Offline only.
"""
import argparse
from collections import Counter
from pathlib import Path

from critical.core.calibration import counterexample_coverage_v23 as calibration
from critical.core.calibration.evidence_support_v21 import SupportedCoverageGate
from critical.core.decision.artifacts import digest, save_json
from critical.core.optimization.prompt.calitree.bound_evidence_cache import BoundEvidenceCache, CachedEvidenceCoveredJudge
from critical.core.optimization.prompt.calitree.task_coverage import LABELS
from run.calitree_evidence_coverage_v20 import CachedRegularCalls, scores
from run.calitree_task_coverage import ROOT, IDENTITY, read, fingerprint

VERSION = 'reviewed-coverage-errors-v23'


def load_examples(previous, split):
    manifest = read(previous / 'manifest.json')
    evidence = Path(manifest['source_root']) / 'logs/exps/261018-three-sampled-splits-luna-compiler-v3'
    cohorts = {}; bound = {}; files = set()
    for scope in ('local', 'outside_training_sources'):
        path = previous / f'split{split}/{scope}_predictions.json'; files.add(path)
        rows = read(path); cohorts[scope] = rows
        for row in rows:
            path = evidence / 'extraction/cases' / (row['case'] + '.json')
            meaning_path = evidence / 'interpretations' / (row['case'] + '.json'); files.update((path, meaning_path))
            extraction = read(path); meaning = read(meaning_path)['interpretation']
            program = extraction['compilation']['program']; observation = extraction['observation']['observation']
            record = calibration.features.project(program, observation, observation['image_pair_ref'], meaning)
            bound[row['case']] = {'example': {'case': row['case'], 'source_group': row['source_group'],
                                               'program': program, 'features': record, 'reference': row['reference']},
                                 'observation': observation, 'interpretation': meaning}
    errors = [r for r in cohorts['outside_training_sources'] if r['route']['covered'] and r['route']['prediction'] != r['reference']]
    controls = [r for r in cohorts['outside_training_sources'] if r['route']['covered'] and r['route']['prediction'] == r['reference']]
    protected = cohorts['local'] + controls
    return cohorts, bound, protected, errors, files


def run(out, previous):
    if out.exists() and any(out.iterdir()):
        raise ValueError('Use a fresh output directory')
    out.mkdir(parents=True, exist_ok=True)
    old_manifest = read(previous / 'manifest.json')
    for name, expected in read(previous / 'completion_seal.json')['files'].items():
        assert fingerprint(previous / name) == expected, name
    prior = Path(old_manifest['prior_directory']); metadata = read(prior / 'manifest.json')['cases']
    calls = CachedRegularCalls(prior)
    source_files = {previous / 'completion_seal.json', previous / 'manifest.json'}
    prepared = []; reviews = []; results = []; all_rows = []; raw_local = []
    for i in (1, 2, 3):
        gate_path = previous / f'split{i}/gate.json'; source_files.add(gate_path)
        gate = SupportedCoverageGate(read(gate_path))
        cohorts, bound, protected, errors, files = load_examples(previous, i); source_files.update(files)
        examples = [bound[r['case']]['example'] for r in protected]
        failures = [bound[r['case']]['example'] for r in errors]
        final, report = calibration.fit(gate, examples, failures)
        save_json(out / f'split{i}/gate.json', final.export()); save_json(out / f'split{i}/fit.json', report)
        save_json(out / f'split{i}/calibration_membership.json', {
            'local': [r['case'] for r in cohorts['local']],
            'protected_correct_transfer': [r['case'] for r in protected if r['scope'] != 'local'],
            'reviewed_errors': [r['case'] for r in errors]})
        # Error-only leave-one-out: a diagnostic of shared rejection patterns,
        # not a fresh test of the full gate (positive controls remain fixed).
        loo = []
        for held in errors:
            remaining = [bound[r['case']]['example'] for r in errors if r['case'] != held['case']]
            partial, _ = calibration.fit(gate, examples, remaining)
            item = bound[held['case']]['example']
            loo.append({'case': held['case'], 'rejected_without_its_counterexample': not partial.select(item['program'], item['features'])['covered']})
        save_json(out / f'split{i}/leave_one_error_out.json', loo)
        for row in errors:
            item = bound[row['case']]['example']; values = calibration.features.feature_values(item['program'], item['features'])
            violated = [c for c in final.artifact['support_clauses'] if not calibration.clause_passes(c, values)]
            review = {'split': i, 'case': row['case'], 'instruction': item['program']['instruction'],
                      'previous_prediction': row['route']['prediction'], 'reference': row['reference'], 'regular_prediction': row['regular'],
                      'previous_matching_regions': row['route']['matches'],
                      'rejection_conditions': [[{'feature': c['feature'], 'actual': values[c['feature']],
                                                 'required_to_pass_clause': c['value'], 'meaning': calibration.features.FEATURES[c['feature']]} for c in clause]
                                                for clause in violated]}
            reviews.append(review)
        prepared.append((i, final, cohorts, bound, report, loo))
        print({'split': i, 'protected': len(protected), 'reviewed_errors': len(errors), 'clauses': report['clauses'],
               'literal_tests': report['literal_tests'], 'loo_rejected': sum(r['rejected_without_its_counterexample'] for r in loo)}, flush=True)
    for i, gate, cohorts, bound, fit, loo in prepared:
        cache = BoundEvidenceCache(IDENTITY)
        for row in cohorts['local']:
            case = metadata[row['case']]; item = bound[row['case']]
            cache.add(case['instruction'], case['evidence'], item['example']['program'], item['observation'], item['interpretation'])
        save_json(out / f'split{i}/evidence_cache.json', cache.export())
        judge = CachedEvidenceCoveredJudge(calls, gate, cache, identity=IDENTITY)
        result = {'split': i, 'clauses': fit['clauses'], 'literal_tests': fit['literal_tests'],
                  'leave_one_error_out': {'rejected': sum(r['rejected_without_its_counterexample'] for r in loo), 'total': len(loo)}}
        for scope, old_rows in cohorts.items():
            current = []
            for row in old_rows:
                case = metadata[row['case']]; item = bound[row['case']]
                if scope == 'local':
                    # No features, program, label or original membership passed.
                    value = judge.judge(case['instruction'], case['evidence'], case_id='new-raw-id-' + str(len(raw_local)))
                    assert value['evidence_source'] == 'content_cache'
                else:
                    value = judge.judge(case['instruction'], case['evidence'], program=item['example']['program'],
                                        observation=item['observation'], interpretation=item['interpretation'], case_id=case['case'])
                route = value['route']; prediction = LABELS.index(value['judgment']['label']) if value['judgment']['label'] in LABELS else -1
                previous_route = row['route']
                if route['covered']:
                    assert previous_route['covered'] and route['prediction'] == previous_route['prediction']
                elif not previous_route['covered']:
                    assert route == previous_route
                if scope == 'local':
                    assert route['covered'] and prediction == row['reference'] and value['source'] == 'frozen_tree'
                elif previous_route['covered']:
                    assert route['covered'] == (previous_route['prediction'] == row['reference'])
                record = {**row, 'previous_route': previous_route, 'previous_system_prediction': row['evidence_gate_tree'],
                          'evidence_gate_tree': prediction, 'route': route, 'served_by': value['source'],
                          'fallback_execution_ref': value['execution_ref'], 'extraction_error': value['extraction_error'],
                          'evidence_source': value['evidence_source']}
                current.append(record); all_rows.append(record)
                if scope == 'local':
                    raw_local.append(record)
            save_json(out / f'split{i}/{scope}_predictions.json', current)
            result[scope] = scores(current)
            result[scope]['new_rejections'] = sum(r['previous_route']['covered'] and not r['route']['covered'] for r in current)
            if scope == 'local':
                result['children'] = {b: scores([r for r in current if r['batch'] == b]) for b in sorted({r['batch'] for r in current})}
                result['preserves_all_original_children'] = all(v['evidence_gate_tree_correct'] == v['total'] for v in result['children'].values())
        results.append(result)
        print({'split': i, 'local_correct': result['local']['evidence_gate_tree_correct'],
               'development_accepted': result['outside_training_sources']['gate_accepted'],
               'development_accepted_correct': result['outside_training_sources']['gate_accepted_correct'],
               'development_system_correct': result['outside_training_sources']['evidence_gate_tree_correct']}, flush=True)
    protocol = {'version': VERSION, 'config': calibration.asdict(calibration.Config()),
                'objective': 'Reject all 22 reviewed false acceptances while preserving every local tree prediction and all 38 previously correct accepted transfer routes.',
                'development_boundary': 'The former transfer set now explicitly participates in rejection calibration. Its post-fit precision is not held-out performance.',
                'negative_selection': 'All previously accepted wrong predictions, no subset selection.',
                'protected_selection': 'All original local inputs plus every previously accepted correct transfer input.',
                'runtime': 'Declared Boolean clauses only; no source/image IDs, instruction text lookup, human labels or changed verdicts at inference.',
                'fallback': 'Exact regular judge, unchanged; its saved responses are replayed by input content.',
                'new_model_calls': 0, 'reserved_final_predictions': 0}
    code = [Path(__file__).resolve(), Path(calibration.__file__).resolve(), ROOT / 'run/calitree_evidence_coverage_v20.py',
            ROOT / 'critical/core/optimization/prompt/calitree/bound_evidence_cache.py']
    manifest = {**old_manifest, 'previous_gate_run': str(previous), 'protocol_ref': digest(protocol),
                'source_hashes': {**old_manifest['source_hashes'], **{str(p): fingerprint(p) for p in sorted(source_files)}},
                'code_hashes': {**old_manifest['code_hashes'], **{str(p.relative_to(ROOT)): fingerprint(p) for p in code}}}
    summary = {'version': VERSION, 'splits': results, 'local': scores([r for r in all_rows if r['scope'] == 'local']),
               'development': scores([r for r in all_rows if r['scope'] != 'local']),
               'reviewed_error_slots': len(reviews), 'reviewed_unique_cases': len({r['case'] for r in reviews}),
               'reviewed_reference_counts': dict(Counter(r['reference'] for r in reviews)),
               'preserves_all_original_children': all(r['preserves_all_original_children'] for r in results),
               'raw_local_tree_predictions': sum(r['served_by'] == 'frozen_tree' for r in raw_local),
               'new_model_calls': 0, 'reserved_final_predictions': 0, 'deployed_by_default': False}
    for name, value in (('protocol', protocol), ('manifest', manifest), ('results', summary), ('error_review', reviews)):
        save_json(out / (name + '.json'), value)
    (out / 'run.log').write_text(str(summary) + '\n')
    (out / 'llm-histories.log').write_text('No new model calls. Original bound evidence and exact regular responses replayed.\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True); p.add_argument('--previous-run', type=Path, required=True)
    a = p.parse_args(); run(a.output_dir.resolve(), a.previous_run.resolve())
