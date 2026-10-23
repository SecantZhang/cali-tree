"""Build explicit local semantic regions and replay the mixed judge offline."""
import argparse
from pathlib import Path

from critical.core.calibration import semantic_regions_v26 as regions
from critical.core.decision.artifacts import digest, save_json
from critical.core.optimization.prompt.calitree.bound_evidence_cache import BoundEvidenceCache, CachedEvidenceCoveredJudge
from critical.core.optimization.prompt.calitree.task_coverage import LABELS
from run.calitree_counterexample_coverage_v23 import load_examples
from run.calitree_evidence_coverage_v20 import CachedRegularCalls
from run.calitree_task_coverage import ROOT, IDENTITY, read, fingerprint


def evaluate(gate, previous_gate, data, cohorts, bound, metadata, calls, cache):
    judge = CachedEvidenceCoveredJudge(calls, gate, cache, identity=IDENTITY)
    records = []
    for scope, cohort in cohorts.items():
        for before in cohort:
            case = metadata[before['case']]; b = bound[before['case']]
            old = previous_gate.select(b['example']['program'], b['example']['features'])
            kwargs = {} if scope == 'local' else {'program': b['example']['program'], 'observation': b['observation'], 'interpretation': b['interpretation']}
            result = judge.judge(case['instruction'], case['evidence'], case_id='anonymous-region-replay', **kwargs)
            route = result['route']; label = result['judgment']['label']
            prediction = LABELS.index(label) if label in LABELS else -1
            assert not route['covered'] or (old['covered'] and route['prediction'] == old['prediction'])
            if scope == 'local':
                assert route['covered'] and prediction == before['reference'] and result['evidence_source'] == 'content_cache'
            if not old['covered']:
                assert not route['covered'] and result['execution_ref'] == before['fallback_execution_ref']
            records.append({'case': before['case'], 'scope': scope, 'batch': before['batch'], 'reference': before['reference'],
                            'before_route': old, 'route': route, 'before_prediction': before['evidence_gate_tree'],
                            'prediction': prediction, 'execution_ref': result['execution_ref'], 'source': result['source']})
    summaries = {}
    for scope in cohorts:
        selected = [r for r in records if r['scope'] == scope]
        summaries[scope] = {'total': len(selected), 'correct': sum(r['prediction'] == r['reference'] for r in selected),
                            'previous_correct': sum(r['before_prediction'] == r['reference'] for r in selected),
                            'accepted': sum(r['route']['covered'] for r in selected),
                            'previous_accepted': sum(r['before_route']['covered'] for r in selected),
                            'new_deferrals': sum(r['before_route']['covered'] and not r['route']['covered'] for r in selected),
                            'new_acceptances': sum(r['route']['covered'] and not r['before_route']['covered'] for r in selected),
                            'changed_final_predictions': sum(r['prediction'] != r['before_prediction'] for r in selected)}
    local = [r for r in records if r['scope'] == 'local']
    batches = {b: [r for r in local if r['batch'] == b] for b in sorted({r['batch'] for r in local})}
    assert all(len(part) == 12 and all(r['prediction'] == r['reference'] for r in part) for part in batches.values())
    return records, summaries


def run(out, parent):
    if out.exists():
        raise ValueError('Use a fresh output directory')
    out.mkdir(parents=True)
    seal = read(parent / 'completion_seal.json')
    for name, expected in seal['files'].items():
        assert fingerprint(parent / name) == expected
    manifest = read(parent / 'manifest.json'); previous = Path(manifest['previous_gate_run']); prior = Path(manifest['prior_directory'])
    metadata = read(prior / 'manifest.json')['cases']; calls = CachedRegularCalls(prior)
    protocol = {'version': regions.VERSION, 'parent': str(parent),
                'fit_scope': 'Only each split\'s original 48 local examples; no new verdict fitting.',
                'region': 'Exact structural task signature, original supported evidence rule, and complete terminal path.',
                'coverage': 'Task shortlist is not decision coverage. Full frozen-bank veto followed by supported semantic-region match.',
                'support': 'At least one correct local example per task/path region; inherited original evidence rule has multiple-source support. Counts are exposed, not probabilities.',
                'default_changed': False, 'new_model_calls': 0, 'reserved_final_predictions': 0}
    save_json(out / 'protocol.json', protocol); prepared = []
    for i in (1, 2, 3):
        data = read(parent / f'split{i}/training_data.json')
        old = regions.previous.restore(read(parent / f'split{i}/gate.json'))
        cohorts, bound, _, _, _ = load_examples(previous, i)
        programs = {r['source_group']: bound[r['case']]['example']['program'] for r in data}
        gate = regions.build(old, data, programs)
        save_json(out / f'split{i}/gate.json', gate.export())
        save_json(out / f'split{i}/definitions.json', [gate.definition(ref) for ref in sorted(gate.regions)])
        prepared.append((i, data, old, gate, cohorts, bound))
    summaries = []
    for i, data, old, gate, cohorts, bound in prepared:
        cache = BoundEvidenceCache(IDENTITY, artifact=read(previous / f'split{i}/evidence_cache.json'))
        records, scores = evaluate(gate, old, data, cohorts, bound, metadata, calls, cache)
        save_json(out / f'split{i}/predictions.json', records)
        summary = {'split': i, 'regions': len(gate.regions), 'task_scopes': len(gate.by_scope),
                   'experts': len({r['expert_ref'] for r in gate.regions.values()}),
                   'singleton_regions': sum(r['support']['sources'] == 1 for r in gate.regions.values()),
                   'multi_batch_regions': sum(r['support']['batches'] > 1 for r in gate.regions.values()), **scores}
        summaries.append(summary); print(summary, flush=True)
    sources = {parent / 'completion_seal.json', parent / 'manifest.json', previous / 'completion_seal.json', prior / 'manifest.json'}
    sources.update(parent / f'split{i}/{name}.json' for i in (1,2,3) for name in ('gate','training_data'))
    save_json(out / 'manifest.json', {'parent': str(parent), 'previous': str(previous), 'prior': str(prior), 'protocol_ref': digest(protocol),
              'source_hashes': {**manifest['source_hashes'], **{str(p): fingerprint(p) for p in sorted(sources)}},
              'code_hashes': {**manifest['code_hashes'], **{str(Path(p).resolve().relative_to(ROOT)): fingerprint(p) for p in (__file__, regions.__file__)}}})
    save_json(out / 'results.json', {'version': regions.VERSION, 'splits': summaries, 'new_model_calls': 0, 'reserved_final_predictions': 0, 'default_changed': False})
    (out/'run.log').write_text('\n'.join(str(s) for s in summaries)+'\n')
    (out/'llm-histories.log').write_text('Zero new calls. Original cached evidence and regular judgments replayed.\n')


def audit(out):
    manifest = read(out/'manifest.json'); protocol = read(out/'protocol.json'); results = read(out/'results.json')
    assert digest(protocol) == manifest['protocol_ref']
    for p, expected in manifest['source_hashes'].items():
        assert fingerprint(p) == expected
    for p, expected in manifest['code_hashes'].items():
        assert fingerprint(ROOT/p) == expected
    parent = Path(manifest['parent']); previous = Path(manifest['previous']); prior = Path(manifest['prior'])
    metadata = read(prior/'manifest.json')['cases']; calls = CachedRegularCalls(prior)
    total = local = deferrals = 0
    for summary in results['splits']:
        i = summary['split']; data = read(parent/f'split{i}/training_data.json')
        old = regions.previous.restore(read(parent/f'split{i}/gate.json'))
        cohorts, bound, _, _, _ = load_examples(previous, i)
        programs = {r['source_group']: bound[r['case']]['example']['program'] for r in data}
        rebuilt = regions.build(old, list(reversed(data)), programs)
        gate = regions.SemanticRegionGate(read(out/f'split{i}/gate.json'))
        assert rebuilt.export() == gate.export()
        assert read(out/f'split{i}/definitions.json') == [gate.definition(ref) for ref in sorted(gate.regions)]
        cache = BoundEvidenceCache(IDENTITY, artifact=read(previous/f'split{i}/evidence_cache.json'))
        records, scores = evaluate(gate, old, data, cohorts, bound, metadata, calls, cache)
        assert records == read(out/f'split{i}/predictions.json')
        assert all(summary[k] == v for k,v in scores.items())
        assert summary['regions'] == len(gate.regions) and summary['singleton_regions'] == sum(r['support']['sources']==1 for r in gate.regions.values())
        assert summary['task_scopes'] == len(gate.by_scope)
        assert summary['experts'] == len({r['expert_ref'] for r in gate.regions.values()})
        assert summary['multi_batch_regions'] == sum(r['support']['batches']>1 for r in gate.regions.values())
        total += len(records); local += scores['local']['correct']; deferrals += scores['outside_training_sources']['new_deferrals']
    report = {'passed': True, 'regions_refitted_from_local_only': True, 'raw_local_correct': local, 'original_batches_preserved': 12,
              'predictions_replayed': total, 'new_acceptances': 0, 'new_development_deferrals': deferrals,
              'new_model_calls': 0, 'reserved_final_predictions': 0}
    save_json(out/'verification.json', report)
    save_json(out/'completion_seal.json', {'files': {str(p.relative_to(out)): fingerprint(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'completion_seal.json'}, 'auditor_sha256': fingerprint(__file__)})
    print(report, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--parent-run', type=Path); p.add_argument('--verify', action='store_true')
    a = p.parse_args()
    if a.verify:
        audit(a.output_dir.resolve())
    elif a.parent_run is None:
        p.error('--parent-run is required when building')
    else:
        run(a.output_dir.resolve(), a.parent_run.resolve())
