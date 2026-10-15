"""Apply fitted local rules inside observed operation scopes; otherwise back off."""
from collections import Counter
from copy import deepcopy

from ...decision.artifacts import digest
from ...decision.bound_evidence_v2 import KINDS
from .interpreted_features_v6 import FEATURES, CONTRACT_REF, validate_record
from .interpreted_tree_v6 import InterpretedSemanticTree, metrics

VERSION='operation-scoped-semantic-policy-v7.1'


def signature(record):
    return tuple(k for k in KINDS if k!='identity' and record['features']['outcome_'+k+'_count_ge_1'])


def mask_record(record,profile):
    validate_record(record)
    if record is None:return None
    value=deepcopy(record)
    if profile=='physical_baseline':
        for key in value['features']:
            if key.startswith('meaning_'):value['features'][key]=False
    return value


def leaf_for(tree,record):
    node=tree;path=[]
    while node['type']!='leaf':
        flag=record['features'][node['feature']];path.append({'feature':node['feature'],'value':flag})
        node=node['true' if flag else 'false']
    return node,path


class ScopedSemanticPolicy:
    def __init__(self):self.artifact=None

    def fit(self,rows,local_policy,local_profile):
        from sklearn.tree import DecisionTreeClassifier
        import sklearn
        InterpretedSemanticTree.restore(local_policy)
        ordered=sorted(rows,key=lambda r:r['source_group']);sources=[r['source_group'] for r in ordered]
        X=[mask_record(r['features'],local_profile) for r in ordered]
        if (local_policy['training']['source_groups']!=sources or digest(X)!=local_policy['training']['feature_ref']
                or digest([r['reference'] for r in ordered])!=local_policy['training']['target_ref']):
            raise ValueError('Local policy was not fit on these sources')
        scopes={}
        for r,x in zip(ordered,X):
            if x is None:continue
            node,path=leaf_for(local_policy['tree'],x);key=digest(path);sig=signature(r['features'])
            entry=scopes.setdefault(key,{'path':path,'signatures':{},'source_groups':[]})
            entry['signatures'].setdefault(sig,[]).append(r['source_group']);entry['source_groups'].append(r['source_group'])
        serialized={k:{'path':s['path'],'source_groups':s['source_groups'],
                     'operation_scopes':[{'kinds':list(sig),'source_groups':ids,'support':len(ids)} for sig,ids in sorted(s['signatures'].items())]}
                    for k,s in sorted(scopes.items())}
        selected=[r for r in ordered if r['features'] is not None]
        keys=[k for k in FEATURES if k.startswith('meaning_')]
        matrix=[[r['features']['features'][k] for k in keys] for r in selected]
        model=DecisionTreeClassifier(max_depth=2,min_samples_leaf=3,random_state=2718).fit(matrix,[r['reference'] for r in selected])
        tree=model.tree_
        def export(index,part):
            if tree.children_left[index]==tree.children_right[index]:
                counts=[sum(r['reference']==k for r in part) for k in range(3)]
                return {'type':'leaf','prediction':max(range(3),key=lambda k:(counts[k],-k)),
                        'support':len(part),'counts':counts,'source_groups':[r['source_group'] for r in part]}
            feature=keys[tree.feature[index]]
            assert tree.threshold[index]==0.5
            return {'type':'split','feature':feature,'support':len(part),
                    'false':export(tree.children_left[index],[r for r in part if not r['features']['features'][feature]]),
                    'true':export(tree.children_right[index],[r for r in part if r['features']['features'][feature]])}
        fallback=export(0,selected)
        a={'version':VERSION,'feature_contract_ref':CONTRACT_REF,'local_profile':local_profile,'local_policy':deepcopy(local_policy),
           'scopes':serialized,'fallback':fallback,'fallback_fit':{'algorithm':'CART','max_depth':2,'min_leaf_sources':3,'random_state':2718,'sklearn_version':sklearn.__version__},
           'training_sources':sources,'scope_semantics':'Exact set of requested outcome kinds seen in this leaf; no object names or source identities are runtime conditions.',
           'scope_limitation':'An operation scope can have only one supporting source even though the local rule has at least two or three. Applicability is not independently validated per scope.'}
        self.artifact=a
        ps=[r['prediction'] for r in self.predict_records([r['features'] for r in ordered])]
        a['training_metrics']=metrics(ps,[r['reference'] for r in ordered])
        assert a['training_metrics']['correct']==local_policy['training']['metrics']['correct']
        assert all(not r['fallback'] for r in self.predict_records([r['features'] for r in selected]))
        a['artifact_ref']=digest(a)
        return self

    def predict_records(self,records):
        if self.artifact is None:raise ValueError('No fitted scoped policy')
        a=self.artifact;result=[]
        for record in records:
            validate_record(record)
            if record is None:
                result.append({'prediction':-1,'fallback':False,'reason':'missing_evidence','operation_kinds':[],'local_trace':[],'fallback_trace':[]})
                continue
            if a['local_profile']!='physical_baseline' and not record['features']['meaning_available']:
                result.append({'prediction':-1,'fallback':False,'reason':'missing_semantic_interpretation',
                               'operation_kinds':list(signature(record)),'local_trace':[],'fallback_trace':[]})
                continue
            local,path=leaf_for(a['local_policy']['tree'],mask_record(record,a['local_profile']))
            scopes=a['scopes'][digest(path)]['operation_scopes'];sig=list(signature(record))
            match=next((s for s in scopes if s['kinds']==sig),None)
            decision=local;fallback_path=[]
            if match is None and not record['features']['meaning_available']:
                result.append({'prediction':-1,'fallback':True,'reason':'missing_semantic_interpretation',
                               'operation_kinds':sig,'local_trace':path,'fallback_trace':[]})
                continue
            if match is None:decision,fallback_path=leaf_for(a['fallback'],record)
            result.append({'prediction':decision['prediction'],'fallback':match is None,
                 'reason':'supported_operation_scope' if match is not None else 'semantic_fallback_outside_local_scope',
                 'operation_kinds':sig,'local_trace':path,'fallback_trace':fallback_path,
                 'operation_scope_support':match['support'] if match is not None else 0,'local_prediction':local['prediction']})
        return result

    def metadata(self):return deepcopy(self.artifact)

    @classmethod
    def restore(cls,a):
        if (a.get('version')!=VERSION or a.get('feature_contract_ref')!=CONTRACT_REF
                or digest({k:v for k,v in a.items() if k!='artifact_ref'})!=a.get('artifact_ref')):
            raise ValueError('Changed scoped policy artifact')
        InterpretedSemanticTree.restore(a['local_policy'])
        if set(a['training_sources'])!=set(a['local_policy']['training']['source_groups']):raise ValueError('Wrong fitting sources')
        for key,s in a['scopes'].items():
            if digest(s['path'])!=key or any(c['feature'] not in FEATURES or type(c['value']) is not bool for c in s['path']):
                raise ValueError('Invalid semantic scope path')
            if not set(s['source_groups'])<=set(a['training_sources']):raise ValueError('Unbound scope source')
            for scope in s['operation_scopes']:
                if not set(scope['kinds'])<=set(KINDS)-{'identity'} or scope['support']!=len(set(scope['source_groups'])):
                    raise ValueError('Invalid operation scope')
        def check(n,depth=0):
            if depth>2:raise ValueError('Fallback exceeds depth budget')
            if n['type']=='leaf':
                if (n['support']<3 or len(n['counts'])!=3 or sum(n['counts'])!=n['support']
                        or any(type(v) is not int or v<0 for v in n['counts'])
                        or type(n['prediction']) is not int or n['prediction'] not in (0,1,2)
                        or n['prediction']!=max(range(3),key=lambda k:(n['counts'][k],-k))
                        or len(set(n['source_groups']))!=n['support']):raise ValueError('Unsupported fallback leaf')
            else:
                if n['feature'] not in FEATURES or not n['feature'].startswith('meaning_'):raise ValueError('Fallback is not semantic-only')
                check(n['true'],depth+1);check(n['false'],depth+1)
        check(a['fallback']);obj=cls();obj.artifact=deepcopy(a);return obj
