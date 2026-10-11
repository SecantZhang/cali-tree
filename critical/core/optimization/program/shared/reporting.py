"""Saved-data experiment reports; no compilation, selection or model calls."""
from collections import Counter
import json
from pathlib import Path
from critical.core.decision.artifacts import save_json

def write_report(output,result,manifest):
    n=len(manifest['cases']);summaries={};lines=['# '+('Weighted fulfillment versus binary comparison' if manifest.get('scoring')=='fulfillment' else 'Counting endpoint leaf experiment' if manifest.get('scoring')=='endpoints' else 'Counting-only leaf experiment' if manifest.get('scoring')=='counting' else 'V4 uncertainty handling and adaptive proposer experiment'),'',manifest['scope'],'',
        'Status: '+result['status'],'',
        'Agreement means reference matches; coverage means a resolved answer, including wrong answers. Each case has five fresh final draws. '
        'Missing or unresolved draws count as nonmatches; repeated draws are not additional cases. Both arms use the corrected runtime and strict gates.','',
        '| Arm | Seed → selected matches | Selected resolved | Locally robust cases | Escalated cases |',
        '|---|---:|---:|---:|---:|']
    if manifest.get('scoring') in ('counting','endpoints'):
        lines.insert(6,'Semantic auditing is disabled. All independent required conditions pass → yes; all fail → no; mixed → partial; any unknown → unresolved. No model readout runs. The confidence/repeat gates still govern empirical robust status.')
    if manifest.get('scoring')=='fulfillment':
        lines.insert(6,'Both arms use the same label-blind anchored grading calls on fresh independently observed programs. Fulfillment measures degree, not confidence. Protected weighted mean: >=.9 yes, <=.1 no, otherwise partial. Unknown mass is [0,1]; resolve only when the entire score interval has one label. Binary derives strict complete (score 1) votes and uses all/some/none. Audit/readout disabled. The historical v6 boolean observer differs; this fresh pair isolates aggregation under a common graded observer.')
    for arm in manifest['arms']:
        rows=[result['cases'].get(c['id'],{}).get(arm,{}) for c in manifest['cases']]
        s={'cases':n,'robust':sum(r.get('support_status')=='locally_robust' for r in rows),
            'escalated':sum(r.get('escalated',False) for r in rows)}
        for which in ('seed','selected'):
            s[which]={k:sum(r.get('final',{}).get(which,{}).get(k,0)*5 for r in rows) for k in ('agreement','coverage')}
        summaries[arm]=s
        if manifest.get('scoring') in ('endpoints','fulfillment'):
            s['accurate_repeatable']=sum(r.get('final',{}).get('selected',{}).get('agreement')==1 and
                r.get('final',{}).get('selected',{}).get('coverage')==1 for r in rows)
            s['raw_accurate_repeatable']=sum(r.get('final',{}).get('selected',{}).get('raw_measurements',{}).get('agreement')==1 and
                r.get('final',{}).get('selected',{}).get('raw_measurements',{}).get('coverage')==1 for r in rows)
        lines.append(f"| {arm} | {round(s['seed']['agreement'])} → {round(s['selected']['agreement'])} / {n*5} | {round(s['selected']['coverage'])} / {n*5} | {s['robust']} / {n} | {s['escalated']} / {n} |")
    if manifest.get('scoring') in ('endpoints','fulfillment'):
        lines+=['','Accurate and repeatable means **all five selected final labels match the reference**, with all five resolved.',
            'Raw means the scheduled observations before recovery. Effective permits one predeclared transport-only replacement check per report; valid wrong/uncertain/schema-invalid observations are never replaced.',
            '', '| Method | Raw accurate and repeatable cases | Effective accurate and repeatable cases |',
            '|---|---:|---:|']
        for arm,s in summaries.items():lines.append(f"| {arm} | {s['raw_accurate_repeatable']} / {n} | {s['accurate_repeatable']} / {n} |")
    lines+=['','| Instruction / reference | Arm | Seed → selected matches / 5 | Resolved / 5 | Mean executed checks | Confidence gate | Status / failure reason |',
            '|---|---|---:|---:|---:|---|---|']
    for c in manifest['cases']:
        for arm in manifest['arms']:
            r=result['cases'].get(c['id'],{}).get(arm,{});a=r.get('final',{}).get('seed',{});b=r.get('final',{}).get('selected',{})
            lines.append('| '+' | '.join([c['instruction'].replace('|','/')+' / '+c['target'],arm,
                f"{round(a.get('agreement',0)*5)} → {round(b.get('agreement',0)*5)}" if b else 'unavailable',
                str(round(b.get('coverage',0)*5)) if b else '0',f"{b['mean_checks']:.1f}" if b else '—',
                'passed' if b.get('confidence_pass') else 'failed/unavailable',
                r.get('support_status',r.get('phase','pending'))+'; '+', '.join(r.get('acceptance',{}).get('reasons',[]))+(('; '+r['error']) if r.get('error') else '')])+' |')
    class_metrics={};by_model={}
    for arm in manifest['arms']:
        class_metrics[arm]={}
        for label in ('yes','partial','no'):
            cases=[c for c in manifest['cases'] if c['target']==label]
            class_metrics[arm][label]={'cases':len(cases),'planned_draws':len(cases)*5}
            for which in ('seed','selected'):
                finals=[result['cases'].get(c['id'],{}).get(arm,{}).get('final',{}).get(which,{}) for c in cases]
                class_metrics[arm][label][which]={'matches':round(sum(v.get('agreement',0)*5 for v in finals)),
                    'resolved':round(sum(v.get('coverage',0)*5 for v in finals))}
    for p in (Path(output)/'jobs').glob('*.json'):
        j=json.loads(p.read_text());model=j.get('response',{}).get('model',j.get('requested_identity',manifest['primary_identity'])['model'])
        u=by_model.setdefault(model,{'calls':0,'input_tokens':0,'charged_completion_tokens':0,'failures':0})
        response=j.get('response',{});u['calls']+=1;u['input_tokens']+=int(response.get('promptTokens',0))
        u['charged_completion_tokens']+=int(response.get('completionTokens',j['max_tokens']))
        u['failures']+=j['outcome']!='completed'
    lines+=['','## Per-case execution details','',
        'Consistency is measured separately from reference agreement. An uncertain answer can repeat consistently yet fail the known-answer stability gate. '
        'Skipped checks remain untested. The observation counts below count checks across five runs, not independent cases.']
    for c in manifest['cases']:
        for arm in manifest['arms']:
            r=result['cases'].get(c['id'],{}).get(arm,{})
            if not r.get('final'):continue
            lines+=['','### '+c['instruction']+' — '+arm,'',
                '| Measurement | Seed | Selected |','|---|---:|---:|']
            for label,key,scale in [('Reference matches / 5','agreement',5),('Resolved draws / 5','coverage',5),
                ('Final-label consistency','label_consistency',1),('Minimum requirement consistency','requirement_consistency',1),
                ('Mean executed checks','mean_checks',1),('Mean charged completion tokens','mean_completion_tokens',1)]:
                lines.append('| '+label+' | '+' | '.join(f"{r['final'].get(w,{}).get(key,0)*scale:.2f}" if w in r['final'] else 'pending' for w in ('seed','selected'))+' |')
            for which in ('seed','selected'):
                if which not in r['final']:continue
                final=r['final'][which];counts=Counter(o.get('event','unknown') for t in final['traces'] for o in t['observations'])
                lines+=['',which.capitalize()+' labels: '+json.dumps(final['label_distribution'])+'. Observation events: '+json.dumps(dict(counts))+'.',
                        'Confidence per check: '+json.dumps({k:v['confidence'] for k,v in final['nodes'].items()})+'.',
                        'Known-answer consistency per check: '+json.dumps({k:v['consistency'] for k,v in final['nodes'].items()})+'.']
                if manifest.get('scoring')=='fulfillment':
                    lines+=['','Fulfillment score bounds: '+json.dumps(final['fulfillment_bounds'])+'.',
                        'Same-observation counterfactual agreement: '+json.dumps(final['counterfactual_agreement'])+'.']
            lines+=['','Search schedule: '+json.dumps(r.get('search_schedule',{}))+'. Stop: '+r.get('stop_reason','')+'.',
                'Escalated: '+str(r.get('escalated',False))+'. Usage: '+json.dumps(r.get('usage',{}))+'.']
    lines+=['','## Accounting','',json.dumps({k:v for k,v in result.get('budget',{}).items() if k not in ('attempted_slots','cases','limits')},indent=2),
        '', 'Returned models: '+', '.join(result.get('returned_models',[])), 'Error: '+str(result.get('error','none')),
        '', 'Historical results are descriptive. This comparison isolates proposer escalation under the same new runtime. '
        'Confidence is self-report, semantic audit is fallible, and unvisited alternatives remain untested. '
        'A reference-conflict flag requests review; it does not certify that the saved label is wrong.']
    Path(output).mkdir(parents=True,exist_ok=True)
    (Path(output)/'report.md').write_text('\n'.join(lines)+'\n');save_json(Path(output)/'summary.json',summaries)
    save_json(Path(output)/'class_metrics.json',class_metrics);save_json(Path(output)/'usage_by_model.json',by_model)
