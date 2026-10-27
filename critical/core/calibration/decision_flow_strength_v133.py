"""Select semantic correction strength after the actual decision guard.

Unknown target identity alone never supplies failure. The optional absence
warrant separately requires explicit negative endpoint and progress claims.
"""
import numpy as np

from .semantic_residual_runtime_v104 import admissible
from .rubric_score_v82 import log_support

GRID=(0.,.25,.5,.75,1.,1.25,1.5,1.75,2.)
MODES=('score','strict','absence')


def absence_witness(flags):
    return (flags['local_single_requirement'] and not flags['local_claim_conflict'] and
            (flags['local_endpoint_absent'] or flags['local_endpoint_opposite']) and
            (flags['local_progress_none'] or flags['local_progress_incidental_only']))


def flow(support,delta,strength,flags,regular,mode):
    if mode not in MODES or strength not in GRID:raise ValueError('Frozen flow mode/strength required')
    p=np.asarray(support,dtype=float);log_support(p);d=np.asarray(delta,dtype=float);r=np.asarray(regular,dtype=int)
    if d.shape!=p.shape or len(flags)!=len(p) or r.shape!=(len(p),) or not np.isfinite(d).all():raise ValueError('Aligned finite semantic scores required')
    masses=np.maximum(p+strength*d,1e-9);masses/=masses.sum(axis=1,keepdims=True)
    teacher=np.argmax(p,axis=1);proposed=np.argmax(masses,axis=1);changed=np.zeros(len(p),dtype=bool)
    for i in range(len(p)):
        if proposed[i]==teacher[i]:continue
        allowed=(mode=='score' or admissible(flags[i],int(teacher[i]),int(r[i]),int(proposed[i])) or
                 (mode=='absence' and proposed[i]==0 and absence_witness(flags[i])))
        changed[i]=bool(allowed)
    used=np.where(changed[:,None],masses,p)
    return np.argmax(used,axis=1),used,changed


def select(support,delta,y,groups,flags,regular,protected_support,protected_delta,protected_y,protected_flags,protected_regular,mode):
    y=np.asarray(y,dtype=int);py=np.asarray(protected_y,dtype=int)
    unique,counts=np.unique(groups,return_counts=True);sizes=dict(zip(unique,counts));weights=np.asarray([1./sizes[g] for g in groups]);weights/=weights.sum()
    trials=[]
    for strength in GRID:
        pred,p,_=flow(support,delta,strength,flags,regular,mode);protected,_,_=flow(protected_support,protected_delta,strength,protected_flags,protected_regular,mode)
        trials.append({'strength':strength,'retained':bool(np.all(protected==py)),'source_weighted_accuracy':float(weights@(pred==y)),
            'squared_error':float(weights@np.sum((p-np.eye(3)[y])**2,axis=1))})
    passing=[t for t in trials if t['retained']]
    if not passing:raise ValueError('Even the original protected decisions fail')
    chosen=min(passing,key=lambda t:(-t['source_weighted_accuracy'],t['squared_error'],t['strength']))
    return chosen['strength'],trials
