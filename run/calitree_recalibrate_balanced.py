"""Class-balanced local recalibration of the exact same cached 36 cases."""
import argparse
from pathlib import Path
import shutil

from critical.core.calibration.evidence_rules_v4 import (
    ClassBalancedEvidenceRuleCalibrator, OBJECTIVE, VERSION, classification_metrics,
)
from critical.core.calibration.evidence_rules_v3 import DOMAIN, FEATURES, LABELS, LIMITS, PREDICATES, feature_conflicts
from critical.core.calibration.registry import CalibrationRegistry
from critical.core.decision.artifacts import digest, save_json
from run.calitree_benchmark36 import verify as verify_source
from run.calitree_recalibrate import DEFAULT_INPUT, ROOT, fingerprint, paired, read, rule_text, score

DEFAULT_PREVIOUS = ROOT / 'logs/exps/261013-corrected-local-calibration-v3'


def classify_metrics(rows):
    return classification_metrics([LABELS.index(r['prediction']) if r['prediction'] is not None else -1 for r in rows],
                                  [LABELS.index(r['reference']) for r in rows])[0]


def prepare(output, source, previous):
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'manifest.json').exists():
        m = read(output / 'manifest.json')
        if m['source_directory'] != str(source) or m['previous_directory'] != str(previous):
            raise ValueError('Changed cached comparison inputs')
        verify(output, m); return m
    old = read(source / 'manifest.json'); verify_source(source, old)
    cached = read(source / 'results.json'); v3 = read(previous / 'results.json')
    if (len(old['cases']) != 36 or any(r.get('extraction') is None for r in cached['cases']['calitree'])
            or [r['id'] for r in old['cases']] != [r['id'] for r in v3['cases']]):
        raise ValueError('Expected the exact same thirty-six cached cases and v3 comparison')
    paths = [source / n for n in ('manifest.json', 'seal.json', 'results.json', 'verification.json')]
    paths += [previous / n for n in ('manifest.json', 'results.json', 'policy_seal.json', 'verification.json')]
    paths += list((source / 'ledgers').glob('*/*/jobs/*.json'))
    files = [p for p in (ROOT / 'critical').rglob('*') if p.is_file() and p.suffix in ('.py', '.txt', '.json')]
    files += [Path(__file__).resolve(), ROOT / 'run/calitree_recalibrate.py', ROOT / 'run/calitree_benchmark36.py',
              ROOT / 'run/calitree_local_calibration.py', ROOT / 'run/calitree_single_call.py']
    code = {}
    for p in files:
        rel = str(p.relative_to(ROOT)); dst = output / 'source_snapshot' / rel
        dst.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dst); code[rel] = fingerprint(p)
    m = {'version': VERSION, 'source_directory': str(source), 'previous_directory': str(previous),
         'cases': old['cases'], 'code_hashes': code, 'cached_files': {str(p): fingerprint(p) for p in paths},
         'objective': OBJECTIVE, 'limits': LIMITS, 'predicates': PREDICATES, 'feature_names': list(FEATURES),
         'scope': 'Fit and score the same cached 36 references; local fitting accuracy only.', 'api_calls': 0,
         'authorization': 'Why is Partial recall zero? Can you fix the optimization objective so it learns all three labels, then recalibrate and test on the same 36 cases?'}
    save_json(output / 'manifest.json', m); save_json(output / 'seal.json', {'manifest_ref': digest(m)})
    verify(output, m); return m


def verify(output, m):
    if (digest(m) != read(output / 'seal.json')['manifest_ref'] or m['version'] != VERSION
            or m['objective'] != OBJECTIVE or m['limits'] != LIMITS or m['predicates'] != PREDICATES):
        raise ValueError('Changed frozen balanced objective or rule contract')
    for p, h in m['cached_files'].items():
        if fingerprint(p) != h: raise ValueError('Changed original cached comparison')
    for rel, h in m['code_hashes'].items():
        if fingerprint(ROOT / rel) != h or fingerprint(output / 'source_snapshot' / rel) != h:
            raise ValueError('Changed frozen calibration source')


def execute(output, m, replay):
    cached = read(Path(m['source_directory']) / 'results.json')
    previous = read(Path(m['previous_directory']) / 'results.json')
    old, flat = cached['cases']['calitree'], cached['cases']['flat']
    if [r['id'] for r in old] != [r['id'] for r in m['cases']]: raise ValueError('Changed case order')
    X = [{'instruction': r['instruction'], 'observations': r['extraction']['observations']} for r in old]
    y = [LABELS.index(r['reference']) for r in old]; groups = [r['group'] for r in m['cases']]
    fitted = ClassBalancedEvidenceRuleCalibrator().fit(X, y, source_groups=groups)
    artifact = {'policy': fitted.metadata(), 'fit_case_ids': [r['id'] for r in old], 'fit_source_groups': groups,
                'cached_results_sha256': fingerprint(Path(m['source_directory']) / 'results.json')}
    if replay:
        seal = read(output / 'policy_seal.json'); saved = read(output / seal['path'])
        if digest(saved) != seal['artifact_ref'] or saved != artifact: raise ValueError('Exact balanced refit changed artifact')
    else:
        version, path = CalibrationRegistry(output / 'registry').publish(artifact)
        seal = {'version': version, 'path': str(path.relative_to(output)), 'artifact_ref': digest(artifact)}
        if (output / 'policy_seal.json').exists() and read(output / 'policy_seal.json') != seal:
            raise ValueError('Refusing changed policy')
        save_json(output / 'policy_seal.json', seal)
    model = ClassBalancedEvidenceRuleCalibrator.restore(artifact['policy']); decisions = model.predict_records(X)
    rows = [{**{k: r[k] for k in ('case', 'id', 'instruction', 'reference')},
             'prediction': d['label'], 'decision': d, 'v3_prediction': v3['prediction'], 'v2_prediction': r['prediction']}
            for r, v3, d in zip(old, previous['cases'], decisions)]
    conflict = feature_conflicts(X, y)
    for c in conflict['identical_evidence_bound_conflicts']: c['cases'] = [rows[i]['case'] for i in c['indices']]
    return {'version': VERSION, 'scope': m['scope'], 'objective': OBJECTIVE,
            'metrics': score(rows), 'class_metrics': classify_metrics(rows),
            'v3_metrics': score(previous['cases']), 'v3_class_metrics': classify_metrics(previous['cases']),
            'v2_metrics': score(old), 'v2_class_metrics': classify_metrics(old),
            'flat_metrics': score(flat), 'flat_class_metrics': classify_metrics(flat),
            'vs_v3': paired(previous['cases'], rows), 'vs_v2': paired(old, rows),
            'cases': rows, 'policy': model.metadata(), 'registry': seal, 'conflicts': conflict,
            'api_calls': 0}


def report(output, r):
    lines = ['# Class-balanced local calibration objective', '',
             '**Same 36 cached records and labels used for fitting and scoring.** No new API/image calls.',
             'V3 maximized total correct and selected a rule with zero Partial recall. V4 maximizes macro-F1 subject to at least two correctly recognized sources per class.',
             'Ties prefer worst-class recall, then total correct, then simpler rules and fewer reference-policy departures.', '',
             '| Method | Accuracy | Macro-F1 | No recall | Partial recall | Yes recall | Resolved |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for name, key, cls in [('Flat baseline', 'flat_metrics', 'flat_class_metrics'),
                           ('V2 local', 'v2_metrics', 'v2_class_metrics'),
                           ('V3 accuracy objective', 'v3_metrics', 'v3_class_metrics'),
                           ('V4 macro-F1 objective', 'metrics', 'class_metrics')]:
        v = r[key]; recalls = ' | '.join(f"{v['per_class_recall'][label]:.1%}" for label in LABELS)
        lines.append(f"| {name} | {v['correct']}/36 ({v['accuracy']:.1%}) | {r[cls]['macro_f1']:.3f} | {recalls} | {v['resolved']}/36 |")
    lines += ['', '## Learned policy', '', '```text', *rule_text(r['policy']['tree']), '```', '',
              f"Definite source support: {r['policy']['leaf_support']}; search: {r['policy']['search_counts']}.",
              'The feature set, labels, unknown intervals, depth-two/three-split/minimum-two-source limits and monotonicity are unchanged from v3. Only the optimization objective and class-coverage eligibility changed.',
              'Unresolved records count as false negatives for their reference class. There is no guessing or forced label for uncertain evidence.', '',
              f"Versus v3: improvements {r['vs_v3']['wins']}; regressions {r['vs_v3']['losses']}.", '',
              '| Case | Reference | V2 | V3 | V4 |', '|---|---|---|---|---|']
    for row in r['cases']:
        lines.append(f"| {row['case']} | {row['reference']} | {row['v2_prediction'] or 'unresolved'} | {row['v3_prediction'] or 'unresolved'} | {row['prediction'] or 'unresolved'} |")
    lines += ['', '## Limitations', '',
              'Class coverage in the fitting batch is enforced; generalization and repeated-model robustness are unmeasured.',
              'A macro-F1 objective can trade raw accuracy or coverage for better performance across classes. The report retains those tradeoffs.',
              'The flat baseline was not fitted to these labels, so these are not equally held-out comparisons.',
              'The reference labels are discretized aggregate human means, not individual-rater or atomic-check labels.',
              'Existing anonymous evidence conflicts and bounded rule capacity remain. No ID, object-name, instruction, text-vocabulary or count lookup is allowed.', '']
    (output / 'report.md').write_text('\n'.join(lines))
    (output / 'llm-histories.log').write_text('No API calls. Same 36 cached rich extractions and baseline responses.\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-dir', type=Path, default=DEFAULT_INPUT)
    p.add_argument('--previous-dir', type=Path, default=DEFAULT_PREVIOUS)
    p.add_argument('--output-dir', type=Path, required=True)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight', action='store_true'); mode.add_argument('--fit', action='store_true'); mode.add_argument('--replay', action='store_true')
    args = p.parse_args(); source, previous, output = args.input_dir.resolve(), args.previous_dir.resolve(), args.output_dir.resolve()
    if output in (source, previous): raise ValueError('Use a new output directory')
    if args.replay and not (output / 'results.json').exists(): raise ValueError('Replay needs saved results')
    m = prepare(output, source, previous)
    if args.preflight: print({'ready': True, 'local_cases': 36, 'objective': OBJECTIVE, 'api_calls': 0}); return
    r = execute(output, m, args.replay); verify(output, m)
    if args.replay:
        if read(output / 'results.json') != r: raise ValueError('Replay changed results')
        save_json(output / 'verification.json', {'exact_refit_and_replay': True, 'api_calls': 0,
                  'original_caches_and_policies_unchanged': True, 'results_sha256': fingerprint(output / 'results.json')})
        print({'exact_refit_and_replay': True, 'api_calls': 0})
    else:
        if (output / 'results.json').exists() and read(output / 'results.json') != r: raise ValueError('Different saved results')
        save_json(output / 'results.json', r); report(output, r)
        print({k: r[k] for k in ('metrics', 'class_metrics', 'vs_v3', 'policy')})


if __name__ == '__main__': main()
