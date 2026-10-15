"""Fit constrained reusable rules on the same twelve cached evidence cases."""
import argparse
from collections import Counter
from pathlib import Path
import shutil

from critical.core.calibration.local_evidence_rules import (
    FEATURES, LABELS, LIMITS, PREDICATES, VERSION,
    LocalEvidenceRuleCalibrator, feature_conflicts, summarize,
)
from critical.core.calibration.registry import CalibrationRegistry
from critical.core.decision.artifacts import digest, save_json
from run.calitree_single_call import ROOT, fingerprint, metrics, paired_comparison, read, verify as verify_evidence


DEFAULT_EVIDENCE = ROOT / 'logs/exps/261013-single-call-evidence-balanced12-v1'


def input_record(row):
    return {'instruction': row['instruction'], 'observations': row['decision']['observations']}


def prepare(output, evidence):
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'manifest.json').exists():
        manifest = read(output / 'manifest.json')
        if manifest['evidence_directory'] != str(evidence): raise ValueError('Changed cached evidence run')
        verify(output, manifest); return manifest
    original = read(evidence / 'manifest.json'); verify_evidence(evidence, original)
    cached = read(evidence / 'results.json')
    if len(cached['cases']) != 12 or any(r['decision'] is None for r in cached['cases']):
        raise ValueError('This local pilot requires twelve valid cached evidence records')
    if Counter(r['reference'] for r in cached['cases']) != {'no': 4, 'partial': 4, 'yes': 4}:
        raise ValueError('Expected the same four-per-class sample')
    flat = Path(original['baseline_directory'])
    inputs = [evidence / name for name in ('manifest.json', 'seal.json', 'results.json', 'prompt.txt')]
    inputs += [flat / name for name in ('manifest.json', 'seal.json', 'results.json')]
    inputs += list((evidence / 'ledgers').glob('*/jobs/*.json'))
    files = [p for p in (ROOT / 'critical').rglob('*') if p.is_file() and p.suffix in ('.py', '.txt', '.json')]
    files += [Path(__file__).resolve(), ROOT / 'run/calitree_single_call.py']
    code = {}
    for p in files:
        rel = str(p.relative_to(ROOT)); target = output / 'source_snapshot' / rel
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, target); code[rel] = fingerprint(p)
    manifest = {
        'version': VERSION, 'evidence_directory': str(evidence), 'flat_directory': str(flat),
        'cases': original['cases'], 'cached_files': {str(p): fingerprint(p) for p in inputs},
        'code_hashes': code, 'feature_names': list(FEATURES), 'predicates': PREDICATES, 'limits': LIMITS,
        'training_and_scoring': 'The exact same twelve cached records and human references; local fitting accuracy.',
        'constraints': 'No IDs, instructions, free-text tokens, object names, category labels or condition counts in executable rules. Monotone evidence mapping; fully fulfilled evidence remains Yes; fixed No/unresolved guards.',
        'api_calls': 0,
        'authorization': 'Please help me implement and test it while constrain the policy to use reusable evidence rules.',
    }
    save_json(output / 'manifest.json', manifest); save_json(output / 'seal.json', {'manifest_ref': digest(manifest)})
    verify(output, manifest); return manifest


def verify(output, manifest):
    if (digest(manifest) != read(output / 'seal.json')['manifest_ref'] or manifest['version'] != VERSION
            or manifest['predicates'] != PREDICATES or manifest['limits'] != LIMITS):
        raise ValueError('Changed frozen local rule experiment')
    for p, expected in manifest['cached_files'].items():
        if fingerprint(p) != expected: raise ValueError('Changed cached evidence/reference artifact')
    for rel, expected in manifest['code_hashes'].items():
        if fingerprint(ROOT / rel) != expected or fingerprint(output / 'source_snapshot' / rel) != expected:
            raise ValueError('Changed frozen implementation: ' + rel)


def execute(output, manifest, replay):
    cached = read(Path(manifest['evidence_directory']) / 'results.json')
    flat = read(Path(manifest['flat_directory']) / 'results.json')
    inputs = [input_record(r) for r in cached['cases']]
    targets = [LABELS.index(r['reference']) for r in cached['cases']]
    groups = [r['group'] for r in manifest['cases']]
    # The learner sees anonymous evidence summaries and labels, never IDs/groups
    # as predicates. Groups serve only to enforce distinct-source leaf support.
    fitted = LocalEvidenceRuleCalibrator().fit(inputs, targets, source_groups=groups)
    artifact = {'policy': fitted.metadata(), 'fit_case_ids': [r['id'] for r in cached['cases']],
                'cached_results_sha256': fingerprint(Path(manifest['evidence_directory']) / 'results.json')}
    seal_path = output / 'policy_seal.json'
    if replay:
        seal = read(seal_path); saved = read(output / seal['path'])
        if digest(saved) != seal['artifact_ref'] or saved != artifact:
            raise ValueError('Exact refit changed the saved policy')
    else:
        version, path = CalibrationRegistry(output / 'registry').publish(artifact)
        seal = {'version': version, 'path': str(path.relative_to(output)), 'artifact_ref': digest(artifact)}
        if seal_path.exists() and read(seal_path) != seal: raise ValueError('Refusing to replace frozen policy')
        save_json(seal_path, seal)
    model = LocalEvidenceRuleCalibrator.restore(artifact['policy'])
    predictions = model.predict_records(inputs)
    rows = [{**{k: r[k] for k in ('case', 'id', 'instruction', 'reference')},
             'prediction': p['label'], 'rule_decision': p, 'uncalibrated_prediction': r['prediction']}
            for r, p in zip(cached['cases'], predictions)]
    conflicts = feature_conflicts(inputs, targets)
    for conflict in conflicts['identical_feature_conflicts']:
        conflict['cases'] = [rows[i]['case'] for i in conflict['indices']]
    return {'version': VERSION, 'scope': 'Same-case local fitting accuracy; not held-out performance.',
            'local_metrics': metrics(rows), 'uncalibrated_metrics': metrics(cached['cases']),
            'flat_metrics': metrics(flat['cases']), 'vs_uncalibrated': paired_comparison(cached, rows),
            'vs_flat': paired_comparison(flat, rows), 'cases': rows, 'policy': artifact['policy'],
            'registry': seal, 'conflicts': conflicts, 'api_calls': 0}


def rule_text(tree, indent=''):
    if 'label' in tree: return [indent + 'Return ' + tree['label'].upper()]
    return ([indent + 'IF ' + tree['predicate'] + ':'] + rule_text(tree['when_true'], indent+'  ')
            + [indent + 'ELSE:'] + rule_text(tree['when_false'], indent+'  '))


def report(output, result, manifest):
    lines = ['# Constrained local calibration: same twelve cached cases', '',
             '**These are local fitting scores on the same twelve training records.**',
             'No checks were re-optimized or images re-judged; zero API calls.', '',
             '| Method | Correct | No | Partial | Yes |', '|---|---:|---:|---:|---:|']
    for name, key in [('Saved flat judge', 'flat_metrics'), ('Fixed evidence policy', 'uncalibrated_metrics'),
                      ('Locally fitted reusable rules', 'local_metrics')]:
        m = result[key]; classes = ' | '.join(f"{round(m['per_class_recall'][k]*4)}/4" for k in LABELS)
        lines.append(f"| {name} | {m['correct']}/12 ({m['accuracy']:.1%}) | {classes} |")
    lines += ['', '## Learned executable policy', '',
              'First retain decisive fixed-policy No and unresolved evidence guards.',
              'For remaining records:', '', '```text', *rule_text(result['policy']['tree']), '```', '',
              'Source-preserved means the cached source-integrity state is preserved; it permits authorized changes. Material deviations take the other branch.',
              'The learner does not reinterpret the evidence text or decide whether a cached materiality judgment is visually correct.', '',
              '## Reusability constraints', '',
              '- At most two learned levels and three split nodes.',
              '- Every fitted leaf covers at least two distinct source cases.',
              '- Predicates inspect only anonymous source-integrity and worst core/constraint fulfillment states.',
              '- No instruction matching, object names, text vocabulary, case IDs, task metadata or exact condition counts.',
              '- Exhaustive monotonicity check: better fulfillment/source integrity cannot lower the label.',
              '- Fully complete, source-preserved evidence remains Yes; decisive No/unknown guards are retained.', '',
              f"Leaf support: {result['policy']['leaf_support']}. Search counts: {result['policy']['search_counts']}.", '',
              '| Case | Reference | Flat | Fixed checks | Local rules |', '|---|---|---|---|---|']
    flat = read(Path(manifest['flat_directory']) / 'results.json')
    for old, row in zip(flat['cases'], result['cases']):
        lines.append(f"| {row['case']} | {row['reference']} | {old['prediction']} | {row['uncalibrated_prediction']} | {row['prediction'] or 'unresolved'} |")
    lines += ['', '## Conflicts and interpretation', '',
              f"Anonymous feature-only optimistic fitting ceiling: {result['conflicts']['feature_only_fitting_ceiling']}/12, before monotonicity/support/guard constraints."]
    for collision in result['conflicts']['identical_feature_conflicts']:
        lines.append(f"Identical anonymous features: {collision['cases']}; conflicting references: {collision['target_counts']}.")
    lines += ['', 'A rule grammar can be reusable in form while still fitting a small batch poorly on new cases. These scores do not establish semantic correctness, repeat robustness or generalization.',
              'A permissive learned branch may treat missing requested aspects as acceptable. Inspect the policy, not only its fitting score.',
              'No free-text semantic features were invented to distinguish individual errors. Any missing distinctions must be addressed through a separately justified evidence schema.', '']
    (output / 'report.md').write_text('\n'.join(lines))
    (output / 'llm-histories.log').write_text('No API calls: all judgments and evidence were reused from frozen caches.\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--evidence-dir', type=Path, default=DEFAULT_EVIDENCE)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight', action='store_true'); mode.add_argument('--fit', action='store_true')
    mode.add_argument('--replay', action='store_true')
    args = parser.parse_args(); output, evidence = args.output_dir.resolve(), args.evidence_dir.resolve()
    if output == evidence: raise ValueError('Use a new output directory')
    if args.replay and not (output / 'results.json').exists(): raise ValueError('Replay requires saved results')
    manifest = prepare(output, evidence)
    if args.preflight:
        print({'ready': True, 'same_case_fit': 12, 'api_calls': 0, 'limits': LIMITS}); return
    result = execute(output, manifest, args.replay); verify(output, manifest)
    if args.replay:
        if read(output / 'results.json') != result: raise ValueError('Replay changed local fitting results')
        save_json(output / 'verification.json', {'exact_refit_and_replay': True, 'api_calls': 0,
                  'caches_unchanged': True, 'monotone_reusable_grammar': True, 'result_sha256': fingerprint(output / 'results.json')})
        print({'exact_refit_and_replay': True, 'api_calls': 0})
    else:
        if (output / 'results.json').exists() and read(output / 'results.json') != result:
            raise ValueError('Refusing to replace different results')
        save_json(output / 'results.json', result); report(output, result, manifest)
        print({k: result[k] for k in ('local_metrics', 'vs_uncalibrated', 'vs_flat', 'policy', 'conflicts')})


if __name__ == '__main__':
    main()
