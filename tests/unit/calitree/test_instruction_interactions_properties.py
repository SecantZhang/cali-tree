from copy import deepcopy
from fractions import Fraction
from itertools import product

from critical.core.calibration.instruction_rules import InstructionRuleCalibrator,candidates,DEFAULT
from tests.unit.calitree.test_instruction_rules import record


def test_every_candidate_forbids_compensation_for_every_active_material_shortfall():
    for thresholds in candidates():
        for shortfall in ('endpoint','identity','relation','attribute','scope','quantity','preservation'):
            x=record(**{shortfall:2})
            x['contract'].update(identity_required=True,relation_required=True,quantity_required=True)
            p=InstructionRuleCalibrator(thresholds).predict_records([x])[0]
            assert p['prediction']!=2
            assert any(b['check']==shortfall for b in p['blocking_yes'])


def test_joint_fit_objective_matches_independent_exact_candidate_enumeration():
    x=[record(progress=v,endpoint=e) for v,e in [(0,0),(1,1),(2,1),(2,2),(3,3),(4,4),(2,4),(3,4),(4,3)]]
    y=[0,0,1,1,2,2,0,1,2]
    fit=InstructionRuleCalibrator().fit(x,y,source_groups=list(range(9)))
    def rank(p):
        tp=[sum(a==b==i for a,b in zip(p,y)) for i in range(3)]
        if min(tp)<2:return None
        macro=sum((Fraction(2*t,y.count(i)+p.count(i)) for i,t in enumerate(tp)),Fraction())/3
        return (Fraction(sum(tp),len(y))+macro,macro,min(Fraction(t,y.count(i)) for i,t in enumerate(tp)),sum(tp))
    ranks=[rank([r['prediction'] for r in InstructionRuleCalibrator(t).predict_records(x)]) for t in candidates()]
    assert rank([r['prediction'] for r in fit.predict_records(x)])==max(r for r in ranks if r is not None)


def test_core_interactions_are_monotone_over_joint_quality_changes():
    policy=InstructionRuleCalibrator();points={}
    for values in product(range(5),repeat=4):
        x=record(**dict(zip(('progress','endpoint','identity','preservation'),values)))
        x['contract']['identity_required']=True
        points[values]=policy.predict_records([x])[0]['prediction']
    for values,p in points.items():
        for j,v in enumerate(values):
            if v<4:
                next_values=list(values);next_values[j]+=1
                assert points[tuple(next_values)]>=p


def test_only_training_cases_select_policy_and_test_predictions_leave_it_frozen():
    train=[record(progress=0),record(progress=0),record(endpoint=1),record(endpoint=1),record(),record()]
    fit=InstructionRuleCalibrator().fit(train,[0,0,1,1,2,2],source_groups=list('abcdef'))
    frozen=deepcopy(fit.metadata())
    test=[record(identity=1),record(endpoint=None),None]
    test[0]['contract']['identity_required']=True
    assert [r['prediction'] for r in fit.predict_records(test)]==[1,-1,-1]
    assert fit.metadata()==frozen
