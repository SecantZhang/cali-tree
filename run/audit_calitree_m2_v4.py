"""Independent evidence, partition, support, prediction and metric audit for M2 v4."""
import argparse
from collections import Counter
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.calibration.semantic_hierarchy.features_v4 import FEATURES, ROLES, STATES
from critical.core.decision.bound_evidence_v2 import KINDS
from run.calitree_single_call import ROOT, read, fingerprint


def audit(output):
    manifest=read(output/'manifest.json');data=read(output/'data.json');result=read(output/'results.json')
    for rel,h in manifest['source_hashes'].items():assert fingerprint(ROOT/rel)==h,rel
    for rel,h in manifest['code_hashes'].items():
        assert fingerprint(ROOT/rel)==fingerprint(output/'source_snapshot'/rel)==h,rel
    assert digest(read(output/'protocol.json'))==manifest['protocol_ref']
    rows=data['train'];dev=data['validation'];by_source={r['source_group']:r for r in rows}
    final={r['group'] for r in read(ROOT/'logs/exps/261014-semantic-hierarchy-m0-fifty-v1/splits/test.json')['cases']}
    assert len(rows)==len(by_source)==48 and len(dev)==12
    assert not final&{r['source_group'] for r in rows+dev}
    assert not set(by_source)&{r['source_group'] for r in dev}
    # Independent projection from authenticated, already audited M1 records.
    feature_checks=0
    for partition,dir_ in [('train','261014-m2-m4-bound-training48-v1'),('validation','261014-m1-bound-evidence-development12-v2')]:
        raw={r['case']:r for r in read(ROOT/'logs/exps'/dir_/'observations.json')}
        for row in data[partition]:
            bound=raw[row['case']]['record']
            if bound is None:assert row['features'] is None;continue
            expected={}
            for role in ROLES:
                for kind in ('all',*sorted(KINDS)):
                    checks=[c for c in bound['checks'].values() if c['role']==role and (kind=='all' or c['kind']==kind)]
                    n=len(checks);prefix=role+'_'+kind
                    for threshold in (1,2,3):expected[prefix+'_count_ge_'+str(threshold)]=n>=threshold
                    for state in STATES:
                        votes=[c['desired_state']==state for c in checks]
                        expected[prefix+'_'+state+'_any']=any(votes)
                        expected[prefix+'_'+state+'_all']=bool(votes) and all(votes)
                        expected[prefix+'_'+state+'_majority']=bool(votes) and sum(votes)>n/2
            assert row['features']['features']==expected,row['case']
            feature_checks+=len(expected)

    def reference(policy,record):
        if record is None:return -1,None,[]
        node=policy['tree'];trace=[];group=None;limits=policy['limits']
        while True:
            is_group=(node['type']=='leaf' or len(trace)>=limits['group_depth'] or
                      min(node['true']['support'],node['false']['support'])<limits['min_group_sources'])
            if group is None and is_group:group='scope-'+digest(trace)[:16]
            if node['type']=='leaf':return node['prediction'],group,trace
            value=record['features'][node['feature']];trace.append({'feature':node['feature'],'value':value})
            node=node['true' if value else 'false']

    def metric(predictions, selected, actual):
        targets=[r['reference'] for r in selected]
        assert actual['total']==len(targets) and actual['correct']==sum(p==y for p,y in zip(predictions,targets))
        assert actual['accuracy']==actual['correct']/len(targets)
        assert actual['unresolved']==predictions.count(-1)
        fs=[]
        for label,name in enumerate(('no','partial','yes')):
            c=actual['per_class'][name];n=targets.count(label);np=predictions.count(label);tp=sum(p==y==label for p,y in zip(predictions,targets))
            assert (c['support'],c['predicted'],c['correct'])==(n,np,tp)
            assert c['recall']==(tp/n if n else None)
            f=2*tp/(n+np) if n+np else 0.0
            assert c['f1']==f;fs.append(f)
        assert abs(actual['macro_f1']-sum(fs)/3)<1e-12

    policies={};leaves=0
    for path in [output/'pooled_policy.json',*sorted((output/'original_groups').glob('*.json')),*sorted((output/'outer_folds').glob('*.json'))]:
        a=read(path);policies[str(path.relative_to(output))]=a
        assert digest({k:v for k,v in a.items() if k!='artifact_ref'})==a['artifact_ref']
        selected=[by_source[g] for g in a['training']['source_groups']]
        assert digest([r['features'] for r in selected])==a['training']['feature_ref']
        assert digest([r['reference'] for r in selected])==a['training']['target_ref']
        def walk(node,part,depth):
            nonlocal leaves
            assert depth<=a['limits']['max_depth'] and node['support']==len(part)
            if node['type']=='leaf':
                leaves+=1
                assert len(part)>=2 and set(node['source_groups'])=={r['source_group'] for r in part}
                assert node['counts']==[sum(r['reference']==k for r in part) for k in range(3)]
                assert node['source_batches']==dict(Counter(r['batch'] for r in part))
                assert node['prediction']==max(range(3),key=lambda k:(node['counts'][k],-k))
            else:
                assert node['feature'] in FEATURES
                for value in (True,False):
                    walk(node['true' if value else 'false'],[r for r in part if r['features']['features'][node['feature']]==value],depth+1)
        walk(a['tree'],[r for r in selected if r['features'] is not None],0)
        ps=[reference(a,r['features'])[0] for r in selected]
        metric(ps,selected,a['training']['metrics'])
        groups=[]
        for group in a['groups']:
            members=[r for r in selected if r['features'] is not None and all(r['features']['features'][c['feature']]==c['value'] for c in group['conditions'])]
            assert set(group['source_groups'])=={r['source_group'] for r in members}
            assert all(reference(a,r['features'])[1]==group['group_id'] for r in members)
            metric([reference(a,r['features'])[0] for r in members],members,group['metrics'])
            groups.extend(group['source_groups'])
        assert len(groups)==len(set(groups))==sum(r['features'] is not None for r in selected)

    checked=0
    def evaluation(a,selected,scores):
        nonlocal checked
        assert [r['case'] for r in selected]==[r['case'] for r in scores['cases']]
        for row,saved in zip(selected,scores['cases']):
            p,g,t=reference(a,row['features'])
            assert (saved['prediction'],saved['group_id'],saved['trace'])==(p,g,t)
            checked+=1
        metric([r['prediction'] for r in scores['cases']],selected,scores['metrics'])
    evaluation(policies['pooled_policy.json'],rows,result['training'])
    evaluation(policies['pooled_policy.json'],dev,result['development12'])
    for group in ('G1','G2','G3','G4'):
        held=[r for r in rows if r['batch']==group]
        evaluation(policies['original_groups/'+group+'.json'],held,result['original_group_local_fits'][group])
        outer=policies['outer_folds/'+group+'.json']
        assert set(outer['training']['source_groups'])=={r['source_group'] for r in rows if r['batch']!=group}
        assert not set(outer['training']['source_groups'])&{r['source_group'] for r in held}
        evaluation(outer,held,result['outer_folds'][group])
    assert result['new_model_calls']==result['reserved_test_predictions']==0
    old=ROOT/'logs/exps/261014-m2-m4-semantic-baselines-v3'
    for rel,h in read(old/'completion_seal.json')['files'].items():assert fingerprint(old/rel)==h,rel
    audit_result={'passed':True,'policies_checked':len(policies),'supported_leaves_checked':leaves,
                  'predictions_checked':checked,'projected_features_checked':feature_checks,
                  'outer_source_separations':4,'reserved_source_overlap':0,'new_model_calls':0,
                  'prior_completion_artifacts_preserved':len(read(old/'completion_seal.json')['files']),
                  'limitation':'Proves faithful execution and measurement, not transfer, repeat robustness, or causal validity of learned rules.'}
    path=output/'independent_audit.json'
    if path.exists():assert read(path)==audit_result
    else:save_json(path,audit_result)
    print(audit_result)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output_dir',type=Path)
    audit(p.parse_args().output_dir.resolve())
