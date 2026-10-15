"""Independent small-space enumeration checks the vectorized policy objective."""
from fractions import Fraction
from itertools import combinations
import pytest

from critical.core.calibration import semantic_calibration as base
from critical.core.calibration import visibility_calibration as visible
from critical.core.decision.semantic_evidence import DESCRIPTORS


def rank(p,y,w,o,g):
    support=[y.count(i) for i in range(3)]
    tp=[sum(a==b==i for a,b in zip(p,y)) for i in range(3)]
    if min(tp)<2:return None
    f1=sum((Fraction(2*t,n+p.count(i)) for i,(t,n) in enumerate(zip(tp,support))),Fraction())/3
    accuracy=Fraction(sum(tp),len(y));recall=min(Fraction(t,n) for t,n in zip(tp,support))
    return (accuracy+f1,f1,sum(tp),recall,-sum(v!=0 for v in w+o)-(g is not None),-sum(w)-sum(abs(v) for v in o))


@pytest.mark.parametrize('module,kind',[(base,base.SemanticOrdinalCalibrator),(visible,visible.VisibilityOrdinalCalibrator)])
def test_vectorized_search_matches_independent_fraction_enumeration(monkeypatch,module,kind):
    d=[1]+[0]*(len(DESCRIPTORS)-1);y=[0]*4+[1]*4+[2]*4
    values=[0,1,2,3,1,2,3,4,2,3,4,4]
    x=[{'lower':[v]*8,'upper':[v]*8,'descriptor':d} for v in values]
    for r in x[2:4]:r['lower'][0:2]=[0,0];r['upper'][0:2]=[4,4]
    weights=[[1]+[0]*7,[0,0,1]+[0]*5,[1,0,1]+[0]*5]
    monkeypatch.setattr(module,'coefficients',lambda k,support,clustered:iter((w,[0]) for w in weights))
    router=base.SemanticRouter().fit([d]*12)
    fitted=kind(router).fit(x,y,source_groups=[str(i) for i in range(12)])
    choices=[]
    for w in weights:
        for g in ([None,0] if module is visible else [None]):
            for a,b in combinations(range(1,25),2):
                if not 0<a<b<=4*sum(w):continue
                p=[]
                for r in x:
                    lo=sum(q*z for q,z in zip(w,r['lower']));hi=sum(q*z for q,z in zip(w,r['upper']))
                    left=int(lo>=a)+int(lo>=b);right=int(hi>=a)+int(hi>=b)
                    value=left if left==right else -1
                    if g is not None and all(r['lower'][i]==0 and r['upper'][i]==4 for i in (0,1)):value=g
                    p.append(value)
                candidate=rank(p,y,w,[0],g)
                if candidate is not None:choices.append(candidate)
    a=fitted.metadata();p=[r['prediction'] for r in fitted.predict_records(x)]
    assert rank(p,y,a['weights'],a['offsets'],a.get('uninspectable_label'))==max(choices)
