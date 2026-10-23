"""Offline pairwise merges with recomputed coverage and frozen route regressions."""
import argparse
from pathlib import Path

from critical.core.calibration import pairwise_merge_v24 as merging
from critical.core.calibration.counterexample_coverage_v23 import RejectionCoverageGate
from critical.core.decision.artifacts import digest, save_json
from critical.core.optimization.prompt.calitree.bound_evidence_cache import BoundEvidenceCache, CachedEvidenceCoveredJudge
from critical.core.optimization.prompt.calitree.task_coverage import LABELS
from run.calitree_counterexample_coverage_v23 import load_examples
from run.calitree_evidence_coverage_v20 import CachedRegularCalls, scores
from run.calitree_task_coverage import ROOT, IDENTITY, read, fingerprint


def run(out, previous, *, split=None, max_rounds=3, max_states=80000):
    if out.exists() and any(out.iterdir()):
        raise ValueError('Use a fresh experiment directory')
    out.mkdir(parents=True, exist_ok=True)
    prior_manifest = read(previous / 'manifest.json')
    for name, expected in read(previous / 'completion_seal.json')['files'].items():
        assert fingerprint(previous / name) == expected, name
    root = Path(prior_manifest['source_root']); prior = Path(prior_manifest['prior_directory'])
    metadata = read(prior / 'manifest.json')['cases']; calls = CachedRegularCalls(prior)
    config = merging.Config(max_rounds=max_rounds); fit_config = merging.learner.Config(max_states=max_states)
    indices = (split,) if split is not None else (1, 2, 3)
    protocol = {'version': merging.VERSION, 'merge_config': merging.asdict(config), 'fit_config': merging.asdict(fit_config),
                'scope': 'Pairwise research development on frozen cached training and reviewed regression cases; no fresh validation claim.',
                'fit_targets': 'Original references on the exact deduplicated child union only.',
                'local_guards': 'Preserve each immediate child, every original batch within each child, and inherited retention scopes.',
                'sharing': 'Correctly served sources from at least two original batches in one terminal rule; prefer after accuracy and compactness.',
                'coverage': 'Rebuild support on local training rows, retain fixed v23 clauses, and distill prior abstentions with short observable support clauses. Never restore removed children behind the gate.',
                'routing': 'Preserve every frozen accepted/deferred decision and each accepted verdict on all 98 local/development probes per split.',
                'selection': 'Among passing proposals prefer fewer deployed experts, fewer terminal rules, correctly shared support, balanced batch support, then fewer stored test occurrences.',
                'new_model_calls': 0, 'reserved_final_predictions': 0}
    save_json(out / 'protocol.json', protocol)
    results = []; all_rows = []; source_files = {previous / 'manifest.json', previous / 'completion_seal.json'}
    for i in indices:
        original_dir = root / f'logs/exps/261018-local-compression-v18-r1/split{i}'
        data = read(original_dir / 'training_data.json'); original = read(original_dir / 'result.json')
        source_files.update((original_dir / 'training_data.json', original_dir / 'result.json'))
        gate_path = previous / f'split{i}/gate.json'; source_files.add(gate_path)
        frozen = RejectionCoverageGate(read(gate_path)); models = []
        for ref in merging.expert_artifacts(frozen):
            matches = [m for m in original['registry'].values() if m['runtime']['artifact_ref'] == ref]
            if len(matches) != 1:
                raise ValueError('Starting expert needs unambiguous training-scope provenance')
            models.append(matches[0])
        cohorts, bound, _, _, files = load_examples(previous, i); source_files.update(files)
        programs = {r['source_group']: bound[r['case']]['example']['program'] for r in data}
        probes = [bound[r['case']]['example'] for scope in ('local', 'outside_training_sources') for r in cohorts[scope]]
        folder = out / f'split{i}'
        save_json(folder / 'baseline_gate.json', frozen.export()); save_json(folder / 'baseline_models.json', models)
        save_json(folder / 'training_data.json', data)
        def emit(kind, value):
            compact = {k: v for k, v in value.items() if k != 'fits'}
            record = {'split': i, 'event': kind, **compact}
            print(record, flush=True)
            with (out / 'run.log').open('a') as stream:
                stream.write(str(record) + '\n')
        result = merging.develop(models, data, programs, frozen, probes, config=config, fit_config=fit_config, emit=emit)
        save_json(folder / 'development.json', result); save_json(folder / 'gate.json', result['gate'])
        gate = merging.route_support.restore(result['gate'])
        cache_path = previous / f'split{i}/evidence_cache.json'; source_files.add(cache_path)
        cache = BoundEvidenceCache(IDENTITY, artifact=read(cache_path))
        judge = CachedEvidenceCoveredJudge(calls, gate, cache, identity=IDENTITY)
        comparisons = {}
        for scope, old_rows in cohorts.items():
            measured = []
            for before in old_rows:
                c = metadata[before['case']]; b = bound[before['case']]
                kwargs = {} if scope == 'local' else {'program': b['example']['program'], 'observation': b['observation'], 'interpretation': b['interpretation']}
                value = judge.judge(c['instruction'], c['evidence'], case_id='pairwise-replay-' + c['case'], **kwargs)
                prediction = LABELS.index(value['judgment']['label']) if value['judgment']['label'] in LABELS else -1
                assert value['route']['covered'] == before['route']['covered'] and prediction == before['evidence_gate_tree']
                if scope == 'local':
                    assert value['source'] == 'frozen_tree' and prediction == before['reference']
                    assert value['evidence_source'] == 'content_cache'
                elif not value['route']['covered']:
                    assert value['execution_ref'] == before['fallback_execution_ref']
                measured.append({**before, 'baseline_route': before['route'], 'route': value['route'],
                                 'evidence_gate_tree': prediction, 'served_by': value['source'],
                                 'fallback_execution_ref': value['execution_ref'], 'extraction_error': value['extraction_error']})
            save_json(folder / (scope + '_predictions.json'), measured); comparisons[scope] = scores(measured); all_rows.extend(measured)
        results.append({'split': i, 'accepted_merges': len(result['accepted']),
                        'before': result['initial_complexity'], 'after': result['final_complexity'],
                        'work': result['work'], 'comparisons': comparisons,
                        'accepted_shared_correct': [r['sharing']['shared_correct'] for r in result['accepted']],
                        'routing_regressions': len(result['final_routing_check']['failures'])})
    code = [Path(__file__).resolve(), Path(merging.__file__).resolve(), Path(merging.learner.__file__).resolve(), Path(merging.route_support.__file__).resolve()]
    manifest = {**prior_manifest, 'previous_gate_run': str(previous), 'protocol_ref': digest(protocol),
                'source_hashes': {**prior_manifest['source_hashes'], **{str(p): fingerprint(p) for p in sorted(source_files)}},
                'code_hashes': {**prior_manifest['code_hashes'], **{str(p.relative_to(ROOT)): fingerprint(p) for p in code}}}
    summary = {'version': merging.VERSION, 'splits': results, 'local': scores([r for r in all_rows if r['scope'] == 'local']),
               'development': scores([r for r in all_rows if r['scope'] != 'local']),
               'new_model_calls': 0, 'reserved_final_predictions': 0, 'deployed_by_default': False}
    save_json(out / 'manifest.json', manifest); save_json(out / 'results.json', summary)
    (out / 'llm-histories.log').write_text('Zero new calls. Cached bound evidence and exact approved regular responses replayed.\n')
    print(summary, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True); p.add_argument('--previous-run', type=Path, required=True)
    p.add_argument('--split', type=int, choices=(1, 2, 3)); p.add_argument('--max-rounds', type=int, default=3)
    p.add_argument('--max-states', type=int, default=80000)
    a = p.parse_args(); run(a.output_dir.resolve(), a.previous_run.resolve(), split=a.split, max_rounds=a.max_rounds, max_states=a.max_states)
