"""Derive descriptive, equally case-weighted results without provider access."""
from collections import Counter
import csv
from itertools import combinations
import json
from pathlib import Path
from critical.core.decision.artifacts import save_json
from run.calitree_dsg_fidelity import SCORES,case_metrics,summary

root=Path(__file__).resolve().parent
m=json.loads((root/'manifest.json').read_text());r=json.loads((root/'results.json').read_text())
assert r['status']=='completed'
jobs=[json.loads(p.read_text()) for p in (root/'jobs').glob('*.json')]
rows=[];mismatches=[];table=[]
for i,c in enumerate(m['cases']):
 row=r['cases'][c['id']];p=row['preparation'];metrics=case_metrics(row,c['target'])
 o=row['draws']['original'];d=row['draws']['dsg'];nodes=p['graph']['nodes']
 native=[x['dsg_score'] for x in d];pairs=list(combinations([x['label'] for x in d],2))
 original_jobs=[j for j in jobs if j['case_id']=='original/'+c['id']]
 dsg_jobs=[j for j in jobs if j['case_id'].startswith('dsg/'+c['id']+'/draw/')]
 prep_jobs=[j for j in jobs if j['case_id']=='prepare/'+c['id']]
 scoped=original_jobs+dsg_jobs+prep_jobs
 fmt=lambda x:'?' if x is None else str(round(x,3)) if isinstance(x,float) else x
 record={'case':i+1,'instruction':c['instruction'],'reference':c['target'],'nodes':len(nodes),
  'requested_nodes':sum(n['role']=='requested' for n in nodes),'support_nodes':sum(n['role']=='support' for n in nodes),
  'audit_accepted':p['audit']['accepted'],'original_labels':','.join(fmt(x['label']) for x in o),
  'dsg_labels':','.join(fmt(x['label']) for x in d),'native_dsg_scores':','.join(fmt(x) for x in native),
  **metrics,'dsg_self_disagreement':sum(a is None or b is None or a!=b for a,b in pairs)/len(pairs),
  'native_exact_ordinal_agreement':sum(x['label'] is not None and score==SCORES[x['label']] for x,score in zip(o,native))/5,
  'original_calls':len(original_jobs),'dsg_calls':len(dsg_jobs),'preparation_calls':len(prep_jobs),
  'input_tokens':sum(j.get('response',{}).get('promptTokens',0) for j in scoped),
  'measured_completion_tokens':sum(j.get('response',{}).get('completionTokens',0) for j in scoped)}
 rows.append(record)
 table.append(f"| {i+1} | {c['instruction']} | {record['nodes']} | {record['original_labels']} | {record['dsg_labels']} | {record['native_dsg_scores']} | {record['paired_agreement']:.0%} |")
 for k,(a,b) in enumerate(zip(o,d)):
  if a['label'] is None or a['label']!=b['label']:
   mismatches.append({'case':i+1,'instruction':c['instruction'],'repeat':k,'original':a,'dsg':b})
with (root/'per_case.csv').open('w') as f:
 writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
save_json(root/'discordances.json',mismatches)
extra={key:sum(row[key] for row in rows)/12 for key in ('dsg_self_disagreement','native_exact_ordinal_agreement')}
extra.update(summary(r,m));extra['scorable_discordances']=sum(x['original']['label'] is not None and x['dsg']['label'] is not None for x in mismatches)
extra['single_question_cases']=[row['case'] for row in rows if row['nodes']==1]
extra['multi_question_paired_agreement']=sum(row['paired_agreement'] for row in rows if row['nodes']>1)/sum(row['nodes']>1 for row in rows)
extra['audited_subset_paired_agreement']=sum(row['paired_agreement'] for row in rows if row['audit_accepted'])/sum(row['audit_accepted'] for row in rows)
extra['native_scores_under_incomplete_request']=[{'case':i+1,'repeat':k,'native':draw['dsg_score'],'requested_only':draw['requested_fraction'],'readout':draw['label']} for i,c in enumerate(m['cases']) for k,draw in enumerate(r['cases'][c['id']]['draws']['dsg']) if draw['requested_fraction']==0 and draw['dsg_score']]
extra['resolved_pairs']=sum(a['label'] is not None and b['label'] is not None for c in m['cases'] for a,b in zip(r['cases'][c['id']]['draws']['original'],r['cases'][c['id']]['draws']['dsg']))
extra['exact_matches']=sum(a['label'] is not None and a['label']==b['label'] for c in m['cases'] for a,b in zip(r['cases'][c['id']]['draws']['original'],r['cases'][c['id']]['draws']['dsg']))
extra['arms']={}
for arm in ('original','dsg'):
    draws=[r['cases'][c['id']]['draws'][arm] for c in m['cases']]
    pairs=[(a['label'],b['label']) for ds in draws for a,b in combinations(ds,2) if a['label'] is not None and b['label'] is not None]
    extra['arms'][arm]={'resolved_draws':sum(x['label'] is not None for ds in draws for x in ds),
        'all_five_stable_cases':sum(all(x['label'] is not None for x in ds) and len({x['label'] for x in ds})==1 for ds in draws),
        'resolved_within_case_pairs':len(pairs),'resolved_pair_disagreements':sum(a!=b for a,b in pairs)}
save_json(root/'analysis.json',extra)
(root/'table.md').write_text('| Case | Instruction | Questions | Original labels | DSG readout labels | Native DSG fractions | Paired agreement |\n|---|---|---:|---|---|---|---:|\n'+'\n'.join(table)+'\n')
print(json.dumps(extra,indent=2))
