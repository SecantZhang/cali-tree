from copy import deepcopy

import pytest

from critical.core.decision import nli_rubric_v81 as nli
from critical.core.decision.bound_evidence_v2 import bind_program
from tests.unit.calitree.test_bound_evidence_v2 import draft,observation


def test_nli_premises_exclude_observer_answer_states_and_explicit_grade_prefix():
    p=bind_program('Move the bowl left',draft());o=observation(p)
    judgment={'label':'No','rationale':'No: The bowl has not moved.'}
    rows=nli.plans(p,o,'pair',judgment)
    assert len(rows)==2*len(nli.HYPOTHESES)
    assert 'No:' not in rows[0]['premise'] and 'not moved' in rows[0]['premise']
    changed=deepcopy(o)
    for v in changed['checks'].values():v['state']='false' if v['state']=='true' else 'true'
    assert nli.plans(p,changed,'pair',judgment)==rows
    assert nli.plans(p,None,None,None)==[]
    with pytest.raises(ValueError):nli.plans(p,o,'other',judgment)


def test_concepts_are_closed_normalized_language_opinions():
    r={'context':'regular','concept':'complete_endpoint','support':[.1,.7,.2]}
    flags=nli.features([r]);assert flags['nli_regular_complete_endpoint_entailment']==.7
    assert flags['nli_observation_complete_endpoint_entailment'] is None
    assert 'not image-truth' in nli.DESCRIPTIONS['nli_regular_complete_endpoint_entailment']
    for bad in ([0.,0.,0.],[float('nan'),.5,.5],[-.1,.7,.4],[0.,1.]):
        with pytest.raises(ValueError,match='supports'):nli.features([{**r,'support':bad}])
    with pytest.raises(ValueError,match='Duplicate'):nli.features([r,r])
