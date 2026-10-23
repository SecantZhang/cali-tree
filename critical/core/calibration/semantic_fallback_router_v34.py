"""Utility-aware semantic resolution after a verified gate defers.

The regular judge is already called on deferred inputs. Override it only when a
strict outcome warrant, matching expert and source-supported error-free training
region agree. Existing trusted routes retain precedence.
"""
from collections import defaultdict
from copy import deepcopy
from itertools import combinations

from ..decision.artifacts import digest
from . import decision_warrant_gate_v33 as warrant

VERSION='semantic-fallback-router-v34'
CONTRACT=digest({'version':VERSION,'warrants':warrant.CONTRACT,'grammar':'OR of up to four conjunctions of zero/one/two semantic literals per warrant/regular disagreement',
                'support':'At least two distinct beneficial source groups and zero training errors per conjunction; no per-case membership.'})


def fit_domain(positive,negative,max_terms=4,min_sources=2):
    full=(1<<len(positive))-1
    if len({e['source_group']for e in positive})<min_sources:return [],{'positive':len(positive),'negative':len(negative),'covered':0}
    if not negative:return [[]],{'positive':len(positive),'negative':0,'covered':len(positive)}
    options={}
    for f in warrant.fixed.VERIFY_FEATURES:
        for v in(False,True):
            pm=sum(1<<i for i,e in enumerate(positive)if e['values'][f]==v)
            nm=sum(1<<i for i,e in enumerate(negative)if e['values'][f]==v)
            lit=(f,v);key=(pm,nm)
            if key not in options or warrant.fixed.priority(lit)<warrant.fixed.priority(options[key]):options[key]=lit
    def sources(mask):return len({e['source_group']for i,e in enumerate(positive)if mask>>i&1})
    candidates={}
    def add(mask,term):
        if sources(mask)<min_sources:return
        term=tuple(sorted(term,key=warrant.fixed.priority))
        if mask not in candidates or (len(term),tuple(map(warrant.fixed.priority,term)))<(len(candidates[mask]),tuple(map(warrant.fixed.priority,candidates[mask]))):candidates[mask]=term
    items=list(options.items())
    for (pm,nm),literal in items:
        if not nm:add(pm,(literal,))
    for ((pa,na),la),((pb,nb),lb)in combinations(items,2):
        if not(na&nb):add(pa&pb,(la,lb))
    remaining=full;selected=[]
    while remaining and len(selected)<max_terms:
        available=[(m,t)for m,t in candidates.items()if m&remaining]
        if not available:break
        mask,term=min(available,key=lambda mt:(-sources(mt[0]&remaining),-(mt[0]&remaining).bit_count(),len(mt[1]),tuple(map(warrant.fixed.priority,mt[1]))))
        selected.append([{'feature':f,'value':v}for f,v in term]);remaining&=~mask
    return selected,{'positive':len(positive),'negative':len(negative),'covered':len(positive)-remaining.bit_count()}


def eligible_experts(base,record,label):
    return [ref for ref,ex in warrant.experts(base).items()if ex.predict_records([record])[0]['prediction']==label]


def fit(base,examples):
    grouped=defaultdict(list);bank=warrant.experts(base)
    for e in examples:
        if e['features']is None or base.select(e['program'],e['features'])['covered']:continue
        label=warrant.certificate(e['features']);regular=e['regular']
        if label is None or label==regular:continue
        if not any(ex.predict_records([e['features']])[0]['prediction']==label for ex in bank.values()):continue
        key=f'{label}:{regular}'
        grouped[key].append({'source_group':e['source_group'],'values':warrant.fixed.shared.evidence.feature_values(e['program'],e['features']),
                             'correct':label==e['reference']})
    domains={};counts={}
    for key,rows in sorted(grouped.items()):
        pos=[e for e in rows if e['correct']];neg=[e for e in rows if not e['correct']]
        domains[key],counts[key]=fit_domain(pos,neg)
    a={'version':VERSION,'contract_ref':CONTRACT,'domains':domains,'counts':counts};a['artifact_ref']=digest(a)
    return SemanticFallbackRouter(base,a)


class SemanticFallbackRouter:
    def __init__(self,base,support):
        if support['version']!=VERSION or support['contract_ref']!=CONTRACT or support['artifact_ref']!=digest({k:v for k,v in support.items()if k!='artifact_ref'}):raise ValueError('Changed fallback support')
        for key,terms in support['domains'].items():
            label,regular=map(int,key.split(':'))
            if label not in(0,2)or regular not in(-1,0,1,2)or label==regular or len(terms)>4:raise ValueError('Invalid disagreement domain')
            for term in terms:
                if len(term)>2:raise ValueError('Oversized support term')
                for c in term:
                    if set(c)!={'feature','value'}or c['feature']not in warrant.fixed.VERIFY_FEATURES or type(c['value'])is not bool:raise ValueError('Undeclared support feature')
        self.base,self.support=base,deepcopy(support);self.experts=warrant.experts(base)
        self.artifact={'version':VERSION,'contract_ref':CONTRACT,'base_gate':base.export(),'support':deepcopy(support)};self.artifact['artifact_ref']=digest(self.artifact)
    def export(self):return deepcopy(self.artifact)
    @classmethod
    def restore(cls,a):
        if a['version']!=VERSION or a['contract_ref']!=CONTRACT or a['artifact_ref']!=digest({k:v for k,v in a.items()if k!='artifact_ref'}):raise ValueError('Changed fallback router')
        result=cls(warrant.fixed.VerifiedRegionGate.restore(a['base_gate']),a['support'])
        if result.export()!=a:raise ValueError('Noncanonical router')
        return result
    def resolve(self,program,record,regular):
        prior=self.base.select(program,record)
        if prior['covered']:return {**prior,'regular_needed':False}
        label=warrant.certificate(record)
        if label is None or label==regular:return {**prior,'regular_needed':True}
        terms=self.support['domains'].get(f'{label}:{regular}',[])
        values=warrant.fixed.shared.evidence.feature_values(program,record)
        if not any(all(values[c['feature']]==c['value']for c in term)for term in terms):return {**prior,'regular_needed':True}
        experts=[ref for ref,ex in self.experts.items()if ex.predict_records([record])[0]['prediction']==label]
        if not experts:return {**prior,'regular_needed':True}
        return {'covered':True,'prediction':label,'reason':'validated_semantic_override','matches':[{'expert_ref':ref,'prediction':label}for ref in experts],
                'regular_needed':True,'regular_prediction':regular,'support_ref':self.support['artifact_ref']}
