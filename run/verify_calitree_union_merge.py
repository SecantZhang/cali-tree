"""Verify and seal the successful router-free, reuse-first merge experiment."""
import argparse
from pathlib import Path
import re
import shutil

from critical.core.decision.artifacts import save_json
from critical.core.calibration.semantic_hierarchy.union_runtime_v11 import load
from run.calitree_union_merge import ROOT, M0, read, fingerprint
from run.calitree_union_reuse import CONTROL
from run.audit_calitree_union_merge import audit
from run.audit_calitree_union_invariance import audit as invariance
from run.verify_calitree_semantic_hierarchy import check_seal as check_previous_seal
from run.calitree_m0_finalize import independent_check


def verify(out):
    check_previous_seal(ROOT / 'logs/exps/261015-semantic-hierarchy-m3-m7-v9.2')
    audited = audit(out); inv = invariance(out)
    reserved = independent_check(M0, read(M0 / 'selection_protocol.json'))
    assert reserved['passed'] and reserved['current_study_final_predictions'] == 0
    tests = (out / 'tests.log').read_text()
    count = re.search(r'(\d+) passed, (\d+) skipped.*in ([\d.]+)s', tests)
    assert count and int(count[1]) >= 969 and int(count[2]) == 23
    assert not re.search(r'\b\d+ (?:failed|errors?)\b', tests)
    replay = (out / 'replay.log').read_text()
    assert "'run': 'semantic8_reuse'" in replay and "'new_fits': 0" in replay
    assert 'Traceback' not in replay
    selected = read(out / 'selected_training_root.json')
    tree = read(out / 'selected_hierarchy.json')
    table = read(out / 'selected_merge_table.json')
    assert selected['node_id'] == tree['root']
    assert len(tree['nodes']) == 15 and len(tree['edges']) == 14 and len(table) == 7
    assert [r['node_id'] for r in table] == selected['selected_merge_order']
    package = load(ROOT / 'examples/calitree_union_reuse_v11')
    assert package.artifact['policy'] == read(out / 'deployment_policy.json')
    smoke = read(out / 'runtime_smoke.json')
    assert smoke['judge_ref'] == package.artifact['artifact_ref'] and smoke['prediction'] == 2
    cold_refs = {}
    for run_name in ('original4_reuse', 'split8_reuse', 'semantic8_reuse'):
        result = read(out / 'runs' / run_name / 'result.json')
        refs = {r for p in result['proposals'] for r in p['fit_refs']}
        refs.update(r for g in read(out / 'runs' / run_name / 'seeds.json')['groups'] for r in g['fit_refs'])
        cold = [r for r in refs if (out / 'fits' / (r + '.json')).exists()]
        assert len(cold) <= 256
        cold_refs[run_name] = len(cold)
    return {'passed': True, 'selected_run': audited['selected_run'],
        'selected_merges': audited['selected_merges'], 'training': audited['training'],
        'development': audited['development'], 'root_only_uses_child_predicates': True,
        'tests': {'passed': int(count[1]), 'skipped': int(count[2]), 'seconds': float(count[3])},
        'equivalent_check_variants': inv['equivalent_check_variants'],
        'selected_hierarchy_nodes': len(tree['nodes']), 'selected_hierarchy_edges': len(tree['edges']),
        'run_audits': audited['reuse_runs'], 'control_audits': audited['control_runs'],
        'referenced_cold_fit_counts': cold_refs, 'solver_fit_replay_exact': True,
        'package_verified': True, 'real_evidence_cli_verified': True,
        'previous_experiment_seal_unchanged': True,
        'm0_images_checked': reserved['image_files_checked'],
        'new_model_calls': 0, 'reserved_test_predictions': 0}


def check(out):
    seal = read(out / 'completion_seal.json')
    for rel, expected in seal['sources'].items():
        assert fingerprint(ROOT / rel) == expected, ('changed_source', rel)
        assert fingerprint(out / 'source_snapshot' / rel) == expected
    for rel, expected in seal['files'].items():
        assert fingerprint(out / rel) == expected, ('changed_artifact', rel)
    for rel, expected in seal['control_files'].items():
        assert fingerprint(CONTROL / rel) == expected, ('changed_control', rel)
    package = ROOT / 'examples/calitree_union_reuse_v11'
    assert read(package / 'manifest.json')['manifest_ref'] == seal['package_ref']
    load(package)


def close(out):
    if (out / 'completion_seal.json').exists():
        check(out); return verify(out)
    result = verify(out); save_json(out / 'verification.json', result)
    paths = [ROOT / 'critical/core/calibration/semantic_hierarchy' / name for name in (
        'union_groups_v10.py', 'union_learning_v10.py', 'union_merges_v10.py',
        'union_reuse_v11.py', 'union_runtime_v11.py')]
    paths += [ROOT / 'run' / name for name in ('calitree_union_merge.py', 'calitree_union_reuse.py',
        'calitree_union_predict.py', 'audit_calitree_union_merge.py',
        'audit_calitree_union_invariance.py', 'verify_calitree_union_merge.py')]
    paths += [ROOT / 'tests/unit/calitree/test_union_merging_v10.py',
              ROOT / 'docs/calitree_router_free_union_merging.md']
    sources = {}
    for p in paths:
        rel = p.relative_to(ROOT); dst = out / 'source_snapshot' / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            assert fingerprint(dst) == fingerprint(p)
        else:
            shutil.copyfile(p, dst)
        sources[str(rel)] = fingerprint(p)
    control_files = {str(p.relative_to(CONTROL)): fingerprint(p) for p in sorted(CONTROL.rglob('*'))
                     if p.is_file() and 'locks' not in p.parts}
    files = {str(p.relative_to(out)): fingerprint(p) for p in sorted(out.rglob('*'))
             if p.is_file() and 'locks' not in p.parts and p.name not in ('completion_seal.json', 'closure.log')}
    save_json(out / 'completion_seal.json', {'version': 'router-free-union-goal-completion-v11',
        'sources': sources, 'files': files, 'control_files': control_files,
        'package_ref': read(ROOT / 'examples/calitree_union_reuse_v11/manifest.json')['manifest_ref']})
    check(out)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True); p.add_argument('--seal', action='store_true')
    a = p.parse_args(); out = a.output_dir.resolve()
    if a.seal:
        result = close(out)
    else:
        if (out / 'completion_seal.json').exists():
            check(out)
        result = verify(out)
    print({k: v for k, v in result.items() if k not in ('run_audits', 'control_audits')})
