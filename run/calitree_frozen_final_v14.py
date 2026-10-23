"""Preflight or explicitly gated evaluation of the reserved fifty.

Preflight freezes existing v12/v14 policies and target-free inputs, verifies all
images and source separation, and makes zero calls. Collection requires --live.
There is no fitting/selection/retry path. Run only after approval to consume the
reserved set; this is a new Luna/compiler-v3 protocol, not the original Sol M0.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from critical.core.decision.artifacts import digest
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import project
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import metrics
from run import calitree_three_splits as base
from run.calitree_three_splits_compiler_v3 import collect_physical, audit_compiler

ROOT = base.ROOT
RESERVED = ROOT / 'logs/exps/261014-semantic-hierarchy-m0-fifty-v1'
TRAINED = ROOT / 'logs/exps/261018-supported-child-compression-v14'
BASELINE = ROOT / 'logs/exps/261018-union-challenger-validation-v12'
VERSION = 'frozen-v14-reserved-fifty-luna-v1'


def prepare(out):
    base.validate_settings()
    inputs = base.read(RESERVED / 'test_inputs.json')['cases']
    # Only metadata, not labels, enters the new input manifest.
    source_groups = {r['case']: r['group'] for r in base.read(RESERVED / 'splits/test.json')['cases']}
    train_sources = {r['source_group'] for i in (1, 2, 3) for r in base.read(TRAINED / f'split{i}/training_data.json')}
    if len(inputs) != 50 or len(set(source_groups.values())) != 50 or train_sources & set(source_groups.values()):
        raise ValueError('Reserved sources must be complete, distinct and excluded from all training')
    cases = []
    for row in inputs:
        evidence = row['input']['evidence']
        cases.append({'case': row['case'], 'id': row['case'], 'group': source_groups[row['case']],
            'instruction': row['input']['instruction'], 'evidence': evidence,
            'image_hashes': {k: base.fingerprint(p) for k, p in evidence.items()}})
    policies = {}; sources = [RESERVED / 'test_inputs.json', RESERVED / 'test_references.json', RESERVED / 'splits/test.json']
    for i in (1, 2, 3):
        for mode in ('direct', 'merge'):
            folder = TRAINED / f'split{i}' / mode; policy = base.read(folder / 'policy.json'); freeze = base.read(folder / 'freeze.json')
            if policy is None or digest(policy) != freeze['runtime_ref']:
                raise ValueError('All six v14 policies must be frozen and complete')
            PortableRuleExecutor(policy)
            policies[f'v14_{mode}_split{i}'] = policy
            sources.extend((folder / 'policy.json', folder / 'freeze.json'))
        folder = BASELINE / f'split{i}'; policy = base.read(folder / 'frozen_policy.json')
        if digest(policy) != base.read(folder / 'freeze.json')['runtime_ref']:
            raise ValueError('Baseline freeze changed')
        PortableRuleExecutor(policy); policies[f'v12_merge_split{i}'] = policy
        sources.extend((folder / 'frozen_policy.json', folder / 'freeze.json'))
    protocol = {'version': VERSION, 'judge_identity': base.IDENTITY, 'compiler_revision': 'bound-instruction-compiler-v3',
        'original_reservation_judge': base.read(RESERVED / 'study_protocol.json')['judge'],
        'model_change': 'Use current Luna/none/temperature-zero profile to match the new training evidence; original M0 specified Sol/high.',
        'cases': 50, 'new_calls_max': 200,
        'completion_tokens_max': 50 * (2 * base.CAPS['compile'] + base.CAPS['observe'] + base.INTERPRET_CAP),
        'attempts': 'One compile, observation and interpretation per case. One bounded text-only compiler repair on schema/contract failure. No transport or observation retries.',
        'comparison': 'Apply every frozen policy to the same shared evidence; report all three training replications without selecting a winner or tuning after evaluation.',
        'selection_and_fitting': False, 'workers': 4,
        'primary_readout': 'Per-policy and paired v14-merge versus v14-direct and v12-merge accuracy, macro-F1, class recall, unresolved count. Repeated policies share the same fifty sources, not 150 independent cases.'}
    code = [Path(__file__).resolve(), ROOT / 'run/calitree_three_splits.py', ROOT / 'run/calitree_three_splits_compiler_v3.py']
    code += sorted((ROOT / 'critical/core/decision').glob('*.py'))
    code += sorted((ROOT / 'critical/core/calibration/semantic_hierarchy').glob('*.py'))
    code += sorted((ROOT / 'critical/core/prompts/templates/bound_compiler_v3').glob('*.txt'))
    code += sorted((ROOT / 'critical/core/prompts/templates/bound_evidence_v2').glob('*.txt'))
    code += [ROOT / rel for rel in ('critical/lm_engine/lm_gpt/engine.py', 'critical/lm_engine/provider_api.py',
        'critical/lm_engine/lm_template/base.py', 'critical/lm_engine/openai_compat.py')]
    manifest = {'version': VERSION, 'cases': cases, 'workers': 4, 'protocol_ref': digest(protocol), 'policies_ref': digest(policies),
        'source_hashes': {str(p.relative_to(ROOT)): base.fingerprint(p) for p in sources},
        'code_hashes': {str(p.relative_to(ROOT)): base.fingerprint(p) for p in code}}
    manifest['artifact_ref'] = digest(manifest)
    base.exact(out / 'protocol.json', protocol); base.exact(out / 'policies.json', policies); base.exact(out / 'manifest.json', manifest)
    return manifest


def collect(out, live):
    if not live:
        raise ValueError('Fresh reserved-set evidence requires explicit --live approval')
    manifest = prepare(out)
    physical = collect_physical(out, manifest, live=True)
    base.exact(out / 'physical_audit.json', audit_compiler(out, manifest, physical))
    by_case = {r['case']: r for r in physical}
    with ThreadPoolExecutor(max_workers=4) as pool:
        meanings = list(pool.map(lambda case: base.interpret_one(out, case, by_case[case['case']], True), manifest['cases']))
    by_meaning = {r['case']: r for r in meanings}; records = []
    for case in manifest['cases']:
        row = by_case[case['case']]
        feature = project(row['compilation']['program'], row['observation']['observation'], image_identity(case['evidence'])[1],
            by_meaning[case['case']]['interpretation']) if row['record'] else None
        records.append({'case': case['case'], 'features': feature})
    base.exact(out / 'portable_records.json', records)
    prepare(out)


def evaluate(out):
    prepare(out)
    records = base.read(out / 'portable_records.json'); policies = base.read(out / 'policies.json')
    if len(records) != 50 or len({r['case'] for r in records}) != 50:
        raise ValueError('Every reserved case must remain in the evaluation')
    predictions = {name: executor.predict_records([r['features'] for r in records])
                   for name, executor in ((k, PortableRuleExecutor(v)) for k, v in policies.items())}
    # Predictions are durable before the scorer loads any reference labels.
    base.exact(out / 'predictions.json', {'case_order': [r['case'] for r in records], 'policies': predictions})
    refs = {r['case']: r['reference'].lower() for r in base.read(RESERVED / 'test_references.json')['cases']}
    targets = [base.LABELS.index(refs[r['case']]) for r in records]
    result = {'metrics': {name: metrics([p['prediction'] for p in ps], targets) for name, ps in predictions.items()},
        'unique_evaluation_sources': 50, 'fitting_or_selection': False, 'shared_evidence': True}
    result['paired'] = {}
    for i in (1, 2, 3):
        for control in (f'v14_direct_split{i}', f'v12_merge_split{i}'):
            counts = Counter()
            for a, b, y in zip(predictions[f'v14_merge_split{i}'], predictions[control], targets):
                ca, cb = a['prediction'] == y, b['prediction'] == y
                counts['both_correct' if ca and cb else 'v14_merge_only' if ca else 'control_only' if cb else 'both_wrong'] += 1
            result['paired'][f'v14_merge_split{i}_vs_{control}'] = dict(counts)
    base.exact(out / 'results.json', result); print(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--mode', choices=('preflight', 'collect', 'evaluate', 'all'), default='preflight')
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args(); out = args.output_dir.resolve()
    if args.mode == 'preflight':
        prepare(out); print(base.read(out / 'protocol.json'))
    else:
        if args.mode in ('collect', 'all'):
            collect(out, args.live)
        if args.mode in ('evaluate', 'all'):
            evaluate(out)
