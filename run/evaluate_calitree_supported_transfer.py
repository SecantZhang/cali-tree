"""Historical development transfer after all v13/v14 policies are frozen.

No fitting, model calls, root selection, or reserved-fifty access. The 36 sources
were inspected in earlier research and are explicitly not a fresh final test.
"""
import argparse
from collections import Counter
from pathlib import Path

from critical.core.decision.artifacts import digest
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import metrics
from run.calitree_regularized_v13 import ROOT, read, exact, fingerprint

V12 = ROOT / 'logs/exps/261018-union-challenger-validation-v12'
V13 = ROOT / 'logs/exps/261018-regularized-child-compression-v13'
V14 = ROOT / 'logs/exps/261018-supported-child-compression-v14'
EVIDENCE = ROOT / 'logs/exps/261018-three-sampled-splits-luna-compiler-v3'


def evaluate(out):
    # Freeze and authenticate ALL policies before opening the evaluation records.
    models = {}; files = {str(Path(__file__).resolve().relative_to(ROOT)): fingerprint(__file__)}
    for i in (1, 2, 3):
        for name, directory, mode in (('v13_merge', V13, 'merge'), ('v14_merge', V14, 'merge'), ('v14_direct', V14, 'direct')):
            folder = directory / f'split{i}' / mode
            freeze = read(folder / 'freeze.json'); policy = read(folder / 'policy.json')
            if freeze['runtime_ref'] != digest(policy):
                raise ValueError('Frozen policy identity changed')
            models[(i, name)] = policy
            for f in (folder / 'freeze.json', folder / 'policy.json'):
                files[str(f.relative_to(ROOT))] = fingerprint(f)
        folder = V12 / f'split{i}'
        freeze = read(folder / 'freeze.json'); policy = read(folder / 'frozen_policy.json')
        if freeze['runtime_ref'] != digest(policy):
            raise ValueError('Frozen baseline changed')
        models[(i, 'v12_merge')] = policy
        for f in (folder / 'freeze.json', folder / 'frozen_policy.json'):
            files[str(f.relative_to(ROOT))] = fingerprint(f)
    for f in [EVIDENCE / 'portable_records.json', *(EVIDENCE / f'splits/split{i}.json' for i in (1, 2, 3))]:
        files[str(f.relative_to(ROOT))] = fingerprint(f)
    exact(out / 'all_frozen.json', {'policies': {f'split{i}/{name}': digest(p) for (i, name), p in models.items()},
        'file_hashes': files, 'selection_in_this_stage': False})
    records = read(EVIDENCE / 'portable_records.json'); pooled = {}; reports = []; evaluation_sources = []
    training_sources = {r['source_group'] for i in (1, 2, 3) for r in read(V14 / f'split{i}/training_data.json')}
    for i in (1, 2, 3):
        split = read(EVIDENCE / f'splits/split{i}.json'); rows = [records[r['case']] for r in split['evaluation']]
        if {r['source_group'] for r in rows} & training_sources:
            raise ValueError('Transfer cohort overlaps any training cohort')
        evaluation_sources.extend(r['source_group'] for r in rows)
        arms = {}
        for name in ('v12_merge', 'v13_merge', 'v14_direct', 'v14_merge'):
            policy = models[(i, name)]
            ps = PortableRuleExecutor(policy).predict_records([r['features'] for r in rows]) if policy else [
                {'prediction': -1, 'reason': 'no_complete_root', 'trace': []} for _ in rows]
            cases = [{'case': r['case'], 'source_group': r['source_group'], 'reference': r['reference'], **p} for r, p in zip(rows, ps)]
            pooled.setdefault(name, []).extend(cases)
            arms[name] = {'metrics': metrics([p['prediction'] for p in ps], [r['reference'] for r in rows]), 'cases': cases}
        report = {'split': f'split{i}', 'arms': arms}; exact(out / f'split{i}.json', report); reports.append(report)
    if len(evaluation_sources) != 36 or len(set(evaluation_sources)) != 36:
        raise ValueError('Expected 36 distinct transfer sources')
    paired = {}
    for other in ('v12_merge', 'v13_merge', 'v14_direct'):
        counts = Counter()
        for a, b in zip(pooled['v14_merge'], pooled[other]):
            assert a['case'] == b['case'] and a['reference'] == b['reference']
            ca, cb = a['prediction'] == a['reference'], b['prediction'] == b['reference']
            counts['both_correct' if ca and cb else 'v14_only' if ca else 'control_only' if cb else 'both_wrong'] += 1
        paired[other] = dict(counts)
    result = {'splits': reports, 'pooled': {name: metrics([r['prediction'] for r in cases], [r['reference'] for r in cases]) for name, cases in pooled.items()},
        'paired': paired, 'new_model_calls': 0, 'new_fits': 0, 'reserved_test_predictions': 0,
        'source_disjoint_from_all_training': True, 'caveat': 'Previously inspected historical development cohort, not a fresh confirmatory evaluation.'}
    exact(out / 'results.json', result)
    lines = ['# Frozen v14 historical development transfer', '', result['caveat'], '',
        '| Split | V12 merged | V13 merged | V14 direct | V14 merged |', '|---|---:|---:|---:|---:|']
    for r in reports:
        lines.append('| ' + r['split'] + ' | ' + ' | '.join(str(r['arms'][name]['metrics']['correct']) + '/12'
            for name in ('v12_merge', 'v13_merge', 'v14_direct', 'v14_merge')) + ' |')
    lines += ['', 'All policies were frozen before this stage read the evaluation evidence. No fitting or selection occurs here. '
        'The 36 sources are mutually distinct and excluded from every training cohort. Missing observations remain unresolved. '
        'The final fifty remain untouched.', '', 'Pooled and paired results are in results.json; exact input policy identities are in all_frozen.json.']
    (out / 'report.md').write_text('\n'.join(lines) + '\n'); print(result['pooled'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    evaluate(parser.parse_args().output_dir.resolve())
