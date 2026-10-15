from copy import deepcopy
import json
import pytest
from critical.core.calibration.factual_rules import FactualRuleCalibrator,test_value as evaluate_fact,labels
from critical.core.decision.observable_facts import PREDICATES


def row(**facts):return {'facts':{k:facts.get(k,'not_applicable') for k in PREDICATES}}


def train():
    x=[row(target_result_visible='false'),row(target_result_visible='false'),
       row(target_result_visible='true',original_instance_at_source='true'),row(target_result_visible='true',original_instance_at_source='true'),
       row(target_result_visible='true',original_instance_at_source='false'),row(target_result_visible='true',original_instance_at_source='false')]
    y=[0,0,1,1,2,2]
    return FactualRuleCalibrator(('scope','identity')).fit(x,y,source_groups=list('abcdef')),x,y


def test_factual_tree_learns_relocation_interaction_and_serializes():
    model,x,y=train();assert [r['prediction'] for r in model.predict_records(x)]==y
    a=model.metadata();assert min(a['leaf_support'].values())>=2
    assert FactualRuleCalibrator.restore(json.loads(json.dumps(a))).predict_records(x)==model.predict_records(x)
    assert 'source location' in model.render() or 'original instance' in model.render()
    assert not {'progress','scope','grade','score','cutpoint'}&set(a['predicate_bank'])


def test_unknown_is_not_false_and_na_is_neither_affirmative_nor_contrary():
    model,x,_=train();x[2]['facts']['original_instance_at_source']='unknown'
    assert model.predict_records([x[2]])[0]['prediction']==-1
    assert model.predict_records([None])[0]['prediction']==-1
    value=row();p={'fact':'original_instance_at_source','test':'false'}
    assert evaluate_fact(value,p) is False
    value['facts']['original_instance_at_source']='unknown';assert evaluate_fact(value,p) is None


def test_no_lookup_or_ordinal_facts_accepted():
    model,x,_=train();x[0]['case_id']='memo'
    with pytest.raises(ValueError):model.predict_records(x)
    bad=deepcopy(model.metadata());bad['tree']['predicate']['fact']='progress'
    with pytest.raises(ValueError):FactualRuleCalibrator.restore(bad)


def test_unknown_branches_can_resolve_when_both_have_same_label():
    t={'predicate':{'fact':'original_instance_at_source','test':'true'},'yes':{'label':1},'no':{'label':1}}
    assert labels(t,row(original_instance_at_source='unknown'))=={1}
