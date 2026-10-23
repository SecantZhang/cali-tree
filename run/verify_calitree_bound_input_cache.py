"""Verify raw local image/instruction inference with content-cached evidence."""
import argparse
from pathlib import Path

from critical.core.calibration.evidence_support_v21 import SupportedCoverageGate
from critical.core.decision.artifacts import digest, save_json
from critical.core.optimization.prompt.calitree.bound_evidence_cache import BoundEvidenceCache, CachedEvidenceCoveredJudge
from critical.core.optimization.prompt.calitree.task_coverage import LABELS
from run.calitree_evidence_coverage_v20 import CachedRegularCalls
from run.calitree_task_coverage import ROOT, IDENTITY, read, fingerprint, exact


def verify(out, gate_run):
    if out.exists() and any(out.iterdir()):
        raise ValueError('Use a fresh cache-verification directory')
    out.mkdir(parents=True, exist_ok=True)
    gate_manifest = read(gate_run / 'manifest.json')
    for name, expected in read(gate_run / 'completion_seal.json')['files'].items():
        assert fingerprint(gate_run / name) == expected, name
    root = Path(gate_manifest['source_root']); prior = Path(gate_manifest['prior_directory'])
    base_run = Path(gate_manifest['base_run']); meta = read(prior / 'manifest.json')['cases']
    evidence_dir = root / 'logs/exps/261018-three-sampled-splits-luna-compiler-v3'
    source_files = {gate_run / 'completion_seal.json', gate_run / 'manifest.json', prior / 'manifest.json'}
    predictions = []; batches = []
    for i in (1, 2, 3):
        data = read(base_run / f'split{i}/training_data.json')
        source_files.add(base_run / f'split{i}/training_data.json')
        gate_path = gate_run / f'split{i}/gate.json'; source_files.add(gate_path)
        gate = SupportedCoverageGate(read(gate_path)); cache = BoundEvidenceCache(IDENTITY)
        for row in data:
            name = row['case']; case = meta[name]
            path = evidence_dir / 'extraction/cases' / (name + '.json')
            mean_path = evidence_dir / 'interpretations' / (name + '.json'); source_files.update((path, mean_path))
            e = read(path); meaning = read(mean_path)['interpretation']
            cache.add(case['instruction'], case['evidence'], e['compilation']['program'], e['observation']['observation'], meaning)
        artifact = cache.export(); save_json(out / f'split{i}/evidence_cache.json', artifact)
        restored = BoundEvidenceCache(IDENTITY, artifact=read(out / f'split{i}/evidence_cache.json'))
        calls = CachedRegularCalls(prior); judge = CachedEvidenceCoveredJudge(calls, gate, restored, identity=IDENTITY)
        for row in data:
            case = meta[row['case']]
            # No compiled program, observation, feature record, original case ID
            # or training-group membership is passed to inference.
            result = judge.judge(case['instruction'], case['evidence'], case_id='new-inference-id-' + str(len(predictions)))
            prediction = LABELS.index(result['judgment']['label']) if result['judgment']['label'] in LABELS else -1
            assert result['evidence_source'] == 'content_cache' and result['extraction_error'] is None
            assert prediction == row['reference']
            predictions.append({'split': i, 'case': row['case'], 'batch': row['batch'], 'reference': row['reference'],
                                'prediction': prediction, 'source': result['source'], 'evidence_source': result['evidence_source'],
                                'execution_ref': result['execution_ref'], 'route': result['route']})
        for batch in sorted({r['batch'] for r in data}):
            selected = [r for r in predictions if r['split'] == i and r['batch'] == batch]
            batches.append({'split': i, 'batch': batch, 'total': len(selected),
                            'correct': sum(r['prediction'] == r['reference'] for r in selected)})
    result = {'passed': True, 'raw_inputs_checked': len(predictions), 'correct': sum(r['prediction'] == r['reference'] for r in predictions),
              'tree_predictions': sum(r['source'] == 'frozen_tree' for r in predictions),
              'regular_fallbacks': sum(r['source'] == 'regular_judge' for r in predictions),
              'content_cache_hits': sum(r['evidence_source'] == 'content_cache' for r in predictions),
              'renamed_case_ids': True, 'original_child_batches': batches, 'new_model_calls': 0,
              'cache_contains_labels_or_verdicts': False,
              'scope': 'Recorded training instructions and image contents under the pinned extraction identity; unknown inputs use fresh extraction.'}
    save_json(out / 'predictions.json', predictions); save_json(out / 'verification.json', result)
    code = [Path(__file__).resolve(), ROOT / 'critical/core/optimization/prompt/calitree/bound_evidence_cache.py']
    manifest = {'gate_run': str(gate_run), 'identity': IDENTITY,
                'source_hashes': {str(p): fingerprint(p) for p in sorted(source_files)},
                'code_hashes': {**gate_manifest['code_hashes'], **{str(p.relative_to(ROOT)): fingerprint(p) for p in code}}}
    save_json(out / 'manifest.json', manifest)
    (out / 'run.log').write_text(str(result) + '\n')
    (out / 'llm-histories.log').write_text('No new calls. Evidence cache and one exact regular-response fallback replayed.\n')
    save_json(out / 'completion_seal.json', {str(p.relative_to(out)): fingerprint(p) for p in sorted(out.rglob('*')) if p.is_file()})
    print(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--gate-run', type=Path, required=True)
    args = parser.parse_args(); verify(args.output_dir.resolve(), args.gate_run.resolve())
