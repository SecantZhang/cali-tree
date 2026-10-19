"""Frozen union-policy prediction from bound evidence; no router or model call."""
import argparse
import json
from pathlib import Path

from critical.core.calibration.semantic_hierarchy.union_runtime_v11 import load


def predict(package, payload):
    if not isinstance(payload, dict) or set(payload) != {'program', 'observation', 'image_pair_ref', 'interpretation'}:
        raise ValueError('Labels, source membership, and routing scopes are prohibited inference inputs')
    judge = load(package)
    return {'judge_ref': judge.artifact['artifact_ref'], **judge.predict_bound(
        payload['program'], payload['observation'], payload['image_pair_ref'], payload['interpretation'])}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package', type=Path, required=True)
    p.add_argument('--evidence', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(predict(a.package, json.loads(a.evidence.read_text())), indent=2))
