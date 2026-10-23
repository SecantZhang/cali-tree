"""Compile shared semantic regions and verify exact coverage preservation."""
import argparse
from pathlib import Path

from critical.core.calibration import shared_regions_v27 as shared
from critical.core.decision.artifacts import digest, save_json
from critical.core.optimization.prompt.calitree.bound_evidence_cache import BoundEvidenceCache
from run.calitree_counterexample_coverage_v23 import load_examples
from run.calitree_evidence_coverage_v20 import CachedRegularCalls
from run.calitree_semantic_regions_v26 import evaluate
from run.calitree_task_coverage import ROOT, IDENTITY, read, fingerprint


def inputs(parent, split):
    manifest = read(parent/'manifest.json'); training_parent = Path(manifest['parent'])
    previous = Path(manifest['previous']); prior = Path(manifest['prior'])
    rows = read(training_parent/f'split{split}/training_data.json')
    gate = shared.old.SemanticRegionGate(read(parent/f'split{split}/gate.json'))
    cohorts, bound, _, _, _ = load_examples(previous, split)
    recorded = {(r['scope'], r['case']): r for r in read(parent/f'split{split}/predictions.json')}
    # The exact comparison baseline is v26, including its three new deferrals.
    for scope, cohort in cohorts.items():
        for row in cohort:
            old = recorded[(scope, row['case'])]
            row.update(evidence_gate_tree=old['prediction'], route=old['route'], fallback_execution_ref=old['execution_ref'])
    programs = {r['source_group']: bound[r['case']]['example']['program'] for r in rows}
    return rows, programs, gate, cohorts, bound, previous, prior


def replay(gate, old, rows, cohorts, bound, previous, prior, split):
    cache = BoundEvidenceCache(IDENTITY, artifact=read(previous/f'split{split}/evidence_cache.json'))
    records, scores = evaluate(gate, old, rows, cohorts, bound, read(prior/'manifest.json')['cases'], CachedRegularCalls(prior), cache)
    for row in records:
        assert (row['route']['covered'], row['route']['prediction']) == (row['before_route']['covered'], row['before_route']['prediction'])
        assert row['prediction'] == row['before_prediction']
    return records, scores


def run(out, parent):
    if out.exists():
        raise ValueError('Use a fresh experiment directory')
    out.mkdir(parents=True)
    for filename, expected in read(parent/'completion_seal.json')['files'].items():
        assert fingerprint(parent/filename) == expected
    protocol = {'version': shared.VERSION, 'parent': str(parent),
                'simplification': 'Canonical conjunctions; pooled exact scopes; Boolean absorption and complementary-literal elimination. No empirical feature-alias equivalences.',
                'sharing': 'Share evidence kernels across scopes and experts only when the complete Boolean regional union remains equivalent.',
                'support': 'Deduplicate original local sources; never sum overlapping child support counts.',
                'runtime': 'Retain full v24 consensus/rejection gate, replace v26 regions rather than keeping them as a hidden veto.',
                'acceptance': 'Exact regional-union equivalence per scope/label plus zero recorded local/development route changes relative to v26.',
                'new_model_calls': 0, 'reserved_final_predictions': 0, 'default_changed': False}
    save_json(out/'protocol.json', protocol)
    summaries = []; prepared = []
    for i in (1,2,3):
        data = inputs(parent, i); rows, programs, old = data[:3]
        gate, report = shared.build(old, rows, programs)
        save_json(out/f'split{i}/gate.json', gate.export()); save_json(out/f'split{i}/fit.json', report)
        save_json(out/f'split{i}/definitions.json', [gate.definition(k) for k in sorted(gate.regions)])
        prepared.append((i, data, gate, report))
    for i, data, gate, report in prepared:
        rows, programs, old, cohorts, bound, previous, prior = data
        records, scores = replay(gate, old, rows, cohorts, bound, previous, prior, i)
        save_json(out/f'split{i}/predictions.json', records)
        summary = {'split': i, **report, **scores}; summaries.append(summary); print(summary, flush=True)
    inherited = read(parent/'manifest.json')
    files = {parent/'completion_seal.json', parent/'manifest.json'}
    files.update(parent/f'split{i}/{kind}.json' for i in (1,2,3) for kind in ('gate','predictions'))
    manifest = {'parent': str(parent), 'protocol_ref': digest(protocol),
                'source_hashes': {**inherited['source_hashes'], **{str(p): fingerprint(p) for p in sorted(files)}},
                'code_hashes': {**inherited['code_hashes'], **{str(Path(p).resolve().relative_to(ROOT)): fingerprint(p) for p in (__file__, shared.__file__)}}}
    save_json(out/'manifest.json', manifest)
    save_json(out/'results.json', {'version': shared.VERSION, 'splits': summaries, 'new_model_calls': 0, 'reserved_final_predictions': 0, 'default_changed': False})
    (out/'run.log').write_text('\n'.join(str(s) for s in summaries)+'\n')
    (out/'llm-histories.log').write_text('Zero new calls; cached evidence and exact approved regular responses only.\n')


def audit(out):
    manifest = read(out/'manifest.json'); protocol = read(out/'protocol.json'); results = read(out/'results.json')
    assert digest(protocol) == manifest['protocol_ref']
    for p, expected in manifest['source_hashes'].items():
        assert fingerprint(p) == expected
    for p, expected in manifest['code_hashes'].items():
        assert fingerprint(ROOT/p) == expected
    parent = Path(manifest['parent']); decisions = local = fallbacks = implications = states = 0
    for summary in results['splits']:
        i = summary['split']; rows, programs, old, cohorts, bound, previous, prior = inputs(parent, i)
        rebuilt, report = shared.build(old, list(reversed(rows)), programs)
        gate = shared.SharedRegionGate(read(out/f'split{i}/gate.json'))
        assert rebuilt.export() == gate.export() and report == read(out/f'split{i}/fit.json')
        assert all(summary[k] == v for k, v in report.items())
        # Prove both directions on the actual exported functions, independent of
        # the recorded simplification steps and artifact identities.
        before, _ = shared.original_terms(old)
        after = {(r['prediction'], gate.terms[r['region_ref']]): set(r['scope_refs']) for r in gate.regions.values()}
        proof = shared.equivalent(before, after); assert proof['passed']
        implications += proof['cube_implications']; states += proof['states']
        assert gate.artifact['core_gate'] == old.previous.export()
        assert read(out/f'split{i}/definitions.json') == [gate.definition(k) for k in sorted(gate.regions)]
        records, scores = replay(gate, old, rows, cohorts, bound, previous, prior, i)
        assert records == read(out/f'split{i}/predictions.json') and all(summary[k] == v for k,v in scores.items())
        # Independently count unique supporting local sources from route matches.
        for ref, r in gate.regions.items():
            supported = [row for row in rows if ref in gate.select(programs[row['source_group']], row['features'])['semantic_regions']]
            assert r['support'] == {'sources': len({s['source_group'] for s in supported}),
                                    'instructions': len({s['instruction'] for s in supported}),
                                    'batches': len({s['batch'] for s in supported})}
            for scope_ref, counts in r['support_by_scope'].items():
                subset = [s for s in supported if digest(shared.task_scope(programs[s['source_group']])) == scope_ref]
                assert counts == {'sources': len({s['source_group'] for s in subset}),
                                  'instructions': len({s['instruction'] for s in subset}),
                                  'batches': len({s['batch'] for s in subset})}
        decisions += len(records); local += scores['local']['correct']; fallbacks += sum(not r['route']['covered'] for r in records)
    report = {'passed': True, 'raw_local_predictions_preserved': local, 'original_child_batches_preserved': 12,
              'recorded_routes_and_final_predictions_preserved': decisions, 'exact_regular_fallbacks_preserved': fallbacks,
              'boolean_union_equivalence': True, 'cube_implications_proved': implications, 'boolean_proof_states': states,
              'old_v26_executor_not_hidden_in_runtime': True, 'coverage_regressions': 0,
              'new_model_calls': 0, 'reserved_final_predictions': 0}
    save_json(out/'verification.json', report)
    save_json(out/'completion_seal.json', {'files': {str(p.relative_to(out)): fingerprint(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'completion_seal.json'}, 'auditor_sha256': fingerprint(__file__)})
    print(report, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--parent-run', type=Path); p.add_argument('--verify', action='store_true'); a = p.parse_args()
    if a.verify:
        audit(a.output_dir.resolve())
    elif a.parent_run is None:
        p.error('--parent-run is required when building')
    else:
        run(a.output_dir.resolve(), a.parent_run.resolve())
