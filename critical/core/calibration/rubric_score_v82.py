"""Small additive semantic corrections to a frozen teacher's class scores.

Coefficients concern observed semantic/model claims, not certified image facts.
The teacher offset stays explicit; this is not a claim to distill it away.
"""
import numpy as np
from scipy.optimize import minimize
from scipy.special import softmax,logsumexp


def log_support(support):
    p=np.asarray(support,dtype=float)
    if p.ndim!=2 or p.shape[1]!=3 or not np.all(np.isfinite(p)) or np.any(p<0) or not np.allclose(p.sum(axis=1),1,atol=1e-5):raise ValueError('Normalized finite teacher supports required')
    return np.log(np.clip(p,1e-9,1.))


class RubricScore:
    version='additive-semantic-score-correction-v82'

    def __init__(self,names,*,regularization=1.,max_features=24):
        if not names or len(set(names))!=len(names) or regularization<=0 or max_features<1:raise ValueError('Named bounded rubric required')
        self.names=list(names);self.regularization=regularization;self.max_features=max_features

    def fit(self,X,y,*,support,groups,protected_X,protected_y,protected_support):
        a=np.asarray(X,dtype=float);y=np.asarray(y,dtype=int);offset=log_support(support)
        if a.ndim!=2 or a.shape[1]!=len(self.names) or len(a)!=len(y) or len(groups)!=len(y) or not np.all(np.isin(y,[0,1,2])):raise ValueError('Aligned semantic fitting rows required')
        # Undefined measurements have a distinct availability feature in the
        # caller. Imputation/normalization and residual ranking use fit only.
        finite=np.isfinite(a);count=finite.sum(axis=0)
        self.means=np.divide(np.where(finite,a,0).sum(axis=0),count,out=np.zeros(a.shape[1]),where=count>0)
        filled=np.where(finite,a,self.means);self.scales=np.std(filled,axis=0);self.scales[self.scales<1e-6]=1.
        Z=np.clip((filled-self.means)/self.scales,-5.,5.)
        unique,counts=np.unique(groups,return_counts=True);sizes=dict(zip(unique,counts));weights=np.asarray([1./sizes[g] for g in groups]);weights/=weights.sum()
        target=np.eye(3)[y];residual=target-np.exp(offset)
        correlations=Z.T@(weights[:,None]*residual)
        order=sorted(range(Z.shape[1]),key=lambda i:(-float(np.linalg.norm(correlations[i])),self.names[i]))
        self.columns=[i for i in order[:self.max_features] if np.std(Z[:,i])>1e-6]
        D=np.concatenate([np.ones((len(Z),1)),Z[:,self.columns]],axis=1);width=D.shape[1]
        def objective(flat):
            W=flat[:width*3].reshape(width,3);temperature=flat[-1]
            logits=temperature*offset+D@W;p=softmax(logits,axis=1)
            value=float(np.sum(weights*(logsumexp(logits,axis=1)-logits[np.arange(len(y)),y]))+.5*self.regularization*np.sum(W[1:]**2)+.01*np.sum(W[0]**2)+.01*(temperature-1)**2)
            error=weights[:,None]*(p-target);gradient=D.T@error;gradient[1:]+=self.regularization*W[1:];gradient[0]+=.02*W[0]
            dt=float(np.sum(error*offset)+.02*(temperature-1))
            return value,np.r_[gradient.reshape(-1),dt]
        initial=np.r_[np.zeros(width*3),1.]
        solved=minimize(objective,initial,jac=True,method='L-BFGS-B',bounds=[(None,None)]*(width*3)+[(.05,3.)],options={'maxiter':300,'ftol':1e-10})
        self.coefficients=solved.x[:width*3].reshape(width,3);self.temperature=float(solved.x[-1]);self.strength=0.
        py=np.asarray(protected_y);pbase=log_support(protected_support);P=self._design(protected_X)
        if np.asarray(P).shape[0]!=len(py):raise ValueError('Protected predictions must align')
        # Choose by fitting OOF accuracy only, after a hard veto on actual
        # original-case inference. Strength0 is the exact teacher fallback.
        trials=[]
        for strength in (0.,.25,.5,.75,1.):
            fitted=offset+strength*((self.temperature-1)*offset+D@self.coefficients)
            actual=pbase+strength*((self.temperature-1)*pbase+P@self.coefficients)
            retained=bool(np.all(np.argmax(actual,axis=1)==py))
            correct=float(np.sum(weights*(np.argmax(fitted,axis=1)==y)))
            loss=float(np.sum(weights*(logsumexp(fitted,axis=1)-fitted[np.arange(len(y)),y])))
            trials.append({'strength':strength,'source_weighted_accuracy':correct,'loss':loss,'retained':retained})
        passing=[r for r in trials if r['retained']]
        if not passing:raise ValueError('The teacher itself fails protected retention')
        chosen=min(passing,key=lambda r:(-r['source_weighted_accuracy'],r['loss'],r['strength']))
        self.strength=chosen['strength'];self.stats={'converged':bool(solved.success),'iterations':int(solved.nit),'strength_trials':trials,'features':len(self.columns)}
        return self

    def _design(self,X):
        a=np.asarray(X,dtype=float)
        if a.ndim!=2 or a.shape[1]!=len(self.names):raise ValueError('Aligned named semantic features required')
        Z=np.clip((np.where(np.isfinite(a),a,self.means)-self.means)/self.scales,-5.,5.)
        return np.concatenate([np.ones((len(Z),1)),Z[:,self.columns]],axis=1)

    def predict_proba(self,X,*,support):
        scores=log_support(support);D=self._design(X)
        if len(D)!=len(scores):raise ValueError('Aligned current teacher supports required')
        return softmax(scores+self.strength*((self.temperature-1)*scores+D@self.coefficients),axis=1)

    def artifact(self,descriptions):
        terms=[]
        for row,col in enumerate(self.columns,1):terms.append({'feature':self.names[col],'description':descriptions[self.names[col]],'mean':float(self.means[col]),'scale':float(self.scales[col]),'coefficients_no_partial_yes':self.coefficients[row].tolist()})
        return {'version':self.version,'regularization':self.regularization,'max_features':self.max_features,'strength':self.strength,'temperature':self.temperature,
            'intercept_no_partial_yes':self.coefficients[0].tolist(),'terms':terms,'training':self.stats,
            'equation':'log(teacher support) + strength * ((temperature-1)*log(teacher support) + intercept + sum(coefficient*clip((feature-mean)/scale,-5,5))). Choose largest of No/Partial/Yes.',
            'limit':'Explicit additive semantic correction with a boosted offset; not a standalone rubric distillation or factual confidence.'}
