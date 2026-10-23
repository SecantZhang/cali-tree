"""Verify expert verdicts using semantic evidence and the regular judge's vote.

Read-only extra judge features are predictions, never human references. Both
verifiers retain correct local support. Newly resolved No-versus-Partial cases
require affirmative wrong-target/incidental-change evidence, not absence alone.
"""
from copy import deepcopy
from itertools import combinations

from ..decision.artifacts import digest
from . import semantic_fallback_router_v34 as utility

fixed=utility.warrant.fixed
VERSION='regular-aware-semantic-gate-v35'
JUDGE_FEATURES={f'judge_predicts_{name}':f'The unchanged regular judge predicts {name}.'for name in('no','partial','yes','unresolved')}
NAMES=(*fixed.VERIFY_FEATURES,*JUDGE_FEATURES)
CONTRACT=digest({'version':VERSION,'base':fixed.CONTRACT,'features':JUDGE_FEATURES,
    'priority':'Existing verified route additionally checks regular-aware evidence; on deferral calibrated semantic correction may override regular.',
    'no_partial_override':'Require explicit incidental change or wrong direction/target when overriding a Partial judgment with No.'})


def values_with_judge(program,record,regular):
    if type(regular)is not int or regular not in(-1,0,1,2):raise ValueError('Invalid regular judgment')
    values=fixed.shared.evidence.feature_values(program,record)
    if values is None:return None
    names={-1:'unresolved',0:'no',1:'partial',2:'yes'}
    return {**values,**{f'judge_predicts_{name}':name==names[regular]for name in names.values()}}


def fit_label(positive,negative,max_clauses=8):
    if not positive:raise ValueError('Protected local support required')
    if not negative:return []
    full=(1<<len(positive))-1;allneg=(1<<len(negative))-1;options={}
    def prior(lit):
        return (0 if lit[0]in JUDGE_FEATURES else 1,fixed.priority(lit))
    for f in NAMES:
        for value in(False,True):
            p=sum(1<<i for i,v in enumerate(positive)if v[f]==value);n=sum(1<<i for i,v in enumerate(negative)if v[f]==value)
            key=(p,n);literal=(f,value)
            if key not in options or prior(literal)<prior(options[key]):options[key]=literal
    candidates={}
    def add(mask,clause):
        if not mask:return
        clause=tuple(sorted(clause,key=prior))
        if mask not in candidates or (len(clause),tuple(map(prior,clause)))<(len(candidates[mask]),tuple(map(prior,candidates[mask]))):candidates[mask]=clause
    items=list(options.items())
    for (p,n),literal in items:
        if p==full:add(allneg^n,(literal,))
    for ((pa,na),la),((pb,nb),lb)in combinations(items,2):
        if (pa|pb)==full:add(allneg^(na|nb),(la,lb))
    remaining=allneg;clauses=[]
    while remaining and len(clauses)<max_clauses:
        available=[(mask,c)for mask,c in candidates.items()if mask&remaining]
        if not available:break
        mask,c=min(available,key=lambda mc:(-(mc[0]&remaining).bit_count(),len(mc[1]),tuple(map(prior,mc[1]))))
        clauses.append([{'feature':f,'value':v}for f,v in c]);remaining&=~mask
    assert all(fixed.passes(clauses,v)for v in positive)
    return clauses


def fit(base,protected,calibration,correction_router):
    clauses={}
    for label in(0,1,2):
        positive=[e['values']for e in protected if e['prediction']==label]
        positive += [e['values']for e in calibration if e['prediction']==label and e['reference']==label]
        negative=[e['values']for e in calibration if e['prediction']==label and e['reference']!=label]
        clauses[str(label)]=fit_label(positive,negative)
    return RegularAwareGate(base,clauses,correction_router)


class RegularAwareGate:
    def __init__(self,base,clauses,correction_router):
        if set(clauses)!={'0','1','2'}:raise ValueError('Incomplete regular-aware clauses')
        for cs in clauses.values():
            if len(cs)>8:raise ValueError('Too many clauses')
            for clause in cs:
                if not 1<=len(clause)<=2:raise ValueError('Invalid clause')
                for c in clause:
                    if set(c)!={'feature','value'}or c['feature']not in NAMES or type(c['value'])is not bool:raise ValueError('Undeclared clause')
        self.base,self.clauses,self.correction=base,deepcopy(clauses),correction_router
        self.artifact={'version':VERSION,'contract_ref':CONTRACT,'base_gate':base.export(),'clauses':deepcopy(clauses),
                       'correction_router':correction_router.export()};self.artifact['artifact_ref']=digest(self.artifact)
    def export(self):return deepcopy(self.artifact)
    @classmethod
    def restore(cls,a):
        if a['version']!=VERSION or a['contract_ref']!=CONTRACT or a['artifact_ref']!=digest({k:v for k,v in a.items()if k!='artifact_ref'}):raise ValueError('Changed regular-aware gate')
        result=cls(fixed.VerifiedRegionGate.restore(a['base_gate']),a['clauses'],utility.SemanticFallbackRouter.restore(a['correction_router']))
        if result.export()!=a:raise ValueError('Noncanonical gate')
        return result
    def resolve(self,program,record,regular,*,corrections=True):
        original=self.base.select(program,record)
        if original['covered']:
            if regular<0 or fixed.passes(self.clauses[str(original['prediction'])],values_with_judge(program,record,regular)):
                return {**original,'regular_aware_verified':True}
            return {'covered':False,'prediction':-1,'reason':'regular_aware_risk_rejection','matches':[]}
        if not corrections:return original
        candidate=self.correction.resolve(program,record,regular)
        if candidate['covered'] and candidate['prediction']==0 and regular==1:
            f=record['features']
            if not(f['meaning_progress_incidental_change_only_all']or f['meaning_endpoint_gap_wrong_direction_or_target_all']):
                return {**original,'correction_rejected':'partial_progress_ambiguity'}
        return candidate
