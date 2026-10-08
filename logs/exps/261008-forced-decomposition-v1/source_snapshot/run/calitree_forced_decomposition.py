"""Fresh broad versus mandatory evidence-decomposition local fitting experiment."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import importlib.metadata
import importlib.util
import json
from pathlib import Path

from PIL import Image
from critical.checkpoint import CheckpointStore
from critical.core.decision.artifacts import save_json
from critical.core.decision.calls import DurableCalls, CaseCalls, BudgetExhausted, ProviderStopped, CallFailure
from critical.core.decision.robust.models import export_program, restore_program
from critical.core.decision.robust.executor import RobustChecker, RobustExecutor
from critical.core.decision.robust.decomposition import (DecompositionCompiler, DecompositionChecker, BroadCompiler,
    validate_decomposition, validate_broad, CONTRACT)
from critical.core.optimization.program.models import Case
from critical.core.optimization.program.robust import RobustLeafOptimizer, RobustEvaluator, RobustPolicy, NodeTextGrad, StructuralProposer
from critical.core.optimization.program.robust.decomposition import DecompositionProposer
from critical.core.optimization.prompt.calitree import CaliTreeBuilder
from critical.core.optimization.prompt.calitree.node.program_leaf import ROBUST_VERSION, validate_program_leaves
from run.calitree_robust_leaf_optimization import ROOT, code_hashes, status_for

SOURCE = ROOT/'logs/exps/261007-robust-hard-cases-v3'
ARMS = ('broad-greedy', 'decomposed-greedy')
SCOPE = ('Previously observed local fitting cases. Fresh observations compare saved label-free broad seeds with '
         'mandatory two/three-evidence-check decomposition and greedy repairs. Repeated draws are not additional cases. '
         'No generalization or atomic semantic correctness claim; evidence-only readout also changes the information flow.')


def preflight(output, *, chalk_only=False):
    source = json.loads((SOURCE/'manifest.json').read_text())
    rows, groups, source_hashes = [], set(), {}
    for index, raw in enumerate(source['cases']):
        if chalk_only and 'chalk' not in raw['instruction']:
            continue
        row = deepcopy(raw)
        seed_path = SOURCE/'prepared'/f'{index}.json'
        row['broad_seed'] = json.loads(seed_path.read_text())['seed']
        original = restore_program(row['broad_seed'])
        validate_broad(original, original)
        if original.instruction != row['instruction'] or original.rubric != row['rubric']:
            raise ValueError('Saved label-free seed differs from frozen case')
        source_hashes[str(seed_path.relative_to(ROOT))] = sha256(seed_path.read_bytes()).hexdigest()
        for key, path in row['evidence'].items():
            if sha256(Path(path).read_bytes()).hexdigest() != row['image_hashes'][key]:
                raise ValueError('Frozen image changed')
        with Image.open(row['evidence']['source_image']) as image:
            pixels = image.convert('RGB')
            group = sha256(str(pixels.size).encode()+pixels.tobytes()).hexdigest()
        if group != row['group'] or group in groups:
            raise ValueError('Changed or repeated source-pixel group')
        groups.add(group)
        rows.append(row)
    if len(rows) != (1 if chalk_only else 3):
        raise ValueError('Unexpected frozen experiment cases')
    if importlib.metadata.version('textgrad') != '0.1.8':
        raise ValueError('Expected TextGrad 0.1.8')
    package = Path(importlib.util.find_spec('textgrad').origin).parent
    dependencies = {'textgrad': '0.1.8', 'hashes': {str(p.relative_to(package)): sha256(p.read_bytes()).hexdigest()
                    for p in sorted(package.rglob('*.py'))}}
    hashes = code_hashes()
    hashes[str(Path(__file__).relative_to(ROOT))] = sha256(Path(__file__).read_bytes()).hexdigest()
    for folder, pattern in [('critical/core/prompts/templates/forced_decomposition_v1','*.txt')]:
        for p in (ROOT/folder).glob(pattern):hashes[str(p.relative_to(ROOT))] = sha256(p.read_bytes()).hexdigest()
    n = len(rows)
    manifest = {'version':'forced-decomposition-pilot-v1','scope':SCOPE,'contract':CONTRACT,
        'model':'gpt-6-luna','provider':'openai','temperature':0,'reasoning_effort':'none','random_seed':20261008,
        'cases':rows,'arms':list(ARMS),'policy':asdict(RobustPolicy()),'round_batches':[1,2],
        'proposals_per_batch':2,'scope_limits':{'search':109,'final':40},'max_calls':300*n,
        'max_completion_tokens':384000*n,'reserve_calls':80*n,'reserve_tokens':81920*n,
        'shared_calls_per_case':2,'max_checks':4,'minimum_supports':2,'final_repeats':5,
        'planned_maximum_calls': 2*n*(109+40)+2*n,
        'chalk_only':chalk_only,'source_manifest_sha256':sha256((SOURCE/'manifest.json').read_bytes()).hexdigest(),
        'seed_source_hashes':source_hashes,'code_hashes':hashes,'dependencies':dependencies}
    output=Path(output); path=output/'manifest.json'
    if path.exists():
        if json.loads(path.read_text()) != manifest:
            raise ValueError('Frozen configuration, code, sources or dependency changed; cannot resume')
    else:
        save_json(path,manifest)
        for relative in hashes:
            dest=output/'source_snapshot'/relative;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes((ROOT/relative).read_bytes())
    return manifest


def write_report(output,result,manifest):
    output=Path(output); count=len(manifest['cases'])
    summary={}
    for arm in manifest['arms']:
        rows=[result['cases'].get(c['id'],{}).get(arm,{}) for c in manifest['cases']]
        summary[arm]={'cases':count,'robust_cases':sum(r.get('support_status')=='locally_robust' for r in rows)}
        for which in ('seed','selected'):
            summary[arm][which]={k:sum(r.get('final',{}).get(which,{}).get(k,0) for r in rows)/count
                for k in ('agreement','coverage','label_consistency','requirement_consistency','mean_checks','mean_completion_tokens')}
    lines=['# Forced decomposition versus broad checking','',manifest['scope'],'','Status: '+result['status'],'',
        '| Method | Seed → selected reference agreement | Selected usable answers | Robust cases | Mean selected checks |',
        '|---|---:|---:|---:|---:|']
    for arm,s in summary.items():
        lines.append(f"| {arm} | {s['seed']['agreement']:.1%} → {s['selected']['agreement']:.1%} | {s['selected']['coverage']:.1%} | {s['robust_cases']}/{count} | {s['selected']['mean_checks']:.2f} |")
    lines+=['','Agreement = matching the reference; coverage = usable final answers, including incorrect ones. '
        'Consistency = most common usable answer frequency. Confidence = model self-report. Each case uses five fresh final draws per program. '
        'A robust case passes every original acceptance gate. Failed/missing draws remain nonmatches.','',
        '| Case | Method | Seed matches / 5 | Selected matches / 5 | Selected usable / 5 | Lowest available confidence | Check consistency | Status / reasons |',
        '|---|---|---:|---:|---:|---:|---|---|']
    for case in manifest['cases']:
        for arm in manifest['arms']:
            row=result['cases'].get(case['id'],{}).get(arm,{})
            a,b=(row.get('final',{}).get(k,{}) for k in ('seed','selected'))
            confidence=[o['confidence'] for t in b.get('traces',[]) for o in t['observations'] if o['queried'] and o['confidence'] is not None]
            count_matches=lambda r:str(round(5*r.get('agreement',0)))
            reasons=', '.join(row.get('acceptance',{}).get('reasons',[])) or row.get('error','none')
            consistency=json.dumps({k:v['consistency'] for k,v in b.get('nodes',{}).items()})
            lines.append('| '+' | '.join([case['instruction'],arm,count_matches(a),count_matches(b),
                str(round(5*b.get('coverage',0))),str(min(confidence)) if confidence else 'missing',consistency,
                row.get('support_status','unattempted')+'; '+reasons])+' |')
    fidelity={}
    for which in ('seed','selected'):
        same=resolved=total=0; per_case=[]
        for c in manifest['cases']:
            arms=result['cases'].get(c['id'],{})
            reports=[arms.get(arm,{}).get('final',{}).get(which,{}) for arm in manifest['arms']]
            labels=[[t['label'] for t in r.get('traces',[])] for r in reports]
            matches=both=0
            for i in range(5):
                pair=[lst[i] if len(lst)>i else None for lst in labels]
                both+=all(v is not None for v in pair)
                matches+=all(v is not None for v in pair) and pair[0]==pair[1]
            same+=matches;resolved+=both;total+=5
            per_case.append({'case_id':c['id'],'same_index_matches':matches,'both_resolved':both,'draw_pairs':5})
        fidelity[which]={'agreement':same/total,'both_resolved':resolved/total,'per_case':per_case,
            'interpretation':'Descriptive same-index comparison of stochastic executions, not an independent sample of cases.'}
    lines+=['','## Broad versus decomposed scoring fidelity','',json.dumps(fidelity,indent=2),'',
        'The evidence checks inspect images independently. The decomposed readout receives no images and must acknowledge every saved dependency. '
        'Known negative support evidence remains usable. Unknown necessary evidence blocks the readout. '
        'This first experiment tests an ordered evidence chain, not conditional shortcutting. '
        'Structural guards and semantic audits do not prove atomic reasoning or semantic equivalence.','',
        'Budget: '+json.dumps(result.get('budget',{}).get('limits',{})),
        'Usage: '+json.dumps({k:v for k,v in result.get('budget',{}).items() if k not in ('limits','cases','attempted_slots')}),
        'Returned models: '+json.dumps(result.get('returned_models',[]))]
    save_json(output/'summary.json',summary);save_json(output/'scoring_fidelity.json',fidelity)
    (output/'report.md').write_text('\n'.join(lines)+'\n')


def execute(output,manifest,engine_factory):
    output=Path(output);policy=RobustPolicy(**manifest['policy'])
    calls=DurableCalls(output,engine_factory,identity={k:manifest[k] for k in ('model','provider','temperature','reasoning_effort')},
        **{k:manifest[k] for k in ('max_calls','max_completion_tokens','reserve_calls','reserve_tokens','scope_limits')})
    checkpoint=CheckpointStore(output/'observations.jsonl')
    result={'status':'running','scope':manifest['scope'],'cases':{r['id']:{} for r in manifest['cases']}}
    bundle={'version':ROBUST_VERSION,'nodes':{},'programs':{}}
    def persist():
        result['budget']=deepcopy(calls.budget)
        result['returned_models']=sorted({j['response'].get('model','unavailable') for p in (output/'jobs').glob('*.json')
            if (j:=json.loads(p.read_text())).get('response')})
        save_json(output/'results.json',result)
        if bundle['nodes']:save_json(output/'leaves.json',validate_program_leaves(bundle))
        write_report(output,result,manifest)
    try:
        for i,raw in enumerate(manifest['cases']):
            case=Case(raw['id'],raw['instruction'],raw['evidence'],raw['group'])
            original=restore_program(raw['broad_seed'])
            prepared_path=output/'prepared'/f'{i}.json'
            if prepared_path.exists():prepared=json.loads(prepared_path.read_text())
            else:
                compiler=DecompositionCompiler(CaseCalls(calls,'prepare/'+case.id),original)
                prepared={'broad':raw['broad_seed']}
                decomposed=None
                try:
                    decomposed=compiler.compile_from(slot='decompose')
                    prepared['decomposed']=export_program(decomposed)
                except (CallFailure,ValueError,TypeError,KeyError,BudgetExhausted) as exc:
                    prepared['decomposition_error']=f'{type(exc).__name__}: {exc}'
                try:prepared['audits']=compiler.audit_pair(decomposed,slot='audit_pair')
                except (CallFailure,ValueError,TypeError,KeyError,BudgetExhausted) as exc:
                    prepared['audit_error']=f'{type(exc).__name__}: {exc}'
                save_json(prepared_path,prepared)
            order=manifest['arms'][i%2:]+manifest['arms'][:i%2]
            for arm in order:
                kind=arm.split('-')[0];path=output/'frozen'/arm/f'{i}.json'
                if not path.exists():
                    if kind not in prepared or 'audits' not in prepared or kind not in prepared['audits']:
                        error = prepared.get('audit_error') or (prepared.get('decomposition_error') if kind=='decomposed' else None)
                        save_json(path,{'error':error or 'Invalid shared preparation'})
                    else:
                        scoped=CaseCalls(calls,arm+'/'+case.id)
                        compiler=DecompositionCompiler(scoped,original) if kind=='decomposed' else BroadCompiler(scoped,original)
                        checker=DecompositionChecker(scoped) if kind=='decomposed' else RobustChecker(scoped)
                        proposer=DecompositionProposer(scoped) if kind=='decomposed' else StructuralProposer(scoped)
                        evaluator=RobustEvaluator(RobustExecutor(checker,checkpoint=checkpoint),policy)
                        optimizer=RobustLeafOptimizer(compiler,proposer,evaluator,NodeTextGrad(scoped),rubric=raw['rubric'],
                            selection='greedy',mode='tree',random_seed=manifest['random_seed']+i,seed_audit=prepared['audits'][kind])
                        local=CaliTreeBuilder.build_program_leaves([case],reference_labels={case.id:raw['target']},
                            optimizer_factory=lambda _:optimizer,seeds={case.id:restore_program(prepared[kind])})
                        save_json(path,local)
                print(json.dumps({'phase':'frozen','case':i+1,'arm':arm,'calls':calls.budget['calls']}),flush=True)
                persist()
        # No search/feedback after this point. Every case-arm selection is frozen.
        for i,raw in enumerate(manifest['cases']):
            original=restore_program(raw['broad_seed']);case=Case(raw['id'],raw['instruction'],raw['evidence'],raw['group'])
            order=manifest['arms'][i%2:]+manifest['arms'][:i%2]
            for arm in order:
                kind=arm.split('-')[0];local=json.loads((output/'frozen'/arm/f'{i}.json').read_text())
                row={'support_status':'unresolved','final':{}};result['cases'][case.id][arm]=row
                if 'error' in local:
                    row['error']=local['error'];persist();continue
                validate_program_leaves(local);node=local['nodes']['leaf:'+case.id]
                row.update(search_status=node['result']['status'],stop_reason=node['result']['stop_reason'])
                scoped=CaseCalls(calls,arm+'/'+case.id)
                checker=DecompositionChecker(scoped) if kind=='decomposed' else RobustChecker(scoped)
                evaluator=RobustEvaluator(RobustExecutor(checker,checkpoint=checkpoint),policy)
                for which in ('seed','selected'):
                    artifact=node['result'][which]
                    if artifact is None:continue
                    program=restore_program(artifact)
                    (validate_decomposition if kind=='decomposed' else validate_broad)(program,original)
                    row['final'][which]=evaluator.evaluate(program,case,raw['target'],repeats=5,
                        namespace=f'final/{which}/{arm}/{case.id}',final=True)
                    persist()
                if row['final'].get('selected'):
                    audit=node['result']['candidates'].get(node['program_ref'],{}).get('audit',{})
                    row['support_status'],row['acceptance']=status_for(row['final']['selected'],audit,policy)
                row['usage']=deepcopy(calls.budget.get('cases',{}).get(arm+'/'+case.id,{}))
                node.update(id=f'leaf:{arm}/{case.id}',support_status=row['support_status'],final_comparison=row['final'],arm=arm)
                bundle['nodes'][node['id']]=node;bundle['programs'].update(local['programs'])
                persist()
                print(json.dumps({'phase':'final','case':i+1,'arm':arm,'status':row['support_status'],'calls':calls.budget['calls']}),flush=True)
        result['status']='completed'
    except (ProviderStopped,BudgetExhausted,CallFailure,ValueError,KeyError,TypeError,RuntimeError) as exc:
        result.update(status='stopped',error=f'{type(exc).__name__}: {exc}')
    persist();return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    modes=parser.add_mutually_exclusive_group()
    for mode in ('preflight','live','report'):modes.add_argument('--'+mode,action='store_true')
    parser.add_argument('--chalk-only',action='store_true');parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    if args.report:
        write_report(args.output_dir,json.loads((args.output_dir/'results.json').read_text()),json.loads((args.output_dir/'manifest.json').read_text()));return
    if args.resume and not (args.output_dir/'manifest.json').exists():parser.error('Resume requires existing manifest')
    manifest=preflight(args.output_dir,chalk_only=args.chalk_only)
    if not args.live:
        print(json.dumps({'status':'ready','cases':len(manifest['cases']),'arms':manifest['arms'],'max_calls':manifest['max_calls']}));return
    from critical.lm_engine import get_engine,load_creds,require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True);creds=load_creds(engine='gpt',provider='openai')
    if creds.provider!='openai' or creds.endpoints!=['https://api.openai.com/v1']:raise ValueError('Official OpenAI endpoint required; no fallback')
    history=LLMHistoryWriter(args.output_dir/'llm-histories.log')
    result=execute(args.output_dir,manifest,lambda cap:get_engine('gpt',model=manifest['model'],creds=creds,
        history=history,max_tokens=cap,temperature=0,max_http_attempts=1,timeout=60))
    print(json.dumps({'status':result['status'],'error':result.get('error'),'output':str(args.output_dir)}))

if __name__=='__main__':main()
