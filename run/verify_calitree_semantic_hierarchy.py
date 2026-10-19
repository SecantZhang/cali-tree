"""Completion verification and immutable closure for the M3--M7 study."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil

from critical.core.decision.artifacts import digest, save_json
from critical.core.calibration.semantic_hierarchy.hierarchy_export_v9 import load
from run.calitree_semantic_hierarchy import ROOT, M0, read, fingerprint, verify_m2
from run.audit_calitree_semantic_hierarchy import audit_hierarchy, route_alternatives
from run.audit_calitree_hierarchy_invariance import audit as invariance_audit
from run.calitree_m0_finalize import independent_check


def verify(out):
    m2 = verify_m2()
    result = audit_hierarchy(out)
    routes = route_alternatives(out)
    invariance = invariance_audit(out)
    reservation = independent_check(M0, read(M0 / 'selection_protocol.json'))
    assert reservation['passed'] and reservation['current_study_final_predictions'] == 0
    assert routes == read(out / 'baseline/route_alternative_audit.json')
    assert len(routes['stable_combinations']) == 1 and not routes['stable_combinations'][0]['routes']
    package = load(ROOT / 'examples/calitree_semantic_hierarchy_v9')
    assert package.export() == read(out / 'hierarchy/frozen_bundle.json')
    replay = read(out / 'hierarchy/replay.json')
    assert replay['exact_replay'] and replay['new_fits'] == replay['new_model_calls'] == 0
    assert replay['bundle_sha256'] == fingerprint(out / 'hierarchy/frozen_bundle.json')
    assert replay['results_sha256'] == fingerprint(out / 'hierarchy/results.json')
    tests = (out / 'tests.log').read_text()
    match = re.search(r'(\d+) passed, (\d+) skipped.*in ([\d.]+)s', tests)
    assert match and int(match[1]) >= 954 and int(match[2]) == 23
    assert not re.search(r'\b\d+ (?:failed|errors?)\b', tests)
    graph = read(out / 'hierarchy/provenance_graph.json')
    seen, active = set(), set()
    def walk(name):
        assert name in graph['nodes'] and name not in active
        if name in seen:
            return
        active.add(name); n = graph['nodes'][name]
        for c in n['children']:
            walk(c)
        if n['children']:
            assert set(n['fit_sources']) == set().union(*(set(graph['nodes'][c]['fit_sources']) for c in n['children']))
            assert n['depth'] == 1 + max(graph['nodes'][c]['depth'] for c in n['children']) <= 3
        active.remove(name); seen.add(name)
    for name in graph['nodes']:
        walk(name)
    assert sorted(graph['edges'], key=lambda e: (e['parent'], e['child'])) == sorted(
        [{'parent': k, 'child': c} for k, n in graph['nodes'].items() for c in n['children']],
        key=lambda e: (e['parent'], e['child']))
    history = read(out / 'hierarchy/history.json')['steps']
    assert all(s['parent']['node_id'] in graph['nodes'] for s in history)
    return {'passed': True, 'M2_prerequisite': m2, 'milestone_audit': result,
            'route_alternative_combinations': routes['combinations_evaluated'],
            'equivalent_check_variants': invariance['equivalent_check_variants'],
            'decision_trace_comparisons': invariance['prediction_and_trace_comparisons'],
            'tests': {'passed': int(match[1]), 'skipped': int(match[2]), 'seconds': float(match[3])},
            'source_partitions': reservation['partition_sizes'], 'checked_images': reservation['image_files_checked'],
            'provenance_nodes': len(graph['nodes']), 'provenance_edges': len(graph['edges']),
            'frozen_export_verified': True, 'new_model_calls': 0, 'reserved_test_predictions': 0}


def close(out):
    if (out / 'completion_seal.json').exists():
        check_seal(out)
        return verify(out)
    result = verify(out)
    save_json(out / 'verification.json', result)
    sources = sorted((ROOT / 'critical/core/calibration/semantic_hierarchy').glob('*v9.py'))
    sources += [ROOT / 'run' / name for name in ('calitree_semantic_hierarchy.py',
        'calitree_semantic_hierarchy_predict.py', 'audit_calitree_semantic_hierarchy.py',
        'audit_calitree_hierarchy_invariance.py', 'verify_calitree_semantic_hierarchy.py')]
    sources += [ROOT / 'tests/unit/calitree/test_semantic_hierarchy_v9.py',
                ROOT / 'docs/calitree_m3_m7_semantic_hierarchy.md']
    source_hashes = {}
    for path in sources:
        rel = path.relative_to(ROOT); dst = out / 'source_snapshot' / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            assert fingerprint(dst) == fingerprint(path)
        else:
            shutil.copyfile(path, dst)
        source_hashes[str(rel)] = fingerprint(path)
    files = {str(p.relative_to(out)): fingerprint(p) for p in sorted(out.rglob('*'))
             if p.is_file() and p.name not in ('completion_seal.json', 'closure.log')}
    seal = {'version': 'semantic-hierarchy-v9.2-completion', 'source_hashes': source_hashes,
            'files': files, 'inference_package_ref': read(ROOT / 'examples/calitree_semantic_hierarchy_v9/manifest.json')['manifest_ref']}
    save_json(out / 'completion_seal.json', seal)
    check_seal(out)
    return result


def check_seal(out):
    seal = read(out / 'completion_seal.json')
    for rel, expected in seal['source_hashes'].items():
        assert fingerprint(ROOT / rel) == expected, ('source_changed', rel)
        assert fingerprint(out / 'source_snapshot' / rel) == expected
    for rel, expected in seal['files'].items():
        assert fingerprint(out / rel) == expected, ('artifact_changed', rel)
    assert read(ROOT / 'examples/calitree_semantic_hierarchy_v9/manifest.json')['manifest_ref'] == seal['inference_package_ref']
    load(ROOT / 'examples/calitree_semantic_hierarchy_v9')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--seal', action='store_true')
    a = p.parse_args(); out = a.output_dir.resolve()
    if a.seal:
        result = close(out)
    else:
        if (out / 'completion_seal.json').exists():
            check_seal(out)
        result = verify(out)
    print({k: v for k, v in result.items() if k not in ('M2_prerequisite', 'milestone_audit')})
