"""Independent casewise leaf fitting. Default preflight never calls a model."""
from __future__ import annotations
import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from critical.checkpoint import CheckpointStore
from critical.core.decision.artifacts import save_json, restore_program
from critical.core.decision.calls import DurableCalls, CaseCalls, ProviderStopped, BudgetExhausted, CallFailure
from critical.core.decision.compiler import ProgramCompiler, TEMPLATES
from critical.core.decision.executor import ModelChecker, ProgramExecutor
from critical.core.optimization.program import Case, CasewiseOptimizer, ModelEditProposer, RepeatedEvaluator
from critical.core.optimization.program.demo import RUBRIC, DemoCompiler, DemoChecker, DemoProposer, demo_case
from critical.core.optimization.prompt.calitree import CaliTreeBuilder
from critical.core.optimization.prompt.calitree.node.program_leaf import VERSION, validate_program_leaves

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / 'logs/exps/261006-16:11:29-exps/manifest.json'
MODEL = 'gpt-6-luna'
SCOPE = 'Previously observed cases fitted independently using their own labels. No generalization evaluation.'

def code_hashes():
    files = [Path(__file__), ROOT / 'critical/core/optimization/prompt/calitree/node/program_leaf.py',
             ROOT / 'critical/core/optimization/prompt/calitree/builder.py', ROOT / 'critical/lm_engine/lm_template/base.py',
             ROOT / 'critical/lm_engine/provider_api.py']
    for folder in ('critical/core/decision', 'critical/core/optimization/program'):
        files += list((ROOT / folder).glob('*.py'))
    files += list(TEMPLATES.glob('*.txt'))
    return {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in sorted(files)}

def frozen_cases():
    from PIL import Image
    old = json.loads(ORIGINAL.read_text())
    rows = sorted((r for part in old['partitions'].values() for r in part), key=lambda r: r['id'])
    assert len(rows) == 12 and all(sum(r['target'] == label for r in rows) == 4 for label in ('yes', 'partial', 'no'))
    groups = set()
    for row in rows:
        for key, path in row['evidence'].items():
            if sha256(Path(path).read_bytes()).hexdigest() != row['image_hashes'][key]:
                raise ValueError('Prior pilot image changed')
        with Image.open(row['evidence']['source_image']) as image:
            pixels = image.convert('RGB')
            group = sha256(str(pixels.size).encode() + pixels.tobytes()).hexdigest()
        if group in groups:
            raise ValueError('Repeated source pixels')
        groups.add(group)
        row['group'] = group
    return rows

def preflight(output):
    output = Path(output); path = output / 'manifest.json'
    hashes = code_hashes()
    if path.exists():
        manifest = json.loads(path.read_text())
        if manifest['version'] != 'casewise-pilot-v2' or manifest['code_hashes'] != hashes:
            raise ValueError('Frozen code changed; start a separately recorded experiment')
        for row in manifest['cases']:
            if any(sha256(Path(p).read_bytes()).hexdigest() != row['image_hashes'][k] for k, p in row['evidence'].items()):
                raise ValueError('Frozen evidence changed')
        return manifest
    manifest = {'version': 'casewise-pilot-v2', 'model': MODEL, 'temperature': 0, 'reasoning_effort': 'none',
                'cases': frozen_cases(), 'scope': SCOPE, 'rubric': RUBRIC, 'code_hashes': hashes,
                'original_manifest_hash': sha256(ORIGINAL.read_bytes()).hexdigest(),
                'max_calls': 600, 'max_completion_tokens': 768000, 'reserve_calls': 288, 'reserve_tokens': 294912,
                'search_calls_per_case': 26, 'final_calls_per_case': 24, 'max_checks': 4,
                'rounds': 2, 'beam_width': 2, 'proposals_per_parent': 2}
    save_json(path, manifest)
    for relative in hashes:
        target = output / 'source_snapshot' / relative
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes((ROOT / relative).read_bytes())
    return manifest

def write_report(output, result):
    lines = ['# CaliTree casewise leaf optimization', '', result.get('scope', SCOPE), '', 'Status: ' + result['status'], '',
             '| Case | Target | Seed agreement | Selected agreement | Coverage | Flips | Atomic unstable/unknown | Checks | Status |',
             '|---|---|---:|---:|---:|---:|---:|---:|---|']
    for row in result.get('cases', {}).values():
        final = row.get('final', {})
        seed, selected = final.get('seed', {}), final.get('selected', {})
        fmt = lambda v: f'{v:.1%}' if v is not None else '—'
        lines.append('| ' + ' | '.join([row['id'], row['target'], fmt(seed.get('agreement')), fmt(selected.get('agreement')),
                    fmt(selected.get('coverage')), fmt(selected.get('flip_rate')), fmt(selected.get('atomic_unstable_or_unknown_rate')),
                    str(selected.get('executed_checks', '—')), row.get('support_status', 'unresolved')]) + ' |')
        lines += ['', 'Search: ' + row.get('search_status', 'n/a') + '; stop: ' + row.get('stop_reason', 'n/a') + '; usage: ' + json.dumps(row.get('usage', {}))]
        if row.get('error'):
            lines += ['', row['id'] + ': ' + row['error']]
    lines += ['', 'Three repetitions are one case, not three independent samples. Agreement and semantic audits do not certify atomic visual correctness.',
              'Final comparisons never feed repair. All fitting is local; no reuse or generalization claim is made.', '',
              'Budget: ' + json.dumps({k:v for k,v in result.get('budget', {}).items() if k not in ('attempted_slots', 'cases')}), '', 'Error: ' + str(result.get('error', 'none'))]
    (Path(output) / 'report.md').write_text('\n'.join(lines) + '\n')

def execute_live(output, manifest, engine_factory):
    output = Path(output)
    calls = DurableCalls(output, engine_factory, identity={k: manifest[k] for k in ('model', 'temperature', 'reasoning_effort')},
                  **{k: manifest[k] for k in ('max_calls', 'max_completion_tokens', 'reserve_calls', 'reserve_tokens')})
    result = {'status': 'running', 'scope': SCOPE, 'cases': {}}
    bundle = {'version': VERSION, 'nodes': {}, 'programs': {}}
    try:
        for index, raw in enumerate(manifest['cases']):
            case = Case(raw['id'], raw['instruction'], raw['evidence'], raw['group'])
            scoped = CaseCalls(calls, case.id)
            executor = ProgramExecutor(ModelChecker(scoped), checkpoint=CheckpointStore(output / 'observations.jsonl'))
            evaluator = RepeatedEvaluator(executor)
            compiler = ProgramCompiler(scoped)
            optimizer = CasewiseOptimizer(compiler, ModelEditProposer(scoped), evaluator, rubric=manifest['rubric'],
                  **{k: manifest[k] for k in ('rounds', 'beam_width', 'proposals_per_parent')})
            frozen_path = output / 'leaves' / (str(index) + '.json')
            if frozen_path.exists():
                local = validate_program_leaves(json.loads(frozen_path.read_text()))
            else:
                local = CaliTreeBuilder.build_program_leaves([case], reference_labels={case.id: raw['target']},
                                                             optimizer_factory=lambda _: optimizer)
                # Immutable selection boundary: final labels can never trigger a new search.
                save_json(frozen_path, local)
            node = local['nodes']['leaf:' + case.id]
            row = {'id': case.id, 'target': raw['target'], 'search_status': node['result']['status'],
                   'stop_reason': node['result']['stop_reason'], 'final': {}, 'support_status': 'unresolved'}
            result['cases'][case.id] = row
            if node['program_ref']:
                for arm in ('seed', 'selected'):
                    try:
                        program = restore_program(node['result'][arm])
                        row['final'][arm] = evaluator.evaluate(program, case, raw['target'], repeats=3,
                                                namespace=case.id + '/final/' + arm, final=True)
                    except (BudgetExhausted, CallFailure, ValueError) as exc:
                        row['error'] = str(exc)
                selected = row['final'].get('selected', {})
                audit = node['result']['candidates'].get(node['program_ref'], {}).get('audit', {})
                if selected.get('agreement') == 1 and selected.get('coverage') == 1 and audit.get('accepted'):
                    row['support_status'] = 'locally_fitted'
                elif selected.get('coverage', 0) < 1:
                    row['support_status'] = 'unresolved'
                elif selected.get('flip_rate', 0) > 0:
                    row['support_status'] = 'unstable'
                else:
                    row['support_status'] = 'unmatched'
            node['support_status'] = row['support_status']
            node['final_comparison'] = row['final']
            bundle['nodes'].update(local['nodes']); bundle['programs'].update(local['programs'])
            row['usage'] = calls.budget.get('cases', {}).get(case.id, {})
            save_json(output / 'leaves.json', bundle)
            result['budget'] = calls.budget
            save_json(output / 'results.json', result); write_report(output, result)
            print(json.dumps({'case': case.id, 'status': row['support_status'], 'calls': calls.budget['calls']}), flush=True)
        result['status'] = 'completed'
    except (ProviderStopped, BudgetExhausted, CallFailure, ValueError, KeyError, TypeError) as exc:
        result.update(status='stopped', error=f'{type(exc).__name__}: {exc}')
    result['budget'] = calls.budget
    save_json(output / 'results.json', result); write_report(output, result)
    with (output / 'run.log').open('a') as log:
        log.write(json.dumps({'status': result['status'], 'calls': calls.budget['calls'], 'error': result.get('error')}) + '\n')
    return result

def run_demo(output):
    output = Path(output)
    case = demo_case(output / 'fixtures')
    evaluator = RepeatedEvaluator(ProgramExecutor(DemoChecker()))
    optimizer = CasewiseOptimizer(DemoCompiler(), DemoProposer(), evaluator, rubric=RUBRIC)
    bundle = CaliTreeBuilder.build_program_leaves([case], reference_labels={case.id: 'yes'}, optimizer_factory=lambda _: optimizer)
    save_json(output / 'leaves.json', bundle)
    node = bundle['nodes']['leaf:' + case.id]
    final = {arm: evaluator.evaluate(restore_program(node['result'][arm]), case, 'yes', repeats=3, namespace='final/' + arm)
             for arm in ('seed', 'selected')}
    result = {'status': 'completed', 'scope': 'Synthetic offline contract, no model-quality claim.', 'cases': {case.id:
              {'id': case.id, 'target': 'yes', 'final': final, 'support_status': 'locally_fitted'}}}
    save_json(output / 'results.json', result); write_report(output, result)
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'logs/exps' /
                  (datetime.now(ZoneInfo('America/Chicago')).strftime('%y%m%d-%H:%M:%S') + '-exps'))
    modes = parser.add_mutually_exclusive_group()
    for mode in ('demo', 'live', 'report', 'preflight'):
        modes.add_argument('--' + mode, action='store_true')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if args.report:
        write_report(args.output_dir, json.loads((args.output_dir / 'results.json').read_text())); return
    if args.demo:
        result = run_demo(args.output_dir)
    else:
        if args.resume and not (args.output_dir / 'manifest.json').exists():
            parser.error('Resume needs an existing manifest')
        manifest = preflight(args.output_dir)
        if not args.live:
            print(json.dumps({'status': 'ready', 'cases': len(manifest['cases']), 'output': str(args.output_dir)})); return
        from critical.lm_engine import get_engine, load_creds, require_live
        from critical.logging.llm_history import LLMHistoryWriter
        require_live(True)
        history = LLMHistoryWriter(args.output_dir / 'llm-histories.log')
        result = execute_live(args.output_dir, manifest, lambda cap: get_engine('gpt', model=MODEL, creds=load_creds(engine='gpt'),
                        history=history, max_tokens=cap, temperature=0, max_http_attempts=1, timeout=60))
    print(json.dumps({'status': result['status'], 'error': result.get('error'), 'output': str(args.output_dir)}))

if __name__ == '__main__':
    main()
