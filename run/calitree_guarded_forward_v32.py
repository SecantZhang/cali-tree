"""Freeze source-disjoint cached forward inputs and a 36-call regular baseline."""
import argparse
from pathlib import Path

from critical.core.decision.artifacts import digest,save_json
from critical.core.calibration import semantic_guarded_merge_v32 as fixed,decision_warrant_gate_v33 as warrant
from run.calitree_guarded_generalization_v32 import ROOT,PILOT,context
from run.calitree_aurora_pilot_v29 import read,fingerprint,IDENTITY

V32=ROOT/'logs/exps/261020-guarded-generalization-v32-r1'
V33=ROOT/'logs/exps/261020-decision-warrants-v33-r1'
SOURCE=Path('/Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/logs/exps/261018-three-sampled-splits-luna-compiler-v3')


def prepare(out):
    if out.exists():raise ValueError('Fresh output directory required')
    out.mkdir(parents=True)
    known=set();fit_sources=set()
    for i in(1,2,3):
        _,_,_,_,_,examples=context(i)
        known.update(e['case']for e in examples);fit_sources.update(e['source_group']for e in examples)
    pilot=read(PILOT/'inputs.json');fit_sources.update(e['source_group']for e in pilot)
    metadata=read(SOURCE/'manifest.json')['cases'];selected=[e for e in metadata if e['case']not in known]
    assert len(selected)==36 and len({e['group']for e in selected})==36
    assert not fit_sources&{e['group']for e in selected}
    assert len(known)==99
    gates={}
    for i in(1,2,3):
        gates[f'v27_split{i}']=fixed.shared.SharedRegionGate(read(PILOT/f'gates/v27_split{i}.json'))
        gates[f'v28_split{i}']=fixed.merging.SemanticMergedRegionGate(read(PILOT/f'gates/v28_split{i}.json'))
        for method in('verified_v27','verified_v28','guarded_merge'):
            gates[f'{method}_split{i}']=fixed.VerifiedRegionGate.restore(read(V32/f'full/split{i}/{method}.json'))
        gates[f'warrant_split{i}']=warrant.DecisionWarrantGate.restore(read(V33/f'full/split{i}/gate.json'))
    frozen={}
    for name,gate in gates.items():
        save_json(out/'gates'/(name+'.json'),gate.export());frozen[name]=gate.artifact['artifact_ref']
    # Model artifacts frozen before accessing forward references for scoring.
    save_json(out/'freeze.json',{'models':frozen,'v32_freeze_sha256':fingerprint(V32/'freeze.json'),'v33_freeze_sha256':fingerprint(V33/'freeze.json')})
    inputs=[];predictions=[];files={SOURCE/'manifest.json',V32/'freeze.json',V33/'freeze.json'}
    for e in sorted(selected,key=lambda e:e['case']):
        p=SOURCE/f"extraction/cases/{e['case']}.json";m=SOURCE/f"interpretations/{e['case']}.json";files.add(p)
        extracted=read(p);interpreted=read(m)if m.exists()else None
        if m.exists():files.add(m)
        program=extracted['compilation']['program']if extracted['compilation']else None;record=None
        if extracted['error']is None and interpreted and interpreted['error']is None:
            obs=extracted['observation']['observation'];record=fixed.shared.evidence.project(program,obs,obs['image_pair_ref'],interpreted['interpretation'])
        entry={'case':e['case'],'source_group':e['group'],'instruction':e['instruction'],'evidence':e['evidence'],
               'image_hashes':e['image_hashes'],'program':program,'features':record,'task':e['task']}
        inputs.append(entry);routes={}
        for name,gate in gates.items():
            routes[name]=gate.select(program,record)if record is not None else {'covered':False,'prediction':-1,'reason':'missing_or_invalid_evidence','matches':[]}
        predictions.append({'case':e['case'],'routes':routes})
    save_json(out/'inputs.json',inputs);save_json(out/'frozen_predictions.json',predictions)
    save_json(out/'prediction_freeze.json',{'predictions_sha256':fingerprint(out/'frozen_predictions.json'),'inputs_sha256':fingerprint(out/'inputs.json')})
    refs={e['case']:e['reference']for e in selected};save_json(out/'references.json',refs)
    summary={}
    for name in gates:
        accepted=[p for p in predictions if p['routes'][name]['covered']]
        correct=sum(p['routes'][name]['prediction']==('no','partial','yes').index(refs[p['case']])for p in accepted)
        summary[name]={'accepted':len(accepted),'correct':correct,'wrong':len(accepted)-correct,'coverage':len(accepted)/36,
                       'accepted_accuracy':correct/len(accepted)if accepted else None}
    save_json(out/'selective_results.json',summary)
    protocol={'version':'guarded-forward-v32','cases':36,'source_disjoint_from_new_fitting':True,'legacy_research_exposure':True,
              'identity':IDENTITY,'collection':'One fresh regular judgment per fixed case. Existing compiler-v3 bound evidence reused; no observation or compiler retries.',
              'max_requests':36,'max_completion_tokens':36*2048,'max_tokens_per_request':2048,'regular_prompt':'unchanged task_coverage_v19/regular.txt',
              'expected_cost_usd':.006,'completion_cap_cost_usd':.036864,'cost_note':'Plus input charges at previously reviewed Luna rates; no new extraction calls.',
              'paid_authorization_required':True,'new_model_calls':0}
    save_json(out/'protocol.json',protocol)
    save_json(out/'manifest.json',{'protocol_ref':digest(protocol),'source_hashes':{str(p):fingerprint(p)for p in sorted(files)},
              'input_ref':digest(inputs),'references_ref':digest(refs),'frozen_gate_refs':frozen,
              'code_hashes':{str(Path(p).resolve()):fingerprint(p)for p in(__file__,fixed.__file__,warrant.__file__)}})
    (out/'run.log').write_text('Forward inputs/models and predictions frozen before reference scoring; regular baseline not collected.\n')
    (out/'llm-histories.log').write_text('Zero model calls; pending separate 36-call baseline authorization.\n')
    print(summary,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();prepare(a.output_dir.resolve())
