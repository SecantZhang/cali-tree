"""Freeze semantic support filters and replay local/transfer evidence offline."""
import argparse
from pathlib import Path

from critical.core.calibration import evidence_coverage_v20 as base, evidence_support_v21 as supported
from critical.core.decision.artifacts import digest, save_json
from critical.core.optimization.prompt.calitree.evidence_covered_judge import EvidenceCoveredJudge
from critical.core.optimization.prompt.calitree.task_coverage import LABELS
from run.calitree_evidence_coverage_v20 import CachedRegularCalls, scores
from run.calitree_task_coverage import ROOT, read, fingerprint


def run(out, previous):
    if out.exists() and any(out.iterdir()):
        raise ValueError('Use a fresh output directory')
    out.mkdir(parents=True, exist_ok=True)
    inherited = read(previous / 'manifest.json')
    for path, expected in inherited['source_hashes'].items():
        assert fingerprint(path) == expected, path
    for path, expected in inherited['code_hashes'].items():
        assert fingerprint(ROOT / path) == expected, path
    root = Path(inherited['source_root']); prior = Path(inherited['prior_directory'])
    evidence = root / 'logs/exps/261018-three-sampled-splits-luna-compiler-v3'
    metadata = read(prior / 'manifest.json')['cases']; calls = CachedRegularCalls(prior)
    source_hashes = {str(previous / 'manifest.json'): fingerprint(previous / 'manifest.json')}
    prepared = []
    for i in (1, 2, 3):
        directory = previous / f'split{i}'
        data = read(directory / 'training_data.json'); gate = base.EvidenceCoverageGate(read(directory / 'gate.json'))
        programs = {r['source_group']: read(evidence / 'extraction/cases' / (r['case'] + '.json'))['compilation']['program'] for r in data}
        filtered = supported.build(gate, data, programs)
        save_json(out / f'split{i}/gate.json', filtered.export())
        prepared.append((i, filtered))
        for name in ('gate.json', 'training_data.json', 'fit.json', 'local_predictions.json', 'outside_training_sources_predictions.json'):
            path = directory / name; source_hashes[str(path)] = fingerprint(path)
    results = []; all_rows = []
    for i, filtered in prepared:
        judge = EvidenceCoveredJudge(calls, filtered); result = {'split': i}
        for scope in ('local', 'outside_training_sources'):
            old = read(previous / f'split{i}/{scope}_predictions.json'); current = []
            for before in old:
                case = before['case']; meta = metadata[case]
                extracted = read(evidence / 'extraction/cases' / (case + '.json'))
                meaning = read(evidence / 'interpretations' / (case + '.json'))['interpretation']
                value = judge.judge(meta['instruction'], meta['evidence'], program=extracted['compilation']['program'],
                                    observation=extracted['observation']['observation'], interpretation=meaning, case_id=case)
                route = value['route']
                prediction = LABELS.index(value['judgment']['label']) if value['judgment']['label'] in LABELS else -1
                if route['covered']:
                    assert before['route']['covered'] and route['prediction'] == before['route']['prediction']
                if scope == 'local':
                    assert (route['covered'], route['prediction']) == (before['route']['covered'], before['route']['prediction'])
                current.append({**before, 'original_evidence_gate_tree': before['evidence_gate_tree'],
                                'original_evidence_route': before['route'], 'evidence_gate_tree': prediction,
                                'route': route, 'served_by': value['source'], 'fallback_execution_ref': value['execution_ref'],
                                'extraction_error': value['extraction_error']})
            save_json(out / f'split{i}/{scope}_predictions.json', current)
            result[scope] = scores(current)
            result[scope]['semantic_support_deferrals'] = sum(r['route']['reason'] == 'outside_semantic_support' for r in current)
            if scope == 'local':
                result['children'] = {b: scores([r for r in current if r['batch'] == b]) for b in sorted({r['batch'] for r in current})}
                result['preserves_all_original_children'] = all(v['evidence_gate_tree_correct'] == v['total'] for v in result['children'].values())
            all_rows.extend(current)
        results.append(result)
        print({'split': i, 'local': result['local'], 'transfer': result['outside_training_sources']}, flush=True)
    protocol = {'version': supported.VERSION, 'base_run': str(previous), 'new_model_calls': 0,
                'selection': 'Keep all semantic predicates constant over each guarded region; never reverse a base rejection.',
                'fitting_scope': 'Original 48 training cases of each gate. No expert-tree or reference-label changes.',
                'development_disclosure': 'Semantic support variants were screened on the historical transfer diagnostic. These are exploratory development results, not untouched confirmation.',
                'accuracy_scope': 'Preservation of local trained accuracy with the original validated cached upstream evidence. Fresh-extraction stability is not established.',
                'reserved_final_predictions': 0}
    code = [Path(__file__).resolve(), Path(supported.__file__).resolve(), Path(base.__file__).resolve(),
            ROOT / 'critical/core/optimization/prompt/calitree/evidence_covered_judge.py', ROOT / 'run/calitree_evidence_coverage_v20.py']
    manifest = {'protocol_ref': digest(protocol), 'base_run': str(previous), 'source_root': str(root), 'prior_directory': str(prior),
                'source_hashes': {**inherited['source_hashes'], **source_hashes},
                'code_hashes': {**inherited['code_hashes'], **{str(p.relative_to(ROOT)): fingerprint(p) for p in code}}}
    summary = {'version': supported.VERSION, 'splits': results, 'local': scores([r for r in all_rows if r['scope'] == 'local']),
               'transfer': scores([r for r in all_rows if r['scope'] != 'local']),
               'preserves_all_original_children': all(s['preserves_all_original_children'] for s in results),
               'new_model_calls': 0, 'reserved_final_predictions': 0, 'deployed_by_default': False}
    save_json(out / 'protocol.json', protocol); save_json(out / 'manifest.json', manifest); save_json(out / 'results.json', summary)
    (out / 'run.log').write_text(str(summary) + '\n')
    (out / 'llm-histories.log').write_text('Zero new calls; exact validated evidence and regular responses reused.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--base-run', type=Path, required=True)
    args = parser.parse_args(); run(args.output_dir.resolve(), args.base_run.resolve())
