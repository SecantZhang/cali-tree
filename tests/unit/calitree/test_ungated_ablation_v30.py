from itertools import permutations

import pytest

from run.calitree_ungated_ablation_v30 import vote,predict_bank


@pytest.mark.parametrize('labels,expected,tied',[
    ([0,0,2,1],0,False),([2,2,0],2,False),([1,1,1],1,False),
    ([0,2],0,True),([0,1],1,True),([1,2],1,True),([0,1,2],1,True),
    ([0,0,2,2],0,True),([1,1,2,2],1,True),
])
def test_fixed_plurality_and_tie_rules(labels,expected,tied):
    for perm in set(permutations(labels)):
        result=vote(perm)
        assert result['prediction']==expected and result['tied']==tied
        assert sum(result['counts'])==len(labels)


@pytest.mark.parametrize('labels',[[],[-1],[0,-1,2],[True,0],[3,1]])
def test_invalid_evidence_or_vote_does_not_fall_back_or_invent_a_verdict(labels):
    assert vote(labels)['prediction']==-1


def test_every_expert_votes_once_without_support_weighting_or_gate_queries():
    class Executor:
        def __init__(self,label):self.label=label;self.calls=0
        def predict_records(self,records):
            self.calls+=1;assert records==['evidence']
            return [{'prediction':self.label,'trace':[]}]
    experts={str(i):Executor(label)for i,label in enumerate([0,0,2])}
    result=predict_bank(experts,'evidence')
    assert result['prediction']==0 and len(result['expert_votes'])==3
    assert all(e.calls==1 for e in experts.values())
