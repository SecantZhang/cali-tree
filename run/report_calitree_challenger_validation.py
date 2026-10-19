"""Add complete validation/failure and per-case comparisons to the v12 report."""
import argparse
from collections import Counter
from pathlib import Path
import csv
import json

from critical.core.decision.artifacts import save_json
from run.calitree_challenger_validation import SOURCE, prepare
from run.calitree_three_splits import read

MARKER = '\n## Complete inner-validation accounting\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    out = parser.parse_args().output_dir.resolve(); prepare(out)
    result = read(out / 'results.json'); rows = []; paired = Counter(); against_direct = Counter()
    for split in result['splits']:
        name = split['split']; previous = read(SOURCE / name / 'results.json')
        for new, old, direct in zip(split['cases'], previous['arms']['merged']['cases'], previous['arms']['direct']['cases']):
            assert new['case'] == old['case'] == direct['case'] and new['reference'] == old['reference'] == direct['reference']
            cn, co, cd = new['prediction'] == new['reference'], old['prediction'] == old['reference'], direct['prediction'] == direct['reference']
            paired['both_correct' if cn and co else 'new_only' if cn else 'old_only' if co else 'both_wrong'] += 1
            against_direct['both_correct' if cn and cd else 'new_only' if cn else 'direct_only' if cd else 'both_wrong'] += 1
            rows.append({'split': name, 'case': new['case'], 'instruction': new['instruction'], 'reference': new['reference'],
                'new_prediction': new['prediction'], 'previous_prediction': old['prediction'], 'direct_prediction': direct['prediction'],
                'selected_grouping': split['selection']['method'], 'selected_family': split['selection']['family']})
    assert dict(paired) == result['paired_vs_previous']
    with (out / 'comparison_cases.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    details = []
    for i in (1, 2, 3):
        summaries = read(out / f'split{i}/validation_summary.json')
        for method, families in summaries.items():
            for family, stats in families.items():
                details.append({'split': f'split{i}', 'method': method, 'family': family, **stats})
    extra = {'validation_configurations': details, 'family_fold_evaluations': len(details) * 4,
        'failed_family_folds': sum(len(d['failed_folds']) for d in details),
        'paired_vs_previous': dict(paired), 'paired_vs_direct': dict(against_direct),
        'new_predictions_identical_to_direct': all(r['new_prediction'] == r['direct_prediction'] for r in rows),
        'new_model_calls': 0}
    save_json(out / 'comparison_details.json', extra)
    lines = [MARKER.strip(), '',
        '| Split | Grouping | Family | OOF correct / 48 | Macro-F1 | Feasible folds / 4 | Unresolved OOF |',
        '|---|---|---|---:|---:|---:|---:|']
    for d in details:
        lines.append(f"| {d['split']} | {d['method']} | {d['family']} | {d['metrics']['correct']}/48 | "
                     f"{d['metrics']['macro_f1']:.3f} | {d['feasible_folds']}/4 | {d['metrics']['unresolved']} |")
    lines += ['', f"All 72 family/fold outcomes are retained, including {extra['failed_family_folds']} failures to produce a qualifying family root. "
        'Every configuration is scored on all 48 original training references through out-of-fold predictions.', '',
        'The unchanged strictly-above-90% gate has a discrete small-sample effect: first unions of 8, 9 or 10 inner sources '
        'require 8/8, 9/9 or 10/10 correct. Full-data eight-group first unions have 12 sources and require 11/12. '
        'Validation therefore measures both transfer and the smaller-training-set feasibility of each grouping procedure. '
        'No inner threshold was softened. This limits how strongly the preference for four groups should be generalized.', '',
        'The selected full-grammar/four-group procedure has all four feasible folds on each split, but OOF correctness of '
        '10/48, 18/48 and 25/48 is weak. Passing the unchanged local gates is not evidence of robust predictive performance.', '',
        '## Paired comparison', '',
        '```json', json.dumps({'vs_previous_merging': dict(paired), 'vs_direct': dict(against_direct)}, indent=2), '```', '',
        f"Revised and direct predictions are {'identical on all 36 evaluation sources' if extra['new_predictions_identical_to_direct'] else 'not identical on all evaluation sources'}.", '',
        'The revised procedure improves split 1 from 3/12 to 6/12, ties split 2 at 6/12, and reduces split 3 from 8/12 to 6/12. '
        'The one-case pooled improvement (17 -> 18 of 36) matches direct fitting overall and does not establish a reliable generalization advantage. '
        'Do not tune this revision further on these evaluation outcomes and present the resulting score as a fresh test.', '',
        'The selection unit is a grouping/generation-family procedure. Its hierarchy is regenerated within each inner training fold. '
        'The final full-48 tree is a refit using the selected procedure, not the same individual tree tested on the inner folds. '
        'All core gate implementations, thresholds, refinement budgets, source cohorts and cached evidence are preserved.', '',
        'Implementation: `critical/core/calibration/semantic_hierarchy/union_validation_v12.py`. '
        'Reproduction: `python -m run.calitree_challenger_validation --output-dir <this-experiment> --mode all`. '
        'Audit: `python -m run.verify_calitree_challenger_validation --output-dir <this-experiment>`. '
        'No live/model-call option exists. Cached fits and completed hierarchies support resumption.', '',
        'See `comparison_cases.csv`, `comparison_details.json`, and `verification.json` for the complete accounting.']
    base = (out / 'report.md').read_text().split(MARKER)[0]
    (out / 'report.md').write_text(base.rstrip() + '\n\n' + '\n'.join(lines) + '\n')
    print({'failed_family_folds': extra['failed_family_folds'], 'same_as_direct': extra['new_predictions_identical_to_direct'], 'paired': dict(paired)})


if __name__ == '__main__':
    main()
