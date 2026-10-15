"""Score the frozen scoped candidate on separately authorized dev12; never fit."""
import argparse
from pathlib import Path

from critical.core.decision.artifacts import digest,save_json
from critical.core.decision.bound_evidence_v2 import VERSION as M1_VERSION
from critical.core.calibration.semantic_hierarchy.interpreted_features_v6 import project
from critical.core.calibration.semantic_hierarchy.scoped_policy_v7 import ScopedSemanticPolicy
from critical.core.calibration.semantic_hierarchy.interpreted_tree_v6 import metrics
from run.calitree_single_call import ROOT,read,fingerprint

FROZEN_SHA256='44f140714514d445b4b6f7612a1cc21fbfb6ada6e2f6e86b87b10f22a3870069'


def evaluate(out):
    context_path=out/'frozen_context.json'
    if fingerprint(context_path)!=FROZEN_SHA256:raise ValueError('Candidate changed after validation authorization')
    context=read(context_path);model=ScopedSemanticPolicy.restore(context['model'])
    interpretation=ROOT/'logs/exps/261014-m2-semantic-interpretation-dev12-v5'
    if read(interpretation/'authorization.json')['frozen_candidate_sha256']!=FROZEN_SHA256:
        raise ValueError('Validation approval refers to another candidate')
    m0=ROOT/'logs/exps/261014-semantic-hierarchy-m0-fifty-v1'
    cases=read(m0/'splits/validation.json')['cases'];final={r['group'] for r in read(m0/'splits/test.json')['cases']}
    original={r['case']:r for r in read(ROOT/'logs/exps/261014-m1-bound-evidence-development12-v2/observations.json')}
    meaning={r['case']:r for r in read(interpretation/'interpretations.json')}
    assert len(cases)==12 and not {r['group'] for r in cases}&(set(context['fit_sources'])|final)
    rows=[]
    for c in cases:
        source=original[c['case']]
        pair=digest([M1_VERSION,'source_first',c['image_hashes']['source_image'],c['image_hashes']['edited_image']])
        features=project(source['compilation']['program'],source['observation']['observation'],pair,meaning[c['case']]['interpretation'])
        rows.append({'case':c['case'],'source_group':c['group'],'reference':('no','partial','yes').index(c['reference']),
                     'features':features,'interpretation_error':meaning[c['case']]['error']})
    ps=model.predict_records([r['features'] for r in rows])
    old=read(ROOT/'logs/exps/261014-m2-conflict-regrouping-v4/results.json')['development12']
    prior={r['case']:r for r in old['cases']}
    result={'frozen_context_sha256':FROZEN_SHA256,'metrics':metrics([p['prediction'] for p in ps],[r['reference'] for r in rows]),
            'cases':[{'case':r['case'],'source_group':r['source_group'],'reference':r['reference'],**p} for r,p in zip(rows,ps)],
            'paired_wins':[r['case'] for r,p in zip(rows,ps) if p['prediction']==r['reference'] and prior[r['case']]['prediction']!=r['reference']],
            'paired_losses':[r['case'] for r,p in zip(rows,ps) if p['prediction']!=r['reference'] and prior[r['case']]['prediction']==r['reference']],
            'baseline':old['metrics'],'new_model_calls_during_scoring':0,'new_fits':0,'upstream_text_attempts':read(interpretation/'results.json')['attempts'],
            'reserved_test_predictions':0,'scope':'Supplementary development validation after freezing this candidate. These sources have historical project exposure, but were excluded from the current fitting and policy selection.'}
    assert fingerprint(context_path)==FROZEN_SHA256
    for name,value in [('development12_data.json',rows),('development12_validation.json',result)]:
        path=out/name
        if path.exists():assert read(path)==value
        else:save_json(path,value)
    print({k:v for k,v in result.items() if k not in ('cases','baseline')})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    evaluate(p.parse_args().output_dir.resolve())
