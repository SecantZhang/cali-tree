"""Label-blind frozen execution of authenticated upstream evidence; zero calls."""
import argparse
import json
from pathlib import Path

from critical.core.calibration.semantic_hierarchy.hierarchy_runtime_v9 import HierarchyExecutor
from critical.core.calibration.semantic_hierarchy.hierarchy_export_v9 import load


def predict(bundle_path, payload):
    if not isinstance(payload, dict) or set(payload) != {'program', 'observation', 'image_pair_ref', 'interpretation'}:
        raise ValueError('Supply only bound evidence; labels and fitting metadata are not inference inputs')
    bundle_path = Path(bundle_path)
    executor = load(bundle_path) if bundle_path.is_dir() else HierarchyExecutor(json.loads(bundle_path.read_text()))
    return {'bundle_ref': executor.bundle['bundle_ref'], **executor.predict_bound(
        payload['program'], payload['observation'], payload['image_pair_ref'], payload['interpretation'])}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--evidence', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(predict(a.bundle, json.loads(a.evidence.read_text())), indent=2))

