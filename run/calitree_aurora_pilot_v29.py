"""Prepare a source-audited 80-output AURORA pilot; no inference by default."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from statistics import mean
import json
import math

from PIL import Image

from critical.core.decision.artifacts import digest, save_json
from critical.database.dl_aurora.loader import AURORA_MODELS, AURORA_TASKS
from run.calitree_task_coverage import ROOT, IDENTITY, read, fingerprint, exact
from run import calitree_m0 as exposure

VERSION = 'aurora-source-audited-pilot-v29'
SEED = 20261020
CAPS = {'compile':8192,'repair':8192,'observe':16384,'interpret':8192,'regular':2048}
PRICING = {'model':'gpt-6-luna','currency':'USD','input_per_million':0.10,'cache_write_per_million':0.125,
           'output_per_million':0.50,'processing':'Standard, short context, no regional premium',
           'source':'https://developers.openai.com/api/docs/models/gpt-6-luna',
           'checked_on':'2026-10-20','caveat':'No cache discounts assumed. Input forecast uses measured billed prompt tokens including image input, not an unverified image-token formula.'}


def audit_sources(out, source_root):
    original_root,original_data,original_files=exposure.ROOT,exposure.DATA,exposure.files_to_audit
    try:
        exposure.DATA=source_root/'data/aurora/bench'
        exposure.files_to_audit=lambda ignored: original_files(out)
        for name,root in (('original',source_root),('worktree',ROOT)):
            exposure.ROOT=root
            target=out/'exposure'/name
            ledger=exposure.audit_exposure(target)
            save_json(target/'scan_context.json',{'root':str(root),'excluded_output':str(out),'auditor_sha256':fingerprint(exposure.__file__)})
    finally:
        exposure.ROOT,exposure.DATA,exposure.files_to_audit=original_root,original_data,original_files


def combine_exposure(out, source_root):
    ledgers={name:read(out/'exposure'/name/'exposure_ledger.json') for name in ('original','worktree')}
    by_uid={t['task_uid']:deepcopy(t) for t in ledgers['original']['tasks']}
    if set(by_uid)!={t['task_uid'] for t in ledgers['worktree']['tasks']}:
        raise ValueError('Exposure catalogs differ')
    for uid,t in by_uid.items():t['events_by_root']={};t['used']=False
    errors=[];unresolved=[]
    for name,ledger in ledgers.items():
        for t in ledger['tasks']:
            other=by_uid[t['task_uid']]
            if other['source_group']!=t['source_group'] or other['outputs']!=t['outputs']:
                raise ValueError('Changed dataset between exposure scans')
            other['events_by_root'][name]=t['events'];other['used'] |= t['status']!='no_exposure_found'
        errors.extend({'root':name,**e} for e in ledger['parse_errors'])
        unresolved.extend({'root':name,**e} for e in ledger['unresolved_aliases'])
    # Conservatively exclude any identified task in malformed records too.
    for e in errors:
        for uid in e.get('aurora_references',[]):
            if uid in by_uid:by_uid[uid]['used']=True
    used_groups={t['source_group']for t in by_uid.values() if t['used']}
    for t in by_uid.values():t['used'] |= t['source_group'] in used_groups
    summary={'catalog_tasks':len(by_uid),'catalog_source_groups':len({t['source_group']for t in by_uid.values()}),
             'historically_used_tasks':sum(t['used']for t in by_uid.values()),'historically_used_source_groups':len(used_groups),
             'no_exposure_found_tasks':sum(not t['used']for t in by_uid.values()),
             'no_exposure_found_by_category':dict(Counter(t['task']for t in by_uid.values()if not t['used'])),
             'files_scanned':{k:len(v['files'])for k,v in ledgers.items()},
             'parse_errors':errors,'unresolved_aliases':unresolved,
             'scope':'Repository artifacts in the original checkout and this worktree; no claim about outside records. Unresolved aliases are disclosed.'}
    return by_uid,summary


def select_tasks(tasks, *, allow_used=False, excluded_groups=(), per_category=2):
    selected=[];seen=set(excluded_groups);shortages={}
    for category in AURORA_TASKS:
        eligible=sorted((t for t in tasks.values()if t['task']==category and (allow_used or not t['used'])),
                        key=lambda t:(t['used'],digest([VERSION,SEED,t['task_uid']])))
        count=0
        for task in eligible:
            if task['source_group'] in seen:continue
            if len(task['outputs'])!=5 or {o['editor']for o in task['outputs']}!=set(AURORA_MODELS):
                continue
            if len({o['instruction']for o in task['outputs']})!=1:
                raise ValueError('Task outputs have inconsistent instructions')
            selected.append(task);seen.add(task['source_group']);count+=1
            if count==per_category:break
        if count<per_category:shortages[category]={'requested':per_category,'available':count}
    return selected,shortages


def recent_exclusions(source_root):
    path=source_root/'logs/exps/261018-three-sampled-splits-luna-compiler-v3/manifest.json'
    manifest=read(path)
    groups=set(manifest['excluded_groups']) | {r['group']for r in manifest['cases']}
    return groups, {'manifest':str(path),'sha256':fingerprint(path),'excluded_source_groups':sorted(groups),
                    'meaning':'All sources in the recent compiler-v3 study, plus its declared exclusions including earlier development/reservation sources.'}


def historical_usage(source_root):
    roots=[source_root/'logs/exps/261018-three-sampled-splits-luna-compiler-v3',ROOT/'logs/exps/261019-task-coverage-v19-r3']
    observations=defaultdict(list);files={}
    stages={'bound_instruction_v3':'compile','bound_visual_observation_v2':'observe',
            'instruction_relative_interpretation':'interpret','flat_judge':'regular'}
    for root in roots:
        for p in sorted(root.rglob('jobs/*.json')):
            r=read(p);v=r.get('response',{});stage=stages.get(r.get('stage'))
            if stage and r.get('outcome')=='completed' and v.get('model')==IDENTITY['model']:
                vals=(v.get('promptTokens'),v.get('completionTokens'))
                if all(type(x)is int and x>=0 for x in vals):
                    observations[stage].append(vals);files[str(p)]=fingerprint(p)
    if set(observations)!=set(stages.values()):raise ValueError('Missing comparable billed token history')
    summary={}
    for stage,rs in observations.items():
        summary[stage]={'count':len(rs),'mean_input':mean(r[0]for r in rs),'mean_output':mean(r[1]for r in rs),
                        'p90_input':sorted(r[0]for r in rs)[math.ceil(.9*len(rs))-1],
                        'p90_output':sorted(r[1]for r in rs)[math.ceil(.9*len(rs))-1]}
    return summary,files


def estimate(cases, instructions, usage):
    counts={'compile':instructions,'observe':cases,'interpret':cases,'regular':cases}
    scenarios={}
    for name,prefix,rate in (('historical_mean','mean',PRICING['input_per_million']),
                             ('historical_p90','p90',PRICING['input_per_million']),
                             ('p90_with_all_input_at_cache_write_rate','p90',PRICING['cache_write_per_million'])):
        inp=sum(n*usage[s][prefix+'_input']for s,n in counts.items());output=sum(n*usage[s][prefix+'_output']for s,n in counts.items())
        scenarios[name]={'estimated_input_tokens':round(inp),'estimated_output_tokens':round(output),
                         'estimated_usd':round((inp*rate+output*PRICING['output_per_million'])/1e6,4)}
    max_output=sum(n*CAPS[s]for s,n in counts.items())+instructions*CAPS['repair']
    return {'stage_requests_without_repairs':counts,'expected_requests':sum(counts.values()),
            'max_requests':sum(counts.values())+instructions,'max_completion_tokens':max_output,
            'completion_cap_cost_usd':max_output*PRICING['output_per_million']/1e6,
            'scenarios':scenarios,'pricing':PRICING,
            'note':'Forecast, not a total dollar cap. Repair calls, differing image/input lengths and provider cache accounting can change charges. Completion ceiling excludes input cost. No retries, repeats or per-gate model calls.'}


def freeze(out, source_root, tasks, summary, selected, exclusion):
    if len(selected)!=16 or len({t['source_group']for t in selected})!=16:raise ValueError('Sixteen distinct source groups required')
    if set(t['source_group']for t in selected)&set(exclusion['excluded_source_groups']):raise ValueError('Pilot overlaps recent study sources')
    input_cases=[];references={};instructions={};media_hashes={}
    data=source_root/'data/aurora/bench'
    for task_index,t in enumerate(selected,1):
        for model_index,output in enumerate(sorted(t['outputs'],key=lambda o:AURORA_MODELS.index(o['editor'])),1):
            case=f'P{task_index:02d}M{model_index}';instruction=output['instruction'];compilation_ref=digest(instruction)
            instructions[compilation_ref]={'instruction':instruction}
            evidence={'source_image':str(data/t['source_path']),'edited_image':str(data/output['edited_path'])}
            image_hashes={}
            for key,path in evidence.items():
                with Image.open(path) as image: image.verify()
                image_hashes[key]=fingerprint(path);media_hashes[path]=image_hashes[key]
            if image_hashes['source_image']!=t['source_sha256'] or image_hashes['edited_image']!=output['edited_sha256']:
                raise ValueError('Changed selected image')
            input_cases.append({'case':case,'task_uid':t['task_uid'],'source_group':t['source_group'],'task':t['task'],
                                'editor':output['editor'],'instruction':instruction,'compilation_ref':compilation_ref,
                                'evidence':evidence,'image_hashes':image_hashes,'historical_exposure':'historically_referenced' if t['used'] else 'no_exposure_found'})
            references[case]={'reference':output['reference'],'human_score':output['human_score'],'item_id':output['item_id']}
    if len(input_cases)!=80:raise ValueError('Expected 80 outputs')
    usage,usage_files=historical_usage(source_root);cost=estimate(80,len(instructions),usage)
    gates={};gate_files={}
    for version,directory in (('v27','261020-shared-regions-v27-r1'),('v28','261020-semantic-region-merge-v28-r2')):
        parent=ROOT/'logs/exps'/directory
        for name,expected in read(parent/'completion_seal.json')['files'].items():
            assert fingerprint(parent/name)==expected
        for i in (1,2,3):
            p=parent/f'split{i}/gate.json';artifact=read(p)
            exact(out/f'gates/{version}_split{i}.json',artifact)
            gates[f'{version}_split{i}']=artifact['artifact_ref'];gate_files[str(p)]=fingerprint(p)
    protocol={'version':VERSION,'identity':IDENTITY,'seed':SEED,'tasks':16,'cases':80,'categories':dict(Counter(c['task']for c in input_cases)),
              'arms':['regular','v27','v28'],'expert_bank_replicates':3,'independent_source_groups':16,
              'collection':'Compile each unique instruction once (one validator repair allowed); fresh observe/interpret and one regular judgment per output. Share evidence and exact regular fallback across all six frozen gates.',
              'failures':'No retries or replacements. Extraction failures fall back; invalid regular responses remain unresolved and count as incorrect.',
              'evaluation':'No fitting or threshold changes. Report accepted precision, coverage, accuracy, macro-F1, per-class/editor/task breakdowns and v28-only acceptances. Cluster uncertainty by source, not output or bank replica.',
              'caps':CAPS,'max_requests':cost['max_requests'],'max_completion_tokens':cost['max_completion_tokens'],
              'temperature':0,'new_model_calls_at_preparation':0,'preflight_ready':True,
              'exposure_policy':'User authorized older exposure after audit found only eight unused tasks. Prefer unused tasks; exclude all recent study and declared-exclusion source groups.',
              'historical_source_counts':dict(Counter('historically_referenced' if t['used'] else 'no_exposure_found' for t in selected)),
              'live_authorization':'Preparation only; a separate explicit authorization is required before collection.'}
    sources={str(data/'metadata.jsonl'):fingerprint(data/'metadata.jsonl'),exclusion['manifest']:exclusion['sha256'],**gate_files,**usage_files,
             **{str(out/'exposure'/name/'exposure_ledger.json'):fingerprint(out/'exposure'/name/'exposure_ledger.json')for name in('original','worktree')}}
    code=[Path(__file__).resolve(),Path(exposure.__file__).resolve()]
    code+=list((ROOT/'critical/core/decision').glob('*.py'))
    code+=list((ROOT/'critical/core/calibration/semantic_hierarchy').glob('*.py'))
    code += [ROOT/p for p in ('critical/core/calibration/shared_regions_v27.py','critical/core/calibration/semantic_region_merge_v28.py',
                              'critical/core/optimization/prompt/calitree/evidence_covered_judge.py','critical/core/optimization/prompt/calitree/task_coverage.py',
                              'critical/lm_engine/lm_gpt/engine.py','critical/lm_engine/openai_compat.py','critical/lm_engine/provider_api.py')]
    code+=list((ROOT/'critical/core/prompts/templates/bound_compiler_v3').glob('*.txt'))
    code+=list((ROOT/'critical/core/prompts/templates/bound_evidence_v2').glob('*.txt'))
    code+=list((ROOT/'critical/core/prompts/templates/task_coverage_v19').glob('*.txt'))
    exact(out/'recent_source_exclusions.json',exclusion)
    manifest={'version':VERSION,'source_root':str(source_root),'protocol_ref':digest(protocol),'gates':gates,
              'source_hashes':sources,'code_hashes':{str(p.relative_to(ROOT)):fingerprint(p)for p in sorted(set(code))},
              'image_hashes':media_hashes,'inputs_ref':digest(input_cases),'references_ref':digest(references),'instructions_ref':digest(instructions),'exclusions_ref':digest(exclusion)}
    for name,value in [('inputs',input_cases),('references',references),('instructions',instructions),('usage_history',usage),('estimate',cost),('protocol',protocol),('manifest',manifest)]:
        exact(out/(name+'.json'),value)
    return verify(out)


def verify(out):
    m=read(out/'manifest.json');protocol=read(out/'protocol.json');cases=read(out/'inputs.json');refs=read(out/'references.json');instructions=read(out/'instructions.json')
    assert digest(protocol)==m['protocol_ref'] and digest(cases)==m['inputs_ref'] and digest(refs)==m['references_ref'] and digest(instructions)==m['instructions_ref']
    for p,expected in m['source_hashes'].items():assert fingerprint(p)==expected,p
    for p,expected in m['code_hashes'].items():assert fingerprint(ROOT/p)==expected,p
    for p,expected in m['image_hashes'].items():assert fingerprint(p)==expected,p
    tasks,summary=combine_exposure(out,Path(m['source_root']));excluded,exclusion=recent_exclusions(Path(m['source_root']))
    assert digest(exclusion)==m['exclusions_ref'] and exclusion==read(out/'recent_source_exclusions.json')
    selected,shortages=select_tasks(tasks,allow_used=True,excluded_groups=excluded)
    assert not shortages and {t['task_uid']for t in selected}=={c['task_uid']for c in cases}
    assert len(cases)==80 and len({c['source_group']for c in cases})==16
    assert set(refs)=={c['case']for c in cases} and all(not {'reference','human_score','target_label'}&set(c)for c in cases)
    for uid in {c['task_uid']for c in cases}:
        group=[c for c in cases if c['task_uid']==uid];assert len(group)==5 and {c['editor']for c in group}==set(AURORA_MODELS)
        assert tasks[uid]['source_group'] not in excluded
        assert all(c['historical_exposure']==('historically_referenced' if tasks[uid]['used'] else 'no_exposure_found')for c in group)
    assert Counter(c['task']for c in cases)=={k:10 for k in AURORA_TASKS}
    for name,expected in m['gates'].items():
        artifact=read(out/'gates'/(name+'.json'));assert artifact['artifact_ref']==expected
        if name.startswith('v27'):
            from critical.core.calibration.shared_regions_v27 import SharedRegionGate
            SharedRegionGate(artifact)
        else:
            from critical.core.calibration.semantic_region_merge_v28 import SemanticMergedRegionGate
            SemanticMergedRegionGate(artifact)
    cost=estimate(80,len(instructions),read(out/'usage_history.json'));assert cost==read(out/'estimate.json')
    report={'passed':True,'cases':80,'distinct_source_groups':16,'tasks_per_category':2,'editors_per_task':5,'frozen_gate_artifacts':6,
            'previously_referenced_selected_sources':sum(t['used']for t in selected),'recent_study_source_overlap':0,'new_model_calls':0,'max_requests':cost['max_requests'],
            'max_completion_tokens':cost['max_completion_tokens'],'scope':summary['scope']}
    exact(out/'preflight_verification.json',report)
    if (out/'preflight_seal.json').exists():
        for name,expected in read(out/'preflight_seal.json')['files'].items():assert fingerprint(out/name)==expected,name
    else:
        save_json(out/'preflight_seal.json',{'files':{str(p.relative_to(out)):fingerprint(p)for p in sorted(out.rglob('*'))if p.is_file()and p.name!='preflight_seal.json' and not {'ledger','collection'} & set(p.relative_to(out).parts)}})
    return report


def prepare(out, source_root):
    tasks,summary=combine_exposure(out,source_root)
    fresh,fresh_shortages=select_tasks(tasks)
    excluded,exclusion=recent_exclusions(source_root)
    selected,shortages=select_tasks(tasks,allow_used=True,excluded_groups=excluded)
    summary['fresh_category_shortages']=fresh_shortages
    summary['recent_excluded_source_groups']=len(excluded)
    summary['selected_sources_with_older_exposure']=sum(t['used']for t in selected)
    summary['requested_category_shortages']=shortages
    save_json(out/'exposure_summary.json',summary)
    save_json(out/'eligible_tasks.json',[{'task_uid':t['task_uid'],'task':t['task'],'source_group':t['source_group']}for t in tasks.values()if not t['used']])
    if shortages:
        usage,files=historical_usage(source_root)
        save_json(out/'usage_history.json',usage);save_json(out/'estimate.json',estimate(80,16,usage))
        save_json(out/'readiness.json',{'ready':False,'reason':'Insufficient source-disjoint, historically unused tasks for two per category.',
                   'shortages':shortages,'available_selected_tasks':len(selected),'new_model_calls':0})
        print({'ready':False,'shortages':shortages,'available_selected_tasks':len(selected)},flush=True)
        return
    save_json(out/'readiness.json',{'ready_for_review':True,'paid_calls_made':0,'live_authorization_required':True})
    print(freeze(out,source_root,tasks,summary,selected,exclusion),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--source-root',type=Path);p.add_argument('--audit',action='store_true');p.add_argument('--verify',action='store_true');a=p.parse_args()
    out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    if a.verify:print(verify(out),flush=True)
    elif a.source_root is None:p.error('--source-root is required')
    else:
        if a.audit:audit_sources(out,a.source_root.resolve())
        prepare(out,a.source_root.resolve())
