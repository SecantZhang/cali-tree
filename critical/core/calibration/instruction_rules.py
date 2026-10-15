"""Noncompensatory, instruction-dependent rules over label-blind evidence.

The rule skeleton is semantic and fixed. Fitting selects four bounded grade
thresholds; it cannot remove a required check or compensate for it with another.
"""
from copy import deepcopy
from fractions import Fraction
from itertools import product
import math

from .base import Calibrator
from .evidence_rules_v4 import classification_metrics
from ..decision.artifacts import digest
from ..decision.semantic_evidence import DESCRIPTORS,QUALITIES,validate

VERSION='instruction-dependent-interactions-v7'
GRID={'meaningful_progress':(1,2),'completed_outcome':(3,4),
      'required_fidelity':(3,4),'preservation':(3,4)}
DEFAULT={'meaningful_progress':2,'completed_outcome':3,'required_fidelity':3,'preservation':3}
CONTRACT={
    'no':'No meaningful progress; or required original identity is clearly wrong (grade 0); or applicable preservation has core meaning destroyed (grade 0).',
    'yes':'Progress AND endpoint clear the outcome threshold AND EVERY instruction-required fidelity check clears its threshold AND applicable preservation clears its threshold.',
    'partial':'Meaningful progress without a No veto, with at least one material required-check shortfall.',
    'unknown':'Evaluate lower and upper fact completions; resolve only if both give the same label. Missing responses always abstain.',
    'identity':'Required only when contract.identity_required.',
    'relation':'Required only when contract.relation_required.',
    'quantity':'Required only when contract.quantity_required.',
    'attribute':'Required for appearance/style/orientation instructions or explicitly applicable attribute evidence.',
    'scope':'Required for explicit global scope or applicable target-scope evidence.',
    'inconsistent_applicability':'A check required by the contract but declared inapplicable is unknown, never automatically complete.',
    'materiality':'Grades <=2 on a required Yes check cannot be compensated by other grades; grade 3 permits ordinary minor deviation.'}
LIMITS={'fitted_thresholds':4,'candidate_policies':16,'min_correct_sources_per_class':2,
        'permitted_model_inputs':['contract','qualities'],'lookup_features':False}


def instruction_record(observation,instruction):
    """Discard prose, identifiers and labels before calibration or prediction."""
    validate(observation,instruction)
    return {'contract':{key:observation['contract'][key] for key in DESCRIPTORS},
            'qualities':{key:{'applicable':f['applicability']=='applicable','grade':f['grade']}
                         for key,f in observation['qualities'].items()}}


def validate_record(record):
    if record is None:return
    if not isinstance(record,dict) or set(record)!={'contract','qualities'}:
        raise ValueError('Only anonymous instruction contract and quality facts allowed')
    c=record['contract'];q=record['qualities']
    if not isinstance(c,dict) or set(c)!=set(DESCRIPTORS) or any(type(v) is not bool for v in c.values()):
        raise ValueError('Exact binary instruction contract required')
    if not isinstance(q,dict) or set(q)!=set(QUALITIES):raise ValueError('All quality facts required')
    for f in q.values():
        if (not isinstance(f,dict) or set(f)!={'applicable','grade'} or type(f['applicable']) is not bool
            or f['grade'] is not None and (type(f['grade']) is not int or not 0<=f['grade']<=4)
            or not f['applicable'] and f['grade']!=4):raise ValueError('Invalid applicability or grade')


def active_checks(record):
    c=record['contract'];q=record['qualities'];active=['progress','endpoint']
    for flag,key in (('identity_required','identity'),('relation_required','relation'),('quantity_required','quantity')):
        if c[flag]:active.append(key)
    if c['appearance'] or c['style'] or c['orientation'] or q['attribute']['applicable']:active.append('attribute')
    if c['global_scope_explicit'] or q['scope']['applicable']:active.append('scope')
    if q['preservation']['applicable']:active.append('preservation')
    return active


def completions(record):
    active=active_checks(record);lo={};hi={};unknown=[]
    for key in active:
        f=record['qualities'][key]
        if f['grade'] is None or not f['applicable']:
            lo[key]=0;hi[key]=4;unknown.append(key)
        else:lo[key]=hi[key]=f['grade']
    return lo,hi,unknown


def resolved_label(record,grades,thresholds):
    c=record['contract']
    if grades['progress']<thresholds['meaningful_progress']:return 0
    if c['identity_required'] and grades['identity']==0:return 0
    if 'preservation' in grades and grades['preservation']==0:return 0
    for key,value in grades.items():
        cut=(thresholds['completed_outcome'] if key in ('progress','endpoint') else
             thresholds['preservation'] if key=='preservation' else thresholds['required_fidelity'])
        if value<cut:return 1
    return 2


def candidates():
    for values in product(*GRID.values()):yield dict(zip(GRID,values))


class InstructionRuleCalibrator(Calibrator):
    version=VERSION
    def __init__(self,thresholds=None):
        self.thresholds=deepcopy(DEFAULT if thresholds is None else thresholds)
        self._check_thresholds(self.thresholds);self._artifact=None

    @staticmethod
    def _check_thresholds(t):
        if not isinstance(t,dict) or set(t)!=set(GRID) or any(type(t[k]) is not int or t[k] not in GRID[k] for k in GRID):
            raise ValueError('Thresholds may not disable semantic materiality floors')

    def predict_records(self,X):
        result=[]
        for record in X:
            validate_record(record)
            if record is None:
                result.append({'prediction':-1,'reason':'missing_response','active_checks':[],
                               'label_bounds':[0,2],'unknown_checks':[],'blocking_yes':[]});continue
            lo,hi,unknown=completions(record)
            labels=[resolved_label(record,g,self.thresholds) for g in (lo,hi)]
            p=labels[0] if labels[0]==labels[1] else -1
            blockers=[]
            for key in lo:
                cut=self.thresholds['completed_outcome' if key in ('progress','endpoint') else 'preservation' if key=='preservation' else 'required_fidelity']
                if lo[key]<cut:blockers.append({'check':key,'grade_interval':[lo[key],hi[key]],'required':cut})
            result.append({'prediction':p,'reason':'uncertainty_changes_label' if p<0 else 'instruction_dependent_gates',
                           'active_checks':list(lo),'label_bounds':labels,'unknown_checks':unknown,'blocking_yes':blockers})
        return result

    def predict(self,X):
        return [math.nan if r['prediction']<0 else float(r['prediction']) for r in self.predict_records(X)]

    def fit(self,X,y,*,sample_weight=None,source_groups=None):
        X,y=list(X),list(y)
        if (sample_weight is not None or not X or len(X)!=len(y) or source_groups is None
            or len(source_groups)!=len(X) or len(set(source_groups))!=len(X)
            or any(type(v) is not int or v not in range(3) for v in y) or any(y.count(i)<2 for i in range(3))):
            raise ValueError('Distinct sources and at least two reference cases per class required')
        evaluated=[]
        for t in candidates():
            policy=type(self)(t);p=[r['prediction'] for r in policy.predict_records(X)]
            metrics,macro,worst=classification_metrics(p,y)
            rank=(Fraction(metrics['correct'],len(y))+macro,macro,worst,metrics['correct'])
            eligible=all(metrics['per_class'][label]['correct']>=2 for label in ('no','partial','yes'))
            evaluated.append({'thresholds':t,'metrics':metrics,'rank':rank,'eligible':eligible})
        feasible=[e for e in evaluated if e['eligible']]
        self.search_diagnostic={'candidates':len(evaluated),'eligible':len(feasible),
            'best_unconstrained_correct':max(e['metrics']['correct'] for e in evaluated)}
        if not feasible:raise ValueError('No instruction-dependent policy recognizes two source cases per class; semantic gates were not weakened')
        best_rank=max(e['rank'] for e in feasible);equivalent=[e for e in feasible if e['rank']==best_rank]
        # Default-biased tie-breaking is fixed in advance; no test labels select
        # among numerically equivalent training policies.
        selected=min(equivalent,key=lambda e:(sum(e['thresholds'][k]!=DEFAULT[k] for k in GRID),tuple(e['thresholds'].values())))
        self.thresholds=deepcopy(selected['thresholds'])
        self._artifact={'version':VERSION,'thresholds':self.thresholds,'rule_contract':deepcopy(CONTRACT),
            'limits':deepcopy(LIMITS),'grid':{k:list(v) for k,v in GRID.items()},'default':deepcopy(DEFAULT),
            'objective':'accuracy plus macro-F1; then macro-F1, worst recall, correct, fewer deviations from default, fixed order',
            'training_metrics':selected['metrics'],'search':self.search_diagnostic,
            'equally_scoring_training_policies':[e['thresholds'] for e in equivalent],
            'training_feature_ref':digest(X),'training_target_ref':digest(y),
            'scope':'A fitted policy freezes all four thresholds; predict accepts no labels or case identifiers.'}
        return self

    def metadata(self):
        return deepcopy(self._artifact) if self._artifact else {'version':VERSION,'thresholds':deepcopy(self.thresholds),
            'rule_contract':deepcopy(CONTRACT),'limits':deepcopy(LIMITS),'scope':'Fixed semantic policy; no calibration labels used.'}

    @classmethod
    def restore(cls,artifact):
        if artifact.get('version')!=VERSION or artifact.get('rule_contract')!=CONTRACT or artifact.get('limits')!=LIMITS:
            raise ValueError('Changed instruction-dependent rule contract')
        result=cls(artifact['thresholds'])
        if 'training_metrics' in artifact and any(artifact['training_metrics']['per_class'][k]['correct']<2 for k in ('no','partial','yes')):
            raise ValueError('Class-collapsed fitted artifact')
        result._artifact=deepcopy(artifact);return result
