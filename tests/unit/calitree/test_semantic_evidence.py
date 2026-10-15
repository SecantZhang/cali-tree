from copy import deepcopy
import pytest
from critical.core.decision.semantic_evidence import *

def observation():
    return {'contract':{'meaning':'A requested change',**{k:k=='appearance' for k in DESCRIPTORS}},
            'aspects':[{'source_quote':'Change it','kind':'attribute','requirement':'Requested attribute',
                        'observed':'Attribute visible','grade':3,'shortfall':'Small residual'}],
            'qualities':{k:{'applicability':'applicable','grade':3,'evidence':'Visible evidence'} for k in QUALITIES}}

def test_factual_grade_is_not_confidence_and_unknown_is_interval():
    value=observation();value['qualities']['identity']['grade']=None
    r=feature_record(value,'Change it')
    i=QUALITIES.index('identity');assert r['lower'][i]==0 and r['upper'][i]==4
    assert all(r['lower'][j]==3 for j in range(8) if j!=i)

def test_descriptor_excludes_outcome_evidence():
    a=observation();b=deepcopy(a)
    for fact in b['qualities'].values():fact['grade']=0;fact['evidence']='Different outcome'
    assert feature_record(a,'Change it')['descriptor']==feature_record(b,'Change it')['descriptor']

@pytest.mark.parametrize('damage',['label','quote','boolean_grade','na_grade'])
def test_invalid_or_label_bearing_records_rejected(damage):
    value=observation()
    if damage=='label':value['reference']='yes'
    elif damage=='quote':value['aspects'][0]['source_quote']='invented'
    elif damage=='boolean_grade':value['qualities']['endpoint']['grade']=True
    else:value['qualities']['endpoint'].update(applicability='not_applicable',grade=1)
    with pytest.raises(ValueError):validate(value,'Change it')
