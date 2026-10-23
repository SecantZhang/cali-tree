"""Report all predeclared policies on the same fifty reserved sources."""
import argparse
from pathlib import Path

from critical.core.decision.artifacts import save_json
from critical.core.calibration.semantic_hierarchy.hierarchy_fit_v9 import complexity
from run.calitree_regularized_v13 import read, fingerprint


def report(out):
    seal = read(out / 'completion_seal.json')
    for name, expected in seal['files'].items():
        if fingerprint(out / name) != expected:
            raise ValueError('Completed evaluation artifact changed: ' + name)
    result = read(out / 'results.json'); audit = read(out / 'verification.json'); protocol = read(out / 'protocol.json')
    if not audit['passed']:
        raise ValueError('An audited evaluation is required')
    policies = read(out / 'policies.json'); predictions = read(out / 'predictions.json')['policies']
    rows = []
    for i in (1, 2, 3):
        names = [f'v12_merge_split{i}', f'v14_direct_split{i}', f'v14_merge_split{i}']
        measurements = {name: {'metrics': result['metrics'][name], 'complexity': complexity(policies[name]['tree']),
                               'policy_ref': policies[name]['artifact_ref']} for name in names}
        rows.append({'split': i, 'policies': measurements,
            'v14_matches_direct_predictions': [p['prediction'] for p in predictions[names[1]]] == [p['prediction'] for p in predictions[names[2]]],
            'v14_matches_direct_runtime': policies[names[1]] == policies[names[2]],
            'paired_vs_v12': result['paired'][f'v14_merge_split{i}_vs_v12_merge_split{i}'],
            'paired_vs_direct': result['paired'][f'v14_merge_split{i}_vs_v14_direct_split{i}']})
    summary = {'version': protocol['version'], 'unique_sources': 50, 'training_replications': 3,
        'replications_share_evaluation_sources': True, 'policies_frozen_before_collection': True,
        'model': protocol['judge_identity'], 'splits': rows,
        'usage': {k: audit[k] for k in ('requests', 'input_tokens_reported', 'completion_tokens_reported',
            'completion_tokens_or_conservatively_reserved', 'request_cap', 'completion_token_cap', 'valid_observations', 'valid_interpretations')},
        'new_fits': 0, 'selection_on_final_set': False,
        'limits': ['Fifty unique sources, not 150 independent cases.',
                   'The set was reserved for this study but has disclosed historical project exposure.',
                   'Only one evidence sample per stage, plus a permitted compiler repair; no repeated-observation robustness estimate.',
                   'Label agreement does not establish correctness of every semantic interpretation or rule.',
                   'No policy or configuration may be selected or retuned from these outcomes and described as an untouched final test.']}
    save_json(out / 'summary.json', summary)
    lines = ['# Frozen v14 reserved-fifty evaluation', '',
        'All nine policies were frozen before collection. Every policy received the same bound Luna/compiler-v3 evidence '
        'for fifty sources excluded from every fitting cohort. No fitting, model selection or observation retry occurred.', '',
        '| Training split | V12 merged | V14 direct | V14 merged | V12 / V14 merged rules |',
        '|---|---:|---:|---:|---:|']
    for row in rows:
        i = row['split']; p = row['policies']
        old, direct, merged = (p[f'{arm}_split{i}'] for arm in ('v12_merge', 'v14_direct', 'v14_merge'))
        lines.append(f"| {i} | {old['metrics']['correct']}/50 | {direct['metrics']['correct']}/50 | {merged['metrics']['correct']}/50 | "
                     f"{old['complexity']['rules']} / {merged['complexity']['rules']} |")
    lines += ['', '## Per-class behavior', '', '| Training split / arm | Macro-F1 | No recall | Partial recall | Yes recall | Unresolved |',
              '|---|---:|---:|---:|---:|---:|']
    for row in rows:
        for name, value in row['policies'].items():
            m = value['metrics']; c = m['per_class']
            lines.append(f"| {name} | {m['macro_f1']:.3f} | {c['no']['recall']:.1%} | {c['partial']['recall']:.1%} | {c['yes']['recall']:.1%} | {m['unresolved']} |")
    lines += ['', '## Paired comparisons', '',
        'These count the same fifty cases for each policy pair; the three training replications are not independent evaluations.', '']
    for row in rows:
        lines.append(f"- Split {row['split']}: versus v12 {row['paired_vs_v12']}; versus direct {row['paired_vs_direct']}. "
                     f"Same v14/direct predictions: {row['v14_matches_direct_predictions']}; same runtime: {row['v14_matches_direct_runtime']}.")
    u = summary['usage']
    lines += ['', '## Usage and verification', '',
        f"{u['requests']} requests out of the approved 200 maximum; {u['completion_tokens_reported']:,} reported completion tokens "
        f"and {u['completion_tokens_or_conservatively_reserved']:,} conservatively charged/reserved tokens out of the 2,048,000 cap. "
        f"{u['valid_observations']}/50 physical observations and {u['valid_interpretations']}/50 interpretations validated. "
        'The offline audit authenticated request payloads, target-free extraction, exact image bindings, all policy predictions, '
        'paired counts and budget ledgers. A completion seal covers the evidence and outputs.', '',
        '## Limits', '', *['- ' + text for text in summary['limits']]]
    (out / 'report.md').write_text('\n'.join(lines) + '\n')
    print({'split_correct': [{name: v['metrics']['correct'] for name, v in row['policies'].items()} for row in rows], 'usage': u})
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    report(parser.parse_args().output_dir.resolve())
