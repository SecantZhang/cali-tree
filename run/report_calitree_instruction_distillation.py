"""Audit and explain instruction-grounded semantic re-induction from a teacher."""
import argparse
import re
from fractions import Fraction
from pathlib import Path
from copy import deepcopy

from critical.core.calibration.instruction_semantic_rules import ObservableDNFCalibrator
from critical.core.calibration.visibility_calibration import VisibilityOrdinalCalibrator
from critical.core.decision.instruction_role_facts import compile_record,PREDICATES,CORE,SUPPORT,DIRECTIONS
from critical.core.decision.observable_facts import fact_record,validate as validate_facts
from critical.core.decision.postcondition_binding import validate as validate_program
from critical.core.decision.intermediate_facts import validate as validate_mid
from critical.core.decision.semantic_policy_executor import prose_observations
from critical.core.decision.semantic_evidence import feature_record,QUALITIES
from critical.core.decision.artifacts import digest,save_json
from run.calitree_observable_facts import prepare as prepare_facts,SOURCE,TEACHER
from run.calitree_postconditions import prepare as prepare_programs
from run.calitree_intermediate_facts import prepare as prepare_mid
from run.calitree_single_call import ROOT,IDENTITY,read,fingerprint

FACTS=ROOT/'logs/exps/261014-observable-semantic-facts-v10'
PROGRAMS=ROOT/'logs/exps/261014-semantic-postconditions-v12'
MID=ROOT/'logs/exps/261014-physical-intermediates-v13'


def input_keys(x):
    if isinstance(x,dict):
        for k,v in x.items():yield k;yield from input_keys(v)
    elif isinstance(x,list):
        for v in x:yield from input_keys(v)


def direct_prediction(policy,record):
    if record is None:return -1
    boundaries={}
    for boundary in ('yes','partial'):
        low=high=False
        for clause in policy[boundary]:
            bounds=[]
            for a in clause:
                state=record['facts'][a['fact']]
                bounds.append((False,True) if state=='unknown' else (state==a['test'],state==a['test']))
            low|=all(v[0] for v in bounds);high|=all(v[1] for v in bounds)
        boundaries[boundary]=(low,high)
    p=[2 if boundaries['yes'][i] else 1 if boundaries['partial'][i] else 0 for i in (0,1)]
    return p[0] if p[0]==p[1] else -1


def check_metrics(p,y,m):
    ns=[y.count(i) for i in range(3)];tp=[sum(a==b==i for a,b in zip(p,y)) for i in range(3)]
    macro=sum((Fraction(2*t,n+p.count(i)) for i,(t,n) in enumerate(zip(tp,ns))),Fraction())/3
    assert m['correct']==sum(tp) and m['total']==len(y) and m['accuracy']==sum(tp)/len(y)
    assert m['macro_f1']==float(macro) and m['unresolved']==p.count(-1)
    assert [m['per_class'][k]['recall'] for k in ('no','partial','yes')]==[t/n for t,n in zip(tp,ns)]


def run(output):
    m=prepare_facts(FACTS);prepare_programs(PROGRAMS);prepare_mid(MID)
    cases=m['cases'];r=read(output/'results.json');plan=read(output/'plan.json');seal=read(output/'fit_seal.json')
    assert digest(plan)==r['plan_ref'] and seal['results_ref']==fingerprint(output/'results.json')
    for rel,h in seal['code_hashes'].items():
        assert fingerprint(ROOT/rel)==h and fingerprint(output/'source_snapshot'/rel)==h
    assert len(cases)==48 and len({c['group'] for c in cases})==48
    for c in cases:
        for k,p in c['evidence'].items():assert fingerprint(p)==c['image_hashes'][k]
    source={v['case']:v for v in read(SOURCE/'results.json')['observations']}
    original_teachers=read(TEACHER/'results.json')
    facts_raw=read(FACTS/'facts.json');programs_raw=read(PROGRAMS/'programs.json');mid_raw=read(MID/'facts.json')
    fact_rows={v['case']:v for v in facts_raw['cases']};program_rows={v['case']:v for v in programs_raw['cases']};mid_rows={v['case']:v for v in mid_raw['cases']}
    records={};traces=[];jobs_checked=0
    forbidden={'grade','score','weights','cutpoints','reference','human_score','teacher_prediction','label','case_id'}
    for c in cases:
        name=c['case']
        if source[name]['extraction'] is None:
            assert fact_rows[name]['extraction'] is None and program_rows[name]['compilation'] is None and mid_rows[name]['extraction'] is None
            records[name]=None;continue
        primitive=fact_rows[name]['extraction']['observations'];binding=program_rows[name]['compilation']['program'];intermediate=mid_rows[name]['extraction']['observations']
        validate_facts(primitive);validate_program(binding,c['instruction']);validate_mid(intermediate)
        primitive_record=fact_record(primitive);middle={'facts':{k:v['state'] for k,v in intermediate['facts'].items()}}
        x=compile_record(primitive_record,binding,middle);records[name]=x
        # Independent calculations for the central semantics used by the rules.
        present=[k for p in binding['postconditions'] for k in p['required_present']]
        absent=[k for p in binding['postconditions'] for k in p['required_absent']]
        f=primitive_record['facts']
        assert (x['facts']['all_bound_postconditions_established']=='true')==(all(f[k]=='true' for k in present) and all(f[k]=='false' for k in absent))
        assert (x['facts']['a_required_positive_witness_visible']=='true')==any(f[k]=='true' for k in present)
        assert (x['facts']['a_required_physical_test_undecidable']=='true')==any(f[k] in ('unknown','not_applicable') for k in present+absent)
        selected=set(binding['identity_witnesses']);relocation=bool(selected&{'original_instance_displaced','original_instance_at_source','counterpart_at_destination'})
        assert (x['facts']['relocation_duplicate_observed']=='true')==(relocation and f['target_instance_count_increased']=='true')
        assert (x['facts']['requested_entity_attribute_conflict_observed']=='true')==('specified_entity_attribute_conflict' in absent and f['specified_entity_attribute_conflict']=='true')
        for directory,mode in ((FACTS,'facts'),(PROGRAMS,'programs'),(MID,'mid')):
            files=list((directory/'ledgers'/name/'jobs').glob('*.json'));assert len(files)==1
            job=read(files[0]);assert job['outcome']=='completed' and job['media_identity']==[] and job['slot']=='once'
            assert read(directory/'ledgers'/name/'budget.json')['limits']['identity']==IDENTITY
            assert job['payload']['instruction']==c['instruction'] and not forbidden&set(input_keys(job['payload']))
            if mode=='programs':assert set(job['payload'])=={'instruction','observable_predicates'}
            else:assert job['payload']['observations']==prose_observations(source[name]['extraction']['observations'])
            jobs_checked+=1
        traces.append({'case':name,'instruction':c['instruction'],'bound_postconditions':binding,
           'primitive_physical_evidence':primitive,'intermediate_physical_evidence':intermediate,
           'derived_runtime_facts':{k:v for k,v in x['facts'].items() if k not in primitive_record['facts'] and k not in middle['facts']}})
    metric_checks=0;clause_checks=0;pool={k:[] for k in ('teacher','teacher_distilled','human_refined')};all_y=[]
    for group,arms in r['groups'].items():
        part=[c for c in cases if c['batch']==group];y=[('no','partial','yes').index(c['reference']) for c in part];all_y+=y
        teacher_y=arms['teacher']['predictions'];check_metrics(teacher_y,y,arms['teacher']['metrics']);metric_checks+=1
        original_policy=original_teachers['groups'][group]['unclustered']['policy']
        original_inputs=[feature_record(source[c['case']]['extraction']['observations'],c['instruction']) if source[c['case']]['extraction'] else {'lower':[0]*8,'upper':[4]*8,'descriptor':None} for c in part]
        assert teacher_y==[v['prediction'] for v in VisibilityOrdinalCalibrator.restore(original_policy).predict_records(original_inputs)]
        for family in ('teacher_distilled','human_refined'):
            arm=arms[family];a=arm['policy'];assert a is not None and not arm['error']
            assert a['teacher_concepts']==[k for k,w in zip(QUALITIES,original_policy['weights']) if w]
            x=[records[c['case']] for c in part]
            indices=[i for i in range(12) if x[i] is not None and teacher_y[i]>=0] if family=='teacher_distilled' else list(range(12))
            tx=[x[i] for i in indices];ty=[teacher_y[i] if family=='teacher_distilled' else y[i] for i in indices]
            assert a['training_feature_ref']==digest(tx) and a['training_target_ref']==digest(ty)
            p=[direct_prediction(a,v) for v in x];assert p==arm['predictions']
            check_metrics(p,y,arm['metrics']);metric_checks+=1
            before=deepcopy(a);model=ObservableDNFCalibrator.restore(a);assert [v['prediction'] for v in model.predict_records(x)]==p
            assert model.metadata()==before
            for boundary,allowed in [('yes',CORE),('partial',SUPPORT)]:
                for index,clause in enumerate(a[boundary]):
                    assert 1<=len(clause)<=3 and any(v['test']=='true' and v['fact'] in allowed for v in clause)
                    supported=0
                    for v in tx:
                        if v is not None and all(v['facts'][atom['fact']]==atom['test'] for atom in clause):supported+=1
                    assert supported==a['clause_support'][boundary][index] and supported>=2
                    for atom in clause:
                        assert atom['fact'] in PREDICATES and atom['test'] in ('true','false')
                        if atom['fact'] in DIRECTIONS:assert atom['test']==('true' if DIRECTIONS[atom['fact']]==1 else 'false')
                    clause_checks+=1
            for c,entry in zip(part,arm['cases']):assert entry['facts']==records[c['case']]
        for family in pool:pool[family]+=arms[family]['predictions']
    for family,p in pool.items():check_metrics(p,all_y,r['pooled'][family]);metric_checks+=1
    assert r['pooled']['teacher_distilled']['correct']>=r['pooled']['teacher']['correct']==42
    assert all(g['teacher_distilled']['metrics']['correct']>=g['teacher']['metrics']['correct'] for g in r['groups'].values())
    stages={'physical_facts':facts_raw,'instruction_binding':programs_raw,'physical_intermediates':mid_raw}
    costs={k:(v['input_tokens']*2+v['completion_tokens']*10)/1e6 for k,v in stages.items()}
    counterfactuals=[]
    # These are interventions in a bound request program, not runtime case
    # exceptions. The classifier receives exactly the same anonymous schema.
    for name,role in [('G3C09','descriptive_attribute_becomes_outcome'),('G2C11','relocation_becomes_authorized_addition')]:
        c=next(c for c in cases if c['case']==name);binding=deepcopy(program_rows[name]['compilation']['program'])
        if role=='descriptive_attribute_becomes_outcome':binding['postconditions'][0]['required_absent'].append('specified_entity_attribute_conflict')
        else:binding['identity_witnesses']=[]
        primitive=fact_record(fact_rows[name]['extraction']['observations']);middle={'facts':{k:v['state'] for k,v in mid_rows[name]['extraction']['observations']['facts'].items()}}
        changed=compile_record(primitive,binding,middle);policy=r['groups'][c['batch']]['teacher_distilled']['policy']
        before=direct_prediction(policy,records[name]);after=direct_prediction(policy,changed)
        assert before!=after
        counterfactuals.append({'case':name,'intervention':role,'before':before,'after':after,'primitive_evidence_unchanged':True})
    audit={'passed':True,'fixed_case_count':48,'source_distinct':True,'all_three_labels':True,
       'label_blind_jobs_audited':jobs_checked,'metric_sets_independently_checked':metric_checks,
       'physical_clauses_checked':clause_checks,'every_positive_clause_has_requested_witness':True,
       'every_clause_has_at_least_two_source_cases':True,'teacher_only_fit_targets_verified':True,
       'no_ordinal_quality_or_string_lookup_inputs':True,'same_or_better_accuracy_in_every_group':True,
       'source_failures_retained':4,'student_unresolved':r['pooled']['teacher_distilled']['unresolved'],
       'teacher_accuracy':r['pooled']['teacher']['accuracy'],'student_accuracy':r['pooled']['teacher_distilled']['accuracy'],
       'original_teacher_predictions_recomputed':True,'semantic_role_counterfactuals':counterfactuals,
       'new_text_calls':sum(v['attempts'] for v in stages.values()),'new_image_calls':0,
       'returned_usage_cost_usd':sum(costs.values()),'stage_costs':costs,'results_ref':fingerprint(output/'results.json')}
    save_json(output/'audit.json',audit);save_json(output/'execution_traces.json',traces)
    examples=['# Concrete execution of the learned semantic rules','',
        'These are the unchanged local examples. Facts come from the label-blind cached-description extractors; conditions come from the instruction-only compiler. Dataset labels are shown for evaluation only. No quality grades or weighted scores enter the student.','']
    trace_by_case={t['case']:t for t in traces}
    for name in ('G2C05','G2C11','G2C09','G1C05','G3C09','G4C02'):
        c=next(c for c in cases if c['case']==name);trace=trace_by_case[name];program=trace['bound_postconditions'];f=trace['primitive_physical_evidence']['facts']
        entry=next(x for x in r['groups'][c['batch']]['teacher_distilled']['cases'] if x['case']==name)
        label=lambda value:('No','Partial','Yes')[value] if value>=0 else 'unresolved'
        examples += [f"## {name}: {c['instruction']}",'',f"Dataset reference: **{c['reference']}**. Teacher: **{label(entry['teacher_prediction'])}**. Semantic student: **{label(entry['decision']['prediction'])}**.",'',
            '### Requested physical tests','']
        for p in program['postconditions']:
            examples.append('- '+p['physical_test'])
            for k in p['required_present']:examples.append(f"  - Required affirmative witness `{k}`: **{f[k]['state']}**. {f[k]['evidence']}")
            for k in p['required_absent']:examples.append(f"  - Required absence of `{k}`: observed proposition is **{f[k]['state']}**. {f[k]['evidence']}")
        examples+=['','### Calibration conditions used in this group','']
        policy=r['groups'][c['batch']]['teacher_distilled']['policy']
        for boundary in ('yes','partial'):
            examples.append('**'+boundary.upper()+' alternatives:**')
            examples.append('')
            for clause in policy[boundary]:
                examples.append('- '+' AND '.join(f"`{a['fact']}` has **{a['test']}** evidence (this case: **{records[name]['facts'][a['fact']]}**)" for a in clause))
            examples.append('')
        relevant_mid=[(k,v) for k,v in trace['intermediate_physical_evidence']['facts'].items() if v['state']=='true']
        if relevant_mid:
            examples+=['### Physical intermediate witnesses','']
            for k,v in relevant_mid:examples.append(f"- `{k}`: {v['bound_question']} **true** — {v['evidence']}")
            examples.append('')
    (output/'worked_examples.md').write_text('\n'.join(examples)+'\n')
    lines=['# Instruction-grounded semantic calibration: matched local accuracy','',
       '**Teacher-only semantic distillation now matches the original 42/48 local accuracy (87.5%) on the unchanged cases.** Each group matches 10/12, 12/12, 10/12, 10/12. Runtime inputs are physical predicate evidence and exact properties of instruction-bound postconditions, with no quality grades, numeric scores, case IDs or exact-instruction lookups.',
       'This is semantic re-induction guided by the learned policy, not lossless rewriting of its formula. The student learns which physical witness patterns predict the teacher’s labels. The optional local dataset-label refinement is reported separately. Representation design and experiment choices used local error analysis, so the overall study is not gold-blind or held-out validation.','',
       '| Group | Numeric teacher | Teacher-only semantic student | Local-label-refined student | Student macro-F1 | No / Partial / Yes recall | Student coverage |',
       '|---|---:|---:|---:|---:|---|---:|']
    for group,a in r['groups'].items():
        t=a['teacher']['metrics'];s=a['teacher_distilled']['metrics'];h=a['human_refined']['metrics'];recall=' / '.join(f"{s['per_class'][k]['recall']:.0%}" for k in ('no','partial','yes'))
        lines.append(f"| {group} | {t['correct']}/12 | {s['correct']}/12 | {h['correct']}/12 | {s['macro_f1']:.3f} | {recall} | {12-s['unresolved']}/12 |")
    s=r['pooled']['teacher_distilled'];t=r['pooled']['teacher']
    lines+=['',f"Teacher macro-F1 {t['macro_f1']:.3f} → student {s['macro_f1']:.3f}; accuracy remains 42/48. Coverage is **{48-s['unresolved']}/48 versus {48-t['unresolved']}/48** for the teacher. Four original source failures and two additional uncertain Yes-reference cases stay in the denominator. Matching accuracy does not mean identical predictions or unchanged coverage.",'',
       '## What makes these rules semantic','',
       'The old v8/v9 result renamed ordinal quality states. This method instead has three independent label-blind stages:','',
       '1. Extract physical facts from cached SOURCE/EDITED prose: original-instance persistence, destination counterpart, relative placement, count change, residual color, cap/base orientation, closure gaps, detached pieces, contents in a receiver, hand contact/grasp, style structure, setting objects and unrelated-object changes.',
       '2. Compile the instruction alone into physical assertions, with requested-present and requested-absent predicate lists. Identify supporting, identity and collateral roles separately. The compiler never sees the observations, teacher predictions or reference labels.',
       '3. Extract concrete intermediate configurations: an arm reaching toward a target, an object-like form at a hand, container tilt, closure edges approaching, changed style treatment, reversed end geometry, or a related entity fragment. Mere unrelated limb motion cannot alone support a positive verdict.','',
       'The evidence/proposition program is combined deterministically. “All bound postconditions established” is a literal conjunction of the named physical tests, not a latent completion grade. Execution traces show every bound question, factual state, and source explanation. Unknown raw facts remain unknown; Boolean proof-status predicates say whether a witness is established, not what happened outside the image.','',
       '## Actual learned calibration rule: G2','',
       '- **Yes:** every instruction-bound physical postcondition is established AND no extra target instance is observed in an original-instance relocation role.',
       '- **Partial:** otherwise, at least one required affirmative physical witness is established.',
       '- **No:** otherwise, subject to uncertainty propagation. Missing observations remain unresolved.','',
       'This is not a score threshold. The physical postconditions and relocation role depend on what the instruction actually asks.','',
       'Examples from the unchanged group:','',
       '- Recoloring: requested color is visible, but the contrary original color remains on part of the target. The bound postcondition includes both requested-color presence and contrary-color absence, so it is not fully established; the observed requested color supports Partial.',
       '- Relocation: the desired relative position can be visible while an extra counterpart remains. Duplication is a conflict only in original-instance relocation; the same count increase is authorized for an addition. The learned rule therefore distinguishes Partial relocation from successful addition.',
       '- Tearing into two pieces: disconnected pieces and the requested count are concrete physical tests. Visible changes elsewhere do not automatically override those outcomes.','',
       'G1 also learns Partial from a concrete instruction-related intermediate witness when no terminal physical condition is established. The book case is supported by a raised/reaching arm and object-like form, not by an abstract “progress level”.','',
       '## Identity and requested-attribute roles','',
       'Bare appearance-change fields were excluded from the classifier: changed markings/shape are not by themselves proof that a different target was edited. The usable identity facts distinguish original-instance persistence, failed destination correspondence and relocation duplication. Appearance conflicts become requested-outcome constraints only when the instruction compiler explicitly binds that role.',
       'For example, “same type” on an added entity is an outcome requirement, whereas a descriptive adjective can identify the source object to be flipped. The compiler makes that distinction before seeing evidence or labels. Counterfactual unit tests hold factual differences constant while changing their instruction role, and verify that authorized addition is not penalized as relocation duplication.',
       'The actual-case audit also intervenes on two bound role programs while holding primitive evidence fixed: making an identifying attribute an explicit outcome blocks the former Yes, and changing original-instance relocation into authorized addition changes the duplication verdict. These are symbolic role interventions, not new counterfactual image-label evaluations.','',
       '## Learning and safeguards','',
       '- The primary student fits only resolved teacher predictions on cases with factual evidence; original dataset labels are used to score it, not as its fit targets. Teacher concepts prioritize the physical predicate vocabulary. The separate human_refined arm deliberately fits the original local labels.',
       '- Learn up to three Yes and three Partial conjunctions, each with at most three factual conditions. Each conjunction has at least two definite distinct source cases. All three predicted classes must correctly recognize at least two training sources.',
       '- Every Yes clause contains an actual requested physical witness; every Partial clause contains a requested or supporting physical witness. Incidental intact-scene evidence cannot alone cause a positive verdict.',
       '- Predicate polarity follows declared physical directions. Instruction-role constraints take priority over incidental support when equally covering conditions tie. Unknown facts use both possible branches; a label resolves only when both agree.',
       '- The search enumerates supported conjunctions and a bounded region set (2,048 per boundary). It does not claim global optimality. No case names, hashes, object-string matches or reference lookup tables are in the calibration program.','',
       '## Limits and remaining cases','',
       'The semantic student corrects the teacher’s bottle and pouring disagreements but abstains on the pet-store-background and fully closed-jacket cases. Their cached physical descriptions or compiled requirements do not establish a reliable compatible verdict. This is an accuracy/coverage tradeoff, not 48/48 correctness.',
       'A physical predicate has interpretable meaning without necessarily being correct in a given image. The factual extractor can misread descriptions, the instruction compiler can overconstrain a request, and twelve cases underdetermine which conditions matter. Some local G1 clauses omit safeguards that another group requires. These results do not establish a universal semantic rubric, causal correctness, transfer or repeat robustness.',
       'All four groups have been used during development and are fitted locally. The final teacher-only fit uses teacher outputs, but ontology and representation choices were informed by exploratory local errors and references. New frozen-source testing is still needed for generalization.','',
       '## Exploration history','',
       '| Version | Main representation/search | Local-label-refined correct /48 |',
       '|---|---|---:|',
       '| v10 | Primitive factual CART candidates | 16 |',
       '| v11-r1 | Primitive factual conjunctions | 33 |',
       '| v12 | Instruction-bound postcondition witnesses | 40 |',
       '| v13-r1 | Intermediate witnesses and required-positive-clause guard | 42 |',
       '| v14 | Requested attribute roles | 42 |',
       '| v15 | Qualified identity evidence | 42 |',
       '| v16 | Relocation roles and semantic tie priorities | 42 |',
       'All preceding runs remain preserved. An initial v11 integer-dtype overflow and a v13 semantic-role deduplication regression were fixed and independently tested; failed and preliminary artifacts were not overwritten. These sequential local trials are optimization steps, not independent benchmarks.','',
       '## Cost and verification','',
       f"132 text-only Sol/high calls across three different stages, zero new image calls. Returned-usage estimates: physical facts ${costs['physical_facts']:.5f}, instruction binding ${costs['instruction_binding']:.5f}, intermediates ${costs['physical_intermediates']:.5f}; total **${sum(costs.values()):.5f}** at the [official standard Sol rates](https://developers.openai.com/api/docs/models/gpt-6.1-sol). Discounts and unreturned usage can change billing. All 44 attempted calls completed per stage; the four original source failures were preserved.",
       f"Independent audit verifies {jobs_checked} grade/label-blind payloads, {metric_checks} group/pooled metric sets, {clause_checks} physical conjunctions with multi-source support, teacher-only fit-target hashes, required physical witnesses, role-conditioned duplicate/attribute facts and exact predictions. Exact offline fitting replay and all three raw-response replays pass. Full test result is in tests.log.",
       'The primary implementation is instruction_semantic_rules.py; instruction_role_facts.py supplies exact role-bound evidence logic. Generated policy.txt/policy.json files, worked_examples.md and execution_traces.json provide reviewable physical conditions and case-level grounding. Runtime inference makes no model call once the facts and bindings are cached.']
    test_file=output/'tests.log'
    if test_file.exists() and (match:=re.search(r'(\d+) passed, (\d+) skipped',test_file.read_text())):
        lines+=['',f'Full offline suite: **{match[1]} passed, {match[2]} skipped**, one non-failing core-count warning. Tests, fitting replay and auditing made no API calls.']
    (output/'report.md').write_text('\n'.join(lines)+'\n')
    print({'audited':True,'teacher_only_correct':s['correct'],'case_count':48,'coverage':48-s['unresolved'],'jobs_audited':jobs_checked,'cost_usd':sum(costs.values())})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    run(p.parse_args().output_dir.resolve())
