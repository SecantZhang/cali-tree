"""Independent rule-level case-portability, support, and accounting audit."""
import argparse
from collections import Counter
from pathlib import Path
import json

from critical.core.decision.artifacts import digest,save_json
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import FEATURES,from_interpreted
from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import PortableSemanticTree
from critical.core.calibration.semantic_hierarchy.portable_review_v8 import review,violations
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from run.calitree_single_call import ROOT,read,fingerprint


def audit(out):
    manifest=read(out/'manifest.json');rows=read(out/'data.json')['train'];original=read(out/'frozen_policy.json')
    reviewed=read(out/'reviewed_policy.json');deployment=read(out/'deployment_policy.json')
    for rel,h in manifest['code_hashes'].items():assert fingerprint(ROOT/rel)==fingerprint(out/'source_snapshot'/rel)==h,rel
    for rel,h in manifest['source_hashes'].items():assert fingerprint(ROOT/rel)==h,rel
    interpreted=read(ROOT/'logs/exps/261014-m2-generalization-interpreted-v6/data.json')['train']
    assert [r['features'] for r in rows]==[from_interpreted(r['features']) for r in interpreted]
    assert [r['reference'] for r in rows]==[r['reference'] for r in interpreted]
    assert len(rows)==len({r['source_group'] for r in rows})==48
    ordered=sorted(rows,key=lambda r:r['source_group'])
    replayed,review_audit=review(original,[r['features'] for r in ordered],[r['reference'] for r in ordered])
    assert replayed==reviewed and review_audit==read(out/'semantic_review.json')
    assert not violations(reviewed['tree'])
    executor=PortableRuleExecutor(deployment)
    assert executor.metadata()==PortableRuleExecutor.from_training_policy(reviewed).metadata()
    text=json.dumps(deployment)
    for r in rows:
        assert r['source_group'] not in text and r['case'] not in text and r['instruction'] not in text
    assert 'source_groups' not in text and 'training' not in deployment and 'scopes' not in deployment
    rules=[];used=set()
    def visit(node,part,path):
        if 'prediction' in node:
            assert len(part)>=2
            counts=[sum(r['reference']==k for r in part) for k in range(3)]
            assert node['prediction']==max(range(3),key=lambda k:(counts[k],-k))
            rules.append({'conditions':path,'prediction':node['prediction'],'support':len(part),
                          'distinct_instructions':len({r['instruction'] for r in part}),
                          'examples':[{'case':r['case'],'instruction':r['instruction']} for r in part]})
            return
        assert set(node)=={'feature','true','false'} and node['feature'] in FEATURES
        assert '_count_ge_' not in node['feature'] and not node['feature'].endswith('_majority')
        used.add(node['feature'])
        for value in (True,False):visit(node['true' if value else 'false'],[r for r in part if r['features']['features'][node['feature']]==value],path+[{'feature':node['feature'],'value':value}])
    visit(deployment['tree'],[r for r in rows if r['features'] is not None],[])
    def reference(x):
        if x is None or not x['features']['meaning_available']:return -1
        n=deployment['tree']
        while 'feature' in n:n=n['true' if x['features'][n['feature']] else 'false']
        return n['prediction']
    predictions=[reference(r['features']) for r in rows]
    assert predictions==[r['prediction'] for r in executor.predict_records([r['features'] for r in rows])]
    assert predictions==[r['prediction'] for r in PortableSemanticTree.restore(reviewed).predict_records([r['features'] for r in rows])]
    correct=sum(p==r['reference'] for p,r in zip(predictions,rows))
    assert correct==44 and reviewed['training']['metrics']['correct']==44
    assert predictions.count(-1)==1
    forbidden={r['group'] for r in read(ROOT/'logs/exps/261014-semantic-hierarchy-m0-fifty-v1/splits/test.json')['cases']}
    assert not forbidden&{r['source_group'] for r in rows}
    result={'passed':True,'local_correct':correct,'local_total':48,'unresolved':1,'rules':len(rules),
        'distinct_semantic_predicates':len(used),'minimum_rule_source_support':min(r['support'] for r in rules),
        'minimum_distinct_instruction_support':min(r['distinct_instructions'] for r in rules),
        'runtime_has_case_identifiers_or_training_records':False,'raw_count_or_majority_predicates':0,
        'explicit_written_semantic_contradictions':0,'review_replay_exact':True,'predictions_independently_recomputed':48,
        'new_model_calls':0,'reserved_test_predictions':0,
        'scope':'Verifies the user-defined semantic portability of rules, not statistical generalization or full-model paraphrase robustness.'}
    save_json(out/'rule_support_examples.json',rules)
    path=out/'portability_audit.json'
    if path.exists():assert read(path)==result
    else:save_json(path,result)
    save_json(out/'reviewed_predictions.json',[{'case':r['case'],'reference':r['reference'],'prediction':p} for r,p in zip(rows,predictions)])
    print(result)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    audit(p.parse_args().output_dir.resolve())
