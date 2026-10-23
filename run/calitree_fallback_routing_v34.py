"""Cross-fit semantic fallback resolution with the regular judge as an expert."""
import argparse
from pathlib import Path

from critical.core.calibration import semantic_fallback_router_v34 as routing
from critical.core.decision.artifacts import digest,save_json
from run.calitree_guarded_generalization_v32 import load_pilot,ROOT,PREVIOUS
from run.calitree_semantic_region_merge_v28 import inputs as old_inputs
from run.collect_calitree_aurora_pilot_v29r1 import metrics
from run.calitree_aurora_pilot_v29 import read,fingerprint

BASE=ROOT/'logs/exps/261020-guarded-generalization-v32-r1'


def old_examples(bank):
    _,_,_,cohorts,bound,*_=old_inputs(PREVIOUS,bank)
    return [{**bound[r['case']]['example'],'regular':r['regular']}for rows in cohorts.values()for r in rows]


def run(out):
    if out.exists():raise ValueError('Fresh output directory required')
    out.mkdir(parents=True);pilot=load_pilot();groups=sorted({r['source_group']for r in pilot});records=read(BASE/'crossfit_predictions.json');by_case={r['case']:r for r in records}
    protocol={'version':routing.VERSION,'base':str(BASE),'support':'Strict outcome warrant plus matching expert and a zero-training-error conjunction supported by >=2 beneficial source groups. <=4 terms, <=2 literals per disagreement pair.',
              'priority':'Keep verified existing route. On fallback use its regular judgment as the comparator; override only in a calibrated disagreement domain.',
              'evaluation':'Source-held-out from both verifier/merge and fallback-router fitting; pilot already reviewed so exploratory. No held source label in fitting.',
              'new_model_calls':0,'default_changed':False}
    save_json(out/'protocol.json',protocol)
    for fold,group in enumerate(groups):
        train=[e for e in pilot if e['source_group']!=group];held=[e for e in pilot if e['source_group']==group]
        for bank in(1,2,3):
            base=routing.warrant.fixed.VerifiedRegionGate.restore(read(BASE/f'fold{fold:02}/split{bank}/guarded_merge.json'))
            router=routing.fit(base,old_examples(bank)+train);save_json(out/f'fold{fold:02}/split{bank}/router.json',router.export())
            for e in held:
                route=router.resolve(e['program'],e['features'],e['regular'])if e['features']is not None else {'covered':False,'prediction':-1,'reason':'missing_or_invalid_evidence','matches':[]}
                arm=f'utility_split{bank}';by_case[e['case']]['routes'][arm]=route;by_case[e['case']][arm]=route['prediction']if route['covered']else e['regular']
        print({'fold_completed':fold+1},flush=True)
    arms=['regular']+[f'{name}_split{i}'for i in(1,2,3)for name in('v27','v28','guarded_merge','utility')]
    summary={'version':routing.VERSION,'crossfit':{a:metrics(records,a)for a in arms},'new_model_calls':0}
    save_json(out/'crossfit_predictions.json',records);save_json(out/'results.json',summary)
    frozen={}
    for bank in(1,2,3):
        base=routing.warrant.fixed.VerifiedRegionGate.restore(read(BASE/f'full/split{bank}/guarded_merge.json'))
        router=routing.fit(base,old_examples(bank)+pilot);save_json(out/f'full/split{bank}/router.json',router.export());frozen[str(bank)]=router.artifact['artifact_ref']
    save_json(out/'freeze.json',{'routers':frozen,'protocol_ref':digest(protocol),'training_source_groups':groups})
    save_json(out/'manifest.json',{'code_hashes':{str(Path(p).resolve()):fingerprint(p)for p in(__file__,routing.__file__)},'protocol_ref':digest(protocol),'base_freeze_sha256':fingerprint(BASE/'freeze.json')})
    (out/'run.log').write_text('Source-held-out semantic utility routing evaluated; no provider calls.\n');(out/'llm-histories.log').write_text('Zero model calls.\n')
    for a,m in summary['crossfit'].items():print(a,m['correct'],m['tree_accepted'],m['accepted_accuracy'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();run(a.output_dir.resolve())
