"""Label-free agreement of two independently bound local observation profiles."""
import argparse
from collections import Counter
from pathlib import Path
import shutil

from critical.core.decision import local_rubric_evidence_v94 as facts
from critical.core.calibration.local_warranted_rubric_v97 import claims
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash


def read(path):
    import json
    return json.loads(Path(path).read_text())


def audit(previous,current,out):
    if out.exists():
        raise ValueError('Fresh agreement snapshot required')
    old_jobs={j['case']:j for j in read(previous/'jobs.json')};new_jobs={j['case']:j for j in read(current/'jobs.json')}
    assert set(old_jobs)==set(new_jobs) and len(old_jobs)==224
    old_profile=read(previous/'identity.json');new_profile=read(current/'identity.json')
    assert digest(old_profile)==read(previous/'manifest.json')['identity_ref'] and digest(new_profile)==read(current/'manifest.json')['identity_ref']
    paths=sorted((current/'responses').glob('*.json'));rows=[];transitions={field:Counter() for field in facts.FIELDS};changes=Counter();flag_changes={};hashes={}
    for path in paths:
        case=path.stem;before_job=old_jobs[case];after_job=new_jobs[case]
        assert all(before_job[key]==after_job[key] for key in ('case','program','image_pair_ref','prompt','prompt_ref','schema','evidence'))
        old_path=previous/'responses'/(case+'.json');old=read(old_path);new=read(path)
        assert old['request_ref']==before_job['request_ref'] and new['request_ref']==after_job['request_ref']
        hashes[str(old_path)]=file_hash(old_path);hashes[str(path)]=file_hash(path)
        row={'case':case,'old_accepted':old['record'] is not None,'new_accepted':new['record'] is not None}
        for job,response,profile in ((before_job,old,old_profile),(after_job,new,new_profile)):
            assert digest({k:v for k,v in job.items() if k!='request_ref'})==job['request_ref']
            if response['record'] is not None:
                facts.project(job['program'],job['image_pair_ref'],digest(profile),job['prompt_ref'],response['record'])
        if row['old_accepted'] and row['new_accepted']:
            a=old['record']['observation'];b=new['record']['observation'];changed=[k for k in facts.FIELDS if a[k]!=b[k]]
            for k in facts.FIELDS:
                transitions[k][a[k]+' -> '+b[k]]+=1
            changes.update(changed);row['changed_fields']=changed
            old_flags=claims(before_job['program'],a);new_flags=claims(after_job['program'],b)
            for flag in ('local_claim_conflict','local_any_uncertainty','local_no_ready','local_partial_ready','local_yes_ready'):
                flag_changes.setdefault(flag,Counter())[(bool(old_flags[flag]),bool(new_flags[flag]))]+=1
        rows.append(row)
    paired=[r for r in rows if r['old_accepted'] and r['new_accepted']];complete=read(current/'results.json')['complete'] if (current/'results.json').exists() else False
    summary={'snapshot_only':not complete,'current_collection_complete':complete,'current_responses':len(rows),'current_accepted':sum(r['new_accepted'] for r in rows),
        'both_accepted':len(paired),'same_all_seven_fields':sum(not r['changed_fields'] for r in paired),'changed_any_field':sum(bool(r['changed_fields']) for r in paired),
        'changed_per_field':dict(changes),'field_transitions':{k:dict(sorted(v.items())) for k,v in transitions.items()},
        'warrant_transitions':{k:{str(a)+' -> '+str(b):count for (a,b),count in sorted(v.items())} for k,v in flag_changes.items()},
        'human_references_read':0,'new_model_calls':0,'reserved_sources_used':0,'accuracy_claim':False,
        'scope':'Label-free paired model-claim agreement. A partial prefix is not representative; changed claims do not establish improvement or factual correctness. No controllers are fitted or modified.'}
    out.mkdir(parents=True);save_json(out/'results.json',summary);save_json(out/'cases.json',rows)
    for cache in(previous,current):
        for name in('jobs.json','manifest.json','identity.json'):
            hashes[str(cache/name)]=file_hash(cache/name)
    save_json(out/'manifest.json',{'code_sha256':file_hash(__file__),'source_hashes':hashes,'old_identity_ref':digest(old_profile),'new_identity_ref':digest(new_profile)})
    dest=out/'source_snapshot/run'/Path(__file__).name;dest.parent.mkdir(parents=True);shutil.copyfile(__file__,dest)
    (out/'run.log').write_text('Paired own-profile bindings and seven-field/derived-warrant agreement checked without human references. Not an accuracy result.\n');(out/'llm-histories.log').write_text('No calls or extraction. Read only completed cached response slots.\n')
    print({k:summary[k] for k in('snapshot_only','current_responses','current_accepted','both_accepted','same_all_seven_fields','changed_any_field','changed_per_field')},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in('previous-cache','current-cache','output-dir'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();audit(a.previous_cache.resolve(),a.current_cache.resolve(),a.output_dir.resolve())
