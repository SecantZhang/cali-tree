"""Explicitly calibrate uninspectable results without fabricating quality facts."""
from copy import deepcopy
from itertools import combinations
from math import lcm

import numpy as np

from .semantic_calibration import SemanticOrdinalCalibrator,SemanticRouter,coefficients,_bounds,LIMITS
from .evidence_rules_v4 import classification_metrics
from ..decision.semantic_evidence import QUALITIES
from ..decision.artifacts import digest

VERSION='semantic-visibility-ordinal-v6'


def uninspectable(record):
    """A completed extraction lacks both progress and endpoint evidence.

    This is an evidence-availability condition, not an imputed outcome grade.
    A failed extraction (descriptor None) can never trigger a verdict here.
    """
    return (record['descriptor'] is not None and all(record['lower'][i]==0 and record['upper'][i]==4 for i in (0,1)))


class VisibilityOrdinalCalibrator(SemanticOrdinalCalibrator):
    version=VERSION
    def fit(self,X,y,*,sample_weight=None,source_groups=None):
        X,y=list(X),list(y)
        if sample_weight is not None or not 6<=len(X)<=16 or len(y)!=len(X) or source_groups is None or len(source_groups)!=len(X) or len(set(source_groups))!=len(X) or any(type(v) is not int or v not in range(3) for v in y) or any(y.count(i)<2 for i in range(3)):
            raise ValueError('Six to sixteen distinct source cases including all three labels required')
        low,high=_bounds(X); clusters=self.router.predict([r['descriptor'] for r in X])
        k=len(self.router.centers); supports=[clusters.count(i) for i in range(k)]
        missing=np.asarray([r['descriptor'] is None for r in X]); visible_guard=np.asarray([uninspectable(r) for r in X])
        guards=[None]+[label for label in range(3) if sum(v and t==label for v,t in zip(visible_guard,y))>=2]
        models=[]
        for w,o in coefficients(k,supports,self.clustered):
            for g in guards:
                if sum(v!=0 for v in w+o)+(g is not None)<=LIMITS['nonzero_coefficients']:models.append((w,o,g))
        cuts=np.asarray(list(combinations(range(1,25),2)),dtype=np.int16);targets=np.asarray(y)
        n=len(y);ns=[y.count(i) for i in range(3)];scale=lcm(n,3*lcm(*range(1,n+max(ns)+1)))
        if scale>np.iinfo(np.int64).max//100:raise ValueError('Exact objective exceeds integer range')
        best=rank_best=None;eligible=0
        for start in range(0,len(models),128):
            batch=models[start:start+128];w=np.asarray([m[0] for m in batch],dtype=np.int16)
            o=np.asarray([m[1] for m in batch],dtype=np.int16);g=np.asarray([-1 if m[2] is None else m[2] for m in batch])
            delta=np.asarray([[a[c] if c>=0 else 0 for c in clusters] for a in o],dtype=np.int16)
            lo=w@low.T+delta;hi=w@high.T+delta
            cut_valid=(cuts[None,:,0]>np.max(o,axis=1)[:,None])&(cuts[None,:,1]<=4*np.sum(w,axis=1)[:,None]+np.min(o,axis=1)[:,None])
            a=(lo[:,None,:]>=cuts[None,:,0,None]).astype(np.int8)+(lo[:,None,:]>=cuts[None,:,1,None]).astype(np.int8)
            b=(hi[:,None,:]>=cuts[None,:,0,None]).astype(np.int8)+(hi[:,None,:]>=cuts[None,:,1,None]).astype(np.int8)
            p=np.where(a==b,a,-1)
            p=np.where((g[:,None,None]>=0)&visible_guard[None,None,:],g[:,None,None],p)
            p[:,:,missing]=-1
            tp=np.stack([np.sum((p==i)&(targets[None,None,:]==i),axis=2) for i in range(3)],axis=2)
            counts=np.stack([np.sum(p==i,axis=2) for i in range(3)],axis=2)
            valid=cut_valid&np.all(tp>=2,axis=2);eligible+=int(valid.sum())
            if not valid.any():continue
            macro=np.zeros(valid.shape,dtype=np.int64)
            for i,num in enumerate(ns):macro+=2*tp[:,:,i]*(scale//(3*(num+counts[:,:,i])))
            correct=tp.sum(axis=2);joint=macro+correct*(scale//n)
            worst=np.min(tp*np.asarray([scale//num for num in ns])[None,None,:],axis=2)
            active=np.count_nonzero(w,axis=1)+np.count_nonzero(o,axis=1)+(g>=0)
            mass=np.sum(w,axis=1)+np.sum(np.abs(o),axis=1)
            criteria=[joint,macro,correct,worst,np.broadcast_to(-active[:,None],valid.shape),np.broadcast_to(-mass[:,None],valid.shape)]
            chosen=[];mask=valid
            for criterion in criteria:
                mx=int(criterion[mask].max());chosen.append(mx);mask&=criterion==mx
            j,t=np.argwhere(mask)[0];rank=tuple(chosen)
            if rank_best is None or rank>rank_best:rank_best=rank;best=(*batch[j],cuts[t].tolist(),p[j,t].tolist())
        if best is None:raise ValueError('No supported policy recognizes two sources per class')
        w,o,g,t,p=best;m,_,_=classification_metrics(p,y)
        self._artifact={'version':VERSION,'clustered':self.clustered,'router':self.router.metadata(),
                        'quality_names':list(QUALITIES),'limits':deepcopy(LIMITS),'weights':w,'offsets':o,'cutpoints':t,
                        'uninspectable_label':g,'uninspectable_support':int(visible_guard.sum()),
                        'uninspectable_correct_support':int(sum(v and target==g for v,target in zip(visible_guard,y))) if g is not None else 0,
                        'cluster_support':supports,'active_coefficients':sum(v!=0 for v in w+o)+(g is not None),'shared_cutpoints':2,
                        'objective':'mean(accuracy, macro-F1); then macro-F1, correct, worst recall, simplicity',
                        'training_metrics':m,'training_feature_ref':digest(X),'training_target_ref':digest(y),
                        'search':{'coefficient_models':len(models),'cutpoint_pairs':len(cuts),'class_supported_policies':eligible},
                        'scope':'Local fitting. An uninspectable-result verdict is a learned evaluation policy, not a factual claim about hidden image content.'}
        return self

    def predict_records(self,X):
        X=list(X);records=super().predict_records(X);g=self._artifact['uninspectable_label']
        for x,r in zip(X,records):
            r['uninspectable_branch']=g is not None and uninspectable(x)
            if r['uninspectable_branch']:r['prediction']=g
            if x['descriptor'] is None:r['prediction']=-1
        return records

    @classmethod
    def restore(cls,artifact):
        from .semantic_calibration import VERSION as BASE_VERSION
        a=deepcopy(artifact);g=a.get('uninspectable_label')
        if a.get('version')!=VERSION or (g is not None and (type(g) is not int or g not in range(3) or a['uninspectable_support']<2 or a['uninspectable_correct_support']<2)):
            raise ValueError('Invalid or unsupported observability branch')
        surrogate=deepcopy(a);surrogate['version']=BASE_VERSION
        base=SemanticOrdinalCalibrator.restore(surrogate)
        if sum(v!=0 for v in a['weights']+a['offsets'])+(g is not None)>4:
            raise ValueError('Observability branch exceeds the shared coefficient budget')
        obj=cls(base.router,clustered=a['clustered']);obj._artifact=a;return obj
