"""Small monotone ordinal policies, optionally routed by label-blind contracts.

The router receives only instruction-derived binary descriptors. Supervised fitting
uses graded evidence, two shared cut points, and at most four nonzero coefficients
INCLUDING cluster offsets. No words, identifiers, or target lookups enter prediction.
"""
from copy import deepcopy
from itertools import combinations, product
from math import lcm

import numpy as np
from sklearn.cluster import KMeans

from .base import Calibrator
from .evidence_rules_v4 import classification_metrics
from ..decision.artifacts import digest
from ..decision.semantic_evidence import DESCRIPTORS, QUALITIES

VERSION = 'semantic-ordinal-calibration-v5'
LIMITS = {'nonzero_coefficients': 4, 'weight_max': 3, 'weight_sum': 6,
          'offset_max': 2, 'min_cluster_sources': 2, 'min_class_correct': 2}


class SemanticRouter:
    """Three deterministic clusters of instruction contracts; never sees outcomes."""
    def fit(self, descriptors):
        values = list(descriptors)
        valid = [list(v) for v in values if v is not None]
        if not valid or any(len(v) != len(DESCRIPTORS) or any(type(x) is not int or x not in (0, 1) for x in v) for v in valid):
            raise ValueError('Binary instruction contracts required')
        ordered = np.asarray(sorted(valid), dtype=float)
        k = min(3, len(set(map(tuple, valid))))
        fitted = KMeans(n_clusters=k, random_state=20261014, n_init=20).fit(ordered)
        # Floating point centroids of binary inputs can drift a few ulps outside
        # [0,1]. Clamp those numerical errors before persisting the router.
        self.centers = np.asarray(sorted(np.clip(fitted.cluster_centers_,0,1).tolist()))
        self._artifact = {'version': VERSION, 'inputs': list(DESCRIPTORS),
                          'centers': self.centers.tolist(), 'seed': 20261014,
                          'input_ref': digest(sorted(valid)), 'sources': len(valid),
                          'scope': 'Label-blind routing; instruction-contract booleans only.'}
        return self

    def predict(self, descriptors):
        result = []
        for d in descriptors:
            if d is None:
                result.append(-1); continue
            if len(d) != len(DESCRIPTORS) or any(type(x) is not int or x not in (0, 1) for x in d):
                raise ValueError('Binary instruction contracts required')
            result.append(int(np.argmin(np.sum((self.centers-np.asarray(d))**2, axis=1))))
        return result

    def metadata(self): return deepcopy(self._artifact)

    @classmethod
    def restore(cls, artifact):
        if artifact.get('version') != VERSION or artifact.get('inputs') != list(DESCRIPTORS):
            raise ValueError('Unknown router contract')
        centers = np.asarray(artifact.get('centers'), dtype=float)
        if centers.ndim != 2 or not 1 <= len(centers) <= 3 or centers.shape[1] != len(DESCRIPTORS) or not np.all(np.isfinite(centers)) or np.any((centers < 0) | (centers > 1)):
            raise ValueError('Invalid contract centers')
        obj = cls(); obj.centers = centers; obj._artifact = deepcopy(artifact); return obj


def _bounds(records):
    if not records: raise ValueError('Evidence records required')
    for r in records:
        if set(r) != {'lower', 'upper', 'descriptor'}:
            raise ValueError('Only whitelisted evidence fields allowed')
        if any(len(r[k]) != len(QUALITIES) or any(type(x) is not int or not 0 <= x <= 4 for x in r[k]) for k in ('lower','upper')):
            raise ValueError('Eight bounded quality grades required')
    low = np.asarray([r['lower'] for r in records], dtype=np.int16)
    high = np.asarray([r['upper'] for r in records], dtype=np.int16)
    if np.any(low > high): raise ValueError('Reversed uncertainty interval')
    return low, high


def coefficients(k, supports, clustered):
    """Same total supervised coefficient budget for both comparison families."""
    for active in range(1, LIMITS['nonzero_coefficients']+1):
        for indices in combinations(range(len(QUALITIES)), active):
            for values in product(range(1, LIMITS['weight_max']+1), repeat=active):
                if sum(values) > LIMITS['weight_sum']: continue
                weights = [0]*len(QUALITIES)
                for i,v in zip(indices,values): weights[i] = v
                options = [range(-2,3) if clustered and supports[i] >= LIMITS['min_cluster_sources'] else (0,) for i in range(1,k)]
                for tail in product(*options):
                    offsets = (0,*tail)
                    if active + sum(v != 0 for v in offsets) <= LIMITS['nonzero_coefficients']:
                        yield weights, list(offsets)


class SemanticOrdinalCalibrator(Calibrator):
    version = VERSION
    def __init__(self, router, *, clustered=False):
        self.router = router; self.clustered = clustered; self._artifact = None

    def fit(self, X, y, *, sample_weight=None, source_groups=None):
        X,y = list(X),list(y)
        if sample_weight is not None or not 6 <= len(X) <= 16 or len(y) != len(X) or source_groups is None or len(source_groups) != len(X) or len(set(source_groups)) != len(X) or any(type(v) is not int or v not in range(3) for v in y) or any(y.count(i) < 2 for i in range(3)):
            raise ValueError('Six to sixteen distinct source cases including all three labels required')
        low, high = _bounds(X)
        clusters = self.router.predict([r['descriptor'] for r in X])
        k = len(self.router.centers); supports = [clusters.count(i) for i in range(k)]
        models = list(coefficients(k, supports, self.clustered))
        cuts = np.asarray(list(combinations(range(1,25),2)), dtype=np.int16)
        targets = np.asarray(y)
        scale = lcm(len(y), 3*lcm(*range(1,len(y)+max(y.count(i) for i in range(3))+1)))
        if scale > np.iinfo(np.int64).max//100: raise ValueError('Exact objective exceeds integer range')
        class_n = [y.count(i) for i in range(3)]
        best = None; best_rank = None; eligible_count = 0
        for start in range(0,len(models),128):
            batch = models[start:start+128]
            w = np.asarray([m[0] for m in batch],dtype=np.int16)
            o = np.asarray([m[1] for m in batch],dtype=np.int16)
            delta = np.asarray([[a[c] if c >= 0 else 0 for c in clusters] for a in o],dtype=np.int16)
            lower = w@low.T + delta; upper = w@high.T + delta
            # Unknown full intervals always straddle No and Yes; extreme complete
            # evidence always maps to the matching extreme in every cluster.
            cut_valid = ((cuts[None,:,0] > np.max(o,axis=1)[:,None]) &
                         (cuts[None,:,1] <= 4*np.sum(w,axis=1)[:,None]+np.min(o,axis=1)[:,None]))
            a = ((lower[:,None,:] >= cuts[None,:,0,None]).astype(np.int8) +
                 (lower[:,None,:] >= cuts[None,:,1,None]).astype(np.int8))
            b = ((upper[:,None,:] >= cuts[None,:,0,None]).astype(np.int8) +
                 (upper[:,None,:] >= cuts[None,:,1,None]).astype(np.int8))
            p = np.where(a==b,a,-1)
            tp = np.stack([np.sum((p==i)&(targets[None,None,:]==i),axis=2) for i in range(3)],axis=2)
            counts = np.stack([np.sum(p==i,axis=2) for i in range(3)],axis=2)
            valid = cut_valid & np.all(tp >= LIMITS['min_class_correct'],axis=2)
            eligible_count += int(valid.sum())
            if not valid.any(): continue
            macro = np.zeros(valid.shape,dtype=np.int64)
            for i,n in enumerate(class_n): macro += 2*tp[:,:,i]*(scale//(3*(n+counts[:,:,i])))
            correct = tp.sum(axis=2); joint = macro+correct*(scale//len(y))
            # Exact lexicographic objective. The enumeration order breaks final ties.
            masks = valid
            worst = np.min(tp*np.asarray([scale//n for n in class_n])[None,None,:],axis=2)
            nonzero = np.count_nonzero(w,axis=1)+np.count_nonzero(o,axis=1)
            mass = np.sum(w,axis=1)+np.sum(np.abs(o),axis=1)
            values = [joint,macro,correct,worst,-nonzero[:,None]+np.zeros(valid.shape,dtype=int),-mass[:,None]+np.zeros(valid.shape,dtype=int)]
            selected = []
            for value in values:
                mx = value[masks].max(); selected.append(int(mx)); masks = masks & (value==mx)
            j,t = np.argwhere(masks)[0]
            rank = tuple(selected)
            if best_rank is None or rank > best_rank:
                best_rank = rank; best = (batch[j][0],batch[j][1],cuts[t].tolist(),p[j,t].tolist())
        if best is None: raise ValueError('No policy learns at least two source cases per class within the shared budget')
        weights,offsets,cutpoints,predictions = best
        metrics,_,_ = classification_metrics(predictions,y)
        self._artifact = {'version':VERSION,'clustered':self.clustered,'router':self.router.metadata(),
                          'quality_names':list(QUALITIES),'limits':deepcopy(LIMITS),'weights':weights,
                          'offsets':offsets,'cutpoints':cutpoints,'cluster_support':supports,
                          'active_coefficients':sum(v!=0 for v in weights+offsets),'shared_cutpoints':2,
                          'objective':'mean(accuracy, macro-F1); then macro-F1, correct, worst recall, simplicity',
                          'training_metrics':metrics,'training_feature_ref':digest(X),'training_target_ref':digest(y),
                          'search':{'coefficient_models':len(models),'cutpoint_pairs':len(cuts),'class_supported_policies':eligible_count},
                          'scope':'Local fit and score; no held-out accuracy or repeat robustness claim.'}
        return self

    def predict_records(self, X):
        X=list(X); low,high=_bounds(X)
        if self._artifact is None: raise ValueError('Fit first')
        a=self._artifact; weights=np.asarray(a['weights']); cuts=np.asarray(a['cutpoints'])
        clusters=self.router.predict([r['descriptor'] for r in X]); result=[]
        for lo,hi,c in zip(low,high,clusters):
            offset=a['offsets'][c] if c>=0 else 0
            scores=[int(lo@weights)+offset,int(hi@weights)+offset]
            labels=[int(np.sum(v>=cuts)) for v in scores]
            result.append({'prediction':labels[0] if labels[0]==labels[1] else -1,
                           'score_interval':scores,'cluster':c,'offset':offset})
        return result

    def predict(self,X):
        return [float('nan') if r['prediction']<0 else float(r['prediction']) for r in self.predict_records(X)]

    def metadata(self): return deepcopy(self._artifact) if self._artifact else {'version':VERSION}

    @classmethod
    def restore(cls, artifact):
        a=deepcopy(artifact)
        if a.get('version')!=VERSION or a.get('quality_names')!=list(QUALITIES) or a.get('limits')!=LIMITS or type(a.get('clustered')) is not bool:
            raise ValueError('Changed ordinal policy contract')
        router=SemanticRouter.restore(a['router']); w=a['weights']; o=a['offsets']; t=a['cutpoints']
        if (len(w)!=8 or any(type(v) is not int or not 0<=v<=3 for v in w) or not 1<=sum(w)<=6 or len(o)!=len(router.centers) or o[0]!=0 or any(type(v) is not int or not -2<=v<=2 for v in o) or sum(v!=0 for v in w+o)>4 or len(t)!=2 or any(type(v) is not int for v in t) or not max(o)<t[0]<t[1]<=4*sum(w)+min(o) or not a['clustered'] and any(o) or len(a['cluster_support'])!=len(o) or any(v and a['cluster_support'][i]<2 for i,v in enumerate(o))):
            raise ValueError('Invalid or unsupported ordinal policy')
        obj=cls(router,clustered=a['clustered']); obj._artifact=a; return obj
