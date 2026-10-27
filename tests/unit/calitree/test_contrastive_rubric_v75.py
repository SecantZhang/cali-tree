from copy import deepcopy

import pytest

from critical.core.optimization.prompt.calitree import contrastive_rubric_v75 as rubric
from critical.core.decision.bound_evidence_v2 import bind_program
from tests.unit.calitree.test_bound_evidence_v2 import draft
from run.calitree_contrastive_pilot_v75 import collect,MAX_CALLS,MAX_OUTPUT


def case(group,label):
    return {'case':group+str(label),'source_group':group,'reference':label,
            'program':bind_program('Change the target color',draft('Change the target color',kind='attribute')),
            'evidence':{'source_image':group+'-source.png','edited_image':group+'-'+str(label)+'.png'},
            'edited_pixel_hash':group+str(label)}


def request():
    pool=[case('A',0),case('A',1),case('B',1),case('B',2)]
    query=case('Q',2)
    return rubric.request(query,rubric.contrasts(pool,query,{'Q'}))


def certificate(payload,label):
    c=next(c for c in payload['query_checks'] if c['role']=='outcome')
    return {'label':label,'rationale':'A decisive visible change.',
            'target_status':'intended_counterpart','endpoint_status':'achieved' if label=='yes' else 'absent',
            'progress_status':'goal_directed' if label in ('yes','partial') else 'none',
            'collateral_status':'none_or_minor','criterion':{'yes':'successful_endpoint','partial':'meaningful_incomplete','no':'failed_target_or_goal'}[label],
            'witnesses':[{'check_id':c['id'],'state':c['expected_state'] if label=='yes' else 'false',
                          'source_observation':'The intended source target.','edited_observation':'Its observed edited counterpart.'}]}


def test_matched_sources_query_exclusion_and_query_reference_blindness():
    pool=[case('A',0),case('A',1),case('B',1),case('B',2),case('Q',0),case('Q',1)]
    query=case('Q',2);chosen=rubric.contrasts(pool,query,{'Q'})
    assert [(a['reference'],b['reference']) for a,b in chosen]==[(0,1),(1,2)]
    assert all(a['source_group']==b['source_group']!='Q' for a,b in chosen)
    original=rubric.request(query,chosen)
    query['reference']=0
    assert rubric.request(query,chosen)==original
    assert sum(m['type']=='image' for m in original['media'])==8


def test_identical_pixels_with_different_labels_cannot_be_a_contrast():
    pool=[case('A',0),case('A',1),case('B',1),case('B',2)]
    pool[1]['edited_pixel_hash']=pool[0]['edited_pixel_hash']
    with pytest.raises(ValueError,match='Insufficient'):
        rubric.contrasts(pool,case('Q',2),{'Q'})


def test_success_and_failure_require_bound_outcome_witnesses():
    payload=request()['payload']
    assert rubric.validate_certificate(payload,certificate(payload,'yes'))['label']=='yes'
    bad=certificate(payload,'no');bad['witnesses'][0]['state']='unknown'
    with pytest.raises(ValueError,match='failed requested'):
        rubric.validate_certificate(payload,bad)
    wrong=certificate(payload,'yes');wrong['witnesses'][0]['check_id']='another-case-check'
    with pytest.raises(ValueError,match='query witness'):
        rubric.validate_certificate(payload,wrong)


def test_no_label_from_uncertainty_and_no_partial_from_incidental_change():
    payload=request()['payload'];bad=certificate(payload,'no')
    bad['endpoint_status']='uncertain';bad['progress_status']='uncertain'
    with pytest.raises(ValueError,match='affirmative'):
        rubric.validate_certificate(payload,bad)
    bad=certificate(payload,'partial');bad['progress_status']='incidental_only'
    with pytest.raises(ValueError,match='meaningful fulfillment'):
        rubric.validate_certificate(payload,bad)


def test_success_needs_full_target_correspondence_and_partial_needs_the_right_goal():
    payload=request()['payload'];bad=certificate(payload,'yes');bad['target_status']='partly_corresponding'
    with pytest.raises(ValueError,match='identity'):
        rubric.validate_certificate(payload,bad)
    bad=certificate(payload,'partial');bad['target_status']='wrong_or_missing'
    with pytest.raises(ValueError,match='wrong target'):
        rubric.validate_certificate(payload,bad)


def test_paid_run_requires_authorization_before_credentials_or_files(tmp_path):
    with pytest.raises(ValueError,match='authorization'):
        collect(tmp_path)
    assert not list(tmp_path.iterdir())
    assert MAX_CALLS==72 and MAX_OUTPUT==344064
