"""Cross-source evaluation of evidence-warrant routing on cached pilot data."""
import argparse
from pathlib import Path
from collections import Counter

from critical.core.calibration import decision_warrant_gate_v33 as warrants
from critical.core.decision.artifacts import digest,save_json
from run.calitree_guarded_generalization_v32 import load_pilot,context
from run.collect_calitree_aurora_pilot_v29r1 import metrics
from run.calitree_aurora_pilot_v29 import ROOT,read,fingerprint

BASE=ROOT/'logs/exps/261020-guarded-generalization-v32-r1'


def run(out):
    if out.exists():raise ValueError('Fresh output directory required')
    out.mkdir(parents=True)
    protocol={'version':warrants.VERSION,'base':str(BASE),
              'routing':'Verified existing route first; otherwise a strict requirement-level No/Yes warrant, supporting raw expert, and calibrated source guard. Partial/unknown evidence defers.',
              'support':'At least two distinct correct source groups; all known training warrant errors must be separated before that warrant label is enabled.',
              'evaluation':'Same source-held-out folds as v32; no held source or sibling label in warrant fitting. Pilot already reviewed, so exploratory.',
              'new_model_calls':0,'default_changed':False}
    save_json(out/'protocol.json',protocol)
    pilot=load_pilot();groups=sorted({r['source_group']for r in pilot});records=read(BASE/'crossfit_predictions.json');by_case={r['case']:r for r in records}
    fits=[]
    for fold,group in enumerate(groups):
        training=[r for r in pilot if r['source_group']!=group];held=[r for r in pilot if r['source_group']==group]
        for bank in(1,2,3):
            base=warrants.fixed.VerifiedRegionGate.restore(read(BASE/f'fold{fold:02}/split{bank}/guarded_merge.json'))
            _,_,_,_,_,old=context(bank)
            support=warrants.fit_support(base,old,training)
            gate=warrants.DecisionWarrantGate(base,support);folder=out/f'fold{fold:02}/split{bank}'
            save_json(folder/'gate.json',gate.export())
            for r in held:
                route=gate.select(r['program'],r['features'])if r['features']is not None else {'covered':False,'prediction':-1,'reason':'missing_or_invalid_evidence','matches':[]}
                arm=f'warrant_split{bank}';by_case[r['case']]['routes'][arm]=route
                by_case[r['case']][arm]=route['prediction']if route['covered']else r['regular']
            fits.append({'fold':fold,'source':group,'bank':bank,'support_ref':support['artifact_ref'],'enabled':support['enabled'],'counts':support['training_counts']})
        print({'fold_completed':fold+1},flush=True)
    arms=['regular']+[f'{name}_split{i}'for i in(1,2,3)for name in('v27','v28','guarded_merge','warrant')]
    summary={'version':warrants.VERSION,'crossfit':{a:metrics(records,a)for a in arms},'folds':fits,'new_model_calls':0}
    save_json(out/'crossfit_predictions.json',records);save_json(out/'results.json',summary)
    final={}
    for bank in(1,2,3):
        base=warrants.fixed.VerifiedRegionGate.restore(read(BASE/f'full/split{bank}/guarded_merge.json'))
        _,_,_,_,_,old=context(bank)
        support=warrants.fit_support(base,old,pilot);gate=warrants.DecisionWarrantGate(base,support)
        save_json(out/f'full/split{bank}/gate.json',gate.export());final[str(bank)]=gate.artifact['artifact_ref']
    save_json(out/'freeze.json',{'gates':final,'protocol_ref':digest(protocol),'pilot_training_sources':groups})
    save_json(out/'manifest.json',{'base':str(BASE),'code_hashes':{str(Path(p).resolve()):fingerprint(p)for p in(__file__,warrants.__file__)},
              'protocol_ref':digest(protocol),'base_freeze_sha256':fingerprint(BASE/'freeze.json')})
    (out/'run.log').write_text('Source-held-out warrant calibration and final freeze.\n');(out/'llm-histories.log').write_text('Zero model calls.\n')
    for a,m in summary['crossfit'].items():print(a,m['correct'],m['tree_accepted'],m['accepted_accuracy'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();run(a.output_dir.resolve())
