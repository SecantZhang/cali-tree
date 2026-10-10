"""Six-case 2x2 local robust leaf experiment. Only --live contacts OpenAI."""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import importlib.metadata
import importlib.util
import json
from pathlib import Path

from critical.checkpoint import CheckpointStore
from critical.core.decision.artifacts import save_json
from critical.core.decision.calls import DurableCalls, CaseCalls, BudgetExhausted, ProviderStopped, CallFailure
from critical.core.decision.robust.models import export_program, restore_program
from critical.core.decision.robust.compiler import RobustCompiler
from critical.core.decision.robust.executor import RobustChecker, RobustExecutor
from critical.core.optimization.program.models import Case
from critical.core.optimization.program.robust import RobustLeafOptimizer, RobustEvaluator, RobustPolicy, NodeTextGrad, StructuralProposer
from critical.core.optimization.prompt.calitree import CaliTreeBuilder
from critical.core.optimization.prompt.calitree.node.program_leaf import ROBUST_VERSION, validate_program_leaves

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'logs/exps/261006-optimizer-comparison-v1/manifest.json'
ARMS = ('flat-greedy', 'flat-pareto', 'tree-greedy', 'tree-pareto')
SCOPE = 'Six previously observed cases, independently fitted in four arms. Repetitions are measurements within cases, not independent cases. No held-out generalization claim.'


def code_hashes():
    files = [Path(__file__), ROOT/'critical/checkpoint.py', ROOT/'critical/core/decision/calls.py',
             ROOT/'critical/core/decision/artifacts.py', ROOT/'critical/core/decision/compiler.py',
             ROOT/'critical/core/decision/models.py', ROOT/'critical/core/optimization/program/models.py',
             ROOT/'critical/core/optimization/program/base.py', ROOT/'critical/core/optimization/program/backends/textgrad.py',
             ROOT/'critical/core/optimization/prompt/calitree/node/program_leaf.py',
             ROOT/'critical/core/optimization/prompt/calitree/builder.py',
             ROOT/'critical/lm_engine/lm_template/base.py', ROOT/'critical/lm_engine/provider_api.py']
    for folder, suffix in (('critical/core/decision/robust', '*.py'), ('critical/core/optimization/program/robust', '*.py'),
                           ('critical/core/prompts/templates/robust_leaf_v3', '*.txt')):
        files += list((ROOT/folder).glob(suffix))
    return {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))}


def preflight(output, prior_attempt=None):
    from PIL import Image
    source = json.loads(SOURCE.read_text())
    cases = sorted([r for label in ('yes', 'partial', 'no') for r in sorted(
        (r for r in source['cases'] if r['target'] == label), key=lambda r: r['id'])[:2]], key=lambda r: r['id'])
    if len(cases) != 6 or Counter(r['target'] for r in cases) != {'yes': 2, 'partial': 2, 'no': 2}:
        raise ValueError('Expected two original cases per class')
    groups = set()
    rows = []
    for raw in cases:
        row = {k: deepcopy(raw[k]) for k in ('id', 'instruction', 'target', 'evidence', 'image_hashes', 'group')}
        row['rubric'] = raw['seed']['program']['rubric']
        for key, path in row['evidence'].items():
            if sha256(Path(path).read_bytes()).hexdigest() != row['image_hashes'][key]:
                raise ValueError('Frozen image changed')
        with Image.open(row['evidence']['source_image']) as image:
            pixels = image.convert('RGB')
            group = sha256(str(pixels.size).encode() + pixels.tobytes()).hexdigest()
        if group != row['group'] or group in groups:
            raise ValueError('Changed or repeated source-pixel group')
        groups.add(group)
        rows.append(row)
    if importlib.metadata.version('textgrad') != '0.1.8':
        raise ValueError('Expected pinned TextGrad 0.1.8')
    folder = Path(importlib.util.find_spec('textgrad').origin).parent
    dependencies = {'textgrad': '0.1.8', 'hashes': {str(p.relative_to(folder)): sha256(p.read_bytes()).hexdigest()
                                                 for p in sorted(folder.rglob('*.py'))}}
    manifest = {'version': 'robust-leaf-pilot-v3', 'scope': SCOPE, 'model': 'gpt-6-luna', 'temperature': 0,
        'reasoning_effort': 'none', 'provider': 'openai', 'random_seed': 20261007, 'cases': rows, 'arms': list(ARMS),
        'policy': asdict(RobustPolicy()), 'round_batches': [1, 2], 'proposals_per_batch': 2,
        'frontier_capacity': 6, 'max_nodes': 4, 'max_depth': 4, 'screen_repeats': 1,
        'max_calls': 3600, 'max_completion_tokens': 4608000, 'reserve_calls': 960, 'reserve_tokens': 983040,
        'scope_limits': {'search': 109, 'final': 40}, 'shared_calls_per_case': 2,
        'source_manifest_hash': sha256(SOURCE.read_bytes()).hexdigest(), 'code_hashes': code_hashes(), 'dependencies': dependencies}
    path = Path(output)/'manifest.json'
    if prior_attempt is None and path.exists():
        prior_attempt = json.loads(path.read_text()).get('prior_attempt', {}).get('directory')
    if prior_attempt is not None:
        prior = Path(prior_attempt).resolve()
        if prior == Path(output).resolve():
            raise ValueError('Restart must use a new directory')
        prior_manifest = json.loads((prior/'manifest.json').read_text())
        prior_budget = json.loads((prior/'budget.json').read_text())
        prior_results = json.loads((prior/'results.json').read_text())
        if not prior_budget.get('stopped') or prior_results.get('status') != 'stopped':
            raise ValueError('Only a stopped attempt can supply restart budget accounting')
        for key in ('version', 'cases', 'arms', 'policy', 'model', 'provider', 'temperature', 'reasoning_effort', 'source_manifest_hash'):
            if prior_manifest[key] != manifest[key]:
                raise ValueError('Restart changes the frozen experiment protocol: ' + key)
        manifest['max_calls'] = prior_budget['limits']['max_calls'] - prior_budget['calls']
        manifest['max_completion_tokens'] = (prior_budget['limits']['max_completion_tokens']
                                             - prior_budget['completion_tokens_or_reserved'])
        if manifest['max_calls'] < manifest['reserve_calls'] or manifest['max_completion_tokens'] < manifest['reserve_tokens']:
            raise ValueError('Remaining original allowance cannot reserve final verification')
        manifest['prior_attempt'] = {'directory': str(prior),
            'manifest_sha256': sha256((prior/'manifest.json').read_bytes()).hexdigest(),
            'budget_sha256': sha256((prior/'budget.json').read_bytes()).hexdigest(),
            'calls_charged': prior_budget['calls'], 'completion_tokens_charged': prior_budget['completion_tokens_or_reserved'],
            'reason': 'User-authorized restart after stopped transport attempt; previous slots are preserved, not resumed.'}
    if path.exists():
        if json.loads(path.read_text()) != manifest:
            raise ValueError('Frozen configuration, code, dependency or source changed; cannot resume')
    else:
        save_json(path, manifest)
        for relative in manifest['code_hashes']:
            dest = Path(output)/'source_snapshot'/relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes((ROOT/relative).read_bytes())
    return manifest


def status_for(report, audit, policy):
    assessment = policy.assess(report, audit)
    if assessment['qualified']:
        return 'locally_robust', assessment
    reasons = assessment['reasons']
    status = ('unresolved' if 'unresolved' in reasons or 'semantic_audit' in reasons else
              'insufficient_evidence' if any('insufficient' in r for r in reasons) else
              ('stable_but_mismatched' if report.get('label_consistency') == 1 else 'unstable_and_mismatched')
              if 'target_mismatch' in reasons else 'label_matched_but_unstable')
    if 'target_mismatch' in reasons and report.get('label_consistency') == 1 and audit.get('accepted'):
        assessment['reference_conflict_suspected'] = True
    return status, assessment


def write_report(output, result, manifest):
    summaries = {}
    for arm in ARMS:
        rows = [v[arm] for v in result['cases'].values() if arm in v]
        finals = [r.get('final', {}) for r in rows]
        summaries[arm] = {'cases': len(rows), 'locally_robust': sum(r.get('support_status') == 'locally_robust' for r in rows),
            'mean_seed_agreement': sum(f.get('seed', {}).get('agreement', 0) for f in finals)/len(manifest['cases']),
            'mean_selected_agreement': sum(f.get('selected', {}).get('agreement', 0) for f in finals)/len(manifest['cases']),
            'mean_selected_coverage': sum(f.get('selected', {}).get('coverage', 0) for f in finals)/len(manifest['cases'])}
    case_count = len(manifest['cases'])
    lines = ['# Robust CaliTree leaf pilot', '', manifest.get('scope', SCOPE), '', 'Status: ' + result['status'], '',
             f'| Arm | Robust / {case_count} | Seed agreement | Selected agreement | Selected coverage |',
             '|---|---:|---:|---:|---:|']
    for arm, s in summaries.items():
        lines.append(f"| {arm} | {s['locally_robust']} | {s['mean_seed_agreement']:.1%} | {s['mean_selected_agreement']:.1%} | {s['mean_selected_coverage']:.1%} |")
    lines += ['', f'Missing/unresolved draws count as nonmatches. Arm means retain all {case_count} cases.', '',
        '| Case / target | Arm | Seed / selected agreement | Seed / selected coverage | Seed / selected consistency | Checks seed / selected | Tokens seed / selected | Status |',
        '|---|---|---|---|---|---|---|---|']
    for raw in manifest['cases']:
        for arm, row in result['cases'].get(raw['id'], {}).items():
            seed, selected = (row.get('final', {}).get(name, {}) for name in ('seed', 'selected'))
            pair = lambda key: ' / '.join(f'{v.get(key, 0):.2f}' for v in (seed, selected))
            lines.append('| ' + ' | '.join([raw['id'] + ' / ' + raw['target'], arm, pair('agreement'), pair('coverage'),
                pair('requirement_consistency'), pair('mean_checks'), pair('mean_completion_tokens'), row.get('support_status', 'unresolved')]) + ' |')
            lines += ['', f"{arm}, {raw['id']}: " + json.dumps({'acceptance': row.get('acceptance'), 'error': row.get('error'),
                'search_status': row.get('search_status'), 'stop_reason': row.get('stop_reason'), 'usage': row.get('usage')})]
    lines += ['', 'Confidence is generated self-report, not calibrated correctness. Atomic consistency is reported separately in results.json.',
        'Unvisited branches are untested. All selections were frozen before final verification; final traces never guide repair.',
        'Tree and flat views may coincide when compilation finds no useful conditional gate. Inspect topology counts before interpreting an arm difference.',
        '', 'Returned model identities: ' + json.dumps(result.get('returned_models', [])),
        'Budget: ' + json.dumps({k: v for k, v in result.get('budget', {}).items() if k not in ('attempted_slots', 'cases')}),
        'Error: ' + str(result.get('error', 'none'))]
    (Path(output)/'report.md').write_text('\n'.join(lines) + '\n')
    save_json(Path(output)/'summary.json', summaries)


def execute(output, manifest, engine_factory):
    output = Path(output)
    policy = RobustPolicy(**manifest['policy'])
    calls = DurableCalls(output, engine_factory, identity={k: manifest[k] for k in ('model', 'temperature', 'reasoning_effort', 'provider')},
        **{k: manifest[k] for k in ('max_calls', 'max_completion_tokens', 'reserve_calls', 'reserve_tokens', 'scope_limits')})
    result = {'status': 'running', 'scope': manifest.get('scope', SCOPE), 'cases': {r['id']: {} for r in manifest['cases']}}
    bundle = {'version': ROBUST_VERSION, 'nodes': {}, 'programs': {}}
    checkpoint = CheckpointStore(output/'observations.jsonl')

    def persist():
        result['budget'] = deepcopy(calls.budget)
        result['returned_models'] = sorted({job.get('response', {}).get('model', 'unavailable') for p in (output/'jobs').glob('*.json')
                                          if (job := json.loads(p.read_text())).get('response')})
        save_json(output/'results.json', result)
        if bundle['nodes']:
            save_json(output/'leaves.json', validate_program_leaves(bundle))
        write_report(output, result, manifest)
        with (output/'run.log').open('a') as stream:
            stream.write(json.dumps({'status': result['status'], 'calls': calls.budget['calls'], 'error': result.get('error')}) + '\n')

    try:
        # Freeze every case-arm before making any final call; no final feedback enters search.
        for index, raw in enumerate(manifest['cases']):
            case = Case(raw['id'], raw['instruction'], raw['evidence'], raw['group'])
            seed_path = output/'prepared'/f'{index}.json'
            if seed_path.exists():
                prepared = json.loads(seed_path.read_text())
            else:
                try:
                    compiler = RobustCompiler(CaseCalls(calls, 'prepare/' + case.id))
                    seed = compiler.compile(case.instruction, raw['rubric'], slot='compile')
                    audits = compiler.audit_views(seed, slot='audit_views')
                    prepared = {'seed': export_program(seed), 'audits': audits}
                except (CallFailure, ValueError, TypeError, KeyError, BudgetExhausted) as exc:
                    prepared = {'error': f'{type(exc).__name__}: {exc}'}
                save_json(seed_path, prepared)
            order = ARMS[index % 4:] + ARMS[:index % 4]
            for arm in order:
                frozen = output/'frozen'/arm/f'{index}.json'
                if not frozen.exists():
                    if 'error' in prepared:
                        save_json(frozen, {'error': prepared['error']})
                    else:
                        mode, selection = arm.split('-')
                        scoped = CaseCalls(calls, arm + '/' + case.id)
                        evaluator = RobustEvaluator(RobustExecutor(RobustChecker(scoped), checkpoint=checkpoint), policy)
                        compiler = RobustCompiler(scoped)
                        optimizer = RobustLeafOptimizer(compiler, StructuralProposer(scoped), evaluator, NodeTextGrad(scoped),
                            rubric=raw['rubric'], selection=selection, mode=mode, random_seed=manifest['random_seed'] + index,
                            seed_audit=prepared['audits'][mode])
                        local = CaliTreeBuilder.build_program_leaves([case], reference_labels={case.id: raw['target']},
                            optimizer_factory=lambda _: optimizer, seeds={case.id: restore_program(prepared['seed']).view(mode)})
                        save_json(frozen, local)
                print(json.dumps({'phase': 'frozen', 'case': index + 1, 'arm': arm, 'calls': calls.budget['calls']}), flush=True)
                persist()
        for index, raw in enumerate(manifest['cases']):
            case = Case(raw['id'], raw['instruction'], raw['evidence'], raw['group'])
            order = ARMS[index % 4:] + ARMS[:index % 4]
            for arm in order:
                local = json.loads((output/'frozen'/arm/f'{index}.json').read_text())
                row = {'support_status': 'unresolved', 'final': {}}
                result['cases'][case.id][arm] = row
                if 'error' in local:
                    row['error'] = local['error']
                    persist()
                    continue
                validate_program_leaves(local)
                node = local['nodes']['leaf:' + case.id]
                row.update(search_status=node['result']['status'], stop_reason=node['result']['stop_reason'])
                scoped = CaseCalls(calls, arm + '/' + case.id)
                evaluator = RobustEvaluator(RobustExecutor(RobustChecker(scoped), checkpoint=checkpoint), policy)
                for comparison in ('seed', 'selected'):
                    artifact = node['result'][comparison]
                    if artifact is None:
                        continue
                    try:
                        row['final'][comparison] = evaluator.evaluate(restore_program(artifact), case, raw['target'], repeats=policy.repeats,
                            namespace=f'final/{comparison}/{arm}/{case.id}', final=True)
                    except (CallFailure, ValueError, BudgetExhausted) as exc:
                        row['error'] = str(exc)
                    persist()
                if row['final'].get('selected'):
                    audit = node['result']['candidates'].get(node['program_ref'], {}).get('audit', {})
                    row['support_status'], row['acceptance'] = status_for(row['final']['selected'], audit, policy)
                row['usage'] = deepcopy(calls.budget.get('cases', {}).get(arm + '/' + case.id, {}))
                node.update(id=f'leaf:{arm}/{case.id}', support_status=row['support_status'], final_comparison=row['final'], arm=arm)
                bundle['nodes'][node['id']] = node
                bundle['programs'].update(local['programs'])
                persist()
                print(json.dumps({'phase': 'final', 'case': index+1, 'arm': arm, 'status': row['support_status'], 'calls': calls.budget['calls']}), flush=True)
        result['status'] = 'completed'
    except (ProviderStopped, BudgetExhausted, CallFailure, ValueError, KeyError, TypeError, RuntimeError) as exc:
        result.update(status='stopped', error=f'{type(exc).__name__}: {exc}')
    persist()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    modes = parser.add_mutually_exclusive_group()
    for mode in ('demo', 'preflight', 'live', 'report'):
        modes.add_argument('--' + mode, action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--prior-attempt', type=Path, help='Authorized restart: subtract a stopped attempt from the original budget')
    args = parser.parse_args()
    if args.demo:
        from critical.core.optimization.program.robust.demo import run_demo
        print(json.dumps(run_demo(args.output_dir))); return
    if args.report:
        write_report(args.output_dir, json.loads((args.output_dir/'results.json').read_text()),
                     json.loads((args.output_dir/'manifest.json').read_text())); return
    if args.resume and not (args.output_dir/'manifest.json').exists():
        parser.error('Resume requires an existing manifest')
    manifest = preflight(args.output_dir, args.prior_attempt)
    if not args.live:
        print(json.dumps({'status': 'ready', 'cases': 6, 'arms': ARMS, 'max_calls': manifest['max_calls'],
                          'max_completion_tokens': manifest['max_completion_tokens']})); return
    from critical.lm_engine import get_engine, load_creds, require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True)
    history = LLMHistoryWriter(args.output_dir/'llm-histories.log')
    creds = load_creds(engine='gpt', provider='openai')
    if creds.provider != 'openai' or creds.endpoints != ['https://api.openai.com/v1']:
        raise ValueError('This frozen pilot requires the official OpenAI endpoint with no fallback')
    result = execute(args.output_dir, manifest, lambda cap: get_engine('gpt', model=manifest['model'], creds=creds,
        history=history, max_tokens=cap, temperature=0, max_http_attempts=1, timeout=60))
    print(json.dumps({'status': result['status'], 'error': result.get('error'), 'output': str(args.output_dir)}))

if __name__ == '__main__':
    main()
