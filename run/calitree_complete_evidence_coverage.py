"""Complete the evidence gate from retained children; no new model calls."""
import argparse
from pathlib import Path

from critical.core.calibration import evidence_coverage_v20 as base
from critical.core.calibration import complete_evidence_coverage as completion
from critical.core.decision.artifacts import digest, save_json
from critical.core.optimization.prompt.calitree.evidence_covered_judge import EvidenceCoveredJudge
from critical.core.optimization.prompt.calitree.task_coverage import LABELS
from run.calitree_evidence_coverage_v20 import CachedRegularCalls, scores
from run.calitree_task_coverage import ROOT, read, fingerprint


def run(out, previous):
    if out.exists() and any(out.iterdir()):
        raise ValueError('Use a fresh output directory')
    out.mkdir(parents=True, exist_ok=True)
    inherited = read(previous / 'manifest.json'); base_run = Path(inherited['base_run'])
    for name, expected in read(previous / 'completion_seal.json')['files'].items():
        assert fingerprint(previous / name) == expected, name
    root = Path(inherited['source_root']); prior = Path(inherited['prior_directory'])
    evidence = root / 'logs/exps/261018-three-sampled-splits-luna-compiler-v3'
    metadata = read(prior / 'manifest.json')['cases']; calls = CachedRegularCalls(prior)
    source_hashes = {str(previous / 'completion_seal.json'): fingerprint(previous / 'completion_seal.json')}
    prepared = []
    for i in (1, 2, 3):
        data = read(base_run / f'split{i}/training_data.json')
        original = read(root / f'logs/exps/261018-local-compression-v18-r1/split{i}/result.json')
        gate = base.EvidenceCoverageGate(read(base_run / f'split{i}/gate.json'))
        programs = {r['source_group']: read(evidence / 'extraction/cases' / (r['case'] + '.json'))['compilation']['program'] for r in data}
        final, report = completion.complete(gate, list(original['registry'].values()), data, programs)
        save_json(out / f'split{i}/gate.json', final.export()); save_json(out / f'split{i}/completion.json', report)
        prepared.append((i, final)); print({'split': i, 'completion': report['added_regions'], 'uncovered': report['uncovered_local_sources']}, flush=True)
        for scope in ('local', 'outside_training_sources'):
            path = previous / f'split{i}/{scope}_predictions.json'; source_hashes[str(path)] = fingerprint(path)
    results = []; all_rows = []
    for i, gate in prepared:
        judge = EvidenceCoveredJudge(calls, gate); result = {'split': i}
        for scope in ('local', 'outside_training_sources'):
            old = read(previous / f'split{i}/{scope}_predictions.json'); current = []
            for before in old:
                case = before['case']; meta = metadata[case]; extracted = read(evidence / 'extraction/cases' / (case + '.json'))
                meaning = read(evidence / 'interpretations' / (case + '.json'))['interpretation']
                value = judge.judge(meta['instruction'], meta['evidence'], program=extracted['compilation']['program'],
                                    observation=extracted['observation']['observation'], interpretation=meaning, case_id=case)
                prediction = LABELS.index(value['judgment']['label']) if value['judgment']['label'] in LABELS else -1
                if scope == 'local':
                    assert value['route']['covered'] and prediction == before['reference']
                current.append({**before, 'previous_semantic_route': before['route'], 'evidence_gate_tree': prediction,
                                'route': value['route'], 'served_by': value['source'], 'fallback_execution_ref': value['execution_ref'],
                                'extraction_error': value['extraction_error']})
            save_json(out / f'split{i}/{scope}_predictions.json', current); result[scope] = scores(current)
            result[scope]['semantic_support_deferrals'] = sum(r['route']['reason'] == 'outside_semantic_support' for r in current)
            if scope == 'local':
                result['children'] = {b: scores([r for r in current if r['batch'] == b]) for b in sorted({r['batch'] for r in current})}
                result['preserves_all_original_children'] = all(v['evidence_gate_tree_correct'] == v['total'] for v in result['children'].values())
            all_rows.extend(current)
        results.append(result); print({'split': i, 'local': result['local'], 'transfer': result['outside_training_sources']}, flush=True)
    protocol = {**read(previous / 'protocol.json'), 'version': completion.VERSION,
                'completion': 'Search retained hierarchy children only when the selected-forest gate leaves local cases uncovered; append supported zero-local-error regions, then semantic filters.',
                'selection': 'Completion selected on local fitting rows only. Earlier semantic-envelope design used historical transfer diagnostics.'}
    code = [Path(__file__).resolve(), Path(completion.__file__).resolve()]
    manifest = {**inherited, 'protocol_ref': digest(protocol), 'previous_support_run': str(previous),
                'source_hashes': {**inherited['source_hashes'], **source_hashes},
                'code_hashes': {**inherited['code_hashes'], **{str(p.relative_to(ROOT)): fingerprint(p) for p in code}}}
    summary = {'version': completion.VERSION, 'splits': results, 'local': scores([r for r in all_rows if r['scope'] == 'local']),
               'transfer': scores([r for r in all_rows if r['scope'] != 'local']),
               'preserves_all_original_children': all(r['preserves_all_original_children'] for r in results),
               'new_model_calls': 0, 'reserved_final_predictions': 0, 'deployed_by_default': False}
    save_json(out / 'protocol.json', protocol); save_json(out / 'manifest.json', manifest); save_json(out / 'results.json', summary)
    (out / 'run.log').write_text(str(summary) + '\n')
    (out / 'llm-histories.log').write_text('No new model calls. Original evidence and approved regular judgments replayed.\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True); p.add_argument('--previous-run', type=Path, required=True)
    a = p.parse_args(); run(a.output_dir.resolve(), a.previous_run.resolve())
