"""Reproduce the reviewed portable policy and deployment-only artifact offline."""
import argparse
from pathlib import Path

from critical.core.decision.artifacts import save_json
from critical.core.calibration.semantic_hierarchy.portable_review_v8 import review
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import PortableSemanticTree,metrics
from run.calitree_single_call import read,fingerprint


def exact(path,value):
    if path.exists():
        if read(path)!=value:raise ValueError('Reviewed artifact changed: '+str(path))
    else:save_json(path,value)


def run(out):
    rows=read(out/'data.json')['train'];ordered=sorted(rows,key=lambda r:r['source_group'])
    policy,audit=review(read(out/'frozen_policy.json'),[r['features'] for r in ordered],[r['reference'] for r in ordered])
    runtime=PortableRuleExecutor.from_training_policy(policy)
    exact(out/'reviewed_policy.json',policy);exact(out/'semantic_review.json',audit);exact(out/'deployment_policy.json',runtime.metadata())
    (out/'reviewed_rules.txt').write_text(PortableSemanticTree.restore(policy).render()+'\n')
    ps=runtime.predict_records([r['features'] for r in rows])
    result={'version':'reviewed-portable-m2-v8.1','metrics':metrics([p['prediction'] for p in ps],[r['reference'] for r in rows]),
            'cases':[{'case':r['case'],'reference':r['reference'],**p} for r,p in zip(rows,ps)],
            'deployment_sha256':fingerprint(out/'deployment_policy.json'),
            'new_model_calls':0,'new_fits':0,'acceptance_scope':'User-defined semantic portability plus local accuracy above 90%; not a held-out accuracy claim.'}
    exact(out/'reviewed_result.json',result)
    print({'version':result['version'],'metrics':result['metrics'],'new_model_calls':0,'new_fits':0})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    run(p.parse_args().output_dir.resolve())
