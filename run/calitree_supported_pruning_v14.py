"""Matched v13 ablation: preserve supported classes during child/parent pruning.

Same six profiles, source cohorts, nested folds, grower and merge gates as v13.
Only the fixed-shape pruning algorithm changes. No evaluation/model-call mode.
"""
import argparse
import gzip
import json
from pathlib import Path
import time

from critical.core.decision.artifacts import digest
from critical.core.calibration.semantic_hierarchy import supported_pruning_v14 as supported
from run import calitree_regularized_v13 as base

ROOT = base.ROOT
PREVIOUS = ROOT / 'logs/exps/261018-regularized-child-compression-v13'
VERSION = 'nested-supported-semantic-pruning-v14'


def prepare(out):
    previous = base.read(PREVIOUS / 'manifest.json')
    for group in ('source_hashes', 'code_hashes'):
        for rel, expected in previous[group].items():
            if base.fingerprint(ROOT / rel) != expected:
                raise ValueError('The matched v13 study changed: ' + rel)
    protocol = base.read(PREVIOUS / 'protocol.json')
    protocol.update(version=VERSION, learner_version=supported.VERSION,
        matched_previous=str(PREVIOUS.relative_to(ROOT)),
        changed_component='Fixed-shape pruning retains the best error-plus-rule-cost candidate for each correctly recognized class set. Preserve every supported class when achievable. Growth, semantic alternatives, profiles, pairing, gates and nested folds unchanged.',
        infeasible_class_coverage='Explicit pruning report and unchanged class-collapse rejection; no forced labels or guard relaxation.')
    code = dict(previous['code_hashes'])
    for p in (Path(__file__).resolve(), Path(supported.__file__).resolve()):
        code[str(p.relative_to(ROOT))] = base.fingerprint(p)
    manifest = {'protocol_ref': digest(protocol), 'source_hashes': previous['source_hashes'], 'code_hashes': code}
    manifest['artifact_ref'] = digest(manifest)
    base.exact(out / 'protocol.json', protocol); base.exact(out / 'manifest.json', manifest)
    for rel in code:
        path = out / 'source_snapshot' / rel
        if path.exists():
            if base.fingerprint(path) != code[rel]:
                raise ValueError('Changed source snapshot: ' + rel)
        else:
            path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes((ROOT / rel).read_bytes())
    for i in (1, 2, 3):
        base.exact(out / f'split{i}/training_data.json', base.read(PREVIOUS / f'split{i}/training_data.json'))
    return manifest


class Runs(base.Runs):
    def fit(self, rows, profile, mode):
        rows = sorted(rows, key=lambda r: r['source_group'])
        key = digest([self.manifest['artifact_ref'], rows, profile, mode])
        if key in self.memory:
            return self.memory[key]
        path = self.directory / (key + '.json.gz')
        if path.exists():
            value = json.loads(gzip.decompress(path.read_bytes()))
            if value['content_ref'] != digest({k: v for k, v in value.items() if k != 'content_ref'}):
                raise ValueError('Changed v14 cache')
        else:
            if self.total >= 1000:
                raise RuntimeError('Declared procedure-fit budget exhausted')
            start = time.monotonic()
            result = supported.learn(rows, base.PROFILES[profile], mode=mode, fits=supported.SupportedFits(128))
            value = {'fit_ref': key, 'source_groups': [r['source_group'] for r in rows], 'rows_ref': digest(rows),
                'profile': profile, 'mode': mode, 'result': result, 'elapsed_seconds': time.monotonic() - start}
            value['content_ref'] = digest(value)
            data = gzip.compress(json.dumps(value, sort_keys=True).encode(), mtime=0)
            temporary = path.with_suffix('.tmp'); temporary.write_bytes(data); temporary.replace(path)
            self.total += 1
        if value['fit_ref'] != key or value['rows_ref'] != digest(rows) or value['profile'] != profile or value['mode'] != mode:
            raise ValueError('Changed cached procedure inputs')
        compact = {**value, 'result': {k: v for k, v in value['result'].items() if k not in ('nodes', 'proposals')}}
        self.memory[key] = compact
        return compact


def train(out):
    manifest = prepare(out); runs = Runs(out, manifest); reports = []; pooled = {m: [] for m in base.MODES}
    for i in (1, 2, 3):
        name = f'split{i}'; directory = out / name; rows = base.read(directory / 'training_data.json')
        plan = base.outer_folds(rows); scores = {m: [] for m in base.MODES}
        for fold in plan:
            for mode in base.MODES:
                d = directory / f'outer/{fold["fold"]}/{mode}'
                chosen, selection = base.select(runs, base.inner_folds(fold['train']), mode)
                base.exact(d / 'selection.json', {'selected': chosen, 'candidates': selection})
                measured = base.score(runs.fit(fold['train'], chosen, mode), fold['validation'])
                base.exact(d / 'score.json', measured); scores[mode].append(measured)
            print({'split': name, 'fold': fold['fold'], 'correct': {m: scores[m][-1]['metrics']['correct'] for m in base.MODES}}, flush=True)
        selected = {}
        for mode in base.MODES:
            chosen, selection = base.select(runs, plan, mode)
            base.exact(directory / mode / 'selection.json', {'selected': chosen, 'candidates': selection})
            value = runs.fit(rows, chosen, mode); root = value['result']['root']; runtime = root['runtime'] if root else None
            base.exact(directory / mode / 'policy.json', runtime)
            freeze = {'profile': chosen, 'fit_ref': value['fit_ref'], 'training_ref': digest(rows),
                'selection_ref': digest(selection), 'runtime_ref': digest(runtime), 'complete': root is not None,
                'training_metrics': root['metrics'] if root else None, 'complexity': root['complexity'] if root else None,
                'work': value['result']['work']}
            base.exact(directory / mode / 'freeze.json', freeze); selected[mode] = freeze
            pooled[mode].extend(scores[mode])
        report = {'split': name, 'nested': {m: base.summarize(scores[m]) for m in base.MODES}, 'selected': selected}
        base.exact(directory / 'results.json', report); reports.append(report)
    results = {'version': VERSION, 'splits': reports, 'pooled_nested': {m: base.summarize(v) for m, v in pooled.items()},
        'procedure_fits': runs.total, 'new_model_calls': 0, 'historical_evaluation_predictions': 0,
        'reserved_test_predictions': 0, 'caveat': 'Exploratory nested training validation. Overlapping training cohorts; pooled slots are correlated.'}
    base.exact(out / 'results.json', results)
    lines = ['# V14 supported-class child and parent pruning', '',
        'Matched v13 ablation: same six profiles, nested source folds, grower, pairing, compression and regularized gates. '
        'Pruning now retains a frontier by correctly recognized class set. No evaluation or model calls.', '',
        '| Split | Nested direct | Nested merged | Merged feasible folds | Full direct rules | Full merged rules |',
        '|---|---:|---:|---:|---:|---:|']
    for r in reports:
        d, m = (r['nested'][k] for k in base.MODES)
        lines.append(f"| {r['split']} | {d['metrics']['correct']}/48 | {m['metrics']['correct']}/48 | {m['feasible_folds']}/4 | "
            f"{(r['selected']['direct']['complexity'] or {}).get('rules', 'No root')} | {(r['selected']['merge']['complexity'] or {}).get('rules', 'No root')} |")
    lines += ['', 'The legacy >90% training gate remains diagnostic. The explicitly declared experimental parent gate '
        'requires >=20% rule reduction, no complexity-adjusted loss regression, support, scope, class-coverage and written '
        'consistency checks. This is not a silent relaxation of the frozen v12 experiment. '
        'Selection and every upstream fitting stage are rebuilt inside each fold. No missing root is replaced by direct fitting.', '',
        'Full policies are frozen development candidates. Historical 36-case evaluation and reserved fifty remain unread by this runner. '
        'Do not treat source-overlapping pooled validation slots as independent observations.']
    (out / 'report.md').write_text('\n'.join(lines) + '\n')
    prepare(out); print(results['pooled_nested'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args(); out = args.output_dir.resolve()
    if args.preflight:
        print(prepare(out))
    else:
        train(out)
