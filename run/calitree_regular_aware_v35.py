"""Cross-source evaluation of regular-aware semantic verification and routing."""
import argparse
from pathlib import Path
from critical.core.calibration import regular_aware_gate_v35 as aware
from critical.core.decision.artifacts import digest,save_json
from run.calitree_guarded_generalization_v32 import load_pilot,context,calibrations,ROOT
from run.calitree_fallback_routing_v34 import old_examples
from run.collect_calitree_aurora_pilot_v29r1 import metrics
from run.calitree_aurora_pilot_v29 import read,fingerprint

BASE=ROOT/'logs/exps/261020-guarded-generalization-v32-r1'


def build(bank,base,training):
    _,_,raw,_,_,_=context(bank);old=old_examples(bank)
    protected=[];calibration=[]
    for examples,destination in((old,protected),(training,calibration)):
        for e in examples:
            if e['features']is None:continue
            route=raw.previous.select(e['program'],e['features'])
            if route['covered']and(destination is calibration or route['prediction']==e['reference']):
                destination.append({'prediction':route['prediction'],'reference':e['reference'],
                    'values':aware.values_with_judge(e['program'],e['features'],e['regular'])})
    correction=aware.utility.fit(base,old+training)
    return aware.fit(base,protected,calibration,correction)


def run(out):
    if out.exists():raise ValueError('Fresh output directory required')
    out.mkdir(parents=True);pilot=load_pilot();groups=sorted({e['source_group']for e in pilot});records=read(BASE/'crossfit_predictions.json');by_case={r['case']:r for r in records}
    protocol={'version':aware.VERSION,'base':str(BASE),'verifier':'Same protected local support, now with regular judge prediction as an additional typed feature; <=8 clauses of <=2 literals.',
              'correction':'Source-supported utility region and outcome warrant; do not override Partial with No based on missing progress alone.',
              'evaluation':'Each source and all five sibling outputs excluded from both fit stages. Prior pilot review disclosed; exploratory procedure validation.',
              'arms':['regular_aware','regular_aware_correction'],'new_model_calls':0,'default_changed':False}
    save_json(out/'protocol.json',protocol)
    for fold,group in enumerate(groups):
        train=[e for e in pilot if e['source_group']!=group];held=[e for e in pilot if e['source_group']==group]
        for bank in(1,2,3):
            base=aware.fixed.VerifiedRegionGate.restore(read(BASE/f'fold{fold:02}/split{bank}/guarded_merge.json'))
            gate=build(bank,base,train);save_json(out/f'fold{fold:02}/split{bank}/gate.json',gate.export())
            for e in held:
                for name,corrections in(('regular_aware',False),('regular_aware_correction',True)):
                    route=gate.resolve(e['program'],e['features'],e['regular'],corrections=corrections)if e['features']is not None else {'covered':False,'prediction':-1,'reason':'missing_or_invalid_evidence','matches':[]}
                    arm=f'{name}_split{bank}';by_case[e['case']]['routes'][arm]=route;by_case[e['case']][arm]=route['prediction']if route['covered']else e['regular']
        print({'fold_completed':fold+1},flush=True)
    arms=['regular']+[f'{name}_split{i}'for i in(1,2,3)for name in('v27','v28','guarded_merge','regular_aware','regular_aware_correction')]
    summary={'version':aware.VERSION,'crossfit':{a:metrics(records,a)for a in arms},'new_model_calls':0}
    save_json(out/'crossfit_predictions.json',records);save_json(out/'results.json',summary)
    final={}
    for bank in(1,2,3):
        base=aware.fixed.VerifiedRegionGate.restore(read(BASE/f'full/split{bank}/guarded_merge.json'))
        gate=build(bank,base,pilot);save_json(out/f'full/split{bank}/gate.json',gate.export());final[str(bank)]=gate.artifact['artifact_ref']
        # Check actual local labels, using the already recorded regular judgments.
        for e in old_examples(bank):
            before=base.select(e['program'],e['features'])
            if before['covered']:
                route=gate.resolve(e['program'],e['features'],e['regular'])
                assert route['covered']and route['prediction']==e['reference']
    save_json(out/'freeze.json',{'gates':final,'protocol_ref':digest(protocol),'training_source_groups':groups})
    save_json(out/'manifest.json',{'code_hashes':{str(Path(p).resolve()):fingerprint(p)for p in(__file__,aware.__file__)},
              'protocol_ref':digest(protocol),'base_freeze_sha256':fingerprint(BASE/'freeze.json')})
    (out/'run.log').write_text('Source-held-out regular-aware verification and semantic routing.\n');(out/'llm-histories.log').write_text('Zero model calls.\n')
    for a,m in summary['crossfit'].items():print(a,m['correct'],m['tree_accepted'],m['accepted_accuracy'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();run(a.output_dir.resolve())
