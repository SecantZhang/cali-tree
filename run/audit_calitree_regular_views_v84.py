"""Find reusable generic visual-judge views for the current915 fitting inputs.

Metadata and request identities only. Never calls a model, reads human labels,
or reuses a fitted/example-conditioned prompt as an independent regular judge.
"""
import argparse
from collections import Counter,defaultdict
from pathlib import Path
import subprocess

from critical.core.decision.artifacts import digest,save_json
from critical.core.decision.compiler import media_inputs
from critical.core.optimization.prompt.calitree import task_coverage as task
from run.calitree_aurora_pilot_v29 import ROOT,read,fingerprint


def media_identity(evidence,hashes):
    return [{'type':'image','sha256':hashes[m['path']]} if m['type']=='image' else m for m in media_inputs(evidence)]


def audit(roots,out):
    if out.exists():raise ValueError('Fresh audit directory required')
    frozen=ROOT/'logs/exps/261021-frozen-visual-policy-v69';vision=ROOT/'logs/exps/261021-paired-vision-v63'
    hashes=read(vision/'manifest.json')['image_hashes']
    raw=read(frozen/'replay_inputs_without_references.json')
    primary={case for f in read(ROOT/'logs/exps/261021-visual-policy-v64/folds.json') if f['candidate']=='boost_full_vision' for case in f['held_cases']}
    assert len(primary)==276
    expected={};instructions=defaultdict(list)
    for entry in raw:
        media=media_identity(entry['evidence'],hashes)
        expected[entry['case']]=media;instructions[entry['program']['instruction']].append(entry['case'])
    budgets=subprocess.run(['rg','--files','--no-ignore',*map(str,roots),'-g','budget.json'],capture_output=True,text=True,check=True).stdout.splitlines()
    prompt=(task.TEMPLATES/'regular.txt').read_text();counts=Counter();matches=defaultdict(dict)
    out.mkdir(parents=True);(out/'run.log').write_text('Audit historical generic regular-judge slots, before scoring or reusing outcomes.\n');(out/'llm-histories.log').write_text('Zero API calls; no human references or images read.\n')
    for index,file in enumerate(sorted(budgets)):
        path=Path(file)
        try:budget=read(path)
        except (OSError,ValueError):counts['invalid_budget']+=1;continue
        identity=budget.get('limits',{}).get('identity') if isinstance(budget,dict) else None
        if not isinstance(identity,dict):continue
        counts['durable_ledgers']+=1
        for job in sorted((path.parent/'jobs').glob('*.json')):
            counts['job_files']+=1
            r=read(job)
            if not isinstance(r,dict) or r.get('stage')!='flat_judge':continue
            payload=r.get('payload')
            if not isinstance(payload,dict) or set(payload)!={'instruction'}:continue
            cases=instructions.get(payload['instruction'],[])
            if not cases:continue
            counts['instruction_matches']+=1
            cases=[case for case in cases if r.get('media_identity')==expected[case]]
            if not cases:counts['different_media']+=1;continue
            counts['same_ordered_media_matches']+=1
            slot=digest([identity,r.get('case_id'),'flat_judge',payload,task.SCHEMA,prompt,r.get('media_identity'),r.get('slot'),r.get('max_tokens')])
            if slot!=job.stem or slot!=r.get('execution_ref'):
                counts['different_prompt_schema_or_protocol']+=1;continue
            # Equal execution refs copied into multiple studies are one view.
            for case in cases:
                matches[case].setdefault(slot,{'job':str(job.resolve()),'job_sha256':fingerprint(job),'ledger':str(path.resolve()),
                    'identity':identity,'slot_ref':slot,'outcome_status':r.get('outcome',{}).get('status') if isinstance(r.get('outcome'),dict) else r.get('outcome')})
        if index%500==0:print({'budget_files_processed':index+1,'budget_files':len(budgets),'jobs_scanned':counts['job_files']},flush=True)
    source_models=Counter();multiple={};other_models={}
    for case,views in matches.items():
        source_models.update((v['identity'].get('model','unknown') for v in views.values()))
        if case in primary and len(views)>1:multiple[case]=list(views.values())
        non_luna=[v for v in views.values() if v['identity'].get('model')!='gpt-6-luna']
        if case in primary and non_luna:other_models[case]=non_luna
    result={'counts':dict(counts),'budget_files':len(budgets),'matched_cases':len(matches),
        'matched_primary_cases':len(set(matches)&primary),'primary_cases_with_multiple_slots':len(multiple),
        'primary_cases_with_other_models':len(other_models),'models_by_unique_matched_slot':dict(source_models),
        'multiple_primary_views':multiple,'other_model_primary_views':other_models,
        'all_matches':{k:list(v.values()) for k,v in matches.items()},
        'new_api_calls':0,'human_references_read':False,'image_files_read':False,'reserved_cases_scored':0,
        'scope':'Only exact instruction, ordered image hashes and cryptographically matched generic regular prompt/schema slots. Different fitted prompts excluded. An alternative token cap/model identity is a separate expert, never a replacement baseline.',
        'roots':[str(p.resolve()) for p in roots]}
    save_json(out/'results.json',result)
    save_json(out/'manifest.json',{'auditor_sha256':fingerprint(__file__),'input_sha256':fingerprint(frozen/'replay_inputs_without_references.json'),
        'vision_manifest_sha256':fingerprint(vision/'manifest.json'),'regular_template_sha256':fingerprint(task.TEMPLATES/'regular.txt')})
    snapshot=out/'source_snapshot/run'/Path(__file__).name;snapshot.parent.mkdir(parents=True);snapshot.write_bytes(Path(__file__).read_bytes())
    (out/'run.log').write_text('Completed generic judge-view cache audit. No outcome labels scored or copied into a collector.\n')
    print({k:v for k,v in result.items() if k not in ('multiple_primary_views','other_model_primary_views','all_matches','roots')},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--search-root',type=Path,action='append',required=True);p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();audit(a.search_root,a.output_dir.resolve())
