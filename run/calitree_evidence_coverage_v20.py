"""Offline guarded-expert learning and exact replay of cached bound evidence.

Each gate fits only its original 48 training rows. Other training-pool sources
are a separate transfer diagnostic after all three gates have been frozen.
Fallbacks replay exact regular-judge requests from the approved v19 run.
"""
import argparse
from copy import deepcopy
from pathlib import Path
import time

from critical.core.calibration import evidence_coverage_v20 as coverage
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.compiler import media_inputs
from critical.core.optimization.prompt.calitree.evidence_covered_judge import EvidenceCoveredJudge
from critical.core.optimization.prompt.calitree import task_coverage as task
from run.calitree_task_coverage import ROOT, read, fingerprint, IDENTITY, CAP

VERSION = 'guarded-expert-local-replay-v20'


def request_key(stage, payload, schema, template, media, max_tokens):
    identity = [{'type': 'image', 'sha256': fingerprint(m['path'])} if m['type'] == 'image' else m for m in media]
    return digest([IDENTITY, stage, payload, schema, template, identity, max_tokens])


class CachedRegularCalls:
    """Content-addressed response replay; cannot contact a model or use labels."""
    def __init__(self, prior):
        m = read(prior / 'manifest.json'); self.index = {}; self.requests = []
        for key, job in m['jobs'].items():
            if job['request']['stage'] != 'flat_judge':
                continue
            case = m['cases'][job['case']]; spec = job['request']
            response = read(prior / 'responses' / (key + '.json'))
            if response['error'] or response['judgment'] is None:
                continue
            actual = read(prior / 'ledger/jobs' / (response['execution_ref'] + '.json'))
            if (actual['outcome'] != 'completed' or actual['parsed'] != response['judgment']
                    or actual['payload'] != spec['payload'] or actual['stage'] != spec['stage']
                    or actual['response']['model'] != IDENTITY['model']):
                raise ValueError('Changed fallback response provenance')
            identity = request_key(spec['stage'], spec['payload'], spec['schema'], spec['template'], media_inputs(case['evidence']), CAP)
            if identity in self.index and self.index[identity][0] != response['judgment']:
                raise ValueError('Ambiguous saved responses for identical request')
            self.index[identity] = (response['judgment'], response['execution_ref'])

    def call(self, stage, payload, schema, *, template, media, case_id=None, slot='once', max_tokens=CAP):
        if stage != 'flat_judge' or slot != 'once' or set(payload) != {'instruction'}:
            raise AssertionError('Offline evaluation attempted an unapproved request type')
        key = request_key(stage, payload, schema, template, media, max_tokens)
        if key not in self.index:
            raise ValueError('No exact cached regular judgment; no live fallback is available')
        value, ref = self.index[key]
        self.requests.append({'request_ref': key, 'execution_ref': ref})
        return deepcopy(value), ref


def baseline_prediction(calls, case):
    value, _ = calls.call('flat_judge', {'instruction': case['instruction']}, task.SCHEMA,
                          template=(task.TEMPLATES / 'regular.txt').read_text(), media=media_inputs(case['evidence']))
    return task.LABELS.index(value['label']) if value['label'] in task.LABELS else -1


def scores(rows):
    arms = ('regular', 'task_gate_tree', 'task_and_rule_tree', 'evidence_gate_tree')
    return {'total': len(rows),
            **{arm + '_correct': sum(r[arm] == r['reference'] for r in rows) for arm in arms},
            'gate_accepted': sum(r['route']['covered'] for r in rows),
            'gate_accepted_correct': sum(r['route']['covered'] and r['route']['prediction'] == r['reference'] for r in rows),
            'gate_accepted_wrong': sum(r['route']['covered'] and r['route']['prediction'] != r['reference'] for r in rows),
            'gate_rejected_with_correct_expert': sum(not r['route']['covered'] and r['oracle_correct_expert'] for r in rows),
            'gate_rejected_without_correct_expert': sum(not r['route']['covered'] and not r['oracle_correct_expert'] for r in rows),
            'conflict_deferrals': sum(r['route']['reason'] == 'conflicting_supported_experts' for r in rows),
            'task_gate_accepted': sum(r['task_route']['covered'] for r in rows),
            'task_gate_selected_expert_correct': sum(r['task_route']['covered'] and r['task_gate_tree'] == r['reference'] for r in rows),
            'task_and_rule_accepted': sum(r['task_and_rule_covered'] for r in rows),
            'task_and_rule_accepted_correct': sum(r['task_and_rule_covered'] and r['task_and_rule_tree'] == r['reference'] for r in rows)}


def run(out, source_root, prior):
    if out.exists() and any(out.iterdir()):
        raise ValueError('Use a fresh output directory')
    out.mkdir(parents=True, exist_ok=True)
    evidence = source_root / 'logs/exps/261018-three-sampled-splits-luna-compiler-v3'
    prior_manifest = read(prior / 'manifest.json')
    # Verify the approved run's completion seal without mutating its sources.
    for name, expected in read(prior / 'completion_seal.json')['files'].items():
        if fingerprint(prior / name) != expected:
            raise ValueError('Changed approved prior artifact: ' + name)
    cache = CachedRegularCalls(prior)
    source_files = set(); prepared = []; pool = {}; bound = {}
    for i in (1, 2, 3):
        directory = source_root / f'logs/exps/261018-local-compression-v18-r1/split{i}'
        source_files.update(directory / name for name in ('training_data.json', 'result.json'))
        data = read(directory / 'training_data.json'); old = read(directory / 'result.json')
        models = [old['registry'][k] for k in old['forest']]; programs = {}
        for r in data:
            case = r['case']; extraction_path = evidence / 'extraction/cases' / (case + '.json')
            meaning_path = evidence / 'interpretations' / (case + '.json'); source_files.update((extraction_path, meaning_path))
            extracted = read(extraction_path); meaning = read(meaning_path)
            p = extracted['compilation']['program']; obs = extracted['observation']['observation']; interp = meaning['interpretation']
            meta = prior_manifest['cases'][case]
            if meta['instruction'] != r['instruction'] or meta['reference'] != r['reference'] or meta['source_group'] != r['source_group']:
                raise ValueError('Changed training identity or target')
            pair = obs['image_pair_ref']; actual = coverage.project(p, obs, pair, interp)
            if actual != r['features']:
                raise ValueError('Cached bound evidence differs from trained features')
            if case in pool and any(pool[case][k] != r[k] for k in ('features', 'reference', 'instruction', 'source_group')):
                raise ValueError('Shared training case changed across splits')
            programs[r['source_group']] = p; pool[case] = r; bound[case] = (p, obs, interp)
        started = time.monotonic(); gate, fitting = coverage.build(models, data, programs)
        fitting['elapsed_seconds'] = time.monotonic() - started
        folder = out / f'split{i}'
        save_json(folder / 'gate.json', gate.export()); save_json(folder / 'fit.json', fitting)
        save_json(folder / 'training_data.json', data)
        prepared.append((i, data, models, gate))
        print({'split': i, 'training_covered': fitting['covered_sources'], 'rules': fitting['selected_rules'],
               'states': fitting['pair_states'], 'seconds': fitting['elapsed_seconds']}, flush=True)
    # All gate artifacts are frozen before transfer scoring. Neither transfer
    # targets nor baseline correctness enter build(), thresholds or selection.
    results = []; predictions = []
    for i, data, models, gate in prepared:
        local_sources = {r['source_group'] for r in data}
        outside = sorted((r for r in pool.values() if r['source_group'] not in local_sources), key=lambda r: r['case'])
        task_gate = task.TaskCoverageGate(read(prior / f'split{i}/gate.json'))
        by_ref = {m['runtime']['artifact_ref']: coverage.PortableRuleExecutor(m['runtime']) for m in models}
        judge = EvidenceCoveredJudge(cache, gate)
        recorded = {}
        for scope, cohort in (('local', data), ('outside_training_sources', outside)):
            measured = []
            for row in cohort:
                case = prior_manifest['cases'][row['case']]; p, obs, interp = bound[row['case']]
                fallback = baseline_prediction(cache, case)
                result = judge.judge(row['instruction'], case['evidence'], program=p, observation=obs, interpretation=interp, case_id=row['case'])
                route = result['route']; prediction = task.LABELS.index(result['judgment']['label']) if result['judgment']['label'] in task.LABELS else -1
                task_route = task_gate.select(row['instruction'], p)
                selected = by_ref[task_route['policy_ref']].predict_records([row['features']])[0]['prediction'] if task_route['covered'] else fallback
                rule_matches = [r for r in task_route['reference']['rules'] if all(row['features']['features'][c['feature']] == c['value'] for c in r['conditions'])] if task_route['covered'] else []
                rule_covered = len(rule_matches) == 1
                item = {'split': i, 'scope': scope, 'case': row['case'], 'source_group': row['source_group'],
                        'batch': row['batch'] if scope == 'local' else None, 'reference': row['reference'],
                        'regular': fallback, 'task_gate_tree': selected,
                        'task_and_rule_tree': selected if rule_covered else fallback,
                        'task_and_rule_covered': rule_covered, 'evidence_gate_tree': prediction,
                        'oracle_correct_expert': any(ex.predict_records([row['features']])[0]['prediction'] == row['reference'] for ex in by_ref.values()),
                        'route': route, 'task_route': task_route, 'served_by': result['source'],
                        'fallback_execution_ref': result['execution_ref'], 'extraction_error': result['extraction_error']}
                measured.append(item); predictions.append(item)
            recorded[scope] = scores(measured)
            if scope == 'local':
                batches = {b: scores([r for r in measured if r['batch'] == b]) for b in sorted({r['batch'] for r in measured})}
                recorded['children'] = batches
                recorded['preserves_all_original_children'] = all(v['evidence_gate_tree_correct'] == v['total'] for v in batches.values())
            save_json(out / f'split{i}/{scope}_predictions.json', measured)
        results.append({'split': i, **recorded})
        print(results[-1], flush=True)
    protocol = {'version': VERSION, 'config': coverage.asdict(coverage.Config()),
                'fitting': 'Original per-split 48-case training pool only; references supervise expert coverage, never new verdicts.',
                'inference': 'Original compiled/observed/interpreted evidence, deterministic guarded expert consensus, otherwise exact cached regular judgment.',
                'transfer': 'Other v19 training-pool sources excluded by source_group; historical exploratory diagnostic, not untouched final data.',
                'new_model_calls': 0, 'reserved_final_predictions': 0,
                'scope_limit': 'Local preservation is verified on the recorded upstream evidence. Fresh extraction can change features.'}
    source_files.update((prior / 'manifest.json', prior / 'completion_seal.json'))
    source_files.update(prior / f'split{i}/gate.json' for i in (1, 2, 3))
    code = [Path(__file__).resolve(), Path(coverage.__file__).resolve(), ROOT / 'critical/core/optimization/prompt/calitree/evidence_covered_judge.py',
            ROOT / 'critical/core/optimization/prompt/calitree/task_coverage.py', ROOT / 'critical/core/calibration/local_compression_v18.py']
    code += list((ROOT / 'critical/core/decision').glob('*.py'))
    code += list((ROOT / 'critical/core/calibration/semantic_hierarchy').glob('*.py'))
    code += list(task.TEMPLATES.glob('*.txt'))
    manifest = {'version': VERSION, 'protocol_ref': digest(protocol), 'source_root': str(source_root), 'prior_directory': str(prior),
                'source_hashes': {str(p): fingerprint(p) for p in sorted(source_files)},
                'code_hashes': {str(p.relative_to(ROOT)): fingerprint(p) for p in code}}
    summary = {'version': VERSION, 'splits': results, 'local': scores([r for r in predictions if r['scope'] == 'local']),
               'transfer': scores([r for r in predictions if r['scope'] != 'local']),
               'preserves_all_original_children': all(r['preserves_all_original_children'] for r in results),
               'new_model_calls': 0, 'reserved_final_predictions': 0}
    save_json(out / 'protocol.json', protocol); save_json(out / 'manifest.json', manifest); save_json(out / 'results.json', summary)
    (out / 'llm-histories.log').write_text('No model calls. Original bound evidence and approved v19 regular responses replayed exactly.\n')
    (out / 'run.log').write_text(str(summary) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--prior-directory', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve(), args.source_root.resolve(), args.prior_directory.resolve())
