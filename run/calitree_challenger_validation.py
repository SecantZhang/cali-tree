"""Offline always-challenger + training-only validation on the same three splits.

There is deliberately no --live switch or extraction path. Only cached portable
records are used. All three roots must be frozen before evaluation is enabled.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import json
import shutil
import subprocess
import sys

from critical.core.decision.artifacts import digest, save_json
from critical.core.calibration.semantic_hierarchy import union_validation_v12 as learner
from critical.core.calibration.semantic_hierarchy.union_learning_v10 import PROFILES
from critical.core.calibration.semantic_hierarchy.union_reuse_v11 import REPAIR
from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import metrics
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from run.calitree_union_reuse import merge_order
from run.calitree_three_splits import ROOT, read, exact, fingerprint

SOURCE = ROOT / 'logs/exps/261018-three-sampled-splits-luna-compiler-v3'
VERSION = 'three-split-challenger-validation-v12-20261018'


def prepare(out):
    if (out / 'manifest.json').exists():
        manifest = read(out / 'manifest.json'); verify(out, manifest); return manifest
    out.mkdir(parents=True, exist_ok=True)
    source_seal = read(SOURCE / 'completion_seal.json')
    assert all(fingerprint(SOURCE / name) == sha for name, sha in source_seal['files'].items())
    old = read(SOURCE / 'protocol.json')
    assert old['limits'] == learner.LIMITS and old['profiles'] == PROFILES and old['repair'] == REPAIR
    protocol = {'version': VERSION, 'learner': learner.VERSION, 'cached_evidence': str(SOURCE.relative_to(ROOT)),
        'new_model_calls': 0, 'reserved_test_predictions': 0, 'folds': learner.CV, 'families': learner.FAMILIES,
        'groupings': learner.GROUPINGS, 'profiles': PROFILES, 'limits': learner.LIMITS, 'refinement': REPAIR,
        'always_challenger': 'Every parent offers full-grammar shallow/compact or compact/deep cold fits even when restricted reuse passes. Every model uses the original gate against that exact child pair.',
        'retention': 'Two slots per union: cover reused/refined and full-grammar generation families when available, then training rank. The same runtime can record both generating recipes. Distinct qualifying lineages retain truthful provenance.',
        'inner_grouping': '4 folds stratified within original batch/reference: fit 36, validate 12. Recompute original4 (9 each), split8 (4/5 each) and semantic8 (4/5 capacities, label-blind); no full-48 grouping or fitted child is reused inside a fold.',
        'validation_selection': 'Select grouping/root-generation-family procedures by pooled 48-source OOF macro-F1, worst-class recall, then lower fold-score dispersion. Within a procedure retain the best passing training-rank root. Training rank, reuse tie-break and stable identity break tied procedure scores.',
        'infeasible_folds': 'No root for a family means 12 Unresolved predictions; no fold omitted, gate relaxed, retry or resampling. All-zero validation ties use the declared training/stable tie-break and are labeled uninformative.',
        'freeze_then_evaluate': 'Workers receive only their 48 training records. Freeze every selected runtime and selection manifest; evaluation refuses to run until all three are frozen.',
        'gate_changes': False, 'selection_unit': 'Root-generating procedures, not individual trees learned on all 48',
        'comparison_scope': 'Combined always-challenger, family-preserving two-slot retention and validation-based root selection versus the previous reuse-first procedure. Previously inspected evaluation cases are development diagnostics.'}
    exact(out / 'protocol.json', protocol)
    files = [Path(__file__).resolve(), ROOT / 'critical/core/calibration/semantic_hierarchy/union_validation_v12.py']
    files += sorted((ROOT / 'critical/core/calibration/semantic_hierarchy').glob('*.py'))
    files += [ROOT / 'critical/core/decision/artifacts.py', ROOT / 'run/calitree_three_splits.py', ROOT / 'run/calitree_union_reuse.py']
    sources = [SOURCE / 'completion_seal.json', SOURCE / 'protocol.json', SOURCE / 'portable_records.json']
    for i in (1, 2, 3):
        name = f'split{i}'; directory = out / name
        for source, target in [(SOURCE / name / 'training_data.json', directory / 'training_data.json'),
                               (SOURCE / 'splits' / (name + '.json'), out / 'splits' / (name + '.json'))]:
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target); sources.append(source)
        # Cache keys include every source, original target, feature record, batch,
        # vocabulary and fit profile. Full-48 fits cannot match inner-fold keys.
        for folder in ('fits', 'reuse_fits'):
            shutil.copytree(SOURCE / name / folder, directory / 'cache' / folder, dirs_exist_ok=True)
    manifest = {'version': VERSION, 'protocol_ref': digest(protocol),
        'code_hashes': {str(p.relative_to(ROOT)): fingerprint(p) for p in dict.fromkeys(files)},
        'source_hashes': {str(p.relative_to(ROOT)): fingerprint(p) for p in sources},
        'training_hashes': {f'split{i}': fingerprint(out / f'split{i}/training_data.json') for i in (1, 2, 3)},
        'split_hashes': {f'split{i}': fingerprint(out / f'splits/split{i}.json') for i in (1, 2, 3)}}
    for rel in manifest['code_hashes']:
        target = out / 'source_snapshot' / rel; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(ROOT / rel, target)
    exact(out / 'manifest.json', manifest); exact(out / 'seal.json', {'manifest_ref': digest(manifest)})
    verify(out, manifest); return manifest


def verify(out, manifest):
    assert manifest['version'] == VERSION and read(out / 'seal.json')['manifest_ref'] == digest(manifest)
    assert digest(read(out / 'protocol.json')) == manifest['protocol_ref']
    for rel, sha in manifest['code_hashes'].items():
        assert fingerprint(ROOT / rel) == sha and fingerprint(out / 'source_snapshot' / rel) == sha, rel
    for rel, sha in manifest['source_hashes'].items():
        assert fingerprint(ROOT / rel) == sha, rel
    for name, sha in manifest['training_hashes'].items():
        assert fingerprint(out / name / 'training_data.json') == sha
    for name, sha in manifest['split_hashes'].items():
        assert fingerprint(out / 'splits' / (name + '.json')) == sha
    old = read(SOURCE / 'protocol.json'); new = read(out / 'protocol.json')
    assert old['limits'] == new['limits'] and old['profiles'] == new['profiles'] and old['repair'] == new['refinement']
    old_files = read(SOURCE / 'manifest.json')['code_hashes']
    for name in ('union_merges_v10.py', 'union_learning_v10.py', 'union_reuse_v11.py'):
        rel = 'critical/core/calibration/semantic_hierarchy/' + name
        assert manifest['code_hashes'][rel] == old_files[rel]


def run_hierarchy(folder, rows, method, fits):
    exact(folder / 'training_scope.json', {'sources': sorted(r['source_group'] for r in rows),
        'rows_ref': digest(sorted(rows, key=lambda r: r['source_group'])), 'method': method})
    # A resumed completed hierarchy is immutable; reuse fitting caches if a run
    # was interrupted before its result was saved.
    if (folder / 'result.json').exists():
        return read(folder / 'result.json')
    groups = learner.grouping(rows, method)
    exact(folder / 'groups.json', groups)
    try:
        result = learner.learn(rows, groups, 'reuse', fits, lambda key, value: exact(folder / (key + '.json'), value))
    except ValueError as error:
        # Integrity/programming errors must fail loudly, not masquerade as a
        # statistically infeasible fold. Only declared learner stops are scored.
        if not str(error).startswith(('No portable initial policy', 'Declared union proposal budget exhausted')):
            raise
        failure = {'error': str(error), 'training_sources': [r['source_group'] for r in rows]}
        exact(folder / 'failure.json', failure)
        result = {'version': learner.VERSION, 'root': None, 'root_candidates': [], 'registry': {},
            'stop': 'infeasible:' + str(error), 'proposal_count': None, 'accepted_proposals': 0, 'failure': failure}
    exact(folder / 'result.json', result)
    return result


def train_split(out, name):
    manifest = prepare(out); directory = out / name
    rows = read(directory / 'training_data.json')
    assert len(rows) == 48 and len({r['source_group'] for r in rows}) == 48
    fits = learner.ChallengerFits(directory / 'cache')
    validation = {method: {family: [] for family in learner.FAMILIES} for method in learner.GROUPINGS}
    fold_plan = learner.folds(rows)
    exact(directory / 'folds.json', [{k: [r['source_group'] for r in v] if k in ('train', 'validation') else v
        for k, v in fold.items()} for fold in fold_plan])
    for fold in fold_plan:
        assert not {r['source_group'] for r in fold['train']} & {r['source_group'] for r in fold['validation']}
        for method in learner.GROUPINGS:
            folder = directory / 'inner' / ('fold' + str(fold['fold'])) / method
            result = run_hierarchy(folder, fold['train'], method, fits)
            for node in result['registry'].values():
                assert set(node['fit_sources']) <= {r['source_group'] for r in fold['train']}
            for family in learner.FAMILIES:
                root = learner.family_root(result, family)
                ps = PortableRuleExecutor(root['runtime']).predict_records([r['features'] for r in fold['validation']]) if root else [
                    {'prediction': -1, 'trace': [], 'reason': 'inner_hierarchy_infeasible'} for r in fold['validation']]
                ys = [r['reference'] for r in fold['validation']]
                item = {'fold': fold['fold'], 'available': root is not None, 'node_id': root['node_id'] if root else None,
                    'training_sources': [r['source_group'] for r in fold['train']],
                    'validation_sources': [r['source_group'] for r in fold['validation']],
                    'predictions': [p['prediction'] for p in ps], 'references': ys,
                    'cases': [{'case': row['case'], 'reference': row['reference'], **p} for row, p in zip(fold['validation'], ps)],
                    'metrics': metrics([p['prediction'] for p in ps], ys), 'hierarchy_stop': result['stop']}
                exact(folder / (family + '-validation.json'), item)
                validation[method][family].append(item)
            print({'split': name, 'inner_fold': fold['fold'], 'method': method,
                'family_roots': {f: learner.family_root(result, f) is not None for f in learner.FAMILIES}}, flush=True)
    summary = {method: {family: learner.cv_summary(values) for family, values in families.items()} for method, families in validation.items()}
    exact(directory / 'validation_summary.json', summary)
    outer = {method: run_hierarchy(directory / 'full' / method, rows, method, fits) for method in learner.GROUPINGS}
    chosen = learner.choose_root(outer, summary)
    candidates = []
    for method, result in outer.items():
        for family in learner.FAMILIES:
            root = learner.family_root(result, family)
            if root:
                candidates.append({'method': method, 'family': family, 'node_id': root['node_id'],
                    'training': root['metrics'], 'complexity': root['complexity'], 'validation': summary[method][family]})
    exact(directory / 'selection_candidates.json', candidates)
    if chosen:
        root = chosen['root']; method, family = chosen['method'], chosen['family']
        order = merge_order(outer[method], root)
        steps = []
        for index, key in enumerate(order, 1):
            node = outer[method]['registry'][key]
            cohort = [r for r in rows if r['source_group'] in node['fit_sources']]
            children = [outer[method]['registry'][k] for k in node['children']]
            decision = learner.gate(node, children, cohort)
            assert decision['status'] == 'accepted'
            steps.append({'step': index, 'node_id': key, 'decision': decision})
        selection = {'method': method, 'family': family, 'node_id': root['node_id'], 'training': root['metrics'],
            'complexity': root['complexity'], 'validation': chosen['validation'],
            'validation_informative': chosen['validation_informative'],
            'root_generation': root['generation_alternatives'][family], 'source_groups': root['fit_sources'],
            'selection_used_outer_evaluation': False}
        policy = root['runtime']
        exact(directory / 'selected_merges.json', steps)
    else:
        selection = {'method': None, 'family': None, 'node_id': None, 'training': None,
            'validation_informative': any(v['metrics']['correct'] for m in summary.values() for v in m.values()),
            'selection_used_outer_evaluation': False, 'reason': 'no_qualifying_full_hierarchy'}
        policy = None
    exact(directory / 'selected_training_root.json', selection)
    exact(directory / 'frozen_policy.json', policy)
    exact(directory / 'freeze.json', {'selection_ref': digest(selection), 'runtime_ref': digest(policy),
        'training_ref': digest(rows), 'validation_ref': digest(summary), 'new_model_calls': 0})
    verify(out, manifest)
    print({'split': name, 'frozen': True, 'method': selection['method'], 'family': selection['family'],
        'training_correct': (selection['training'] or {}).get('correct'), 'new_fits': fits.new_fits}, flush=True)


def evaluate(out):
    manifest = prepare(out)
    # Evaluation cannot be interleaved with family/configuration tuning.
    freezes = {}
    for i in (1, 2, 3):
        name = f'split{i}'; folder = out / name
        if not (folder / 'freeze.json').exists():
            raise ValueError('All three policies must be frozen before any outer evaluation')
        freeze = read(folder / 'freeze.json'); selection = read(folder / 'selected_training_root.json'); policy = read(folder / 'frozen_policy.json')
        assert freeze['selection_ref'] == digest(selection) and freeze['runtime_ref'] == digest(policy)
        freezes[name] = freeze
    exact(out / 'all_frozen.json', freezes)
    records = read(SOURCE / 'portable_records.json')
    results = []
    for i in (1, 2, 3):
        name = f'split{i}'; selection = read(out / name / 'selected_training_root.json'); policy = read(out / name / 'frozen_policy.json')
        split = read(out / 'splits' / (name + '.json'))
        cases = [records[row['case']] for row in split['evaluation']]
        ps = PortableRuleExecutor(policy).predict_records([r['features'] for r in cases]) if policy else [
            {'prediction': -1, 'trace': [], 'reason': 'no_qualifying_full_hierarchy'} for r in cases]
        previous = read(SOURCE / name / 'results.json')
        result = {'split': name, 'selection': selection,
            'evaluation': metrics([p['prediction'] for p in ps], [r['reference'] for r in cases]),
            'cases': [{'case': row['case'], 'source_group': row['source_group'], 'reference': row['reference'],
                'instruction': row['instruction'], **p} for row, p in zip(cases, ps)],
            'previous_merged': previous['arms']['merged']['metrics'], 'direct_control': previous['arms']['direct']['metrics'],
            'new_model_calls': 0, 'reserved_test_predictions': 0}
        exact(out / name / 'results.json', result); results.append(result)
    pooled = metrics([r['prediction'] for s in results for r in s['cases']], [r['reference'] for s in results for r in s['cases']])
    previous = read(SOURCE / 'results.json'); paired = Counter()
    for s, old in zip(results, previous['replications']):
        for a, b in zip(s['cases'], old['arms']['merged']['cases']):
            assert a['case'] == b['case'] and a['reference'] == b['reference']
            ca, cb = a['prediction'] == a['reference'], b['prediction'] == b['reference']
            paired['both_correct' if ca and cb else 'new_only' if ca else 'old_only' if cb else 'both_wrong'] += 1
    report = {'version': VERSION, 'splits': results, 'pooled_evaluation': pooled,
        'previous_merged_pooled': previous['pooled_evaluation']['merged'],
        'direct_control_pooled': previous['pooled_evaluation']['direct'], 'paired_vs_previous': dict(paired),
        'completed_hierarchies': sum(r['selection']['node_id'] is not None for r in results),
        'new_model_calls': 0, 'reserved_test_predictions': 0,
        'caveat': 'Previously inspected, correlated training samples and small development evaluation cohorts; not a fresh confirmatory test.'}
    exact(out / 'results.json', report)
    lines = ['# Always-challenger generation and validation-based selection', '',
        'Same three sampled splits and cached compiler-v3 evidence. Original merge gate function, thresholds, support floor, '
        'retention formula, search profiles, two-slot beam bound and proposal cap remain unchanged. No model calls.', '',
        'Four source-grouped inner folds rebuild all grouping, child fitting and parent vocabularies using 36 training sources. '
        'Each grouping/root-generation-family procedure is scored on 48 out-of-fold predictions. Missing inner roots are retained '
        'as Unresolved for the full validation denominator. The eight-group inner variants use four/five-source groups; outer '
        'groups retain their original sizes. The two-slot retention rule covers both generation families before filling by training rank.', '',
        '| Split | Selected method/family | Inner OOF | Feasible folds | Training | New evaluation | Previous merging | Direct control |',
        '|---|---|---|---|---|---|---|---|']
    for r in results:
        s = r['selection']; cv = s.get('validation'); training = s['training']
        lines.append(f"| {r['split']} | {s['method']} / {s['family']} | {str(cv['metrics']['correct']) + '/48' if cv else 'Unavailable'} | "
            f"{str(cv['feasible_folds']) + '/4' if cv else 'Unavailable'} | {str(training['correct']) + '/48' if training else 'No root'} | "
            f"{r['evaluation']['correct']}/12 | {r['previous_merged']['correct']}/12 | {r['direct_control']['correct']}/12 |")
    lines += ['', f"Pooled: revised merging **{pooled['correct']}/36**, previous merging **{previous['pooled_evaluation']['merged']['correct']}/36**, "
        f"direct control **{previous['pooled_evaluation']['direct']['correct']}/36**.", '',
        'The inner validation unit is a complete grouping/family learning procedure; it is not a held-out score of a tree already '
        'fitted on all 48 sources. All three selected runtime policies were frozen before any outer evaluation. '
        'If every inner procedure is infeasible, validation is explicitly labeled uninformative and the predeclared deterministic '
        'training/stable tie-break applies among passing outer roots. No source, failed fold or missing observation is dropped.', '',
        'This combined algorithm revision does not isolate the separate effects of candidate expansion, family-preserving retention '
        'and validation selection. The current evaluation data were previously inspected; improvement or regression is descriptive.', '',
        'Details: `validation_summary.json`, per-fold validation artifacts, selection candidates, full training lineages, '
        '`selected_merges.json`, frozen policies, and per-case evaluation traces are retained under each split. '
        'The original study and the final-fifty reservation are preserved.']
    (out / 'report.md').write_text('\n'.join(lines) + '\n')
    verify(out, manifest)
    print({'pooled_correct': pooled['correct'], 'previous': 17, 'direct': 18, 'new_model_calls': 0}, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--mode', choices=('prepare', 'train', 'evaluate', 'all'), default='all')
    parser.add_argument('--split', choices=('split1', 'split2', 'split3'))
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args(); out = args.output_dir.resolve(); prepare(out)
    if args.mode == 'prepare':
        print(read(out / 'protocol.json')); return
    if args.mode == 'train':
        if not args.split:
            parser.error('--mode train requires --split')
        train_split(out, args.split); return
    if args.mode == 'all':
        def work(name):
            with (out / (name + '-execution.log')).open('a') as stream:
                return subprocess.run([sys.executable, '-u', '-m', 'run.calitree_challenger_validation',
                    '--output-dir', str(out), '--mode', 'train', '--split', name], stdout=stream, stderr=subprocess.STDOUT).returncode
        with ThreadPoolExecutor(max_workers=max(1, min(3, args.workers))) as pool:
            codes = list(pool.map(work, ('split1', 'split2', 'split3')))
        if any(codes):
            raise RuntimeError('Training worker failed; inspect its retained log before continuing: ' + str(codes))
    evaluate(out)


if __name__ == '__main__':
    main()
