"""Teacher-guided local induction of disjunctive physical-evidence rules."""
from copy import deepcopy
from itertools import combinations
from math import lcm
import math

import numpy as np

from .base import Calibrator
from ..decision.physical_witness_program import DIRECTIONS,CONCEPTS,validate_record,PREDICATES,CORE,SUPPORT
from .evidence_rules_v4 import classification_metrics
from ..decision.artifacts import digest

VERSION='instruction-bound-physical-rules-v13'
LIMITS={'atoms_per_clause':3,'clauses_per_boundary':3,'candidate_regions_per_boundary':2048,
        'min_clause_sources':2,'min_correct_per_class':2}


def atom_bounds(x,atom):
    v=x['facts'][atom['fact']]
    if v=='unknown':return False,True
    result=v==atom['test'];return result,result


def region_bounds(x,clauses):
    lo=hi=False
    for clause in clauses:
        bounds=[atom_bounds(x,a) for a in clause]
        lo=lo or all(v[0] for v in bounds);hi=hi or all(v[1] for v in bounds)
    return lo,hi


def program_prediction(x,yes,partial):
    if x is None:return -1
    a,b=region_bounds(x,yes),region_bounds(x,partial)
    low=2 if a[0] else 1 if b[0] else 0;high=2 if a[1] else 1 if b[1] else 0
    return low if low==high else -1


class ObservableDNFCalibrator(Calibrator):
    version=VERSION
    def __init__(self,teacher_concepts=()):
        if any(k not in CONCEPTS for k in teacher_concepts):raise ValueError('Unknown teacher concept')
        self.teacher_concepts=tuple(teacher_concepts);self._artifact=None

    def fit(self,X,y,*,sample_weight=None,source_groups=None,teacher_targets=None):
        X,y=list(X),list(y);n=len(y)
        if sample_weight is not None or not 6<=n<=16 or len(X)!=n or source_groups is None or len(source_groups)!=n or len(set(source_groups))!=n or any(type(v) is not int or v not in range(3) for v in y) or any(y.count(k)<2 for k in range(3)):
            raise ValueError('Distinct local sources including all three classes required')
        for x in X:validate_record(x)
        teacher=list(y if teacher_targets is None else teacher_targets)
        if len(teacher)!=n or any(type(v) is not int or v not in (-1,0,1,2) for v in teacher):raise ValueError('Invalid teacher labels')
        preferred={p for k in self.teacher_concepts for p in CONCEPTS[k]}
        atoms=[]
        for fact in sorted(PREDICATES,key=lambda k:(k not in preferred,list(PREDICATES).index(k))):
            tests=('true',) if DIRECTIONS.get(fact)==1 else ('false',) if DIRECTIONS.get(fact)==-1 else ('true','false')
            for test in tests:
                a={'fact':fact,'test':test};lo=hi=0
                for i,x in enumerate(X):
                    if x is not None:
                        low,high=atom_bounds(x,a);lo|=int(low)<<i;hi|=int(high)<<i
                if lo.bit_count()>=2:atoms.append((a,lo,hi))
        terms={}
        for arity in range(1,LIMITS['atoms_per_clause']+1):
            for chosen in combinations(range(len(atoms)),arity):
                if len({atoms[i][0]['fact'] for i in chosen})!=arity:continue
                lo=hi=(1<<n)-1
                for i in chosen:lo&=atoms[i][1];hi&=atoms[i][2]
                if lo.bit_count()<2:continue
                role=(2 if any(atoms[i][0]['test']=='true' and atoms[i][0]['fact'] in CORE for i in chosen) else
                      1 if any(atoms[i][0]['test']=='true' and atoms[i][0]['fact'] in SUPPORT for i in chosen) else 0)
                # Equal local coverage does not make a physical-outcome witness
                # interchangeable with an incidental condition. Preserve its role
                # until the requested-witness filter has been applied.
                key=(lo,hi,role);rank=(arity,sum(atoms[i][0]['fact'] not in preferred for i in chosen),chosen)
                if key not in terms or rank<terms[key][1]:terms[key]=(chosen,rank)
        term_list=[(lo,hi,value[0]) for (lo,hi,role),value in terms.items()]
        target_masks=[sum(1<<i for i,v in enumerate(y) if v==k) for k in range(3)]
        observed=sum(1<<i for i,x in enumerate(X) if x is not None)
        def make_regions(positive):
            core=CORE if positive==target_masks[2] else SUPPORT
            eligible=[j for j,(lo,hi,indices) in enumerate(term_list) if (lo&positive).bit_count()>=1 and any(atoms[i][0]['test']=='true' and atoms[i][0]['fact'] in core for i in indices)]
            pool={(0,0):()}
            def region_rank(item):
                (lo,hi),clauses=item;tp=(lo&positive).bit_count();fp=(hi&~positive&observed).bit_count()
                return (tp-fp,tp,-fp,-sum(len(term_list[j][2]) for j in clauses),-len(clauses),tuple(-j for j in clauses))
            for _ in range(LIMITS['clauses_per_boundary']):
                current=list(pool.items());updated=dict(pool)
                for (a,b),clauses in current:
                    if len(clauses)>=LIMITS['clauses_per_boundary']:continue
                    for j in eligible:
                        lo,hi,_=term_list[j];key=(a|lo,b|hi);candidate=tuple(sorted(set((*clauses,j))))
                        if len(candidate)==len(clauses):continue
                        prior=updated.get(key)
                        if prior is None or (sum(len(term_list[k][2]) for k in candidate),len(candidate),candidate)<(sum(len(term_list[k][2]) for k in prior),len(prior),prior):updated[key]=candidate
                if len(updated)>LIMITS['candidate_regions_per_boundary']:
                    updated=dict(sorted(updated.items(),key=region_rank,reverse=True)[:LIMITS['candidate_regions_per_boundary']])
                if updated==pool:break
                pool=updated
            return [(lo,hi,c) for (lo,hi),c in pool.items() if (lo&positive).bit_count()>=2]
        yes_regions=make_regions(target_masks[2]);partial_regions=make_regions(target_masks[1]|target_masks[2])
        self.search_diagnostic={'atoms':len(atoms),'supported_conjunctions':len(term_list),'yes_regions':len(yes_regions),'partial_regions':len(partial_regions)}
        if not yes_regions or not partial_regions:raise ValueError('Insufficient factual conjunction support')
        # Keep counts in int64: exact objective scaling can exceed int16 even
        # though every individual class count is small.
        bitcount=np.asarray([i.bit_count() for i in range(1<<n)],dtype=np.int64)
        py_lo=np.asarray([r[0] for r in yes_regions],dtype=np.int64);py_hi=np.asarray([r[1] for r in yes_regions],dtype=np.int64)
        pp_lo=np.asarray([r[0] for r in partial_regions],dtype=np.int64);pp_hi=np.asarray([r[1] for r in partial_regions],dtype=np.int64)
        costs=lambda regions:np.asarray([sum(len(term_list[j][2]) for j in r[2]) for r in regions])
        yes_cost,partial_cost=costs(yes_regions),costs(partial_regions)
        yes_clauses=np.asarray([len(r[2]) for r in yes_regions]);partial_clauses=np.asarray([len(r[2]) for r in partial_regions])
        ns=[y.count(k) for k in range(3)];scale=lcm(n,3*lcm(*range(1,n+max(ns)+1)))
        teacher_masks=[sum(1<<i for i,v in enumerate(teacher) if v==k) for k in range(3)]
        best=best_rank=None;eligible_count=0
        for start in range(0,len(yes_regions),64):
            a=py_lo[start:start+64,None];b=py_hi[start:start+64,None]
            masks=[np.bitwise_and(~(b|pp_hi[None,:]),observed),np.bitwise_and(pp_lo[None,:]&~b,observed),np.broadcast_to(a&observed,(len(a),len(partial_regions)))]
            tp=np.stack([bitcount[v&target_masks[k]] for k,v in enumerate(masks)],axis=2)
            count=np.stack([bitcount[v] for v in masks],axis=2);valid=np.all(tp>=2,axis=2);eligible_count+=int(valid.sum())
            if not valid.any():continue
            macro=np.zeros(valid.shape,dtype=np.int64)
            for k,num in enumerate(ns):macro+=2*tp[:,:,k]*(scale//(3*(num+count[:,:,k])))
            correct=tp.sum(axis=2);joint=macro+correct*(scale//n);worst=np.min(tp*np.asarray([scale//num for num in ns])[None,None,:],axis=2)
            agreement=sum(bitcount[v&teacher_masks[k]] for k,v in enumerate(masks))
            clauses=yes_clauses[start:start+64,None]+partial_clauses[None,:];cost=yes_cost[start:start+64,None]+partial_cost[None,:]
            selection=valid;rank=[]
            for value in (joint,macro,worst,agreement,-clauses,-cost):
                value=np.broadcast_to(value,valid.shape);mx=int(value[selection].max());selection&=value==mx;rank.append(mx)
            i,j=np.argwhere(selection)[0];r=tuple(rank)
            if best_rank is None or r>best_rank:best_rank=r;best=(start+int(i),int(j))
        self.search_diagnostic['class_supported_pairs']=eligible_count
        if best is None:raise ValueError('No supported semantic DNF recognizes two sources per class')
        def clauses_for(regions,index):return [[deepcopy(atoms[i][0]) for i in term_list[j][2]] for j in regions[index][2]]
        yes,partial=clauses_for(yes_regions,best[0]),clauses_for(partial_regions,best[1])
        p=[program_prediction(x,yes,partial) for x in X];metric=classification_metrics(p,y)[0]
        support={}
        for label,clauses in [('yes',yes),('partial',partial)]:
            support[label]=[sum(x is not None and all(atom_bounds(x,a)[0] for a in c) for x in X) for c in clauses]
        self._artifact={'version':VERSION,'yes':yes,'partial':partial,'limits':deepcopy(LIMITS),'predicate_bank':deepcopy(PREDICATES),
            'directions':deepcopy(DIRECTIONS),'teacher_concepts':list(self.teacher_concepts),'clause_support':support,
            'training_metrics':metric,'training_feature_ref':digest(X),'training_target_ref':digest(y),
            'teacher_agreements':sum(a==b for a,b in zip(p,teacher) if b>=0),'search':self.search_diagnostic,
            'scope':'Local teacher-assisted observable-predicate induction; no ordinal qualities, scores, strings or case identifiers as inputs.',
            'search_scope':'Supported conjunction enumeration and bounded region search; no global-optimality claim.'}
        return self

    def predict_records(self,X):
        if self._artifact is None:raise ValueError('Fit first')
        result=[]
        for x in X:
            validate_record(x);p=program_prediction(x,self._artifact['yes'],self._artifact['partial'])
            result.append({'prediction':p,'reason':'missing_observations' if x is None else 'physical_witness_conjunctions'})
        return result

    def predict(self,X):return [math.nan if r['prediction']<0 else float(r['prediction']) for r in self.predict_records(X)]
    def metadata(self):return deepcopy(self._artifact) if self._artifact else {'version':VERSION}
    def render(self):
        lines=['Bind the generic target/reference/operation questions to the instruction. Use factual evidence only.']
        for key,title in [('yes','Return Yes if any complete conjunction below is established:'),('partial','Otherwise return Partial if any complete conjunction below is established:')]:
            lines.append(title)
            for c in self._artifact[key]:lines.append('- '+' AND '.join(('Affirmative witness: ' if a['test']=='true' else 'Observed contrary: ')+PREDICATES[a['fact']] for a in c))
        lines.append('Otherwise No. Unknown witnesses remain uncertain; resolve only when both evidence bounds give the same label. Missing evidence is unresolved.')
        return '\n'.join(lines)

    @classmethod
    def restore(cls,a):
        if a.get('version')!=VERSION or a.get('limits')!=LIMITS or a.get('predicate_bank')!=PREDICATES or a.get('directions')!=DIRECTIONS:raise ValueError('Changed factual DNF contract')
        for label in ('yes','partial'):
            if not isinstance(a[label],list) or not 1<=len(a[label])<=3 or len(a['clause_support'][label])!=len(a[label]) or min(a['clause_support'][label])<2:raise ValueError('Unsupported semantic clauses')
            for clause in a[label]:
                if not any(x['test']=='true' and x['fact'] in (CORE if label=='yes' else SUPPORT) for x in clause):raise ValueError('Positive verdict requires a requested physical witness')
                if not 1<=len(clause)<=3 or len({x['fact'] for x in clause})!=len(clause):raise ValueError('Invalid semantic conjunction')
                for atom in clause:
                    if set(atom)!={'fact','test'} or atom['fact'] not in PREDICATES or atom['test'] not in ('true','false'):raise ValueError('Invalid physical predicate')
                    expected='true' if DIRECTIONS.get(atom['fact'])==1 else 'false' if DIRECTIONS.get(atom['fact'])==-1 else atom['test']
                    if atom['test']!=expected:raise ValueError('Reversed semantic evidence direction')
        if any(a['training_metrics']['per_class'][k]['correct']<2 for k in ('no','partial','yes')):raise ValueError('Class collapse')
        obj=cls(a.get('teacher_concepts',()));obj._artifact=deepcopy(a);return obj
