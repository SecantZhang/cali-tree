"""Offline nested validation of bounded child optimization and compression.

Reads only the three existing 48-source TRAINING files. No collection, historical
36-case evaluation, or reserved-fifty evaluation entry point exists. Selection
rebuilds the complete procedure inside each fold. Failed roots remain Unresolved.
"""
import argparse
from collections import defaultdict
from dataclasses import asdict
import gzip
from hashlib import sha256
import json
from pathlib import Path
import statistics
import time

from critical.core.decision.artifacts import digest, save_json
from critical.core.calibration.semantic_hierarchy import regularized_tree_v13 as learner
from critical.core.calibration.semantic_hierarchy.union_validation_v12 import folds as outer_folds

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'logs/exps/261018-union-challenger-validation-v12'
VERSION = 'nested-regularized-semantic-compression-v13'
PROFILES = {
    f'{name}_{quantifier}': learner.Config(max_depth=depth, min_sources=support, leaf_penalty=penalty,
        quantifier=quantifier, gate_mode='regularized')
    for name, depth, support, penalty in (('shallow', 2, 3, 1), ('compact', 3, 2, 1), ('flexible', 4, 2, 1))
    for quantifier in ('all', 'any')
}
MODES = ('direct', 'merge')


def read(path):
    return json.loads(Path(path).read_text())


def fingerprint(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def exact(path, value):
    value = json.loads(json.dumps(value))
    if path.exists():
        if read(path) != value:
            raise ValueError('Frozen v13 artifact changed: ' + str(path))
    else:
        save_json(path, value)


def prepare(out):
    sources = [SOURCE / f'split{i}/training_data.json' for i in (1, 2, 3)]
    code = [Path(__file__).resolve(), ROOT / 'critical/core/decision/artifacts.py']
    code += sorted((ROOT / 'critical/core/calibration/semantic_hierarchy').glob('*.py'))
    protocol = {'version': VERSION, 'learner_version': learner.VERSION,
        'profiles': {k: asdict(v) for k, v in PROFILES.items()}, 'modes': list(MODES),
        'data_scope': 'Existing training sources only. Historical evaluation and reserved fifty are not read.',
        'outer_folds': 4, 'inner_folds': 3, 'seed': 20261018,
        'selection': 'Pooled inner macro-F1, worst-class recall, lower fold dispersion, fewer mean rules, stable profile identity.',
        'parent_gate': 'Experimental regularized-error budget and >=20% rule compression; original support, class-collapse, scope and written-contradiction checks remain. Legacy >90% and per-child retention outcomes are recorded separately, not claimed passed.',
        'seed_optimizer': 'Same semantic vocabulary and quantifier preference; depth six, minimum two distinct sources/instructions, no leaf penalty.',
        'search': 'Six seed-pair proposals; two distinct policies retained per union; at most twelve root-pair proposals; no direct fallback.',
        'budgets': {'max_procedure_fits': 1000, 'max_tree_fits_per_procedure': 128},
        'missing_root': 'Every held source is Unresolved; no omitted fold or substitution.',
        'interpretation': 'Exploratory nested training validation after earlier inspection of these training cohorts. Correlated training samples; not a confirmatory test or production promotion.',
        'new_model_calls': 0, 'reserved_test_predictions': 0}
    manifest = {'protocol_ref': digest(protocol),
        'source_hashes': {str(p.relative_to(ROOT)): fingerprint(p) for p in sources},
        'code_hashes': {str(p.relative_to(ROOT)): fingerprint(p) for p in code}}
    manifest['artifact_ref'] = digest(manifest)
    exact(out / 'protocol.json', protocol); exact(out / 'manifest.json', manifest)
    for p in sources:
        exact(out / p.parent.name / 'training_data.json', read(p))
    return manifest


def inner_folds(rows):
    buckets = defaultdict(list)
    for row in rows:
        buckets[(row['batch'], row['reference'])].append(row)
    if len(rows) != 36 or len(buckets) != 12 or any(len(v) != 3 for v in buckets.values()):
        raise ValueError('Inner validation requires the declared 36-source training fold')
    held = [[] for _ in range(3)]
    for key, values in sorted(buckets.items()):
        for i, row in enumerate(sorted(values, key=lambda r: digest([VERSION, key, r['source_group']]))):
            held[i].append(row)
    result = []
    for i, selected in enumerate(held):
        sources = {r['source_group'] for r in selected}
        result.append({'fold': i, 'train': [r for r in rows if r['source_group'] not in sources], 'validation': selected})
    return result


class Runs:
    def __init__(self, out, manifest):
        self.out, self.manifest = out, manifest
        self.memory = {}
        self.directory = out / 'procedure_cache'
        self.directory.mkdir(parents=True, exist_ok=True)
        self.total = len(list(self.directory.glob('*.json.gz')))

    def fit(self, rows, profile, mode):
        rows = sorted(rows, key=lambda r: r['source_group'])
        key = digest([self.manifest['artifact_ref'], rows, profile, mode])
        if key in self.memory:
            return self.memory[key]
        path = self.directory / (key + '.json.gz')
        if path.exists():
            value = json.loads(gzip.decompress(path.read_bytes()))
            if value['content_ref'] != digest({k: v for k, v in value.items() if k != 'content_ref'}):
                raise ValueError('Changed cached procedure')
        else:
            if self.total >= 1000:
                raise RuntimeError('Declared procedure-fit budget exhausted')
            start = time.monotonic()
            fits = learner.TreeFits(max_fits=128)
            # Do not mask programming/integrity errors as infeasible folds.
            result = learner.learn(rows, PROFILES[profile], mode=mode, fits=fits)
            value = {'fit_ref': key, 'source_groups': [r['source_group'] for r in rows],
                'rows_ref': digest(rows), 'profile': profile, 'mode': mode, 'result': result,
                'elapsed_seconds': time.monotonic() - start}
            value['content_ref'] = digest(value)
            data = gzip.compress(json.dumps(value, sort_keys=True).encode(), mtime=0)
            temporary = path.with_suffix('.tmp'); temporary.write_bytes(data); temporary.replace(path)
            self.total += 1
        if (value['fit_ref'] != key or value['rows_ref'] != digest(rows)
                or value['profile'] != profile or value['mode'] != mode):
            raise ValueError('Procedure cache input mismatch')
        # Cache only metadata/root in memory; full lineages remain on disk.
        compact = {**value, 'result': {k: v for k, v in value['result'].items() if k not in ('nodes', 'proposals')}}
        self.memory[key] = compact
        return compact


def score(value, rows):
    if set(value['source_groups']) & {r['source_group'] for r in rows}:
        raise ValueError('Validation overlaps procedure fitting sources')
    root = value['result']['root']
    ps = learner.predict(root, rows) if root else [{'prediction': -1, 'reason': 'no_qualifying_root', 'trace': []} for _ in rows]
    return {'fit_ref': value['fit_ref'], 'available': root is not None,
        'rules': root['complexity']['rules'] if root else None,
        'training_sources': value['source_groups'], 'validation_sources': [r['source_group'] for r in rows],
        'cases': [{'source_group': r['source_group'], 'reference': r['reference'], **p} for r, p in zip(rows, ps)],
        'metrics': learner.metrics([p['prediction'] for p in ps], [r['reference'] for r in rows])}


def summarize(scores):
    cases = [r for s in scores for r in s['cases']]
    return {'metrics': learner.metrics([r['prediction'] for r in cases], [r['reference'] for r in cases]),
        'feasible_folds': sum(s['available'] for s in scores), 'folds': len(scores),
        'macro_f1_std': statistics.pstdev(s['metrics']['macro_f1'] for s in scores),
        'mean_rules': statistics.mean(s['rules'] for s in scores if s['rules'] is not None) if any(s['available'] for s in scores) else None}


def selection_key(summary, profile):
    m = summary['metrics']
    return (-m['macro_f1'], -m['worst_present_class_recall'], summary['macro_f1_std'],
            summary['mean_rules'] if summary['mean_rules'] is not None else float('inf'), profile)


def select(runs, plan, mode):
    values = {}
    for profile in PROFILES:
        scores = [score(runs.fit(f['train'], profile, mode), f['validation']) for f in plan]
        values[profile] = {'scores': scores, 'summary': summarize(scores)}
    chosen = min(values, key=lambda p: selection_key(values[p]['summary'], p))
    return chosen, values


def train(out):
    manifest = prepare(out); runs = Runs(out, manifest); reports = []
    for i in (1, 2, 3):
        name = f'split{i}'; directory = out / name; rows = read(directory / 'training_data.json')
        plan = outer_folds(rows); scores = {mode: [] for mode in MODES}
        for fold in plan:
            for mode in MODES:
                folder = directory / 'outer' / str(fold['fold']) / mode
                chosen, selection = select(runs, inner_folds(fold['train']), mode)
                exact(folder / 'selection.json', {'selected': chosen, 'candidates': selection})
                value = runs.fit(fold['train'], chosen, mode)
                measured = score(value, fold['validation'])
                exact(folder / 'score.json', measured); scores[mode].append(measured)
            print({'split': name, 'outer_fold': fold['fold'],
                   'correct': {m: scores[m][-1]['metrics']['correct'] for m in MODES}}, flush=True)
        selected = {}
        for mode in MODES:
            chosen, selection = select(runs, plan, mode)
            exact(directory / mode / 'selection.json', {'selected': chosen, 'candidates': selection})
            value = runs.fit(rows, chosen, mode); root = value['result']['root']
            runtime = root['runtime'] if root else None
            exact(directory / mode / 'policy.json', runtime)
            freeze = {'profile': chosen, 'fit_ref': value['fit_ref'], 'training_ref': digest(rows),
                'selection_ref': digest(selection), 'runtime_ref': digest(runtime),
                'complete': root is not None, 'training_metrics': root['metrics'] if root else None,
                'complexity': root['complexity'] if root else None, 'work': value['result']['work']}
            exact(directory / mode / 'freeze.json', freeze)
            selected[mode] = freeze
        report = {'split': name, 'nested': {m: summarize(scores[m]) for m in MODES}, 'selected': selected}
        exact(directory / 'results.json', report); reports.append(report)
    all_scores = {m: [read(out / f'split{i}/outer/{j}/{m}/score.json') for i in (1, 2, 3) for j in range(4)] for m in MODES}
    results = {'version': VERSION, 'splits': reports, 'pooled_nested': {m: summarize(v) for m, v in all_scores.items()},
        'procedure_fits': runs.total, 'new_model_calls': 0, 'historical_evaluation_predictions': 0,
        'reserved_test_predictions': 0, 'caveat': 'Training cohorts overlap; pooled slots are not 144 independent sources. Nested scores are exploratory.'}
    exact(out / 'results.json', results)
    lines = ['# V13 regularized child and parent learning', '',
        'Training-only nested validation. No historical 36-case or reserved-fifty predictions. '
        'This opt-in experiment replaces the parent training-accuracy floor and fixed child error allowance '
        'with a declared error-plus-rule-cost budget. Original gate outcomes are retained per proposal. '
        'Every accepted parent must reduce the combined child rule count by at least 20%.', '',
        '| Split | Nested direct | Nested merged | Merged feasible folds | Full direct rules | Full merged rules |',
        '|---|---:|---:|---:|---:|---:|']
    for r in reports:
        d, m = (r['nested'][k] for k in MODES)
        lines.append(f"| {r['split']} | {d['metrics']['correct']}/48 | {m['metrics']['correct']}/48 | {m['feasible_folds']}/4 | "
            f"{(r['selected']['direct']['complexity'] or {}).get('rules', 'No root')} | {(r['selected']['merge']['complexity'] or {}).get('rules', 'No root')} |")
    lines += ['', 'Selection uses inner folds. Each outer score comes from a complete procedure with grouping, '
        'child fitting, predicate alternatives, pruning and parent selection rebuilt without that outer fold. '
        'No unavailable hierarchy is replaced by the direct control. Six candidate profiles receive the same '
        'selection treatment in both arms. Full-48 policies are development candidates, not promoted deployments.', '',
        'Cached procedure files retain original targets via their source references, full training lineages, '
        'predicate alternatives, measured work, all proposal gates and every rejected candidate. '
        'Source and code identities are sealed in manifest.json.']
    (out / 'report.md').write_text('\n'.join(lines) + '\n')
    prepare(out)
    print(results['pooled_nested'], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args(); out = args.output_dir.resolve()
    if args.preflight:
        print(prepare(out))
    else:
        train(out)


if __name__ == '__main__':
    main()
