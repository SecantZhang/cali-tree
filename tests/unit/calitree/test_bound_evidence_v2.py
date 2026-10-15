from copy import deepcopy
from itertools import product

import pytest

from critical.core.decision.bound_evidence import EvidenceContractError
from critical.core.decision.bound_evidence_v2 import (
    bind_program, derive_record, diagnostic_readout, validate_program, validate_observation,
)
from tests.unit.calitree.test_bound_evidence import draft as v1_draft, observation


def draft(instruction='Move the bowl left', kind='spatial_relation', intermediate=False):
    d = v1_draft(instruction, kind=kind, intermediate=intermediate)
    for r in d['requirements']:
        r.pop('check_ids')
    for c in d['checks']:
        c['absence_when'] = 'true' if c['kind'] == 'absence' else 'never'
        c['absence_source_anchor'] = 'required'
    return d


def score(p, v):
    return diagnostic_readout(derive_record(p, v, 'pair'))


def test_negative_polarity_removal_has_the_same_absence_safeguard():
    instruction = 'Remove the cylinder'
    d = draft(instruction, kind='absence')
    d['checks'][0].update(question='Does any part of the original cylinder remain?', expected_state='false', absence_when='false')
    p = bind_program(instruction, d); v = observation(p)
    assert score(p, v)['label'] == 'Yes'
    for k, value in [('source_anchor', 'ambiguous'), ('edited_coverage', 'occluded')]:
        invalid = deepcopy(v); invalid['checks']['endpoint'][k] = value
        r = derive_record(p, invalid, 'pair')
        assert r['checks']['endpoint']['state'] == 'unknown'
        assert diagnostic_readout(r)['label'] == 'Unresolved'


def test_nonappearance_of_new_entity_does_not_require_nonexistent_source_identity():
    instruction = 'Add a frog'
    d = draft(instruction, kind='presence')
    d['checks'][0].update(question='Is a frog visible in the edited scene?', absence_when='false', absence_source_anchor='not_required')
    p = bind_program(instruction, d); v = observation(p, endpoint='false')
    v['checks']['endpoint']['source_anchor'] = 'not_needed'
    assert score(p, v)['label'] == 'No'
    v['checks']['endpoint']['edited_coverage'] = 'cropped'
    assert score(p, v)['label'] == 'Unresolved'


def test_preserved_layout_never_supplies_requested_progress():
    instruction = 'Render the scene with crayons'
    d = draft(instruction, kind='style', intermediate=True)
    c = deepcopy(d['checks'][0]); c.update(id='layout', role='preservation', kind='spatial_relation', question='Is the original layout retained?')
    d['checks'].append(c)
    p = bind_program(instruction, d); v = observation(p, endpoint='false', intermediate='false', layout='true')
    r = derive_record(p, v, 'pair')
    assert r['features']['any_required_witness'] == 'false'
    assert diagnostic_readout(r)['label'] == 'No'
    assert 'layout' in p['requirements'][0]['check_ids']


def test_preservation_only_requirement_is_not_a_requested_outcome():
    d = draft(); d['requirements'].append({'id': 'preserve', 'source_quote': 'Move the bowl left', 'description': 'Keep scene unchanged'})
    c = deepcopy(d['checks'][0]); c.update(id='layout', role='preservation', requirement_ids=['preserve'])
    d['checks'].append(c)
    with pytest.raises(EvidenceContractError, match='vacuous_requirement'):
        bind_program('Move the bowl left', d)


@pytest.mark.parametrize('kind', ['pose', 'grasp', 'material_transfer', 'closure', 'style', 'separation'])
def test_temporal_or_style_endpoint_requires_a_linked_intermediate(kind):
    with pytest.raises(EvidenceContractError, match='missing_linked_intermediate'):
        bind_program('Move the bowl left', draft(kind=kind))
    assert bind_program('Move the bowl left', draft(kind=kind, intermediate=True))


def test_pose_geometry_remains_available_when_identity_is_unknown():
    instruction = 'Make the man partially stand up'
    d = draft(instruction, kind='pose', intermediate=True)
    identity = deepcopy(d['checks'][0]); identity.update(id='identity', role='identity', kind='identity', question='Is original-instance correspondence established?')
    d['checks'].append(identity)
    p = bind_program(instruction, d)
    v = observation(p, endpoint='unknown', intermediate='true', identity='unknown')
    r = derive_record(p, v, 'pair')
    assert r['features']['linked_intermediate_witness'] == 'true'
    assert diagnostic_readout(r)['label'] == 'Unresolved'
    d['checks'][3]['dependencies'] = ['identity']
    with pytest.raises(EvidenceContractError, match='intermediate_identity_gate'):
        bind_program(instruction, d)


def test_absence_polarity_and_required_links_are_hashed():
    p = bind_program('Move the bowl left', draft())
    for mutation in ('absence_when', 'check_ids'):
        q = deepcopy(p)
        if mutation == 'absence_when':
            q['checks'][0]['absence_when'] = 'false'
        else:
            q['requirements'][0]['check_ids'].append('missing')
        with pytest.raises(EvidenceContractError, match='program_hash_mismatch'):
            validate_program(q)


def test_wrong_question_or_image_pair_cannot_be_consumed():
    p = bind_program('Move the bowl left', draft()); v = observation(p)
    q = deepcopy(v); q['checks']['endpoint']['question'] = 'Is a hand visible?'
    with pytest.raises(EvidenceContractError, match='check_binding_mismatch'):
        validate_observation(p, q, 'pair')
    with pytest.raises(EvidenceContractError, match='observation_binding_mismatch'):
        validate_observation(p, v, 'swapped')


def test_required_preservation_unknown_cannot_vacuously_pass():
    d = draft(); c = deepcopy(d['checks'][0]); c.update(id='layout', role='preservation', question='Is the unrelated scene configuration retained?')
    d['checks'].append(c); p = bind_program('Move the bowl left', d)
    v = observation(p, layout='not_applicable'); v['checks']['layout']['applicability'] = 'not_applicable'
    assert score(p, v)['label'] == 'Unresolved'


def test_tri_state_bounds_with_preservation_match_all_completions():
    d = draft(); c = deepcopy(d['checks'][0]); c.update(id='layout', role='preservation')
    d['checks'].append(c); p = bind_program('Move the bowl left', d)
    keys = [c['id'] for c in p['checks']]
    for states in product(('true', 'false', 'unknown'), repeat=len(keys)):
        v = observation(p, **dict(zip(keys, states)))
        unknowns = [k for k in keys if v['checks'][k]['state'] == 'unknown']; possible = set()
        for assignment in product(('true', 'false'), repeat=len(unknowns)):
            known = deepcopy(v)
            for k, s in zip(unknowns, assignment):
                known['checks'][k]['state'] = s
            possible.add(score(p, known)['prediction'])
        assert score(p, v)['prediction'] == (next(iter(possible)) if len(possible) == 1 else -1)
