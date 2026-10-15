from copy import deepcopy
from itertools import product

from PIL import Image
import pytest

from critical.core.decision.bound_evidence import (
    BoundInstructionCompiler, BoundVisualObserver, EvidenceContractError,
    bind_program, derive_record, diagnostic_readout, image_identity,
    observation_schema, tri_all, tri_any, validate_observation, validate_program,
)


def draft(instruction='Move the bowl left', *, kind='spatial_relation', intermediate=False):
    def check(i, role, kind, question, expected='true'):
        return {'id': i, 'requirement_ids': ['r1'], 'role': role, 'kind': kind,
                'question': question, 'source_quote': instruction, 'target': 'the intended target',
                'reference': 'the original scene', 'applicability_condition': 'The target is inspectable.',
                'expected_state': expected, 'dependencies': []}
    checks = [check('endpoint', 'outcome', kind, 'Is the specified physical endpoint established?'),
              check('missing', 'collateral_disappearance', 'absence', 'Did an unrelated source entity disappear?', 'false'),
              check('deformed', 'collateral_deformation', 'other_physical', 'Was an unrelated entity structurally changed?', 'false')]
    if intermediate:
        checks.append(check('intermediate', 'intermediate', 'pose', 'Is the torso higher with bent knees than in the source?'))
    return {'contract': {'authorized_changes': ['The requested physical transformation'], 'preservation_scope': 'Unrelated entities'},
            'requirements': [{'id': 'r1', 'source_quote': instruction, 'description': 'The requested endpoint', 'check_ids': ['endpoint']}],
            'checks': checks}


def observation(program, **states):
    return {'program_ref': program['program_ref'], 'image_pair_ref': 'pair', 'checks': {
        c['id']: {'check_ref': c['check_ref'], 'question': c['question'],
                  'state': states.get(c['id'], c['expected_state']), 'applicability': 'applicable',
                  'source_anchor': 'identified', 'edited_coverage': 'adequate',
                  'source_evidence': 'The target is identifiable in the source.',
                  'edited_evidence': 'The relevant edited region is visible.',
                  'comparison': 'Concrete physical comparison.'}
        for c in program['checks']}}


def score(program, value):
    return diagnostic_readout(derive_record(program, value, value['image_pair_ref']))


def test_stable_program_and_full_semantic_hash_coverage():
    instruction = 'Move the bowl left'
    original = draft(instruction)
    p = bind_program(instruction, original)
    assert p == bind_program(instruction, deepcopy(original))
    assert validate_program(p) == p
    for key, value in [('question', 'Is powder falling?'), ('target', 'another target'),
                       ('reference', 'another reference'), ('applicability_condition', 'Only if visible.')]:
        altered = deepcopy(p); altered['checks'][0][key] = value
        with pytest.raises(EvidenceContractError, match='program_hash_mismatch'):
            validate_program(altered)
    altered = deepcopy(p); altered['contract']['authorized_changes'].append('A newly permitted change')
    with pytest.raises(EvidenceContractError, match='program_hash_mismatch'):
        validate_program(altered)


def test_hand_visibility_cannot_be_attached_as_powder_release_question():
    instruction = 'Drop the coffee powder down'
    d = draft(instruction, kind='material_transfer'); d['checks'][0]['question'] = 'Is coffee powder visibly falling or deposited below the spoon?'
    p = bind_program(instruction, d); v = observation(p)
    v['checks']['endpoint']['question'] = 'Can the hand and spoon be located?'
    with pytest.raises(EvidenceContractError, match='check_binding_mismatch'):
        validate_observation(p, v, 'pair')
    v = observation(p); v['checks']['endpoint']['check_ref'] = 'another-check'
    with pytest.raises(EvidenceContractError, match='check_binding_mismatch'):
        validate_observation(p, v, 'pair')


def test_old_observation_cannot_execute_new_program_or_pair():
    p = bind_program('Move the bowl left', draft()); v = observation(p)
    with pytest.raises(EvidenceContractError, match='observation_binding_mismatch'):
        validate_observation(p, v, 'different-pair')
    p2 = bind_program('Move the bowl right', draft('Move the bowl right'))
    with pytest.raises(EvidenceContractError, match='observation_binding_mismatch'):
        validate_observation(p2, v, 'pair')


def test_required_unknown_is_not_default_no():
    p = bind_program('Move the bowl left', draft()); v = observation(p, endpoint='unknown')
    r = derive_record(p, v, 'pair')
    assert r['features']['all_requirements_satisfied'] == 'unknown'
    assert r['features']['any_required_witness'] == 'unknown'
    assert score(p, v)['label'] == 'Unresolved'


def test_required_not_applicable_is_a_diagnostic_not_an_automatic_pass():
    p = bind_program('Move the bowl left', draft()); v = observation(p, endpoint='not_applicable')
    v['checks']['endpoint']['applicability'] = 'not_applicable'
    r = derive_record(p, v, 'pair')
    assert r['checks']['endpoint']['state'] == 'unknown'
    assert {'check_id': 'endpoint', 'code': 'required_check_not_applicable'} in r['diagnostics']
    assert diagnostic_readout(r)['label'] == 'Unresolved'


@pytest.mark.parametrize('anchor,coverage', [('not_found', 'adequate'), ('ambiguous', 'adequate'), ('identified', 'occluded'), ('identified', 'cropped')])
def test_absence_cannot_pass_without_source_anchor_and_edited_coverage(anchor, coverage):
    p = bind_program('Remove the cylinder', draft('Remove the cylinder', kind='absence'))
    v = observation(p); v['checks']['endpoint'].update(source_anchor=anchor, edited_coverage=coverage)
    r = derive_record(p, v, 'pair')
    assert r['checks']['endpoint']['asserted_state'] == 'true'
    assert r['checks']['endpoint']['state'] == 'unknown'
    assert diagnostic_readout(r)['label'] == 'Unresolved'


def test_absence_can_be_established_with_appropriate_observations():
    p = bind_program('Remove the cylinder', draft('Remove the cylinder', kind='absence'))
    assert score(p, observation(p))['label'] == 'Yes'


def test_empty_requirement_and_missing_answers_are_rejected():
    d = draft(); d['requirements'][0]['check_ids'] = []
    with pytest.raises(EvidenceContractError):
        bind_program('Move the bowl left', d)
    p = bind_program('Move the bowl left', draft()); v = observation(p); v['checks'] = {}
    with pytest.raises(EvidenceContractError, match='observation_check_set'):
        score(p, v)
    assert tri_all([]) == tri_any([]) == 'not_applicable'


def test_collateral_disappearance_and_deformation_are_separate_available_facts():
    p = bind_program('Remove the cylinder', draft('Remove the cylinder', kind='absence'))
    v = observation(p, missing='true', deformed='false')
    r = derive_record(p, v, 'pair')
    assert r['features']['all_requirements_satisfied'] == 'true'
    assert r['features']['collateral_disappearance'] == 'true'
    assert r['features']['collateral_deformation'] == 'false'
    assert diagnostic_readout(r)['label'] == 'Partial'


def test_pose_intermediate_is_not_lost_when_endpoint_is_contradicted():
    instruction = 'Make the man partially stand up'
    p = bind_program(instruction, draft(instruction, kind='pose', intermediate=True))
    v = observation(p, endpoint='false', intermediate='true')
    r = derive_record(p, v, 'pair')
    assert r['features']['linked_intermediate_witness'] == 'true'
    assert diagnostic_readout(r)['label'] == 'Partial'


def test_compound_action_cannot_use_a_spatial_shortcut():
    instruction = 'Move the hand with the spoon right to drop powder'
    d = draft(instruction)
    for name, kind, question in [('grasp', 'grasp', 'Does the hand coherently hold the spoon?'),
                                 ('release', 'material_transfer', 'Is powder visibly released?')]:
        c = deepcopy(d['checks'][0]); c.update(id=name, kind=kind, question=question)
        d['checks'].append(c); d['requirements'][0]['check_ids'].append(name)
    p = bind_program(instruction, d)
    assert score(p, observation(p, endpoint='true', grasp='false', release='false'))['label'] == 'Partial'


def test_dependencies_are_bound_acyclic_and_cannot_hide_failed_prerequisites():
    d = draft(); c = deepcopy(d['checks'][0]); c.update(id='identity', role='identity', kind='identity', question='Is it the same original instance?')
    d['checks'].append(c); d['requirements'][0]['check_ids'].append('identity')
    d['checks'][0]['dependencies'] = ['identity']
    p = bind_program('Move the bowl left', d)
    assert score(p, observation(p, endpoint='true', identity='false'))['label'] != 'Yes'
    d['checks'][-1]['dependencies'] = ['endpoint']
    with pytest.raises(EvidenceContractError, match='dependency_cycle'):
        bind_program('Move the bowl left', d)


def test_unknown_collateral_does_not_prove_preservation():
    p = bind_program('Move the bowl left', draft())
    assert score(p, observation(p, missing='unknown'))['label'] == 'Unresolved'
    # An irrelevant unknown does not force abstention when no outcome exists.
    assert score(p, observation(p, endpoint='false', missing='unknown'))['label'] == 'No'


def test_uncertainty_readout_matches_all_known_completions():
    p = bind_program('Move the bowl left', draft(intermediate=True))
    keys = [c['id'] for c in p['checks']]
    for states in product(('true', 'false', 'unknown'), repeat=len(keys)):
        v = observation(p, **dict(zip(keys, states)))
        unknowns = [k for k in keys if v['checks'][k]['state'] == 'unknown']
        possibles = set()
        for fill in product(('true', 'false'), repeat=len(unknowns)):
            completed = deepcopy(v)
            for k, value in zip(unknowns, fill):
                completed['checks'][k]['state'] = value
            possibles.add(score(p, completed)['prediction'])
        expected = next(iter(possibles)) if len(possibles) == 1 else -1
        assert score(p, v)['prediction'] == expected


def test_two_stage_payloads_and_image_order(tmp_path):
    source, edited = tmp_path / 'source.png', tmp_path / 'edited.png'
    Image.new('RGB', (2, 2), (10, 20, 30)).save(source)
    Image.new('RGB', (2, 2), (100, 120, 130)).save(edited)
    evidence = {'source_image': str(source), 'edited_image': str(edited)}
    calls = []
    class FakeCalls:
        def call(self, stage, payload, schema, **kwargs):
            calls.append((stage, deepcopy(payload), kwargs))
            if stage == 'bound_instruction_v1':
                assert set(payload) == {'instruction', 'max_checks'}
                assert not kwargs.get('media')
                return draft(payload['instruction']), 'compile-ref'
            assert set(payload) == {'program', 'image_pair_ref'}
            v = observation(payload['program']); v['image_pair_ref'] = payload['image_pair_ref']
            return v, 'observe-ref'
    compiled = BoundInstructionCompiler(FakeCalls()).compile('Move the bowl left', case_id='local-ledger-id')
    result = BoundVisualObserver(FakeCalls()).observe(compiled['program'], evidence, case_id='local-ledger-id')
    assert len(calls) == 2
    assert calls[1][2]['media'] == [{'type': 'text', 'text': 'SOURCE image'}, {'type': 'image', 'path': str(source)},
                                     {'type': 'text', 'text': 'EDITED image'}, {'type': 'image', 'path': str(edited)}]
    assert score(compiled['program'], result['observation'])['label'] == 'Yes'
    assert image_identity(evidence)[1] != image_identity({'source_image': str(edited), 'edited_image': str(source)})[1]
    assert 'local-ledger-id' not in str(calls[0][1]) + str(calls[1][1])
