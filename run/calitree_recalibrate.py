"""Corrected three-label local calibration of the cached 36-case benchmark."""
import argparse
from pathlib import Path
import shutil

from critical.core.calibration.evidence_rules_v3 import (
    DOMAIN, FEATURES, LABELS, LIMITS, PREDICATES, VERSION,
    EvidenceRuleCalibrator, feature_conflicts,
)
from critical.core.calibration.registry import CalibrationRegistry
from critical.core.decision.artifacts import digest, save_json
from run.calitree_benchmark36 import verify as verify_source
from run.calitree_local_calibration import rule_text
from run.calitree_single_call import ROOT, fingerprint, metrics, paired_comparison, read

DEFAULT_INPUT = ROOT / 'logs/exps/261013-flat-vs-calitree36-v1'


def score(rows):
    value = metrics(rows); value.pop('wilson_95_interval', None); return value


def paired(before, after):
    value = paired_comparison({'cases': before}, after); value.pop('mcnemar_exact_two_sided_p', None); return value


def prepare(output, source):
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'manifest.json').exists():
        m = read(output / 'manifest.json')
        if m['source_directory'] != str(source): raise ValueError('Changed cached source')
        verify(output, m); return m
    old = read(source / 'manifest.json'); verify_source(source, old)
    cached = read(source / 'results.json')
    if len(old['cases']) != 36 or any(r.get('extraction') is None for r in cached['cases']['calitree']):
        raise ValueError('Need the 36 valid cached rich-evidence extractions')
    files = [p for p in (ROOT / 'critical').rglob('*') if p.is_file() and p.suffix in ('.py', '.txt', '.json')]
    files += [Path(__file__).resolve(), ROOT / 'run/calitree_single_call.py', ROOT / 'run/calitree_local_calibration.py', ROOT / 'run/calitree_benchmark36.py']
    code = {}
    for p in files:
        rel = str(p.relative_to(ROOT)); dst = output / 'source_snapshot' / rel
        dst.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dst); code[rel] = fingerprint(p)
    paths = [source / name for name in ('manifest.json', 'seal.json', 'results.json', 'verification.json')]
    paths += list((source / 'ledgers').glob('*/*/jobs/*.json'))
    m = {'version': VERSION, 'source_directory': str(source), 'cases': old['cases'],
         'cached_files': {str(p): fingerprint(p) for p in paths}, 'code_hashes': code,
         'feature_names': list(FEATURES), 'predicates': PREDICATES, 'limits': LIMITS,
         'scope': 'Fit and score the same 36 cached observations/references; local fitting only.',
         'changes': ['All three labels learned', 'No immutable No guards',
                     'Unknown evidence resolves by lower/upper learned label agreement',
                     'Target correspondence and any-core progress are anonymous learned predicates'],
         'api_calls': 0, 'authorization': 'Can you fix this for me?'}
    save_json(output / 'manifest.json', m); save_json(output / 'seal.json', {'manifest_ref': digest(m)})
    verify(output, m); return m


def verify(output, m):
    if (digest(m) != read(output / 'seal.json')['manifest_ref'] or m['version'] != VERSION
            or m['limits'] != LIMITS or m['predicates'] != PREDICATES):
        raise ValueError('Changed corrected calibration protocol')
    for path, expected in m['cached_files'].items():
        if fingerprint(path) != expected: raise ValueError('Changed cached observation/reference')
    for rel, expected in m['code_hashes'].items():
        if fingerprint(ROOT / rel) != expected or fingerprint(output / 'source_snapshot' / rel) != expected:
            raise ValueError('Changed frozen calibration code')


def execute(output, m, replay):
    cached = read(Path(m['source_directory']) / 'results.json')
    old, flat = cached['cases']['calitree'], cached['cases']['flat']
    if [r['id'] for r in old] != [r['id'] for r in m['cases']]: raise ValueError('Changed case order')
    X = [{'instruction': r['instruction'], 'observations': r['extraction']['observations']} for r in old]
    y = [LABELS.index(r['reference']) for r in old]; groups = [r['group'] for r in m['cases']]
    fitted = EvidenceRuleCalibrator().fit(X, y, source_groups=groups)
    artifact = {'policy': fitted.metadata(), 'fit_case_ids': [r['id'] for r in old], 'fit_source_groups': groups,
                'cached_results_ref': fingerprint(Path(m['source_directory']) / 'results.json')}
    if replay:
        seal = read(output / 'policy_seal.json'); saved = read(output / seal['path'])
        if digest(saved) != seal['artifact_ref'] or saved != artifact: raise ValueError('Exact refit changed artifact')
    else:
        version, path = CalibrationRegistry(output / 'registry').publish(artifact)
        seal = {'version': version, 'path': str(path.relative_to(output)), 'artifact_ref': digest(artifact)}
        if (output / 'policy_seal.json').exists() and read(output / 'policy_seal.json') != seal:
            raise ValueError('Refusing to replace different policy')
        save_json(output / 'policy_seal.json', seal)
    model = EvidenceRuleCalibrator.restore(artifact['policy']); decisions = model.predict_records(X)
    rows = [{**{k: row[k] for k in ('case', 'id', 'instruction', 'reference')},
             'previous_prediction': row['prediction'], 'prediction': d['label'], 'decision': d}
            for row, d in zip(old, decisions)]
    common = [i for i, (a, b) in enumerate(zip(flat, old)) if a['prediction'] is not None and b['prediction'] is not None]
    conflict = feature_conflicts(X, y)
    for c in conflict['identical_evidence_bound_conflicts']: c['cases'] = [rows[i]['case'] for i in c['indices']]
    return {'version': VERSION, 'scope': m['scope'], 'local_metrics': score(rows), 'old_metrics': score(old),
            'flat_metrics': score(flat), 'vs_old': paired(old, rows), 'vs_flat': paired(flat, rows),
            'cases': rows, 'policy': model.metadata(), 'registry': seal, 'conflicts': conflict,
            'resolved_previous_unknowns': [r['case'] for r in rows if r['previous_prediction'] is None and r['prediction'] is not None],
            'remaining_unknowns': [r['case'] for r in rows if r['prediction'] is None],
            'common_old_cohort': {'n': len(common), 'flat': score([flat[i] for i in common]),
                                  'old': score([old[i] for i in common]), 'local': score([rows[i] for i in common])},
            'api_calls': 0}


def report(output, r):
    lines = ['# Corrected three-label local calibration', '',
             '**All 36 cached labels are used for fitting and scoring. These are local fitting results.**',
             'No new image judgments or model calls. Original evidence and prior policies remain unchanged.', '',
             '| Method | Correct | No | Partial | Yes | Resolved |', '|---|---:|---:|---:|---:|---:|']
    for name, key in [('Flat baseline', 'flat_metrics'), ('Previous frozen/local v2', 'old_metrics'), ('Corrected local v3', 'local_metrics')]:
        m = r[key]; classes = ' | '.join(f"{round(m['per_class_recall'][label]*12)}/12" for label in LABELS)
        lines.append(f"| {name} | {m['correct']}/36 ({m['accuracy']:.1%}) | {classes} | {m['resolved']}/36 |")
    lines += ['', '## What was corrected', '',
              '- All three leaf labels are learnable; no preassigned No labels.',
              '- Target correspondence and some-core progress are inputs rather than immutable guards.',
              '- Unknown facts retain feasible lower/upper values. Return a label only when all completions agree under the learned monotone policy.',
              '- Minimum support counts only distinct sources guaranteed to reach each leaf; uncertain routing cannot fabricate support.',
              '- Depth <=2, split nodes <=3, minimum leaf support >=2, no IDs/text/object/category/count predicates.', '',
              '## Learned policy', '', '```text', *rule_text(r['policy']['tree']), '```', '',
              f"Leaf support: {r['policy']['leaf_support']}; search: {r['policy']['search_counts']}.",
              f"Resolved prior unknowns: {r['resolved_previous_unknowns']}. Remaining unknowns: {r['remaining_unknowns']}.",
              f"Improvements versus v2: {r['vs_old']['wins']}; regressions: {r['vs_old']['losses']}.", '',
              '| Case | Reference | Old | Corrected | Label bounds |', '|---|---|---|---|---|']
    for row in r['cases']:
        lines.append(f"| {row['case']} | {row['reference']} | {row['previous_prediction'] or 'unresolved'} | {row['prediction'] or 'unresolved'} | {row['decision']['label_bounds']} |")
    lines += ['', '## Evidence limitations', '',
              f"Optimistic anonymous-evidence bound ceiling: {r['conflicts']['optimistic_feature_only_ceiling']}/36 before monotonicity, support, depth and unresolved-completion constraints."]
    for c in r['conflicts']['identical_evidence_bound_conflicts']:
        lines.append(f"Identical anonymous bounds: {c['cases']}; references: {c['target_counts']}.")
    lines += ['', f'Monotonicity checked across all {len(DOMAIN)} feasible known-evidence points.',
              'Syntax and monotonicity do not establish semantic correctness. Labels are aggregate-mean classes, and cached check errors remain.',
              'These same-case numbers cannot be compared as equally held-out performance against the flat judge. No claim of generalization or repeat robustness.',
              'The canonical fulfillment optimizer and v1/v2 saved experiments retain their original contracts.', '']
    (output / 'report.md').write_text('\n'.join(lines))
    (output / 'llm-histories.log').write_text('No API calls; reused the exact 36 rich extractions and flat responses.\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output-dir', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight', action='store_true'); mode.add_argument('--fit', action='store_true'); mode.add_argument('--replay', action='store_true')
    args = parser.parse_args(); source, output = args.input_dir.resolve(), args.output_dir.resolve()
    if source == output: raise ValueError('Use a new output directory')
    if args.replay and not (output / 'results.json').exists(): raise ValueError('Replay needs saved results')
    m = prepare(output, source)
    if args.preflight:
        print({'ready': True, 'fit_and_score': 36, 'api_calls': 0, 'learnable_labels': LABELS}); return
    result = execute(output, m, args.replay); verify(output, m)
    if args.replay:
        if read(output / 'results.json') != result: raise ValueError('Replay changed result')
        save_json(output / 'verification.json', {'exact_refit_and_replay': True, 'api_calls': 0,
                  'original_caches_unchanged': True, 'results_sha256': fingerprint(output / 'results.json')})
        print({'exact_refit_and_replay': True, 'api_calls': 0})
    else:
        if (output / 'results.json').exists() and read(output / 'results.json') != result: raise ValueError('Different saved results')
        save_json(output / 'results.json', result); report(output, result)
        print({k: result[k] for k in ('local_metrics', 'vs_old', 'resolved_previous_unknowns', 'remaining_unknowns', 'policy')})


if __name__ == '__main__': main()
