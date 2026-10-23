"""Offline attribution diagnostics for rejected pilot cases; no fitting/calls."""
import argparse
from collections import Counter
from copy import deepcopy
from pathlib import Path

from critical.core.decision.artifacts import digest,save_json
from critical.core.calibration.semantic_hierarchy.portable_review_v8 import CONTRADICTS_YES
from critical.core.decision import semantic_interpretation_v5 as meaning
from run.calitree_aurora_pilot_v29 import read,fingerprint
from run.calitree_ungated_ablation_v30 import load_banks,predict_bank,shared

VERSION='rejected-case-attribution-v31'
REVIEWED=('P01M1','P03M4','P05M5','P06M3','P09M1','P14M5')


def bank_stats(rows,bank):
    key=str(bank);gated=f'v27_split{bank}';ungated=f'ungated_split{bank}'
    rejected=[r for r in rows if not r['routes'][gated]['covered']]
    valid=[r for r in rejected if not r['extraction_error']]
    wrong=[r for r in valid if r[ungated]!=r['reference']]
    def correct_refs(row):
        return {ref for ref,v in row['votes'][key]['expert_votes'].items()if v['prediction']==row['reference']}
    def shortlisted(row):
        return set(row['routes'][gated].get('semantic_candidates',{}).get('expert_refs',[]))
    def counts(subset):
        return {'cases':len(subset),'vote_correct':sum(r[ungated]==r['reference']for r in subset),
                'regular_correct':sum(r['regular']==r['reference']for r in subset),
                'any_expert_correct':sum(bool(correct_refs(r))for r in subset),
                'correct_expert_in_task_shortlist':sum(bool(correct_refs(r)&shortlisted(r))for r in subset)}
    return {'bank':bank,'rejected':len(rejected),'extraction_failures':len(rejected)-len(valid),
            'valid_rejected':counts(valid),'wrong_vote_cases':len(wrong),
            'wrong_vote_with_correct_expert':sum(bool(correct_refs(r))for r in wrong),
            'wrong_vote_with_correct_shortlisted_expert':sum(bool(correct_refs(r)&shortlisted(r))for r in wrong),
            'all_experts_wrong':sum(not correct_refs(r)for r in wrong),
            'all_experts_wrong_cases':[r['case']for r in wrong if not correct_refs(r)],
            'by_rejection_reason':{reason:counts([r for r in valid if r['routes'][gated]['reason']==reason])
                                   for reason in sorted({r['routes'][gated]['reason']for r in valid})}}


def warnings(saved):
    req=list(saved['interpretation']['requirements'].values())
    return {'any_goal_failure':any(r['progress']in('none','incidental_change_only') or r['endpoint_gap']in('core_endpoint_missing','wrong_direction_or_target')for r in req),
            'any_material_shortfall':any(r['identity_materiality']=='material_shortfall' or r['collateral_materiality']=='material_unrequested_change'for r in req),
            'any_evidence_uncertainty':any(r['progress']=='uncertain' or r['evidence_consistency']!='coherent'for r in req),
            'multiple_requirements':len(req)>1}


def manual_doodle_repair(saved):
    """Illustrative visual-review intervention; never replace recorded evidence.

    The cat remains visible in the doodle image. Correct the three observation
    judgments that claim its loss, then make the interpretation consistent with
    those corrections. This is not a new model draw or a human gold annotation.
    """
    repaired=deepcopy(saved);obs=repaired['observation'];interp=repaired['interpretation']
    for key,state in (('c04','false'),('c05','false'),('c06','true')):
        obs['checks'][key]['state']=state
        obs['checks'][key]['edited_evidence']='Manual diagnostic review: the outlined gray cat-shaped figure remains in front of the television, between the smaller figures.'
        obs['checks'][key]['comparison']='Manual diagnostic review: the recognizable cat and scene configuration remain; changed linework and shading are authorized by the doodle-style request.'
    payload=meaning.make_input(repaired['program'],obs,repaired['pair_ref'])
    interp['evidence_ref']=digest([meaning.VERSION,{k:v for k,v in payload.items()if k!='evidence_ref'}])
    assert interp['evidence_ref']==payload['evidence_ref']
    interp['requirements']['r1'].update(identity_materiality='no_shortfall',collateral_materiality='none',evidence_consistency='coherent',
        explanation='Manual diagnostic interpretation: the style endpoint is achieved and the central cat remains a recognizable counterpart. No material deletion or unauthorized structural change is established.')
    meaning.validate(payload,interp)
    return repaired


def run(out,ablation):
    if out.exists():raise ValueError('Use a fresh diagnostic directory')
    for name,h in read(ablation/'completion_seal.json')['files'].items():assert fingerprint(ablation/name)==h
    parent=Path(read(ablation/'manifest.json')['parent']);rows=read(ablation/'predictions.json')
    inputs={r['case']:r for r in read(parent/'inputs.json')};banks=load_banks(parent)
    out.mkdir(parents=True)
    protocol={'version':VERSION,'scope':'Descriptive bank-case/trace diagnostics and six targeted visual reviews; no causal population percentages.',
              'oracle':'A correct expert exists is an upper bound on routing/selection headroom, not an implementable router.',
              'warning':'Cached goal-failure/materiality flags diagnose disagreement with available evidence; they are not automatically assumed visually correct.',
              'counterfactual':'One manually reviewed doodle repair, isolated copies only; no relabeling, fitting or model calls.',
              'reviewed_cases':list(REVIEWED),'new_model_calls':0}
    save_json(out/'protocol.json',protocol);statistics=[bank_stats(rows,i)for i in (1,2,3)]
    evidence_stats={};all_records={};source_files={ablation/'completion_seal.json',ablation/'predictions.json',parent/'inputs.json'}
    for row in rows:
        path=parent/'collection/cases'/(row['case']+'.json');source_files.add(path);saved=read(path)
        if saved['extraction_error']:continue
        record=shared.evidence.project(saved['program'],saved['observation'],saved['pair_ref'],saved['interpretation'])
        all_records[row['case']]=(saved,record,warnings(saved))
    for i in (1,2,3):
        gated=f'v27_split{i}';ungated=f'ungated_split{i}';valid=[r for r in rows if not r['routes'][gated]['covered'] and not r['extraction_error']]
        yes=[r for r in valid if r[ungated]==2]
        flags={f:[r['case']for r in yes if all_records[r['case']][2][f]]for f in('any_goal_failure','any_material_shortfall','any_evidence_uncertainty')}
        strong=[r['case']for r in yes if any(all_records[r['case']][1]['features'][f]for f in CONTRADICTS_YES)]
        expert_yes=[]
        for r in valid:
            record=all_records[r['case']][1]
            for ref,v in r['votes'][str(i)]['expert_votes'].items():
                if v['prediction']==2:
                    active=[f for f in CONTRADICTS_YES if record['features'][f]]
                    read_names={c['feature']for c in v['trace']}
                    expert_yes.append({'case':r['case'],'expert_ref':ref,'gold_correct':r['reference']==2,
                                       'active_contradictions':active,'unread_contradictions':[f for f in active if f not in read_names]})
        evidence_stats[str(i)]={'valid_rejected':len(valid),'ungated_yes':len(yes),'ungated_yes_correct':sum(r['reference']==2 for r in yes),
                               'yes_with_all_requirements_goal_contradiction':strong,'yes_warning_cases':flags,
                               'expert_yes_votes':len(expert_yes),'expert_yes_with_unread_goal_contradiction':sum(bool(r['unread_contradictions'])for r in expert_yes),
                               'expert_yes_details':expert_yes}
    examples=[]
    for case in REVIEWED:
        row=next(r for r in rows if r['case']==case);saved,record,flags=all_records[case]
        examples.append({'case':case,'instruction':inputs[case]['instruction'],'images':inputs[case]['evidence'],
                         'image_hashes':inputs[case]['image_hashes'],'reference':row['reference'],'regular':row['regular'],
                         'contract':saved['program']['contract'],'requirements':saved['program']['requirements'],
                         'interpretation':saved['interpretation'],'warnings':flags,
                         'bank_traces':{str(i):{'vote':row[f'ungated_split{i}'],'gate_reason':row['routes'][f'v27_split{i}']['reason'],
                            'experts':row['votes'][str(i)]['expert_votes']}for i in(1,2,3)}})
    saved,_,_=all_records['P06M3'];repaired=manual_doodle_repair(saved)
    repaired_record=shared.evidence.project(repaired['program'],repaired['observation'],repaired['pair_ref'],repaired['interpretation'])
    repaired_predictions={str(i):predict_bank(experts,repaired_record)for i,(_,experts)in banks.items()}
    save_json(out/'manual_doodle_counterfactual.json',{'case':'P06M3','scope':'Illustrative manual evidence intervention, not official corrected labels or new model output.',
              'observation':repaired['observation'],'interpretation':repaired['interpretation'],'predictions':repaired_predictions})
    summary={'version':VERSION,'banks':statistics,'evidence_diagnostics':evidence_stats,'new_model_calls':0,
             'manual_counterfactual_predictions':{i:p['prediction']for i,p in repaired_predictions.items()}}
    save_json(out/'results.json',summary);save_json(out/'review_examples.json',examples)
    code=[Path(__file__).resolve(),Path('critical/core/calibration/semantic_hierarchy/portable_review_v8.py').resolve()]
    save_json(out/'manifest.json',{'ablation':str(ablation),'parent':str(parent),'protocol_ref':digest(protocol),
              'source_hashes':{str(p):fingerprint(p)for p in sorted(source_files)},'code_hashes':{str(p):fingerprint(p)for p in code}})
    (out/'run.log').write_text('Cached predictions and evidence diagnosed; six image pairs visually reviewed; one isolated manual counterfactual.\n')
    (out/'llm-histories.log').write_text('Zero model calls.\n')
    print({'banks':statistics,'evidence_summary':{i:{k:v for k,v in s.items()if k!='expert_yes_details'}for i,s in evidence_stats.items()},'counterfactual':summary['manual_counterfactual_predictions']},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--ablation-run',type=Path,required=True);a=p.parse_args()
    run(a.output_dir.resolve(),a.ablation_run.resolve())
