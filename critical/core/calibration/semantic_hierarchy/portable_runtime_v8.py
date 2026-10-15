"""Deployment form containing semantic predicates and output labels only."""
from copy import deepcopy

from ...decision.artifacts import digest
from .portable_features_v8 import FEATURES,CONTRACT_REF,SPECS,validate_record
from .portable_tree_v8 import PortableSemanticTree

VERSION='portable-semantic-runtime-v8.1'


class PortableRuleExecutor:
    def __init__(self,artifact):
        if (set(artifact)!={'version','feature_contract_ref','tree','predicate_descriptions','artifact_ref'}
                or artifact['version']!=VERSION or artifact['feature_contract_ref']!=CONTRACT_REF
                or digest({k:v for k,v in artifact.items() if k!='artifact_ref'})!=artifact['artifact_ref']):
            raise ValueError('Changed portable runtime contract')
        used=set()
        def validate(node):
            if set(node)=={'prediction'}:
                if type(node['prediction']) is not int or node['prediction'] not in (0,1,2):raise ValueError('Invalid output label')
            elif set(node)=={'feature','true','false'}:
                if node['feature'] not in FEATURES:raise ValueError('Case-specific or undeclared predicate')
                used.add(node['feature']);validate(node['true']);validate(node['false'])
            else:raise ValueError('Runtime rule contains non-executable metadata or literals')
        validate(artifact['tree'])
        if artifact['predicate_descriptions']!={k:SPECS[k] for k in sorted(used)}:raise ValueError('Predicate meaning changed')
        self.artifact=deepcopy(artifact)
        self.requires_interpretation=any(k.startswith('meaning_') and k!='meaning_available' for k in used)

    @classmethod
    def from_training_policy(cls,policy):
        PortableSemanticTree.restore(policy);used=set()
        def strip(node):
            if node['type']=='leaf':return {'prediction':node['prediction']}
            used.add(node['feature'])
            return {'feature':node['feature'],'true':strip(node['true']),'false':strip(node['false'])}
        tree=strip(policy['tree'])
        a={'version':VERSION,'feature_contract_ref':CONTRACT_REF,'tree':tree,
           'predicate_descriptions':{k:SPECS[k] for k in sorted(used)}}
        a['artifact_ref']=digest(a);return cls(a)

    def predict_records(self,records):
        result=[]
        for x in records:
            validate_record(x)
            if x is None:result.append({'prediction':-1,'reason':'missing_evidence','trace':[]});continue
            if self.requires_interpretation and not x['features']['meaning_available']:
                result.append({'prediction':-1,'reason':'missing_semantic_interpretation','trace':[]});continue
            node=self.artifact['tree'];trace=[]
            while 'feature' in node:
                value=x['features'][node['feature']];trace.append({'feature':node['feature'],'value':value})
                node=node['true' if value else 'false']
            result.append({'prediction':node['prediction'],'reason':'portable_semantic_rule','trace':trace})
        return result

    def metadata(self):return deepcopy(self.artifact)
