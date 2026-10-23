"""Summarize matched profiles, compression and measured work without refitting."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.calibration.semantic_hierarchy.regularized_tree_v13 import predict, metrics
from critical.core.calibration.semantic_hierarchy.union_validation_v12 import folds
from run.calitree_regularized_v13 import ROOT, read


def cached(out, key):
    value = json.loads(gzip.decompress((out / 'procedure_cache' / (key + '.json.gz')).read_bytes()))
    if value['content_ref'] != digest({k: v for k, v in value.items() if k != 'content_ref'}):
        raise ValueError('Changed procedure cache')
    return value


def report(out):
    manifest = read(out / 'manifest.json'); results = read(out / 'results.json')
    paired = Counter(); cases = []; comparisons = []
    for i in (1, 2, 3):
        folder = out / f'split{i}'; rows = read(folder / 'training_data.json'); same = 0; selected_cases = []
        for fold in folds(rows):
            d = folder / f'outer/{fold["fold"]}/merge'; selection = read(d / 'selection.json'); score = read(d / 'score.json')
            key = digest([manifest['artifact_ref'], sorted(fold['train'], key=lambda r: r['source_group']), selection['selected'], 'direct'])
            control = cached(out, key)['result']['root']; merged = cached(out, score['fit_ref'])['result']['root']
            same += control['runtime'] == merged['runtime'] if merged and control else control is merged
            ps = predict(control, fold['validation']) if control else [{'prediction': -1} for _ in fold['validation']]
            for row, a, b in zip(fold['validation'], score['cases'], ps):
                ca, cb = a['prediction'] == row['reference'], b['prediction'] == row['reference']
                paired['both_correct' if ca and cb else 'merge_only' if ca else 'matched_direct_only' if cb else 'both_wrong'] += 1
                item = {'split': i, 'fold': fold['fold'], 'source_group': row['source_group'], 'reference': row['reference'],
                        'merged': a['prediction'], 'matched_profile_direct': b['prediction']}
                cases.append(item); selected_cases.append(item)
        freeze = read(folder / 'merge/freeze.json'); run = cached(out, freeze['fit_ref']); r = run['result']
        registry = {n['node_id']: n for n in r['nodes']}; seed_rules = []; reductions = []
        def visit(node):
            if not node['children']:
                seed_rules.append(node['complexity']['rules']); return
            reductions.append(node['acceptance']['compression'])
            for k in node['children']:
                visit(registry[k])
        if r['root']:
            visit(r['root'])
        legacy = ROOT / f'logs/exps/261018-union-challenger-validation-v12/split{i}'
        old = read(legacy / 'full/original4/result.json'); seeds = read(legacy / 'full/original4/seeds.json')
        refs = {k for p in old['proposals'] for k in p['fit_refs']} | {k for g in seeds['groups'] for k in g['fit_refs']}
        comparisons.append({'split': i, 'matched_profile_direct': metrics([r['matched_profile_direct'] for r in selected_cases], [r['reference'] for r in selected_cases]),
            'identical_outer_policies': same, 'outer_folds': 4, 'initial_child_rules': sum(seed_rules),
            'root_rules': r['root']['complexity']['rules'] if r['root'] else None,
            'selected_merge_compressions': reductions, 'v14_procedure_work': r['work'],
            'v14_pair_proposals': len(r['proposals']), 'v12_unique_cold_or_restricted_fit_refs': len(refs),
            'v12_pair_proposals': old['proposal_count'],
            'work_comparison_caveat': 'Different learning procedures. Old count excludes child-shape relabeling; new fit count includes shape evaluation. These are not matched hardware timing or isolated-compute ablations.'})
    value = {'nested': results['pooled_nested'], 'matched_profile_direct': metrics([r['matched_profile_direct'] for r in cases], [r['reference'] for r in cases]),
        'paired_vs_matched_profile_direct': dict(paired), 'splits': comparisons, 'cases': cases,
        'unique_nested_sources': len({r['source_group'] for r in cases}), 'nested_slots': len(cases),
        'independence_claim': False, 'new_fits': 0, 'new_model_calls': 0}
    save_json(out / 'comparison.json', value)
    lines = ['# V14 child contribution, compression and work', '',
        f"Nested merged: {value['nested']['merge']['metrics']['correct']}/144; separately tuned direct: "
        f"{value['nested']['direct']['metrics']['correct']}/144; direct with the exact merge-selected profiles: "
        f"{value['matched_profile_direct']['correct']}/144.", '',
        'The matched-profile control is already present in the frozen caches. This report adds no fits and does not select policies. '
        f"There are {value['unique_nested_sources']} distinct sources behind 144 correlated validation slots.", '',
        '| Split | Initial child rules | Final root rules | New fits including warm shapes | V12 cold/restricted fit references |',
        '|---|---:|---:|---:|---:|']
    for r in comparisons:
        lines.append(f"| {r['split']} | {r['initial_child_rules']} | {r['root_rules']} | {r['v14_procedure_work']['fits']} | {r['v12_unique_cold_or_restricted_fit_refs']} |")
    lines += ['', 'Every selected merge passes the declared >=20% immediate-child compression gate. '
        'Search-work counts compare complete, different procedures; they do not establish a hardware-independent speedup factor. '
        'Direct fitting remains much cheaper than hierarchy construction.', '',
        'Paired validation outcomes versus matched-profile direct: ' + json.dumps(dict(paired)) + '.', '',
        'Nested source overlap and prior training-cohort inspection limit inference. This supports continued merging research; '
        'it does not replace a prospectively frozen final evaluation.']
    (out / 'comparison.md').write_text('\n'.join(lines) + '\n'); print({k: v for k, v in value.items() if k not in ('cases', 'splits', 'nested')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    report(parser.parse_args().output_dir.resolve())
