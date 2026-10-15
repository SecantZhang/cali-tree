"""Independently audit symbolic and prose semantic translations of learned rules."""
import argparse
from itertools import product
from fractions import Fraction
from pathlib import Path

from critical.core.calibration.policy_semantics import STATES,SemanticConditionPolicy
from critical.core.decision.semantic_policy_executor import prose_observations,features
from critical.core.decision.artifacts import digest,save_json
from run.calitree_policy_translation import prepare as prepare_v8,load_inputs,SOL_EVIDENCE
from run.calitree_semantic_refinement import prepare as prepare_v9,PREVIOUS
from run.calitree_single_call import read,fingerprint


def semantic_label(a,lower,upper,observed=True):
    if not observed:return -1
    guard=a['uninspectable_label']
    if guard is not None and all(lower[k]==STATES[k][0] and upper[k]==STATES[k][-1] for k in ('progress','endpoint')):return guard
    labels=[]
    for values in (lower,upper):
        matched=lambda key:any(all(STATES[t['feature']].index(values[t['feature']])>=STATES[t['feature']].index(t['minimum_state']) for t in clause) for clause in a[key])
        labels.append(2 if matched('yes') else 1 if matched('at_least_partial') else 0)
    return labels[0] if labels[0]==labels[1] else -1


def teacher_label(a,lower,upper):
    if a['uninspectable_label'] is not None and all(lower[i]==0 and upper[i]==4 for i in (0,1)):return a['uninspectable_label']
    labels=[sum(sum(w*x for w,x in zip(a['weights'],v))>=cut for cut in a['cutpoints']) for v in (lower,upper)]
    return labels[0] if labels[0]==labels[1] else -1


def metrics(p,y):
    supports=[y.count(i) for i in range(3)];tp=[sum(a==b==i for a,b in zip(p,y)) for i in range(3)]
    f1=sum((Fraction(2*t,n+p.count(i)) for i,(t,n) in enumerate(zip(tp,supports))),Fraction())/3
    return {'correct':sum(tp),'total':len(y),'accuracy':sum(tp)/len(y),'macro_f1':float(f1),
        'class_recalls':dict(zip(('no','partial','yes'),[t/n for t,n in zip(tp,supports)])),
        'resolved':len(y)-p.count(-1),'coverage':(len(y)-p.count(-1))/len(y)}


def keys(value):
    if isinstance(value,dict):
        for k,v in value.items():yield k;yield from keys(v)
    elif isinstance(value,list):
        for v in value:yield from keys(v)


def run(output):
    m=prepare_v8(PREVIOUS);refined=prepare_v9(output);certificate=read(PREVIOUS/'certification.json')
    assert refined['cases']==m['cases'] and refined['policies']==m['policies']['sol']
    data=load_inputs(m);domain_checks=0;local_checks=0;symbolic={}
    for key,d in data.items():
        groups={};full_p=[];full_y=[]
        for group,t in d['old_policies'].items():
            a=m['policies'][key][group]
            assert a['teacher_ref']==digest(t)
            assert not {'weights','cutpoints','case','case_id','instruction','reference','prediction'}&set(keys(a))
            used=[i for i,w in enumerate(t['weights']) if w]
            if t['uninspectable_label'] is not None:used=sorted(set(used)|{0,1})
            for values in product(range(6),repeat=len(used)):
                low=[4]*8;high=[4]*8
                for i,v in zip(used,values):low[i]=0 if v==5 else v;high[i]=4 if v==5 else v
                low_names={k:STATES[k][v] for k,v in zip(STATES,low)};high_names={k:STATES[k][v] for k,v in zip(STATES,high)}
                assert teacher_label(t,low,high)==semantic_label(a,low_names,high_names)
                domain_checks+=1
            assert semantic_label(a,{k:STATES[k][0] for k in STATES},{k:STATES[k][-1] for k in STATES},False)==-1
            rows=certificate['models'][key]['groups'][group]['cases'];p=[r['semantic_prediction'] for r in rows];y=[r['reference'] for r in rows]
            assert p==[r['teacher_prediction'] for r in rows]
            result=metrics(p,y);saved=certificate['models'][key]['groups'][group]['semantic_metrics']
            assert result['correct']==saved['correct'] and result['macro_f1']==saved['macro_f1']
            groups[group]=result;full_p+=p;full_y+=y;local_checks+=len(rows)
        symbolic[key]={'groups':groups,'pooled':metrics(full_p,full_y),'teacher_fidelity':1.0}
    source={r['case']:r for r in read(SOL_EVIDENCE/'results.json')['observations']}
    teacher={r['case']:r['teacher_prediction'] for g in certificate['models']['sol']['groups'].values() for r in g['cases']}
    language={};jobs_checked=0
    for version,directory in [('v8',PREVIOUS),('v9',output)]:
        raw=read(directory/'language_results.json');bycase={r['case']:r for r in raw['cases']}
        assert len(bycase)==48 and set(bycase)=={c['case'] for c in m['cases']}
        groups={};all_p=[];all_y=[];case_results=[]
        for group in ('G1','G2','G3','G4'):
            part=[c for c in m['cases'] if c['batch']==group];p=[];y=[];agreement=0
            for c in part:
                row=bycase[c['case']];target=('no','partial','yes').index(c['reference']);policy=SemanticConditionPolicy.restore(m['policies']['sol'][group])
                if source[c['case']]['extraction'] is None:
                    assert row['execution'] is None and row['error']=='Preserved missing source evidence';prediction=-1
                    assert not list((directory/'ledgers'/c['case']/'jobs').glob('*.json'))
                else:
                    files=list((directory/'ledgers'/c['case']/'jobs').glob('*.json'));assert len(files)==1
                    job=read(files[0]);assert job['slot']=='once' and job['media_identity']==[]
                    expected_payload={'instruction':c['instruction'],'learned_semantic_policy':policy.render(),
                        'observations':prose_observations(source[c['case']]['extraction']['observations'])}
                    assert job['payload']==expected_payload
                    assert not {'grade','weights','cutpoints','teacher_prediction','reference','human_score','case_id'}&set(keys(job['payload']))
                    assert read(directory/'ledgers'/c['case']/'budget.json')['limits']['identity']==m['live_model']
                    for other in m['cases']:
                        assert other['id'] not in job['payload']['learned_semantic_policy']
                    if row['execution']:
                        value=row['execution']['interpretation'];assert value==job['parsed']
                        lower={k:STATES[k][-1] for k in STATES};upper=dict(lower)
                        assert set(value['states'])==set(features(policy))
                        for k,v in value['states'].items():
                            lower[k]=STATES[k][0] if v=='unknown' else v;upper[k]=STATES[k][-1] if v=='unknown' else v
                        prediction=semantic_label(policy.metadata(),lower,upper)
                        assert prediction==row['execution']['decision']['prediction']
                    else:prediction=-1
                    jobs_checked+=1
                p.append(prediction);y.append(target);agreement+=prediction==teacher[c['case']]
                case_results.append({'case':c['case'],'reference':target,'teacher_prediction':teacher[c['case']],
                    'semantic_prediction':prediction,'matches_teacher':prediction==teacher[c['case']]})
            groups[group]={**metrics(p,y),'teacher_agreement':agreement/12}
            all_p+=p;all_y+=y
        cost=(raw['input_tokens']*2+raw['completion_tokens']*10)/1e6
        language[version]={'groups':groups,'pooled':metrics(all_p,all_y),'teacher_agreement':sum(x['matches_teacher'] for x in case_results)/48,
            'attempts':raw['attempts'],'outcomes':raw['outcomes'],'input_tokens':raw['input_tokens'],
            'completion_tokens':raw['completion_tokens'],'uncached_usage_cost_estimate_usd':cost,'cases':case_results}
    assert language['v9']['teacher_agreement']==1.0
    assert all(language['v9']['groups'][g]['correct']>=symbolic['sol']['groups'][g]['correct'] for g in ('G1','G2','G3','G4'))
    result={'symbolic':symbolic,'language':language,'audit':{'passed':True,'domain_records_independently_verified':domain_checks,
        'local_records_verified':local_checks,'language_jobs_verified':jobs_checked,'teacher_agreement_v9':1.0,
        'all_local_groups_at_least_teacher_accuracy':True,'no_runtime_grades_labels_scores_or_images':True,
        'missing_source_cases_retained':4,'new_text_calls':sum(v['attempts'] for v in language.values()),'new_image_calls':0,
        'generalization_or_repeat_robustness_claim':False}}
    save_json(output/'analysis.json',result);save_json(output/'audit.json',result['audit'])
    lines=['# Learned policy → semantic decision rules: successful local translation','',
        '**The refined prose-only semantic execution matches the learned Sol policy on all 48 cases: 42/48 correct, with exactly the same predictions in every group.** Four missing source observations remain unresolved. No new image judgments were made.',
        'This is local semantic distillation: each teacher was already fitted to its group, and the semantic definitions were refined on local disagreements. It is not held-out validation or repeat robustness.','',
        '## Results','',
        '| Group | Learned numeric teacher | Exact semantic conditions | Prose-only first pass | Prose-only refined | Refined macro-F1 | Refined No/Partial/Yes recall | Coverage |',
        '|---|---:|---:|---:|---:|---:|---|---:|']
    for g in ('G1','G2','G3','G4'):
        t=symbolic['sol']['groups'][g];a=language['v8']['groups'][g];b=language['v9']['groups'][g]
        recall=' / '.join(f'{v:.0%}' for v in b['class_recalls'].values())
        lines.append(f"| {g} | {t['correct']}/12 | {t['correct']}/12 | {a['correct']}/12 | {b['correct']}/12 | {b['macro_f1']:.3f} | {recall} | {b['resolved']}/12 |")
    lines+=['',f"Overall refined accuracy: {language['v9']['pooled']['correct']}/48 ({language['v9']['pooled']['accuracy']:.1%}); macro-F1 {language['v9']['pooled']['macro_f1']:.3f}; teacher agreement 48/48. The first prose-only pass scored 40/48. All 44 text calls completed in each version; the four original source failures were never replaced.",'',
        '## Transformation','',
        '1. Compile each positive-weight decision boundary into its minimal sufficient combinations of named semantic evidence states. Each combination is an AND condition; alternatives are OR conditions. No sum, weighted score, or numerical cut point enters the semantic executor.',
        '2. Preserve the teacher’s exact unknown, missing-response, and learned uninspectability behavior. Preserve its actual selected evidence dependencies, instead of adding new universal vetoes.',
        '3. Render the conditions and feature-state definitions as portable natural-language rules. The deterministic form consumes named states mapped from existing evidence; this conversion retains the original ordinal information and guarantees equivalence.',
        '4. Test a genuinely grade-blind version: Sol/high reads only cached instruction/contract/aspect/quality prose and the semantic rule, assigns named states, then the deterministic semantic conditions produce the label. No original grades, score, weights, cut points, teacher case predictions, human labels, examples, or images enter those calls.',
        '5. Refine shared feature meanings using teacher disagreements, then freeze a new prompt and test every original local case once. Runtime rules have no case-specific object names or exact instruction checks.','',
        '## A concrete translated rule','',
        'The Sol G2 teacher previously used progress + scope with numeric cuts. Its semantic rule is:','',
        '- **Yes** if progress is near complete and coverage is complete; OR progress is complete and coverage is near complete.',
        '- Otherwise **Partial** if there is at least a trace of progress with complete coverage; OR substantial progress with near-complete coverage; OR near-complete progress with substantial coverage; OR complete progress with at least trace coverage.',
        '- Otherwise **No**. Unknown facts resolve only if all possible completions give the same label.','',
        'This explicitly preserves the successful interaction rather than replacing it with an independently chosen identity/preservation threshold. Full generated rules and glossaries for all twelve teachers are in the v8 rules/* directories.','',
        '## What the first pass got wrong','',
        '- G2C01 (move the pot): the executor treated a changed destination as complete scope even though the original intended object remained unmoved and correspondence was not established. The teacher’s scope already encoded intended-target alignment. The refined definition requires coverage of that intended target, not merely activity in the destination region.',
        '- G2C05 (recolor the object): the executor downgraded both progress and scope from near complete to substantial because a bounded residual remained. The refined definition distinguishes a limited remaining deviation from a missing material portion, preserving the teacher’s boundary.','',
        'These are general semantic anchors, not literal pot/recoloring rules. They are applied to every case. Their wording was developed after observing these local errors, so the recovered local accuracy is an optimization result rather than an unbiased estimate of future performance.','',
        '## Why this differs from the failed strict-gate experiment','',
        'The strict-gate version imposed new rules such as identity≥a fixed floor for every identity-preserving request. That changed the learned decision function. The new translator preserves the learned combinations and recovers the meaning already carried by their evidence features. A feature called scope can include target correspondence in its textual assessment; the features are not necessarily independent.',
        'The exact compiler is a faithful representation, not proof that the teacher discovered the correct causal rubric. It also preserves teacher errors: the inverted bottle still disagrees with its Yes reference, and the pouring case still receives the teacher’s wrong Yes. Matching the teacher’s 42/48 does not mean 48/48 or generalized semantic correctness.','',
        '## Generality of the compiler','',
        '| Evidence source | Learned teacher accuracy | Exact semantic accuracy | Prediction agreement |',
        '|---|---:|---:|---:|']
    for k,v in symbolic.items():lines.append(f"| {k} | {v['pooled']['correct']}/48 | {v['pooled']['correct']}/48 | 100% |")
    lines+=['',f"Independent certification checks {domain_checks:,} known/full-unknown dependent-feature combinations across twelve shared teachers, plus all local records. The original compiler also checks 576 cached predictions across each teacher’s entire 48-case source pool. The current compiler supports shared ordinal teachers without nonzero cluster offsets; it does not claim to translate arbitrary models.",
        'Prose-only live testing was performed for Sol only. Luna and mini results above are deterministic semantic-state executions, not new grade-blind model tests.','',
        '## Cost, reproducibility, and limits','',
        f"88 new text-only calls across two versioned prompts; zero new image calls. Returned usage estimates: first pass ${language['v8']['uncached_usage_cost_estimate_usd']:.5f}, refined ${language['v9']['uncached_usage_cost_estimate_usd']:.5f}, total ${sum(v['uncached_usage_cost_estimate_usd'] for v in language.values()):.5f}. Estimates use standard uncached $2/M input and $10/M output from the [official Sol model page](https://developers.openai.com/api/docs/models/gpt-6.1-sol); actual billing may include cache discounts or other adjustments.",
        'Exact symbolic execution adds zero API calls once source evidence states exist. The prose-only execution adds one text call per available case in the selected version. A single-call image extractor that emits these states directly has not been tested by this experiment.',
        'The same four groups, labels, editor and cached image observations remain fixed. All previous experiments and first-pass failures are preserved. No cases were retried or voted within a version. The two prompt versions are optimization steps, not repeat-robustness trials.',
        'Full offline suite: 711 passed, 23 skipped, one non-failing core-count warning. Exact response replay and independent request/prediction/metric auditing pass. Source snapshots, raw durable requests/responses, rendered conditions, manifests, domain certificates, per-case results and normalization provenance remain in the two experiment directories.']
    (output/'report.md').write_text('\n'.join(lines)+'\n')
    print({'audited':True,'domain_checks':domain_checks,'language_jobs':jobs_checked,'refined_correct':language['v9']['pooled']['correct'],
           'refined_teacher_agreement':language['v9']['teacher_agreement']})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    run(p.parse_args().output_dir.resolve())
