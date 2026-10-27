"""Exact named univariate/pairwise score tables from an interpretable booster."""
from copy import deepcopy

import numpy as np
from scipy.special import softmax

from ..decision.artifacts import digest

VERSION='additive-semantic-tables-v140'


def content_ref(artifact):return digest({k:v for k,v in artifact.items() if k!='artifact_ref'})


def export(model,names,descriptions):
    if model.classes_.tolist()!=[0,1,2] or model.link_!='mlogit':raise ValueError('Three-class additive logit model required')
    terms=[]
    for features,scores in zip(model.term_features_,model.term_scores_):
        cuts=[model.bins_[j][min(len(features)-1,len(model.bins_[j])-1)].tolist() for j in features]
        terms.append({'features':[names[j] for j in features],'cuts':cuts,'scores':scores.tolist()})
    artifact={'version':VERSION,'feature_names':list(names),'feature_descriptions':{n:descriptions[n] for n in names},
        'intercept':model.intercept_.tolist(),'terms':terms,'equation':'Add the intercept and every matching per-feature/pair table cell; softmax the three scores; choose largest No/Partial/Yes, ties in that order.',
        'limit':'Statistical prediction of human grades from named semantic/model scores, not a physical certificate or calibrated correctness probability.'}
    artifact['artifact_ref']=content_ref(artifact);AdditiveTables(artifact)
    return artifact


class AdditiveTables:
    def __init__(self,artifact):
        if artifact.get('version')!=VERSION or artifact.get('artifact_ref')!=content_ref(artifact):raise ValueError('Changed additive table artifact')
        names=artifact['feature_names']
        if not 1<=len(names)<=256 or len(set(names))!=len(names) or set(names)!=set(artifact['feature_descriptions']):raise ValueError('Closed named vocabulary required')
        if len(artifact['intercept'])!=3 or not np.isfinite(artifact['intercept']).all() or not 1<=len(artifact['terms'])<=512:raise ValueError('Finite bounded three-class score tables required')
        for term in artifact['terms']:
            features=term['features'];cuts=term['cuts']
            if (set(term)!={'features','cuts','scores'} or not 1<=len(features)<=2 or len(set(features))!=len(features) or
                    not set(features)<=set(names) or len(cuts)!=len(features)):raise ValueError('Named univariate/pair term required')
            for boundaries in cuts:
                if len(boundaries)>64 or not np.isfinite(boundaries).all() or any(a>=b for a,b in zip(boundaries,boundaries[1:])):raise ValueError('Finite increasing cut points required')
            scores=np.asarray(term['scores'],dtype=float)
            if scores.shape!=tuple(len(c)+3 for c in cuts)+(3,) or not np.isfinite(scores).all():raise ValueError('Table dimensions/values differ from cut points')
        self.artifact=deepcopy(artifact)

    def predict_proba(self,X):
        a=np.asarray(X,dtype=float);names=self.artifact['feature_names']
        if a.ndim!=2 or a.shape[1]!=len(names) or np.isinf(a).any():raise ValueError('Aligned finite-or-missing numeric inputs required')
        result=np.tile(self.artifact['intercept'],(len(a),1)).astype(float)
        for term in self.artifact['terms']:
            indices=[]
            for feature,cuts in zip(term['features'],term['cuts']):
                x=a[:,names.index(feature)];indices.append(np.where(np.isnan(x),0,np.searchsorted(cuts,x,side='right')+1))
            result+=np.asarray(term['scores'])[tuple(indices)]
        return softmax(result,axis=1)
