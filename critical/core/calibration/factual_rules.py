"""Teacher-assisted decision trees whose only inputs are grounded factual tests."""
from copy import deepcopy
from fractions import Fraction
from itertools import product
import math

import numpy as np
from sklearn.tree import DecisionTreeClassifier

from .base import Calibrator
from .evidence_rules_v4 import classification_metrics
from ..decision.observable_facts import PREDICATES,STATES
from ..decision.artifacts import digest

VERSION='teacher-distilled-observable-rules-v10'
LIMITS={'max_depth':4,'max_leaves':6,'min_definite_leaf_sources':2,'min_correct_per_class':2}
DIRECTIONS={k:1 for k in ('target_result_visible','counterpart_at_destination','original_instance_displaced','requested_direction_change',
 'requested_spatial_relation','explicit_count_matches','requested_attribute_visible','orientation_landmarks_match',
 'requested_closure_configuration','disconnected_pieces_visible','contents_in_receiving_container','hand_supports_or_grasps_target',
 'requested_actor_pose_visible','added_entity_recognizable','requested_removal_absent','requested_style_structure_visible',
 'setting_specific_cues_visible','source_subject_layout_retained')}
DIRECTIONS.update({k:-1 for k in ('original_instance_at_source','contradictory_attribute_remains','target_structure_changed',
 'specified_entity_attribute_conflict','original_style_still_visible','original_background_still_visible',
 'unrequested_entity_missing','unrequested_entity_deformed','target_markings_or_size_changed')})
CONCEPTS={
 'progress':('requested_direction_change','requested_attribute_visible','requested_actor_pose_visible','added_entity_recognizable','requested_style_structure_visible','setting_specific_cues_visible'),
 'endpoint':('requested_spatial_relation','orientation_landmarks_match','requested_closure_configuration','disconnected_pieces_visible','contents_in_receiving_container','hand_supports_or_grasps_target','requested_removal_absent'),
 'identity':('original_instance_at_source','original_instance_displaced','counterpart_at_destination','target_markings_or_size_changed','target_structure_changed'),
 'relation':('requested_spatial_relation','requested_direction_change','hand_target_contact_visible','hand_supports_or_grasps_target','counterpart_at_destination'),
 'attribute':('requested_attribute_visible','contradictory_attribute_remains','specified_entity_attribute_conflict','requested_style_structure_visible','orientation_landmarks_match'),
 'scope':('target_result_visible','original_instance_at_source','original_instance_displaced','counterpart_at_destination','contradictory_attribute_remains','original_background_still_visible','original_style_still_visible'),
 'quantity':('target_instance_count_increased','explicit_count_matches'),
 'preservation':('source_subject_layout_retained','unrequested_entity_missing','unrequested_entity_deformed','target_markings_or_size_changed','target_structure_changed')}


def validate_record(x):
    if x is None:return
    if not isinstance(x,dict) or set(x)!={'facts'} or not isinstance(x['facts'],dict) or set(x['facts'])!=set(PREDICATES) or any(v not in STATES for v in x['facts'].values()):
        raise ValueError('Only the closed bank of nonordinal observable facts is allowed')


def test_value(record,predicate):
    state=record['facts'][predicate['fact']]
    return None if state=='unknown' else state==predicate['test']


def labels(tree,record):
    if record is None:return {0,1,2}
    if 'label' in tree:return {tree['label']}
    value=test_value(record,tree['predicate'])
    if value is None:return labels(tree['yes'],record)|labels(tree['no'],record)
    return labels(tree['yes'] if value else tree['no'],record)


def definite_leaf(tree,record,path='root'):
    if record is None:return None
    if 'label' in tree:return path
    value=test_value(record,tree['predicate'])
    if value is None:return None
    return definite_leaf(tree['yes'] if value else tree['no'],record,path+('/yes' if value else '/no'))


def structure(tree):
    if 'label' in tree:return 0,1
    a,b=structure(tree['yes']),structure(tree['no']);return 1+max(a[0],b[0]),a[1]+b[1]


def used_facts(tree):
    if 'label' in tree:return set()
    return {tree['predicate']['fact']}|used_facts(tree['yes'])|used_facts(tree['no'])


def directionally_consistent(tree):
    names=sorted(used_facts(tree));values={}
    for bits in product((0,1),repeat=len(names)):
        x={'facts':{k:'not_applicable' for k in PREDICATES}}
        for k,b in zip(names,bits):x['facts'][k]='true' if b else 'false'
        values[bits]=next(iter(labels(tree,x)))
    for bits,value in values.items():
        for i,k in enumerate(names):
            if bits[i]==0 and k in DIRECTIONS:
                higher=list(bits);higher[i]=1
                if DIRECTIONS[k]*(values[tuple(higher)]-value)<0:return False
    return True


def leaf_paths(tree,path='root'):
    if 'label' in tree:return [path]
    return leaf_paths(tree['yes'],path+'/yes')+leaf_paths(tree['no'],path+'/no')


def validate_tree(tree,depth=0):
    if not isinstance(tree,dict):raise ValueError('Invalid fact tree')
    if set(tree)=={'label'}:
        if type(tree['label']) is not int or tree['label'] not in range(3):raise ValueError('Invalid fact-tree verdict')
        return
    if set(tree)!={'predicate','yes','no'} or depth>=LIMITS['max_depth']:raise ValueError('Invalid fact-tree structure')
    p=tree['predicate']
    if not isinstance(p,dict) or set(p)!={'fact','test'} or p['fact'] not in PREDICATES or p['test'] not in ('true','false'):raise ValueError('Only observable factual tests allowed')
    validate_tree(tree['yes'],depth+1);validate_tree(tree['no'],depth+1)


def convert(model,feature_names,node=0):
    t=model.tree_
    if t.children_left[node]==t.children_right[node]:return {'label':int(model.classes_[np.argmax(t.value[node][0])])}
    name=feature_names[t.feature[node]];fact,test=name
    if not 0<=t.threshold[node]<1:raise ValueError('Nonboolean split rejected')
    a=convert(model,feature_names,t.children_right[node]);b=convert(model,feature_names,t.children_left[node])
    if a==b:return a
    return {'predicate':{'fact':fact,'test':test},'yes':a,'no':b}


class FactualRuleCalibrator(Calibrator):
    version=VERSION
    def __init__(self,teacher_concepts=()):
        if any(k not in CONCEPTS for k in teacher_concepts):raise ValueError('Unknown teacher concept')
        self.teacher_concepts=tuple(teacher_concepts);self._artifact=None

    def fit(self,X,y,*,sample_weight=None,source_groups=None,teacher_targets=None):
        X,y=list(X),list(y)
        if (sample_weight is not None or not 6<=len(X)<=16 or len(X)!=len(y) or source_groups is None
            or len(source_groups)!=len(X) or len(set(source_groups))!=len(X)
            or any(type(v) is not int or v not in range(3) for v in y) or any(y.count(k)<2 for k in range(3))):
            raise ValueError('Six to sixteen distinct cases, including at least two of each class, required')
        for x in X:validate_record(x)
        teacher=list(y if teacher_targets is None else teacher_targets)
        if len(teacher)!=len(y) or any(type(t) is not int or t not in (-1,0,1,2) for t in teacher):raise ValueError('Invalid teacher targets')
        valid=[i for i,x in enumerate(X) if x is not None]
        if any(sum(y[i]==k for i in valid)<2 for k in range(3)):raise ValueError('Insufficient observable source support for all three labels')
        preferred={p for k in self.teacher_concepts for p in CONCEPTS[k]}
        bank=[(fact,test) for fact in PREDICATES for test in ('true','false')]
        orders=[sorted(bank,key=lambda p:(p[0] not in preferred,list(PREDICATES).index(p[0]),p[1])),list(reversed(bank))]
        seen=set();best=rank_best=None;counts={'sklearn_fits':0,'unique_programs':0,'supported':0,'class_supported':0,'directionally_consistent':0}
        for names in orders:
            for unknown in (0,1):
                matrix=np.asarray([[unknown if test_value(X[i],{'fact':f,'test':v}) is None else int(test_value(X[i],{'fact':f,'test':v})) for f,v in names] for i in valid],dtype=np.int8)
                for depth in (2,3,4):
                    for leaves in (3,4,5,6):
                        for criterion in ('gini','entropy'):
                            for weights in (None,'balanced',{0:1,1:2,2:1}):
                                for seed in (0,20261014):
                                    estimator=DecisionTreeClassifier(max_depth=depth,max_leaf_nodes=leaves,min_samples_leaf=2,criterion=criterion,class_weight=weights,random_state=seed)
                                    estimator.fit(matrix,[y[i] for i in valid]);counts['sklearn_fits']+=1
                                    tree=convert(estimator,names);ref=digest(tree)
                                    if ref in seen:continue
                                    seen.add(ref);counts['unique_programs']+=1;validate_tree(tree)
                                    support={path:set() for path in leaf_paths(tree)}
                                    for x,group in zip(X,source_groups):
                                        leaf=definite_leaf(tree,x)
                                        if leaf is not None:support[leaf].add(group)
                                    if min(map(len,support.values()))<2:continue
                                    counts['supported']+=1
                                    p=[next(iter(a)) if len(a:=labels(tree,x))==1 else -1 for x in X]
                                    metric,macro,worst=classification_metrics(p,y)
                                    if any(metric['per_class'][k]['correct']<2 for k in ('no','partial','yes')):continue
                                    counts['class_supported']+=1
                                    if not directionally_consistent(tree):continue
                                    counts['directionally_consistent']+=1
                                    agreement=sum(a==b for a,b in zip(p,teacher) if b>=0)
                                    d,n=structure(tree);rank=(Fraction(metric['correct'],len(y))+macro,macro,worst,agreement,-n,-d)
                                    if rank_best is None or rank>rank_best:
                                        rank_best=rank;best=(deepcopy(tree),metric,{k:len(v) for k,v in support.items()},agreement)
        self.search_diagnostic=counts
        if best is None:raise ValueError('No supported factual rule tree recognizes two sources per class')
        tree,metric,support,agreement=best
        self._artifact={'version':VERSION,'tree':tree,'limits':deepcopy(LIMITS),'predicate_bank':deepcopy(PREDICATES),'directions':deepcopy(DIRECTIONS),
            'teacher_concepts':list(self.teacher_concepts),'training_metrics':metric,'leaf_support':support,
            'teacher_agreements':agreement,'teacher_known_targets':sum(t>=0 for t in teacher),
            'training_feature_ref':digest(X),'training_target_ref':digest(y),'search':counts,
            'objective':'accuracy + macro-F1, macro-F1, worst recall, teacher fidelity, fewer leaves/depth, fixed candidate order',
            'search_scope':'Finite CART candidate search, not a claim of exact global optimality.',
            'uncertainty':'Unknown explores both branches; label only if all reachable leaves agree. NA supports neither affirmative nor contrary evidence.',
            'scope':'Local semantic tree induction; factual predicates only, no ordinal quality/score/IDs/operation-only class priors.'}
        return self

    def predict_records(self,X):
        if self._artifact is None:raise ValueError('Fit or restore first')
        result=[]
        for x in X:
            validate_record(x);a=sorted(labels(self._artifact['tree'],x))
            result.append({'prediction':a[0] if len(a)==1 else -1,'possible_labels':a,
                           'reason':'missing_observations' if x is None else 'grounded_factual_conditions'})
        return result

    def predict(self,X):return [math.nan if r['prediction']<0 else float(r['prediction']) for r in self.predict_records(X)]
    def metadata(self):return deepcopy(self._artifact) if self._artifact else {'version':VERSION}

    def render(self):
        lines=['Bind TARGET, REFERENCE and requested physical state to the instruction. The following branches test observable factual witnesses, not quality levels. Unknown facts explore both branches; return unresolved unless reachable leaves agree.']
        def visit(node,indent=''):
            if 'label' in node:lines.append(indent+'Return '+('No','Partial','Yes')[node['label']]+'.');return
            p=node['predicate'];word='affirmative' if p['test']=='true' else 'contrary'
            lines.append(indent+'IF the observations establish '+word+' evidence for: '+PREDICATES[p['fact']])
            visit(node['yes'],indent+'  ');lines.append(indent+'ELSE:');visit(node['no'],indent+'  ')
        visit(self._artifact['tree']);return '\n'.join(lines)

    @classmethod
    def restore(cls,artifact):
        if artifact.get('version')!=VERSION or artifact.get('limits')!=LIMITS or artifact.get('predicate_bank')!=PREDICATES or artifact.get('directions')!=DIRECTIONS:raise ValueError('Changed factual rule contract')
        validate_tree(artifact['tree']);d,n=structure(artifact['tree'])
        if d>4 or n>6 or set(artifact['leaf_support'])!=set(leaf_paths(artifact['tree'])) or min(artifact['leaf_support'].values())<2:
            raise ValueError('Unsupported factual leaves')
        if any(artifact['training_metrics']['per_class'][k]['correct']<2 for k in ('no','partial','yes')):raise ValueError('Class collapse')
        if not directionally_consistent(artifact['tree']):raise ValueError('Semantically reversed factual interaction')
        obj=cls(artifact.get('teacher_concepts',()));obj._artifact=deepcopy(artifact);return obj
