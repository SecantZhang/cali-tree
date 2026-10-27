from copy import deepcopy

import numpy as np
import pytest

from critical.vision import caption_audit_v79 as audit
from critical.core.decision.bound_evidence_v2 import bind_program
from tests.unit.calitree.test_bound_evidence_v2 import draft,observation


def test_caption_audit_uses_raw_visible_descriptions_and_no_judgment_states():
    p=bind_program('Make the book blue',draft('Make the book blue',kind='attribute'))
    o=observation(p);rows=audit.plan(p,o,'pair')
    assert rows and all(set(r)=={'check_id','check_ref','role','expected_state','goal','source_description','edited_description'} for r in rows)
    changed=deepcopy(o)
    for v in changed['checks'].values():v['state']='false' if v['state']=='true' else 'true'
    assert audit.plan(p,changed,'pair')==rows
    assert audit.plan(p,None,None)==[]
    with pytest.raises(ValueError):audit.plan(p,o,'different-image-pair')


def test_question_redescription_never_inserts_an_answer():
    assert audit.goal_caption('Is a supernova visible in the edited scene?')=='An image showing a supernova visible.'
    assert 'not' in audit.goal_caption('Is the hand not holding the pot?')
    assert 'blue' in audit.goal_caption('Does the cylinder have a blue surface?')


def test_matching_descriptions_and_image_change_align_but_reversed_claims_do_not():
    source=np.tile(np.eye(1,768,0),(14,1));edited=np.tile(np.eye(1,768,1),(14,1))
    texts={'goal':edited[0],'before':source[0],'after':edited[0]}
    rows=[{'role':'outcome','goal':'goal','source_description':'before','edited_description':'after','check_id':'c1','check_ref':'bound'}]
    scores,trace=audit.measure(source,edited,rows,texts.__getitem__)
    assert scores['caption_outcome_description_change_alignment_min']==pytest.approx(1.)
    assert scores['caption_outcome_goal_delta_min']==pytest.approx(1.)
    assert scores['caption_identity_goal_delta_min'] is None
    rows[0].update(source_description='after',edited_description='before')
    scores,_=audit.measure(source,edited,rows,texts.__getitem__)
    assert scores['caption_outcome_description_change_alignment_min']==pytest.approx(-1.)


def test_identical_images_do_not_produce_spurious_change_alignment():
    source=np.tile(np.eye(1,768,0),(14,1));texts={'goal':source[0],'before':source[0],'after':np.eye(1,768,1)[0]}
    rows=[{'role':'outcome','goal':'goal','source_description':'before','edited_description':'after','check_id':'c1','check_ref':'bound'}]
    scores,_=audit.measure(source,source,rows,texts.__getitem__)
    assert scores['caption_outcome_description_change_alignment_min']==0.
    with pytest.raises(ValueError,match='14-view'):audit.measure(source[:2],source,[],texts.__getitem__)
