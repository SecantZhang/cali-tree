"""Separate feasibility, upstream failures, and evaluation for the fixed study."""
import argparse
from collections import Counter
from pathlib import Path

from run.calitree_three_splits import read, exact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    out = parser.parse_args().output_dir.resolve()
    report = read(out / 'results.json'); manifest = read(out / 'manifest.json')
    observations = {r['case']: r for r in read(out / 'extraction/observations.json')}
    meanings = {r['case']: r for r in read(out / 'interpretations.json')}
    records = read(out / 'portable_records.json')
    available = {k for k, r in records.items() if r['features'] and r['features']['features']['meaning_available']}
    errors = Counter((r['error'] or {}).get('code') for r in observations.values() if r['error'])
    failed_cases = [{'case': r['case'], 'stage': r['error']['stage'], 'code': r['error']['code']}
                    for r in observations.values() if r['error']]
    semantic_errors = [{'case': r['case'], 'error': r['error']} for r in meanings.values()
                       if r['interpretation'] is None and observations[r['case']]['record'] is not None]
    rows = []
    for result in report['replications']:
        split = read(out / 'splits' / (result['split'] + '.json'))
        usable_train = sum(r['case'] in available for r in split['train'])
        usable_eval = sum(r['case'] in available for r in split['evaluation'])
        rows.append({'split': result['split'], 'usable_training': usable_train, 'usable_evaluation': usable_eval,
            'max_possible_training_correct': usable_train, 'required_training_correct': 44,
            'merged_root_available': result['arms']['merged']['available'],
            'merged_training': result['selection']['training'],
            'merged_evaluation': result['arms']['merged']['metrics'] if result['arms']['merged']['available'] else None,
            'direct_training': result['direct_training'], 'direct_evaluation': result['arms']['direct']['metrics'],
            'original_v11_on_luna_evidence': result['arms']['original_v11']['metrics']})
    assessment = {'model': manifest['judge_identity'], 'unique_sources': manifest['unique_sources'], 'unique_inputs': len(records), 'usable_records': len(available),
        'physical_errors': dict(errors), 'semantic_errors': semantic_errors, 'failed_physical_cases': failed_cases,
        'replications': rows, 'completed_hierarchies': report['completed_hierarchies'],
        'inference': 'The unchanged Luna pipeline is infeasible under the sealed local gate; this run cannot measure a merged-tree generalization benefit.'
            if report['completed_hierarchies'] == 0 else 'Compare paired evaluation and feasibility under the fixed procedures; small correlated replications limit inference.',
        'transport_failure_caveat': 'Transport failures are counted separately from compiler/interpretation contract failures. Neither is silently retried or dropped.',
        'model_change': read(out / 'model_change.json'), 'reserved_test_predictions': 0}
    exact(out / 'assessment.json', assessment)
    lines = ['# Three sampled splits with GPT-6 Luna', '', assessment['inference'], '',
        'The sampled cases, prompts, feature vocabulary, calibration profiles, M5–M7 gates and bounded searches were fixed before observing results. '
        'All new calls use `gpt-6-luna`, reasoning disabled, temperature 0. '
        'Three balanced 48-training / 12-evaluation splits use 134 distinct sources. '
        'All 36 evaluation sources are distinct and excluded from every training split; training samples overlap by 23, 16 and 20 sources pairwise. '
        'The original 60 and reserved 50 are excluded. Historical exposure is disclosed; these are not globally fresh examples.', '',
        '| Split | Usable training / 48 | Usable evaluation / 12 | Qualifying merged root | Direct-fit training | Direct-fit evaluation |',
        '|---|---|---|---|---|---|']
    for row in rows:
        lines.append(f"| {row['split']} | {row['usable_training']}/48 | {row['usable_evaluation']}/12 | "
            f"{'Available' if row['merged_root_available'] else 'None'} | "
            f"{row['direct_training']['correct'] if row['direct_training'] else 0}/48 | {row['direct_evaluation']['correct']}/12 |")
    lines += ['', 'The unchanged gate requires at least 44/48 correct. Missing/invalid records produce Unresolved and remain in the denominator. '
        'A merged policy that was never produced has no conditional classifier accuracy; the machine-readable all-source end-to-end score records its twelve outputs as Unresolved. '
        'The direct-fit arm is a diagnostic control, not a qualified replacement deployment.', '',
        '## Failure accounting', '', f"- Valid complete portable records: {len(available)}/{len(records)}."]
    lines += [f'- {key}: {value} source(s).' for key, value in sorted(errors.items())]
    lines += [f'- Semantic interpretation failures after valid physical evidence: {len(semantic_errors)}.',
        f"- Actual Luna attempts: {report['collection']['attempts']} (ceiling 402).",
        '- The corrected cache distinguishes 135 exact inputs from 134 source-pixel groups; all 180 sampled input slots stay fixed. Original input-identity errors and partial fits are preserved separately, and only the one missing exact input was collected.',
        '- Two completed Sol calls from before the model-change request are preserved separately and not reused.', '',
        assessment['transport_failure_caveat'], '', '## What this says about merging', '',
        'This evaluates the complete Luna pipeline with unchanged prompts and contracts. Upstream failures can prevent the parent gate from being satisfiable even if fitting is perfect on all usable sources. '
        'Consequently, an absent merged tree cannot support a claim for or against the generalization benefit of merging. '
        'A later compiler/observer reliability revision should be a separately declared experiment, or a learner-only study can hold evidence fixed. '
        'No prompt repair, retries, resampling, gate relaxation, or reserved-final inference was performed in this study.', '',
        'See `results.json` for every arm/case/prediction/trace, `assessment.json` for failure attribution, '
        '`splits/` for the fixed source assignments, `protocol.json` for settings and `verification.json` for the offline audit.']
    (out / 'assessment.md').write_text('\n'.join(lines) + '\n')
    print(assessment['inference'])
    print(rows)


if __name__ == '__main__':
    main()
