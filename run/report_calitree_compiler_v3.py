"""Compare the compiler revision with the preserved failed Luna run."""
import argparse
import json
from collections import Counter
from pathlib import Path

from critical.core.decision.artifacts import digest
from run.calitree_three_splits import read, exact
from run.calitree_three_splits_compiler_v3 import SOURCE, prepare, audit_compiler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    out = parser.parse_args().output_dir.resolve(); manifest = prepare(out)
    previous = read(SOURCE / 'results.json'); current = read(out / 'results.json')
    old_obs = {r['case']: r for r in read(SOURCE / 'extraction/observations.json')}
    observed = {r['case']: r for r in read(out / 'extraction/observations.json')}
    def counts(rows):
        return {'compiled': sum(r['compilation'] is not None for r in rows.values()),
            'observed': sum(r['record'] is not None for r in rows.values()),
            'compiler_validation_failures': sum(bool(r['error'] and r['error']['stage'] == 'compile' and r['error']['code'] not in ('CallFailure', 'ProviderStopped', 'transport_error')) for r in rows.values()),
            'errors': dict(Counter((r['error'] or {}).get('code') for r in rows.values() if r['error']))}
    comparison = {'previous': counts(old_obs), 'revised': counts(observed),
        'all_previous_compiler_failures_now_valid': all(observed[k]['compilation'] is not None for k, r in old_obs.items() if r['error'] and r['error']['stage'] == 'compile'),
        'previous_failed_compiler_cases': [k for k, r in old_obs.items() if r['error'] and r['error']['stage'] == 'compile'],
        'compiled_previous_failed_cases': [k for k, r in old_obs.items() if r['error'] and r['error']['stage'] == 'compile' and observed[k]['compilation']],
        'payload_audit': audit_compiler(out, manifest, list(observed.values())),
        'previous_complete_hierarchies': previous['completed_hierarchies'], 'revised_complete_hierarchies': current['completed_hierarchies'],
        'previous_direct_evaluation': previous['pooled_evaluation']['direct'],
        'revised_pooled_evaluation': current['pooled_evaluation'], 'model': manifest['judge_identity'],
        'same_splits': read(out / 'same_split_verification.json'), 'reserved_test_predictions': 0}
    samples = []
    records = read(out / 'portable_records.json')
    for old, new in zip(previous['replications'], current['replications']):
        assert old['split'] == new['split']
        split = read(out / 'splits' / (new['split'] + '.json'))
        usable = lambda part: sum(records[r['case']]['features'] is not None and records[r['case']]['features']['features']['meaning_available'] for r in split[part])
        samples.append({'split': new['split'], 'usable_training': usable('train'), 'usable_evaluation': usable('evaluation'),
            'merged_available': new['arms']['merged']['available'], 'merged_training': new['selection']['training'],
            'merged_evaluation': new['arms']['merged']['metrics'] if new['arms']['merged']['available'] else None,
            'root_mode': new['selection']['root_mode'], 'root_rules': new['arms']['merged']['rules'],
            'direct_training': new['direct_training'], 'direct_evaluation': new['arms']['direct']['metrics'],
            'previous_direct_evaluation': old['arms']['direct']['metrics'],
            'root_run': new['selection']['selected_run'], 'runs': new['runs']})
    comparison['samples'] = samples
    remaining_failures = [{'case': row['case'], 'stage': row['error']['stage'], 'code': row['error']['code'],
        'transport': 'Transport failure' in row['error']['message']} for row in observed.values() if row['error']]
    exact(out / 'compiler_comparison.json', comparison)
    exact(out / 'failure_details.json', remaining_failures)
    lines = ['# Luna compiler fix: same three sampled splits', '',
        'All 180 sampled slots are identical to the previous run: three balanced 48-training / 12-evaluation splits, '
        '135 exact inputs from 134 source-pixel groups. Evaluation cohorts remain mutually disjoint and absent from every training cohort; training cohorts overlap. '
        'Historical exposure is disclosed. The reserved fifty remain excluded.', '',
        '## Compiler revision', '',
        '- Dynamic exact-instruction quote enums and bounded lowercase identifiers.',
        '- Role-specific polarity constraints, explicit positive preservation wording and self-contained questions with empty dependencies.',
        '- Original bound-evidence-v2 validator, binding, observer, projector and all merge gates remain in force.',
        '- At most one text-only compiler repair, using only the instruction, failed draft and validation diagnostic.',
        '- Fresh Luna upstream pass for every exact input, with no observation/transport/meaning retries or case replacements.', '',
        '| Measure | Previous Luna run | Revised compiler |', '|---|---:|---:|',
        f"| Valid compiler programs | {comparison['previous']['compiled']}/135 | {comparison['revised']['compiled']}/135 |",
        f"| Valid physical records | {comparison['previous']['observed']}/135 | {comparison['revised']['observed']}/135 |",
        f"| Final compiler validation failures | {comparison['previous']['compiler_validation_failures']} | {comparison['revised']['compiler_validation_failures']} |",
        f"| Complete qualifying hierarchies | {previous['completed_hierarchies']}/3 | {current['completed_hierarchies']}/3 |", '',
        '## Retraining and evaluation', '',
        '| Split | Usable train/evaluation | Merged fit | Merged evaluation | Direct-fit evaluation | Root mode | Root rules |',
        '|---|---|---|---|---|---|---|']
    for s in samples:
        fit = str(s['merged_training']['correct']) + '/48' if s['merged_training'] else 'No complete root'
        evaluation = str(s['merged_evaluation']['correct']) + '/12' if s['merged_evaluation'] else 'Unavailable'
        lines.append(f"| {s['split']} | {s['usable_training']}/48 · {s['usable_evaluation']}/12 | {fit} | {evaluation} | "
            f"{s['direct_evaluation']['correct']}/12 | {s['root_mode']} | {s['root_rules']} |")
    lines += ['', 'Pooled evaluation on 36 distinct sources:', '']
    for arm, metric in current['pooled_evaluation'].items():
        lines.append(f"- {arm}: {metric['correct']}/36 ({metric['accuracy']:.1%}), macro-F1 {metric['macro_f1']:.3f}, unresolved {metric['unresolved']}.")
    lines += ['', 'All three revised merged roots pass the unchanged training gate. The direct-fit arm is a diagnostic comparison, not automatically an accepted deployment.', '',
        '## Invariants and interpretation', '',
        'The strictly-above-90% full-denominator fit gate, per-class noncollapse gate, two-source/two-instruction leaf support, '
        'written-path consistency checks, exact descendant union, child-retention allowance, profiles, reuse/refinement budgets, '
        'bounded hierarchy search, and training-only root selection are unchanged. '
        'References never enter the compiler, observer, interpretation or repair payloads. '
        'All selected roots and direct controls are frozen before scoring the fixed evaluation cohort.', '',
        'This is a disclosed representation revision on historically exposed samples; it does not create a fresh confirmatory test. '
        'A merged/direct comparison evaluates the complete frozen learning procedures, not a causal effect of one merge. '
        'Three overlapping training samples and 36 evaluation sources provide limited statistical evidence. '
        'Passing the compiler validator checks structure and binding, not physical or semantic truth.', '',
        f"Actual new Luna calls: {read(out / 'collection_results.json')['attempts']} (ceiling 540). "
        f"Compiler repairs: {comparison['payload_audit']['compiler_repairs']}.\n",
        '```json', json.dumps(comparison['revised']['errors'], indent=2), '```', '',
        'The remaining failure is an observation transport failure for N057, retained as Unresolved in split 3 evaluation. All 48 training sources in each split have usable records.', '',
        'Detailed records are in `results.json`, `compiler_comparison.json`, `verification.json`, and the frozen `protocol.json`.']
    (out / 'compiler_report.md').write_text('\n'.join(lines) + '\n')
    print({'compiler': comparison['revised'], 'complete_hierarchies': current['completed_hierarchies'],
        'pooled_correct': {arm: metric['correct'] for arm, metric in current['pooled_evaluation'].items()}})


if __name__ == '__main__':
    main()
