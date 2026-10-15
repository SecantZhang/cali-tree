"""Review explicit rule contradictions without imposing a universal label gate."""
from collections import Counter
from copy import deepcopy

from ...decision.artifacts import digest
from .portable_tree_v8 import PortableSemanticTree,metrics

VERSION='portable-rule-review-v8.1'
CONTRADICTS_YES=(
    'meaning_endpoint_gap_core_endpoint_missing_all',
    'meaning_endpoint_gap_wrong_direction_or_target_all',
    'meaning_progress_none_all',
    'meaning_progress_incidental_change_only_all',
)


def violations(tree):
    result=[]
    def visit(node,path):
        if node['type']=='leaf':
            if node['prediction']==2:
                reasons=[c['feature'] for c in path if c['value'] and c['feature'] in CONTRADICTS_YES]
                if reasons:result.append({'path':path,'reasons':reasons,'prediction':2,'source_support':node['support']})
            return
        for value in (True,False):visit(node['true' if value else 'false'],path+[{'feature':node['feature'],'value':value}])
    visit(tree,[]);return result


def review(policy,records,targets):
    """Collapse a contradictory exception split only when the >90% fit survives.

    This inspects conditions explicitly written on a learned path. It does not
    veto Yes at runtime whenever an arbitrary input feature happens to be false.
    No case ID or object identity is consulted when choosing a pruning action.
    """
    PortableSemanticTree.restore(policy)
    if digest(records)!=policy['training']['feature_ref'] or digest(targets)!=policy['training']['target_ref']:
        raise ValueError('Review must use the exact canonical fitting rows')
    current=deepcopy(policy);original=current['artifact_ref'];actions=[]
    def nodes(n):return 1 if n['type']=='leaf' else 1+nodes(n['true'])+nodes(n['false'])
    def internal(n,path=()):
        if n['type']=='split':
            yield path
            for value in (True,False):yield from internal(n['true' if value else 'false'],path+(value,))
    def collapse(n):
        leaves=[]
        def collect(x):
            if x['type']=='leaf':leaves.append(x)
            else:collect(x['true']);collect(x['false'])
        collect(n);counts=[sum(x['counts'][k] for x in leaves) for k in range(3)];batches=Counter()
        for x in leaves:batches.update(x['source_batches'])
        return {'type':'leaf','prediction':max(range(3),key=lambda k:(counts[k],-k)),'support':sum(counts),'counts':counts,
                'source_groups':sorted(s for x in leaves for s in x['source_groups']),'source_batches':dict(sorted(batches.items()))}
    def score(a):
        m=PortableSemanticTree(limits=a['limits']);m._artifact=a
        return metrics([p['prediction'] for p in m.predict_records(records)],targets)
    before=violations(current['tree'])
    while violations(current['tree']):
        previous=len(violations(current['tree']));options=[]
        for path in internal(current['tree']):
            candidate=deepcopy(current);parent=None;node=candidate['tree'];last=None
            for value in path:parent=node;last='true' if value else 'false';node=node[last]
            leaf=collapse(node)
            if parent is None:candidate['tree']=leaf
            else:parent[last]=leaf
            remaining=violations(candidate['tree'])
            if len(remaining)>=previous:continue
            metric=score(candidate)
            if metric['correct']<=.9*metric['total']:continue
            options.append(((len(remaining),-metric['correct'],nodes(candidate['tree']),path),candidate,metric,path))
        if not options:break
        _,current,metric,path=min(options,key=lambda v:v[0])
        actions.append({'pruned_branch_values':list(path),'remaining_explicit_contradictions':len(violations(current['tree'])),
                        'training_correct':metric['correct'],'training_total':metric['total'],'nodes':nodes(current['tree'])})
    if violations(current['tree']):raise ValueError('A written semantic contradiction cannot be removed within the accepted fit floor')
    current.pop('artifact_ref',None)
    current['training']['metrics']=score(current)
    current['search']['nodes']=nodes(current['tree'])
    current['review']={'version':VERSION,'parent_artifact_ref':original,'actions':actions,
       'scope':'Prunes explicitly contradictory written branches; not a universal output veto or a proof that every learned correlation is causal.'}
    model=PortableSemanticTree(limits=current['limits']);model._artifact=current
    current['groups']=model._groups(records,targets,current['training']['source_groups'])
    current['artifact_ref']=digest(current);PortableSemanticTree.restore(current)
    return current,{'version':VERSION,'original_contradictions':before,'remaining_contradictions':[],
                   'actions':actions,'training_metrics':current['training']['metrics'],'parent_artifact_ref':original}
