"""Independently reconcile the frozen v75 pilot; never call or fit a model."""
import argparse
from collections import Counter
from pathlib import Path

from critical.core.decision.artifacts import digest,save_json
from critical.core.optimization.prompt.calitree import contrastive_rubric_v75 as rubric
from run.calitree_contrastive_pilot_v75 import verify,ARMS,LUNA,SOL,MAX_CALLS,MAX_OUTPUT
from run.calitree_semantic_rubric_v70 import ROOT,STUDY,read,fingerprint


def slot_ref(job):
    identity=SOL if job['route']=='sol' else LUNA
    media=[{'type':'image','sha256':fingerprint(m['path'])} if m['type']=='image' else m for m in job['media']]
    key=digest([identity,job['case'],'semantic_contrastive_v75',job['payload'],job['schema'],job['template'],media,job['arm'],job['max_tokens']])
    return digest([key,job['route']]) if job['route'] is not None else key


def validate_value(job,value):
    if job['arm']=='regular_luna':
        if not isinstance(value,dict) or set(value)!={'label','rationale'} or value['label'] not in (*rubric.LABELS,'unresolved') or not isinstance(value['rationale'],str) or not value['rationale'].strip():raise ValueError('Invalid regular judgment')
    else:rubric.validate_certificate(job['payload'],value)


def metrics(rows,arm):
    confusion={label:dict.fromkeys((*rubric.LABELS,'unresolved'),0) for label in rubric.LABELS}
    for row in rows:
        prediction=rubric.LABELS[row[arm]] if row[arm]>=0 else 'unresolved'
        confusion[rubric.LABELS[row['reference']]][prediction]+=1
    correct=sum(r[arm]==r['reference'] for r in rows)
    return {'correct':correct,'total':len(rows),'accuracy':correct/len(rows),'unresolved':sum(r[arm]<0 for r in rows),'confusion':confusion}


def audit(prepared,out,complete=False):
    if out.exists():raise ValueError('Fresh audit directory required')
    if (prepared/'mock_only.json').exists():raise ValueError('Mock artifacts are not live pilot results')
    protocol=verify(prepared);jobs=read(prepared/'jobs.json');cases=read(prepared/'cases.json');pool=read(prepared/'training_pool.json')
    query={r['source_group'] for r in cases};primary={g for f in read(STUDY/'folds.json') if f['candidate']=='boost_full_vision' for g in f['held_sources']}
    reserved={r['source_group'] for r in read(ROOT/'logs/exps/261020-validation-reservation-v39/inputs_without_labels.json')}
    assert not query&primary and not (query|{r['source_group'] for r in pool})&reserved
    assert not query&{r['source_group'] for r in pool}
    references={c['case']:c for c in cases};expected={slot_ref(j):j for j in jobs};assert len(expected)==MAX_CALLS
    ledger=prepared/'ledger';budget=read(ledger/'budget.json') if (ledger/'budget.json').exists() else None
    saved={p.stem:read(p) for p in (ledger/'jobs').glob('*.json')}
    attempts=set(budget.get('attempted_slots',[])) if budget else set()
    assert set(saved)<=attempts<=set(expected) and len(attempts)==(budget['calls'] if budget else 0)<=MAX_CALLS
    if budget:
        limits=budget['limits'];assert limits['max_calls']==72 and limits['max_completion_tokens']==344064 and limits['identity']==LUNA and limits['routes']=={'sol':SOL} and limits['scope_limits']=={'search':3,'final':0}
        assert all(v['search']<=3 and v['final']==0 for v in budget['cases'].values())
    totals={'calls':0,'input_tokens':0,'known_completion_tokens':0,'completion_tokens_or_reserved':0,'estimated_known_usage_usd':0.,'estimated_with_output_reservations_usd':0.}
    arms={arm:{'attempts':0,'accepted':0,'unresolved':0,'certificate_rejections':0,'provider_failures':0,'input_tokens':0,'known_completion_tokens':0,'completion_tokens_or_reserved':0,'estimated_usd_with_reservations':0.} for arm in ARMS}
    details=[];unattempted=[]
    for key,job in expected.items():
        record=saved.get(key);wrapper=prepared/'responses'/(job['case']+'-'+job['arm']+'.json');entry=read(wrapper) if wrapper.exists() else None
        row={'case':job['case'],'arm':job['arm'],'slot_ref':key,'attempted':key in attempts,'wrapper_exists':entry is not None,'accepted':False,'prediction':-1,'raw_prediction':-1}
        if key not in attempts:
            assert entry is None;unattempted.append([job['case'],job['arm']]);details.append(row);continue
        a=arms[job['arm']];a['attempts']+=1;totals['calls']+=1
        if record:
            assert record['execution_ref']==key and record['case_id']==job['case'] and record['slot']==job['arm'] and record['stage']=='semantic_contrastive_v75' and record['phase']=='search' and record['max_tokens']==job['max_tokens'] and record['payload']==job['payload']
            assert record.get('route')==job['route']
            if job['route']:assert record['requested_identity']==SOL
        response=(record or {}).get('response')
        inputs=int(response.get('promptTokens',response.get('prompt_tokens',0)) or 0) if response else 0
        known=int(response.get('completionTokens',response.get('completion_tokens',0)) or 0) if response else 0
        reservation=known if response else job['max_tokens']
        assert 0<=known<=job['max_tokens']
        for values in (a,totals):
            values['input_tokens']+=inputs;values['known_completion_tokens']+=known;values['completion_tokens_or_reserved']+=reservation
        input_rate,output_rate=(2.,10.) if job['route']=='sol' else (.1,.5)
        a['estimated_usd_with_reservations']+=(inputs*input_rate+reservation*output_rate)/1e6
        totals['estimated_known_usage_usd']+=(inputs*input_rate+known*output_rate)/1e6
        totals['estimated_with_output_reservations_usd']+=(inputs*input_rate+reservation*output_rate)/1e6
        parsed=(record or {}).get('parsed');row['provider_outcome']=(record or {}).get('outcome','interrupted_without_job')
        if isinstance(parsed,dict) and parsed.get('label') in rubric.LABELS:row['raw_prediction']=rubric.LABELS.index(parsed['label'])
        if record and record['outcome']=='completed':
            try:validate_value(job,parsed);valid=True
            except (ValueError,KeyError,TypeError) as exc:valid=False;row['validation_error']=str(exc);a['certificate_rejections']+=1
            if entry is not None:
                if valid:assert entry['judgment']==parsed and entry['error'] is None and entry['execution_ref']==key
                else:assert entry['judgment'] is None
                row['accepted']=valid
                if valid:
                    a['accepted']+=1;row['prediction']=row['raw_prediction'];a['unresolved']+=row['prediction']<0
        else:
            a['provider_failures']+=1
            if entry is not None:assert entry['judgment'] is None
        details.append(row)
    assert totals['completion_tokens_or_reserved']<=MAX_OUTPUT
    if budget:assert totals['input_tokens']==budget['input_tokens'] and totals['completion_tokens_or_reserved']==budget['completion_tokens_or_reserved']
    done=len(attempts)==72 and all(r['wrapper_exists'] for r in details)
    if complete:assert done,'The frozen72-slot collection is incomplete; never fill missing results with new retries'
    rows=[];results={}
    if done:
        for case in cases:
            row={'case':case['case'],'reference':case['reference'],'cached_regular':case['regular'],'cached_error':case['regular']!=case['reference']}
            for arm in ARMS:row[arm]=next(r['prediction'] for r in details if r['case']==case['case'] and r['arm']==arm)
            rows.append(row)
        results['accuracy']={arm:metrics(rows,arm) for arm in ('cached_regular',*ARMS)}
        results['paired_vs_fresh_regular']={arm:{'gains':sum(r[arm]==r['reference']!=r['regular_luna'] for r in rows),'losses':sum(r['regular_luna']==r['reference']!=r[arm] for r in rows),'disagreements':sum(r[arm]!=r['regular_luna'] for r in rows)} for arm in ('semantic_luna','semantic_sol')}
        results['strata']={name:{arm:metrics(subset,arm) for arm in ARMS} for name,subset in [('cached_errors',[r for r in rows if r['cached_error']]),('cached_correct_controls',[r for r in rows if not r['cached_error']])]}
        if (prepared/'results.json').exists():assert read(prepared/'results.json')['correct']=={arm:results['accuracy'][arm]['correct'] for arm in ('cached_regular',*ARMS)}
    result={'passed':True,'complete':done,'status':'complete' if done else 'incomplete' if attempts else 'not_started','cases':24,'attempts':len(attempts),'max_requests':72,'max_completion_tokens':344064,
        'totals':totals,'arms':arms,'results':results,'unattempted':unattempted,
        'source_excluded_contrasts':True,'reserved_sources_used':0,'new_auditor_api_calls':0,'fits':0,
        'scope':'Paired training-only error/control diagnostic, not the276-case target or a generalization estimate. Unresolved and rejected responses count as incorrect. Cost estimates use frozen Standard prices without cache discounts; failed input charges may be unrecorded.'}
    out.mkdir(parents=True);save_json(out/'verification.json',result);save_json(out/'slots.json',details);save_json(out/'rows.json',rows)
    save_json(out/'manifest.json',{'auditor_sha256':fingerprint(__file__),'prepared_manifest_sha256':fingerprint(prepared/'manifest.json'),'budget_sha256':fingerprint(ledger/'budget.json') if budget else None})
    snapshot=out/'source_snapshot/run'/Path(__file__).name;snapshot.parent.mkdir(parents=True);snapshot.write_bytes(Path(__file__).read_bytes())
    (out/'run.log').write_text('Independent frozen-pilot audit: '+result['status']+'. No new API calls, fitting, retries or repairs.\n');(out/'llm-histories.log').write_text('Zero auditor model calls. Collection histories remain in the approved pilot ledger.\n')
    print({k:v for k,v in result.items() if k not in ('unattempted','results')},flush=True)
    if results:print(results,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepared-dir',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--require-complete',action='store_true')
    a=p.parse_args();audit(a.prepared_dir.resolve(),a.output_dir.resolve(),a.require_complete)
