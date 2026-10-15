"""Cached local and frozen cross-group tests of instruction-dependent rules."""
import argparse
from collections import Counter
from pathlib import Path
import shutil

from critical.core.calibration.instruction_rules import InstructionRuleCalibrator,instruction_record,GRID,DEFAULT,CONTRACT,LIMITS
from critical.core.calibration.visibility_calibration import VisibilityOrdinalCalibrator
from critical.core.calibration.evidence_rules_v4 import classification_metrics
from critical.core.calibration.registry import CalibrationRegistry
from critical.core.decision.artifacts import digest,save_json
from critical.core.decision.semantic_evidence import feature_record
from critical.core.decision.literal_quotes import normalize_literal_quotes
from run.calitree_single_call import ROOT,read,fingerprint

FIXED=ROOT/'logs/exps/261013-four-groups-local-v4'
FAST=ROOT/'logs/exps/261014-fast-models-four-groups-v2'
SOL=ROOT/'logs/exps/261014-semantic-visibility-calibration-v6'
SOL_EVIDENCE=ROOT/'logs/exps/261014-semantic-contract-evidence-v5'
VERSION='instruction-interaction-frozen-transfer-v7'


def prepare(output):
    output.mkdir(parents=True,exist_ok=True)
    if (output/'manifest.json').exists():
        m=read(output/'manifest.json');verify(output,m);return m
    cases=read(FIXED/'manifest.json')['cases']
    pinned=[FIXED/'manifest.json',FIXED/'results.json',FAST/'manifest.json',FAST/'observations.json',FAST/'results.json',
            SOL/'results.json',SOL_EVIDENCE/'results.json']
    files=[Path(__file__).resolve(),ROOT/'tests/unit/calitree/test_instruction_rules.py']
    files += [ROOT/f'critical/core/{p}' for p in ('calibration/instruction_rules.py','calibration/visibility_calibration.py',
        'calibration/semantic_calibration.py','calibration/evidence_rules_v4.py','decision/semantic_evidence.py','decision/literal_quotes.py')]
    hashes={}
    for p in files:
        rel=str(p.relative_to(ROOT));dst=output/'source_snapshot'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst);hashes[rel]=fingerprint(p)
    m={'version':VERSION,'cases':cases,'models':['luna','sol','mini_normalized'],
       'primary_model':'luna','primary_train_group':'G1','primary_evaluation_groups':['G2','G3','G4'],
       'protocol':'Fit on one group of 12; freeze policy before scoring each other group. Four reciprocal folds are secondary. Local diagonals reported separately.',
       'selection':'Only training-group labels determine thresholds. Fixed default-biased tie-break; no test-label selection.',
       'candidates':{k:list(v) for k,v in GRID.items()},'default':DEFAULT,'rule_contract':CONTRACT,'limits':LIMITS,
       'controls':['same-model flat','frozen previous v6 shared rubric from the same training group','fixed unfitted semantic default'],
       'evidence':'Cached same-model v5 responses only; mini uses the previously validated literal-quote normalization. No new visual judgments or label changes.',
       'development_caveat':'All four groups have been inspected historically. Cross-group tests hold out labels from each fit, not from all prior method development.',
       'failures':'Keep missing/invalid evidence in the denominator. An unsupported trained fit remains unresolved; fixed default is a separately named control.',
       'new_api_calls':0,'pinned_files':{str(p):fingerprint(p) for p in pinned},'code_hashes':hashes}
    save_json(output/'manifest.json',m);save_json(output/'seal.json',{'manifest_ref':digest(m)});verify(output,m);return m


def verify(output,m):
    if m['version']!=VERSION or digest(m)!=read(output/'seal.json')['manifest_ref']:
        raise ValueError('Changed frozen interaction experiment')
    for p,h in m['pinned_files'].items():
        if fingerprint(p)!=h:raise ValueError('Changed cached input')
    for rel,h in m['code_hashes'].items():
        if fingerprint(ROOT/rel)!=h or fingerprint(output/'source_snapshot'/rel)!=h:raise ValueError('Changed rule implementation')
    if len(m['cases'])!=48 or len({c['group'] for c in m['cases']})!=48:raise ValueError('Fixed distinct sources required')
    for b in ('G1','G2','G3','G4'):
        if Counter(c['reference'] for c in m['cases'] if c['batch']==b)!={'no':4,'partial':4,'yes':4}:raise ValueError('Changed label balance')
    for c in m['cases']:
        for k,p in c['evidence'].items():
            if fingerprint(p)!=c['image_hashes'][k]:raise ValueError('Changed source or edit image')


def load_inputs(m):
    fast=read(FAST/'results.json');fast_observed={(r['model_key'],r['case'],r['arm']):r for r in read(FAST/'observations.json')['observations']}
    sol=read(SOL/'results.json');sol_observed={r['case']:r for r in read(SOL_EVIDENCE/'results.json')['observations']}
    fixed=read(FIXED/'results.json');models={}
    for key in m['models']:
        values=[];flat=[];old_features=[];old_policies={}
        for c in m['cases']:
            if key=='sol':
                observed=sol_observed[c['case']];value=observed['extraction']['observations'] if observed['extraction'] else None
                flat_row=next(r for r in fixed['batches'][c['batch']]['flat_cases'] if r['case']==c['case'])
                old_policies[c['batch']]=sol['groups'][c['batch']]['unclustered']['policy']
            else:
                source='mini' if key=='mini_normalized' else 'luna';observed=fast_observed[(source,c['case'],'evidence')]
                value=observed['extraction']['observations'] if observed['extraction'] else None
                if key=='mini_normalized' and value is None:
                    receipt=next((r for r in fast['models']['mini']['modes']['literal_quote_normalized']['normalizations'] if r['case']==c['case']),None)
                    if receipt:
                        files=list((FAST/'ledgers/mini'/c['case']/'evidence/jobs').glob('*.json'));job=read(files[0])
                        value,changes=normalize_literal_quotes(job['parsed'],c['instruction'])
                        if changes!=receipt['changes']:raise ValueError('Changed previously approved normalization')
                mode='literal_quote_normalized' if source=='mini' else 'strict'
                old_policies[c['batch']]=fast['models'][source]['modes'][mode]['groups'][c['batch']]['local_shared']['policy']
                flat_row=fast_observed[(source,c['case'],'flat')]
            values.append(instruction_record(value,c['instruction']) if value else None)
            old_features.append(feature_record(value,c['instruction']) if value else {'lower':[0]*8,'upper':[4]*8,'descriptor':None})
            flat.append(('no','partial','yes').index(flat_row['prediction']) if flat_row['prediction'] is not None else -1)
        models[key]={'records':values,'old_features':old_features,'flat':flat,'old_policies':old_policies}
    return models


def scored(cases,indices,predictions,records=None):
    part=[cases[i] for i in indices];targets=[('no','partial','yes').index(c['reference']) for c in part]
    metrics=classification_metrics(predictions,targets)[0]
    return {'metrics':metrics,'cases':[{'case':c['case'],'reference':t,'prediction':p,
        **({'decision':d} if records is not None else {})} for c,t,p,d in zip(part,targets,predictions,records if records is not None else [None]*len(part))]}


def execute(output,m):
    cases=m['cases'];inputs=load_inputs(m);result={'version':VERSION,'manifest_ref':digest(m),'models':{},'new_api_calls':0}
    registry=CalibrationRegistry(output/'registry')
    for key,data in inputs.items():
        records=data['records'];models={};folds={}
        default=InstructionRuleCalibrator();default_records=default.predict_records(records)
        default_result=scored(cases,list(range(48)),[r['prediction'] for r in default_records],default_records)
        for train_group in ('G1','G2','G3','G4'):
            train=[i for i,c in enumerate(cases) if c['batch']==train_group]
            train_x=[records[i] for i in train];train_y=[('no','partial','yes').index(cases[i]['reference']) for i in train]
            policy=InstructionRuleCalibrator();artifact=None;error=None;path=version=None
            try:policy.fit(train_x,train_y,source_groups=[cases[i]['group'] for i in train])
            except ValueError as exc:error=str(exc)
            else:
                artifact=policy.metadata();version,path=registry.publish(artifact)
                if InstructionRuleCalibrator.restore(artifact).predict_records(train_x)!=policy.predict_records(train_x):raise AssertionError('Restore changed policy')
            # Policy artifact is frozen and published before evaluation labels
            # are read for scoring. No refitting occurs in this prediction loop.
            models[train_group]={'artifact':artifact,'error':error,'search':policy.search_diagnostic,'registry_version':version,
                'registry_path':str(path) if path else None,'training_cases':[cases[i]['case'] for i in train],
                'training_sources':[cases[i]['group'] for i in train],
                'training_feature_ref':digest(train_x),'training_target_ref':digest(train_y)}
            before=digest(artifact);matrix={}
            old=VisibilityOrdinalCalibrator.restore(data['old_policies'][train_group]) if data['old_policies'][train_group] else None
            for eval_group in ('G1','G2','G3','G4'):
                indices=[i for i,c in enumerate(cases) if c['batch']==eval_group]
                new_records=policy.predict_records([records[i] for i in indices]) if artifact else [{'prediction':-1,'reason':'unsupported_training_fit'} for _ in indices]
                old_records=old.predict_records([data['old_features'][i] for i in indices]) if old else [{'prediction':-1} for _ in indices]
                matrix[eval_group]={'instruction_rules':scored(cases,indices,[r['prediction'] for r in new_records],new_records),
                    'previous_v6':scored(cases,indices,[r['prediction'] for r in old_records],old_records),
                    'flat':scored(cases,indices,[data['flat'][i] for i in indices]),
                    'source_disjoint_from_training':not bool(set(cases[i]['group'] for i in train)&set(cases[i]['group'] for i in indices))}
            if digest(artifact)!=before:raise AssertionError('Evaluation changed fitted policy')
            held=[i for i,c in enumerate(cases) if c['batch']!=train_group]
            off_diag={}
            for family in ('instruction_rules','previous_v6','flat'):
                predictions={r['case']:r['prediction'] for b,row in matrix.items() if b!=train_group for r in row[family]['cases']}
                off_diag[family]=scored(cases,held,[predictions[cases[i]['case']] for i in held])
            # Training-equivalent policies expose underdetermination. These
            # test scores are diagnostics only and NEVER select the deployment.
            ambiguity=[]
            if artifact:
                for t in artifact['equally_scoring_training_policies']:
                    p=InstructionRuleCalibrator(t).predict_records([records[i] for i in held])
                    ambiguity.append({'thresholds':t,'metrics':scored(cases,held,[r['prediction'] for r in p])['metrics']})
            folds[train_group]={'matrix':matrix,'heldout36':off_diag,'equivalent_training_policy_transfer':ambiguity,
                               'frozen_policy_ref_before_and_after':before}
            print({'model':key,'train':train_group,'error':error,'local':matrix[train_group]['instruction_rules']['metrics']['correct'],
                   'other36':{family:value['metrics']['correct'] for family,value in off_diag.items()}},flush=True)
        local={}
        for family in ('instruction_rules','previous_v6','flat'):
            diagonal={r['case']:r['prediction'] for b,row in folds.items() for r in row['matrix'][b][family]['cases']}
            local[family]=scored(cases,list(range(48)),[diagonal[c['case']] for c in cases])
        result['models'][key]={'valid_evidence':sum(r is not None for r in records),'fixed_default':default_result,
                              'policies':models,'folds':folds,'local48':local,'compiled_records_ref':digest(records)}
    verify(output,m)
    if (output/'results.json').exists() and read(output/'results.json')!=result:raise ValueError('Replay changed interaction experiment')
    save_json(output/'results.json',result)
    save_json(output/'compiled_records.json',{key:data['records'] for key,data in inputs.items()})
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--preflight',action='store_true');p.add_argument('--replay',action='store_true');a=p.parse_args()
    output=a.output_dir.resolve();m=prepare(output)
    if a.preflight:print({'ready':True,'new_api_calls':0,'candidates':16,'primary':'Luna G1 train -> frozen G2/G3/G4'});return
    if a.replay and not (output/'results.json').exists():raise ValueError('Replay needs saved results')
    result=execute(output,m)
    if a.replay:save_json(output/'replay.json',{'exact_refit_and_prediction_replay':True,'new_api_calls':0,'results_ref':fingerprint(output/'results.json')})
    (output/'llm-histories.log').write_text('Offline rule calibration and cached inference only; zero API calls. Raw history remains in the pinned source experiment directories.\n')


if __name__=='__main__':main()
