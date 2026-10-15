"""Distill and refine a numeric teacher using instruction-bound observable facts."""
import argparse
from pathlib import Path
import shutil

from critical.core.calibration.bound_factual_dnf import ObservableDNFCalibrator as FactualRuleCalibrator, LIMITS
from critical.core.decision.bound_witnesses import compile_record
from critical.core.calibration.visibility_calibration import VisibilityOrdinalCalibrator
from critical.core.calibration.evidence_rules_v4 import classification_metrics
from critical.core.calibration.registry import CalibrationRegistry
from critical.core.decision.observable_facts import fact_record
from critical.core.decision.semantic_evidence import feature_record,QUALITIES
from critical.core.decision.artifacts import digest,save_json
from run.calitree_observable_facts import prepare as facts_prepare,SOURCE,TEACHER
from run.calitree_single_call import ROOT,read,fingerprint

FACTS=ROOT/'logs/exps/261014-observable-semantic-facts-v10'


def run(output):
    source_manifest=facts_prepare(FACTS);facts=read(FACTS/'facts.json');cases=source_manifest['cases']
    observed={r['case']:r for r in facts['cases']};original={r['case']:r for r in read(SOURCE/'results.json')['observations']}
    teachers=read(TEACHER/'results.json');program_dir=ROOT/'logs/exps/261014-semantic-postconditions-v12';program_rows={r['case']:r for r in read(program_dir/'programs.json')['cases']};output.mkdir(parents=True,exist_ok=True);registry=CalibrationRegistry(output/'registry')
    plan={'version':'teacher-to-bound-physical-rules-v12','facts_ref':fingerprint(FACTS/'facts.json'),
       'teacher_ref':fingerprint(TEACHER/'results.json'),'programs_ref':fingerprint(program_dir/'programs.json'),'cases_ref':digest(cases),'source_extraction_plan':source_manifest['fit_plan'],'fit_spec':LIMITS,
       'teacher_only':'Only resolved teacher predictions on cases with facts are fit targets.',
       'human_refined':'Same-case dataset labels are fit targets; teacher concepts seed predicate order and teacher agreement breaks ties.',
       'semantic_inputs':'Physical factual predicates only. No grade/state levels, instruction/object strings, scores, labels, IDs, or operation-only class priors enter prediction.',
       'new_api_calls':0}
    if (output/'plan.json').exists() and read(output/'plan.json')!=plan:raise ValueError('Changed distillation plan')
    save_json(output/'plan.json',plan)
    groups={};pool={k:[] for k in ('teacher','teacher_distilled','human_refined')};all_y=[]
    for group in ('G1','G2','G3','G4'):
        part=[c for c in cases if c['batch']==group]
        x=[fact_record(observed[c['case']]['extraction']['observations']) if observed[c['case']]['extraction'] else None for c in part]
        x=[compile_record(r,program_rows[c['case']]['compilation']['program']) if r is not None and program_rows[c['case']]['compilation'] else None for r,c in zip(x,part)]
        y=[('no','partial','yes').index(c['reference']) for c in part];all_y+=y
        t=teachers['groups'][group]['unclustered']['policy'];old=VisibilityOrdinalCalibrator.restore(t)
        old_x=[feature_record(original[c['case']]['extraction']['observations'],c['instruction']) if original[c['case']]['extraction'] else {'lower':[0]*8,'upper':[4]*8,'descriptor':None} for c in part]
        teacher_y=[r['prediction'] for r in old.predict_records(old_x)];concepts=[k for k,w in zip(QUALITIES,t['weights']) if w]
        arms={'teacher':{'metrics':classification_metrics(teacher_y,y)[0],'predictions':teacher_y}}
        for family in ('teacher_distilled','human_refined'):
            model=FactualRuleCalibrator(concepts)
            indices=[i for i in range(12) if x[i] is not None and teacher_y[i]>=0] if family=='teacher_distilled' else list(range(12))
            train_x=[x[i] for i in indices];train_y=[teacher_y[i] if family=='teacher_distilled' else y[i] for i in indices]
            error=None;artifact=None;ref=path=None
            try:model.fit(train_x,train_y,source_groups=[part[i]['group'] for i in indices],teacher_targets=[teacher_y[i] for i in indices])
            except ValueError as exc:
                error=str(exc);records=[{'prediction':-1,'reason':'unsupported_fit'} for _ in x]
            else:
                records=model.predict_records(x);artifact=model.metadata();ref,path=registry.publish(artifact)
                if FactualRuleCalibrator.restore(artifact).predict_records(x)!=records:raise AssertionError('Restore changed factual decisions')
                directory=output/'rules'/group/family;directory.mkdir(parents=True,exist_ok=True)
                (directory/'policy.txt').write_text(model.render()+'\n');save_json(directory/'policy.json',artifact)
            p=[r['prediction'] for r in records];metric=classification_metrics(p,y)[0]
            arms[family]={'metrics':metric,'predictions':p,'policy':artifact,'error':error,
                'registry_ref':ref,'registry_path':str(path) if path else None,'training_cases':[part[i]['case'] for i in indices],
                'teacher_agreements':sum(a==b for a,b in zip(p,teacher_y)),'search':getattr(model,'search_diagnostic',None),
                'cases':[{'case':c['case'],'instruction':c['instruction'],'reference':a,'teacher_prediction':b,
                          'facts':r,'decision':d,'extraction_error':observed[c['case']]['error']} for c,a,b,r,d in zip(part,y,teacher_y,x,records)]}
            print({'group':group,'family':family,'correct':metric['correct'],'macro_f1':metric['macro_f1'],
                   'coverage':12-metric['unresolved'],'error':error,'search':arms[family]['search']},flush=True)
        for family in pool:pool[family]+=arms[family]['predictions']
        groups[group]=arms
    result={'version':plan['version'],'plan_ref':digest(plan),'groups':groups,
        'pooled':{k:classification_metrics(v,all_y)[0] for k,v in pool.items()},
        'new_api_calls_in_fit':0,'factual_extraction_cost':{'attempts':facts['attempts'],'outcomes':facts['outcomes'],
            'input_tokens':facts['input_tokens'],'completion_tokens':facts['completion_tokens'],
            'returned_usage_cost_usd':(facts['input_tokens']*2+facts['completion_tokens']*10)/1e6},
        'all_groups_at_least_teacher':all(g['human_refined']['metrics']['correct']>=g['teacher']['metrics']['correct'] for g in groups.values()),
        'scope':'Teacher-assisted local distillation and supervised local refinement. No unseen-case accuracy or repeat robustness claim.'}
    if (output/'results.json').exists() and read(output/'results.json')!=result:raise ValueError('Changed distillation replay')
    save_json(output/'results.json',result)
    files=[Path(__file__).resolve(),ROOT/'critical/core/calibration/bound_factual_dnf.py',ROOT/'critical/core/decision/bound_witnesses.py',ROOT/'critical/core/calibration/factual_rules.py',ROOT/'tests/unit/calitree/test_bound_witnesses.py']
    hashes={}
    for p in files:
        rel=str(p.relative_to(ROOT));dst=output/'source_snapshot'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst);hashes[rel]=fingerprint(p)
    save_json(output/'fit_seal.json',{'code_hashes':hashes,'plan_ref':fingerprint(output/'plan.json'),'results_ref':fingerprint(output/'results.json'),'facts_ref':fingerprint(FACTS/'facts.json')})
    (output/'llm-histories.log').write_text('No model calls in distillation. Raw factual extraction history: ../261014-observable-semantic-facts-v10/llm-histories.log\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    run(p.parse_args().output_dir.resolve())
