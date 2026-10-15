"""Audit request isolation, raw-to-feature fidelity, and fast-model metrics."""
import argparse
from collections import Counter
from fractions import Fraction
from pathlib import Path
from statistics import median

from critical.core.decision.artifacts import save_json
from critical.core.calibration.semantic_calibration import SemanticRouter
from critical.core.decision.semantic_evidence import QUALITIES,DESCRIPTORS
from run.calitree_small_models import prepare,FIXED,SOL
from run.calitree_small_models_calibration import evidence_rows,job_for
from run.calitree_single_call import ROOT,read,fingerprint


def independently_score(predictions,targets):
    support=[targets.count(i) for i in range(3)]
    tp=[sum(a==b==i for a,b in zip(predictions,targets)) for i in range(3)]
    f1=sum((Fraction(2*t,n+predictions.count(i)) for i,(t,n) in enumerate(zip(tp,support))),Fraction())/3
    return sum(tp),float(f1),[t/n for t,n in zip(tp,support)],predictions.count(-1)


def predict(policy,record):
    if record['descriptor'] is None:return -1
    router=SemanticRouter.restore(policy['router']);cluster=router.predict([record['descriptor']])[0]
    values=[sum(w*x for w,x in zip(policy['weights'],record[k]))+policy['offsets'][cluster] for k in ('lower','upper')]
    labels=[sum(v>=cut for cut in policy['cutpoints']) for v in values]
    p=labels[0] if labels[0]==labels[1] else -1
    if policy['uninspectable_label'] is not None and all(record['lower'][i]==0 and record['upper'][i]==4 for i in (0,1)):
        p=policy['uninspectable_label']
    return p


def run(output):
    m=prepare(output,list(read(output/'manifest.json')['models']));r=read(output/'results.json');cases=m['cases']
    assert len(cases)==48 and len({c['group'] for c in cases})==48 and len({c['editing_model'] for c in cases})==1
    assert cases==read(FIXED/'manifest.json')['cases']
    observations=read(output/'observations.json')['observations'];observed={(x['model_key'],x['case'],x['arm']):x for x in observations}
    assert len(observed)==192 and read(output/'replay.json')['exact_replay']
    assert read(output/'fit_seal.json')['results_ref']==fingerprint(output/'results.json')
    for rel,h in read(output/'fit_seal.json')['code_hashes'].items():
        assert fingerprint(ROOT/rel)==h and fingerprint(output/'fit_source_snapshot'/rel)==h
    jobs_verified=0;metrics_verified=0;normalized_verified=0;failures=[]
    for key,model in r['models'].items():
        assert model['identity']==m['models'][key]
        for c in cases:
            for arm in ('flat','evidence'):
                directory=output/'ledgers'/key/c['case']/arm;j=job_for(output,key,c['case'],arm)
                assert read(directory/'budget.json')['limits']['identity']==m['models'][key]
                assert j['payload']=={'instruction':c['instruction']} and j['slot']=='once'
                assert j['media_identity']==[{'type':'text','text':'SOURCE image'},{'type':'image','sha256':c['image_hashes']['source_image']},
                    {'type':'text','text':'EDITED image'},{'type':'image','sha256':c['image_hashes']['edited_image']}]
                if j['outcome']!='completed':failures.append({'model':key,'case':c['case'],'arm':arm,'outcome':j['outcome']})
                jobs_verified+=1
        for mode,data in model['modes'].items():
            features,repairs=evidence_rows(output,key,cases,observed,mode=='literal_quote_normalized')
            assert repairs==data['normalizations']
            for repair in repairs:
                raw=job_for(output,key,repair['case'],'evidence')['parsed']
                instruction=next(c['instruction'] for c in cases if c['case']==repair['case'])
                for change in repair['changes']:
                    assert raw['aspects'][change['aspect']]['source_quote']==change['before']
                    assert change['after'] in instruction and change['before'].strip()[1:-1]==change['after']
                    normalized_verified+=1
            all_predictions={family:[] for family in data['pooled']};all_targets=[]
            for batch,arms in data['groups'].items():
                indices=[i for i,c in enumerate(cases) if c['batch']==batch];part=[cases[i] for i in indices]
                targets=[('no','partial','yes').index(c['reference']) for c in part];all_targets+=targets
                assert Counter(targets)=={0:4,1:4,2:4}
                for family,a in arms.items():
                    predicted=[x['prediction'] for x in a['cases']]
                    assert [x['case'] for x in a['cases']]==[c['case'] for c in part]
                    assert [x['reference'] for x in a['cases']]==targets
                    if family=='flat':
                        expected=[('no','partial','yes').index(observed[(key,c['case'],'flat')]['prediction']) if observed[(key,c['case'],'flat')]['prediction'] is not None else -1 for c in part]
                    else:
                        policy=read(SOL/'results.json')['groups'][batch]['unclustered']['policy'] if family=='frozen_sol_shared' else a['policy']
                        expected=[predict(policy,features[i]) for i in indices] if policy else [-1]*12
                        if policy:
                            assert sum(v!=0 for v in policy['weights']+policy['offsets'])+(policy['uninspectable_label'] is not None)<=4
                            assert policy['shared_cutpoints']==2
                    assert predicted==expected
                    n,f1,recall,unresolved=independently_score(predicted,targets);s=a['metrics']
                    assert s['correct']==n and s['macro_f1']==f1 and s['accuracy']==n/12 and s['unresolved']==unresolved
                    assert [s['per_class'][label]['recall'] for label in ('no','partial','yes')]==recall
                    if family.startswith('local') and a['policy']:assert all(v>=.5 for v in recall)
                    all_predictions[family]+=predicted;metrics_verified+=1
            for family,p in all_predictions.items():
                n,f1,_,unknown=independently_score(p,all_targets);s=data['pooled'][family]
                assert s['correct']==n and s['macro_f1']==f1 and s['unresolved']==unknown and s['total']==48
    audit={'passed':True,'request_jobs_verified':jobs_verified,'independent_group_metrics_verified':metrics_verified,
           'literal_spans_normalized_with_proof':normalized_verified,'transport_failures':failures,
           'new_api_calls_in_audit':0,'fixed_groups_and_labels':True,'one_source_first_call_per_arm_per_case':True,
           'judge_payload_label_blind':True,'same_rule_budget':True,'frozen_and_local_results_separate':True,
           'local_accuracy_is_not_heldout':True,'results_ref':fingerprint(output/'results.json')}
    save_json(output/'audit.json',audit)
    lines=['# Fast-model benchmark on the fixed 48 AURORA cases','',
        'Both approved models were run live on the same four class-balanced 12-case groups, with one source-first presentation per arm per case. Settings: reasoning disabled, temperature 0, eight shared workers, one HTTP attempt, existing prompts/schema and v6 rule limits unchanged.',
        '**Primary pipeline result:** strict evidence validation plus shared v6 calibration fitted and scored on each same twelve-case group. Quote-normalized results are a separate post-hoc, format-only diagnostic. All failures remain in the denominator.','',
        '| Model | Flat | Strict local shared | Strict macro-F1 | Strict coverage | Quote-normalized shared | Quote-normalized clustered |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for key,model in r['models'].items():
        strict=model['modes']['strict']['pooled'];norm=model['modes']['literal_quote_normalized']['pooled'];s=strict['local_shared']
        lines.append(f"| {model['identity']['model']} | {strict['flat']['correct']}/48 ({strict['flat']['accuracy']:.1%}) | {s['correct']}/48 ({s['accuracy']:.1%}) | {s['macro_f1']:.3f} | {48-s['unresolved']}/48 | {norm['local_shared']['correct']}/48 ({norm['local_shared']['accuracy']:.1%}) | {norm['local_clustered']['correct']}/48 ({norm['local_clustered']['accuracy']:.1%}) |")
    lines+=['','Cached Sol/high comparison: flat 30/48 (62.5%), local shared 42/48 (87.5%). Its extraction median latency was 40.06 seconds over 44 successful requests. Failure patterns and reasoning settings differ; this historical comparison is not a controlled measurement of model size alone.','',
        '## Per-group results and class recall','',
        '| Model / mode | Group | Flat | Frozen Sol rules | Shared local | Clustered local | Shared macro-F1 | No / Partial / Yes recall | Shared coverage |',
        '|---|---|---:|---:|---:|---:|---:|---|---:|']
    for key,model in r['models'].items():
        for mode,data in model['modes'].items():
            if key=='luna' and mode!='strict':continue
            for batch,arms in data['groups'].items():
                a=arms['local_shared'];s=a['metrics'];recalls=' / '.join(f"{s['per_class'][label]['recall']:.0%}" for label in ('no','partial','yes'))
                shared=f"{s['correct']}/12" if not a.get('error') else 'No qualifying fit (12 abstentions)'
                lines.append(f"| {key} / {mode} | {batch} | {arms['flat']['metrics']['correct']}/12 | {arms['frozen_sol_shared']['metrics']['correct']}/12 | {shared} | {arms['local_clustered']['metrics']['correct']}/12 | {s['macro_f1']:.3f} | {recalls} | {12-s['unresolved']}/12 |")
    lines+=['','## Interpretation','',
        '- Luna: local shared and clustered results are 8/12, 11/12, 10/12, 10/12. Macro-F1 is 0.831 and class recalls are No 75%, Partial 81.25%, Yes 87.5%. It does not meet the previous near-perfect requirement in G1.',
        '- Mini strict: G1 has only one usable Partial evidence record, making the required two-correct-source class floor impossible. The calibrator refuses a collapsed fallback; all twelve group cases count as unresolved. This explains much of the pooled 23/48 result and is not a claim that its visual accuracy is zero in G1.',
        '- Mini formatting: seven completed evidence records fail literal instruction provenance. Six are recoverable solely by removing decorative outer quotation marks and checking that the remaining text occurs exactly in the instruction. No facts, grades, predictions, or labels are changed, and no model calls are repeated. One record (G4C08) uses an ellipsis rather than a literal instruction span and remains invalid. Transport failures also remain unresolved.',
        '- Mini after normalization: shared local counts 9/12, 8/12, 10/12, 7/12 (34/48); clustered 9/12, 10/12, 10/12, 8/12 (37/48). Clustering helps this model locally at the same fitted-term budget. The formatting correction is post-hoc and is explicitly separated from the frozen strict protocol.',
        '- Frozen Sol rules transfer poorly to these new evidence distributions: Luna 25/48, mini 18/48 strict or 19/48 quote-normalized. Refitting the rubric for the evidence-producing model matters. These frozen rules already used the same source labels historically, so these are cross-extractor controls, not held-out evaluation.',
        '- Each local policy is fitted and scored on the same twelve human-labelled cases. Improvements over flat measure local fitting capacity. One presentation per case does not establish generalization or repeat robustness.','',
        '## Common resolved cases','',
        '| Model / mode | Group | Common cases | Flat correct | Local shared correct |',
        '|---|---|---:|---:|---:|']
    for key,model in r['models'].items():
        for mode,data in model['modes'].items():
            if key=='luna' and mode!='strict':continue
            for batch,arms in data['groups'].items():
                c=arms['local_shared']['common_resolved_with_flat'];lines.append(f"| {key} / {mode} | {batch} | {c['total']} | {c['flat_correct']} | {c['arm_correct']} |")
    lines+=['','## Latency and returned-usage estimates','',
        '| Model | Arm | Median successful-call latency | P90 | Input tokens | Output tokens | Estimated standard uncached cost |',
        '|---|---|---:|---:|---:|---:|---:|']
    total=0
    for key,model in r['models'].items():
        for arm,u in model['usage'].items():
            l=u['successful_api_latency'];cost=u['uncached_standard_cost_estimate_usd'];total+=cost
            lines.append(f"| {key} | {arm} | {l['median_seconds']:.2f}s | {l['p90_seconds']:.2f}s | {u['returned_input_tokens']:,} | {u['returned_output_tokens']:,} | ${cost:.5f} |")
    lines += ['',f'Total across all 192 attempts: **${total:.5f}** estimated from returned token usage. The pipeline cost is the evidence arm; flat is a separate benchmark control. Local calibration, clustering, normalization, replay, and auditing made zero extra API calls.',
        'Costs use standard uncached input/output rates from the official model pages: [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna), [GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini). Cache discounts and unreturned usage on failed requests can change the invoice. Median latency covers successful API calls, excludes offline fitting and failed calls, and is measured under eight shared workers.','',
        '## Failures, policies, and verification','',
        'There were ten SSL transport failures: Luna flat 3, evidence 2; mini flat 2, evidence 3. The seven mini validation errors are additional to transport failures. No retry, relabel, resampling, or case replacement was performed.',
        'Raw requests/results are immutable durable slots. The collection manifest seals cases, model identities, prompts/schema, code and image hashes. Every learned policy, router, per-case prediction, normalization receipt, metric, and class support is saved in results.json and calibration/* registries. Independent audit verifies all 192 request slots, numeric predictions/metrics, class balance, model identity, source-first presentation and rule budgets.',
        'The initial combined launch was rejected by automatic approval review because mini authorization was considered unclear; it made no API calls. After the user explicitly approved mini, both models were executed together. Earlier preflight-only directories remain preserved.']
    (output/'report.md').write_text('\n'.join(lines)+'\n')
    print({'audit_passed':True,'jobs_verified':jobs_verified,'metrics_verified':metrics_verified,'cost_estimate_usd':total})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    run(p.parse_args().output_dir.resolve())
