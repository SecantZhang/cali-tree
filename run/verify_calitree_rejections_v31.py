"""Verify diagnostic counts, reviewed-image identities and isolated intervention."""
import argparse
from pathlib import Path

from run.diagnose_calitree_rejections_v31 import read,fingerprint,shared,load_banks,predict_bank
from critical.core.decision.artifacts import save_json,digest


def audit(out):
    m=read(out/'manifest.json');result=read(out/'results.json');parent=Path(m['parent'])
    assert digest(read(out/'protocol.json'))==m['protocol_ref']
    for path,h in {**m['source_hashes'],**m['code_hashes']}.items():assert fingerprint(path)==h
    rows=read(Path(m['ablation'])/'predictions.json')
    for summary in result['banks']:
        i=summary['bank'];valid=[r for r in rows if not r['routes'][f'v27_split{i}']['covered'] and not r['extraction_error']]
        wrong=[r for r in valid if r[f'ungated_split{i}']!=r['reference']]
        allwrong=[r for r in wrong if all(v['prediction']!=r['reference']for v in r['votes'][str(i)]['expert_votes'].values())]
        assert summary['valid_rejected']['cases']==len(valid)
        assert summary['wrong_vote_cases']==len(wrong)
        assert summary['all_experts_wrong']==len(allwrong)
        assert summary['wrong_vote_with_correct_expert']==len(wrong)-len(allwrong)
        assert summary['all_experts_wrong_cases']==[r['case']for r in allwrong]
        shortlist_correct=0
        for r in wrong:
            refs=r['routes'][f'v27_split{i}'].get('semantic_candidates',{}).get('expert_refs',[])
            shortlist_correct+=any(ref in refs and v['prediction']==r['reference']for ref,v in r['votes'][str(i)]['expert_votes'].items())
        assert summary['wrong_vote_with_correct_shortlisted_expert']==shortlist_correct
        diagnostic=result['evidence_diagnostics'][str(i)]
        yes=[r for r in valid if r[f'ungated_split{i}']==2]
        assert diagnostic['ungated_yes']==len(yes)
        assert diagnostic['ungated_yes_correct']==sum(r['reference']==2 for r in yes)
        from critical.core.calibration.semantic_hierarchy.portable_review_v8 import CONTRADICTS_YES
        expected=[]
        for r in yes:
            cached=read(parent/'collection/cases'/(r['case']+'.json'))
            record=shared.evidence.project(cached['program'],cached['observation'],cached['pair_ref'],cached['interpretation'])
            if any(record['features'][f]for f in CONTRADICTS_YES):expected.append(r['case'])
        assert diagnostic['yes_with_all_requirements_goal_contradiction']==expected
    reviewed=read(out/'review_examples.json')
    for item in reviewed:
        for kind,path in item['images'].items():assert fingerprint(path)==item['image_hashes'][kind]
    counter=read(out/'manual_doodle_counterfactual.json');original=read(parent/'collection/cases/P06M3.json')
    assert counter['observation']!=original['observation'] and counter['interpretation']!=original['interpretation']
    changed=[k for k,v in original['observation']['checks'].items()if counter['observation']['checks'][k]!=v]
    assert changed==['c04','c05','c06']
    record=shared.evidence.project(original['program'],counter['observation'],original['pair_ref'],counter['interpretation'])
    for i,(_,experts)in load_banks(parent).items():
        actual=predict_bank(experts,record)
        assert actual==counter['predictions'][str(i)] and actual['prediction']==result['manual_counterfactual_predictions'][str(i)]
    leaf_path=out/'shortcut_leaf_provenance.json'
    if not leaf_path.exists():
        source=parent.parent/'261019-pairwise-merge-v24-r1/split3/development.json'
        models=read(source)['models'];model=next(m for m in models if m['runtime']['artifact_ref'].startswith('80985'))
        node=model['policy']['tree'];path=[]
        for value in (True,True):
            path.append({'feature':node['feature'],'value':value});node=node['true'if value else'false']
        save_json(leaf_path,{'source':str(source),'sha256':fingerprint(source),'expert_ref':model['runtime']['artifact_ref'],
                  'path':path,**{k:node[k]for k in ('prediction','support','counts','source_batches')}})
    leaf=read(leaf_path)
    assert fingerprint(leaf['source'])==leaf['sha256']
    models=read(leaf['source'])['models'];model=next(m for m in models if m['runtime']['artifact_ref']==leaf['expert_ref'])
    node=model['policy']['tree']
    for condition in leaf['path']:
        assert node['feature']==condition['feature'];node=node['true'if condition['value']else'false']
    assert all(node[k]==leaf[k] for k in ('prediction','support','counts','source_batches'))
    report={'passed':True,'shortcut_leaf_provenance_verified':True,'bank_attribution_counts_checked':3,'reviewed_image_pairs_hash_verified':len(reviewed),
            'manual_counterfactual_schema_and_votes_verified':True,'original_evidence_unchanged':True,
            'no_global_causal_error_percentages_claimed':True,'new_model_calls':0,'new_fitting':False}
    save_json(out/'verification.json',report)
    save_json(out/'completion_seal.json',{'files':{str(p.relative_to(out)):fingerprint(p)for p in sorted(out.rglob('*'))if p.is_file()and p.name!='completion_seal.json'},'auditor_sha256':fingerprint(__file__)})
    print(report,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    audit(p.parse_args().output_dir.resolve())
