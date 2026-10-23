"""Audit v14 provenance and verify its class-preserving pruning replay."""
import argparse
import gzip
import json
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.calibration.semantic_hierarchy import supported_pruning_v14 as supported
from critical.core.calibration.semantic_hierarchy.regularized_tree_v13 import Config
from run.verify_calitree_regularized_v13 import audit as audit_common
from run.calitree_regularized_v13 import read


def audit(out):
    common = audit_common(out)
    datasets = [read(out / f'split{i}/training_data.json') for i in (1, 2, 3)]
    checked = 0
    for path in (out / 'procedure_cache').glob('*.json.gz'):
        value = json.loads(gzip.decompress(path.read_bytes()))
        source_set = set(value['source_groups'])
        rows = next(selected for full in datasets
                    if digest(selected := sorted((r for r in full if r['source_group'] in source_set),
                                                 key=lambda r: r['source_group'])) == value['rows_ref'])
        by_id = {r['source_group']: r for r in rows}; result = value['result']
        models = result['nodes'] or [result['root']]
        for model in models:
            policy = model['policy']; config = Config(**policy['search']['config'])
            cohort = [by_id[k] for k in model['fit_sources']]
            shape = supported.grown_tree(model, cohort)
            tree, report = supported.prune_frontier(shape, [r for r in cohort if r['features'] is not None], config.leaf_penalty)
            assert policy['search']['version'] == supported.VERSION
            assert tree == policy['tree'] and report == policy['search']['pruning']
            assert not supported.violations(tree)
            if model.get('children'):
                assert report['all_supported_classes_preserved']
            checked += 1
    value = {**common, 'supported_pruning_replays': checked,
             'fixed_shape_optimality_check': 'Unit tests enumerate all prunings on a small reference tree; artifact audit replays the bounded frontier.'}
    save_json(out / 'verification.json', value); print(value)
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    audit(parser.parse_args().output_dir.resolve())
