"""Cached logical-equivalence probes; no new images, labels or model calls."""
import argparse
from pathlib import Path

from critical.core.calibration.semantic_hierarchy import features_v4, stable_features_v5
from critical.core.calibration.semantic_hierarchy.conflict_tree_v4 import ConflictAwareSemanticTree
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence_v2 import VERSION, MAX_CHECKS
from run.calitree_single_call import ROOT,read
from tests.unit.calitree.test_stable_evidence_v5 import duplicate,rename_and_reverse


def audit(out):
    v4=ROOT/'logs/exps/261014-m2-conflict-regrouping-v4'
    model=ConflictAwareSemanticTree.restore(read(v4/'pooled_policy.json'))
    M0=ROOT/'logs/exps/261014-semantic-hierarchy-m0-fifty-v1'
    probes=[];skipped=[];cases=0
    for partition,directory in [('train','261014-m2-m4-bound-training48-v1'),('validation','261014-m1-bound-evidence-development12-v2')]:
        original={r['case']:r for r in read(ROOT/'logs/exps'/directory/'observations.json')}
        for case in read(M0/'splits'/(partition+'.json'))['cases']:
            r=original[case['case']]
            if r['observation'] is None:continue
            cases+=1;p=r['compilation']['program'];o=r['observation']['observation']
            pair=digest([VERSION,'source_first',case['image_hashes']['source_image'],case['image_hashes']['edited_image']])
            before=stable_features_v5.project(p,o,pair);raw=features_v4.project(p,o,pair)
            assert stable_features_v5.as_base(before)==raw
            label=model.predict_records([raw])[0]['prediction']
            variants=[('rename_and_reverse',None,*rename_and_reverse(p,o))]
            if len(p['checks'])<MAX_CHECKS:
                variants.extend(('duplicate',c['id'],*duplicate(p,o,c['id'])) for c in p['checks'])
            else:skipped.append({'case':case['case'],'reason':'M1 maximum checks prevents adding a check','checks':len(p['checks'])})
            for kind,check,pp,oo in variants:
                stable=stable_features_v5.project(pp,oo,pair)
                assert stable==before,(case['case'],kind,check)
                frozen=model.predict_records([stable_features_v5.as_base(stable)])[0]['prediction']
                assert frozen==label
                old=model.predict_records([features_v4.project(pp,oo,pair)])[0]['prediction']
                probes.append({'case':case['case'],'partition':partition,'variant':kind,'check':check,
                               'original_prediction':label,'v4_prediction_after':old,'stable_prediction_after':frozen,
                               'old_prediction_changed':old!=label,'stable_features_identical':True})
    result={'passed':True,'observed_cases':cases,'probes':len(probes),'old_prediction_changes':sum(r['old_prediction_changed'] for r in probes),
            'stable_prediction_changes':0,'skipped_duplicate_probes':skipped,'details':probes,'new_model_calls':0,
            'scope':'Exact repeated bound definitions and local-ID/order transformations over cached evidence. This is deterministic representation invariance, not model repeat or natural-language paraphrase robustness.'}
    out.mkdir(parents=True,exist_ok=True);path=out/'stability_audit.json'
    if path.exists():assert read(path)==result
    else:save_json(path,result)
    print({k:v for k,v in result.items() if k!='details'})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    audit(p.parse_args().output_dir.resolve())
