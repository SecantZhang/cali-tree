from copy import deepcopy
import pytest
from critical.core.decision.observable_facts import PREDICATES,validate,fact_record


def observation():
    return {'facts':{k:{'state':'not_applicable','bound_question':question,'evidence':'Operation not requested'} for k,question in PREDICATES.items()}}


def test_factual_interface_has_no_ordinal_quality_or_verdict():
    value=observation();r=fact_record(value)
    assert set(r)=={'facts'} and set(r['facts'])==set(PREDICATES)
    assert not {'progress','scope','quality','identity','preservation','label','grade'}&set(r['facts'])
    original=deepcopy(value);fact_record(value);assert value==original


@pytest.mark.parametrize('damage',['grade','label','extra_predicate','missing_fact','numeric_state'])
def test_reject_quality_or_lookup_fields(damage):
    x=observation()
    if damage=='grade':x['facts']['target_result_visible']['grade']=4
    elif damage=='label':x['label']='yes'
    elif damage=='extra_predicate':x['facts']['case_id']={}
    elif damage=='missing_fact':del x['facts']['target_result_visible']
    else:x['facts']['target_result_visible']['state']=1
    with pytest.raises(ValueError):validate(x)
