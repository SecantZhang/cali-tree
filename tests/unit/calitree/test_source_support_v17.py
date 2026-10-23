from copy import deepcopy
import json

import pytest

from critical.core.decision import bound_evidence_v2 as physical
from critical.core.optimization.prompt.calitree.decomposition import source_support as source
from tests.unit.calitree.test_bound_evidence_v2 import draft
from tests.unit.calitree.test_bound_evidence import observation


def program(instruction='Turn the yellow cylinder brown', *, preservation=True, identity_dependency=False):
    d = draft(instruction, kind='attribute')
    identity = deepcopy(d['checks'][0])
    identity.update(id='identity', role='identity', kind='identity', target='the brown cylinder',
        reference='the original yellow cylinder', question='Is the brown cylinder the original cylinder?',
        applicability_condition='A brown cylinder is present in the edited scene.',
        dependencies=['endpoint'] if identity_dependency else [])
    d['checks'].append(identity)
    if preservation:
        p = deepcopy(identity)
        p.update(id='preservation', role='preservation', kind='presence', dependencies=[], target='the original table',
            question='Is the table present while the cylinder turns brown?')
        d['checks'].append(p)
    return physical.bind_program(instruction, d)


def bundle(tmp_path, *, status='identified', instruction='Turn the yellow cylinder brown', preservation=True):
    image = tmp_path / 'source.png'; image.write_bytes(b'source image bytes')
    edited = tmp_path / 'edited.png'; edited.write_bytes(b'edited image bytes')
    candidates = ('source cylinder',) if status == 'identified' else ('left cylinder', 'right cylinder') if status == 'ambiguous' else ()
    inv = source.inventory(image, {'subject': source.SourceAnchor('the original yellow cylinder', status, candidates),
        'context': source.SourceAnchor('the original table', 'identified', ('source table',))}, origin='manual_source_review')
    bindings = [source.SupportBinding('identity', 'same_instance', 'subject')]
    if preservation:
        bindings.append(source.SupportBinding('preservation', 'presence', 'context'))
    p = program(instruction, preservation=preservation, identity_dependency=True)
    return source.compile_support(p, inv, bindings), {'source_image': str(image), 'edited_image': str(edited)}


def test_support_questions_and_dependencies_no_longer_assume_edit_completion(tmp_path):
    b, _ = bundle(tmp_path)
    source.validate_bundle(b)
    original = b['original_program']; rewritten = b['program']
    assert original['program_ref'] != rewritten['program_ref']
    old = {c['id']: c for c in original['checks']}; new = {c['id']: c for c in rewritten['checks']}
    assert 'brown cylinder' in old['identity']['question']
    assert 'brown' not in new['identity']['question'] and 'brown' not in new['identity']['applicability_condition']
    assert new['identity']['dependencies'] == []
    assert 'while' not in new['preservation']['question']
    assert b['changes'][0]['removed_dependencies'] == ['endpoint']
    for key in ('endpoint', 'missing', 'deformed'):
        assert new[key] == old[key]
    assert rewritten['contract'] == original['contract']


@pytest.mark.parametrize('endpoint', ['true', 'false', 'unknown'])
def test_identity_truth_is_independent_of_endpoint_status(tmp_path, endpoint):
    b, _ = bundle(tmp_path)
    raw = observation(b['program'], endpoint=endpoint, identity='true', preservation='true')
    normalized, audit = source.normalize_observation(b, raw, 'pair')
    record = physical.derive_record(b['program'], normalized, 'pair')
    assert record['checks']['identity']['desired_state'] == 'true'
    assert record['checks']['preservation']['desired_state'] == 'true'
    assert record['requirements'][0]['state'] == endpoint
    assert audit == []


@pytest.mark.parametrize('status', ['ambiguous', 'not_found'])
def test_uncertain_source_binding_cannot_be_overridden_by_observer_confidence(tmp_path, status):
    b, _ = bundle(tmp_path, status=status)
    raw = observation(b['program'], identity='true'); before = deepcopy(raw)
    normalized, audit = source.normalize_observation(b, raw, 'pair')
    assert raw == before
    assert normalized['checks']['identity']['state'] == 'unknown'
    assert normalized['checks']['identity']['source_anchor'] == status
    assert physical.derive_record(b['program'], normalized, 'pair')['requirements'][0]['state'] == 'unknown'
    assert audit[0]['asserted_state'] == 'true' and audit[0]['effective_state'] == 'unknown'


def test_observer_uncertainty_is_not_upgraded_by_inventory(tmp_path):
    b, _ = bundle(tmp_path)
    raw = observation(b['program'], identity='true')
    raw['checks']['identity']['source_anchor'] = 'ambiguous'
    normalized, _ = source.normalize_observation(b, raw, 'pair')
    assert normalized['checks']['identity']['state'] == 'unknown'


def test_negative_presence_requires_adequate_view_but_positive_presence_can_be_partial(tmp_path):
    b, _ = bundle(tmp_path)
    for state, expected in [('false', 'unknown'), ('true', 'true')]:
        raw = observation(b['program'], preservation=state)
        raw['checks']['preservation']['edited_coverage'] = 'cropped'
        normalized, _ = source.normalize_observation(b, raw, 'pair')
        assert physical.derive_record(b['program'], normalized, 'pair')['checks']['preservation']['state'] == expected


@pytest.mark.parametrize('instruction,reason', [('Remove the cylinder', 'authorized_removal'), ('Add a new cylinder', 'new_entity')])
def test_explicit_removal_or_new_entity_waives_support_without_fabricated_success(tmp_path, instruction, reason):
    b, _ = bundle(tmp_path, instruction=instruction)
    bindings = [source.SupportBinding(check, 'waive', authorization_quote=instruction, waiver_reason=reason)
                for check in ('identity', 'preservation')]
    waived = source.compile_support(b['original_program'], b['source_inventory'], bindings)
    ids = {c['id'] for c in waived['program']['checks']}
    assert ids == {'endpoint', 'missing', 'deformed'}
    assert waived['program']['requirements'][0]['check_ids'] == ['endpoint']
    assert all(c['action'] == 'omitted' for c in waived['changes'])
    record = physical.derive_record(waived['program'], observation(waived['program'], endpoint='false'), 'pair')
    assert record['requirements'][0]['state'] == 'false'


def test_replacement_can_preserve_counterpart_while_endpoint_is_incomplete(tmp_path):
    instruction = 'Change the banana to a microphone'
    b, _ = bundle(tmp_path, instruction=instruction, preservation=False)
    inv = deepcopy(b['source_inventory'])
    image = tmp_path / 'banana_source'; image.write_bytes(b'banana source')
    inv = source.inventory(image, {'subject': source.SourceAnchor('the original banana', 'identified', ('source banana',))}, origin='manual_source_review')
    changed = source.compile_support(b['original_program'], inv, [source.SupportBinding('identity', 'counterpart', 'subject', authorization_quote=instruction)])
    check = next(c for c in changed['program']['checks'] if c['id'] == 'identity')
    assert 'microphone' not in check['question'] and 'original banana' in check['question']
    record = physical.derive_record(changed['program'], observation(changed['program'], endpoint='false', identity='true'), 'pair')
    assert record['checks']['identity']['state'] == 'true' and record['requirements'][0]['state'] == 'false'


def test_property_change_does_not_silently_waive_identity(tmp_path):
    b, _ = bundle(tmp_path)
    with pytest.raises(ValueError, match='does not waive identity'):
        source.compile_support(b['original_program'], b['source_inventory'], [
            source.SupportBinding('identity', 'waive', authorization_quote='brown', waiver_reason='authorized_property_change'),
            source.SupportBinding('preservation', 'presence', 'context')])


def test_waiver_with_surviving_dependency_requires_explicit_recompilation(tmp_path):
    b, _ = bundle(tmp_path, instruction='Remove the cylinder')
    d = source._draft(b['original_program'])
    next(c for c in d['checks'] if c['id'] == 'identity')['dependencies'] = []
    next(c for c in d['checks'] if c['id'] == 'endpoint')['dependencies'] = ['identity']
    original = physical.bind_program('Remove the cylinder', d)
    with pytest.raises(ValueError, match='surviving dependent'):
        source.compile_support(original, b['source_inventory'], [
            source.SupportBinding('identity', 'waive', authorization_quote='Remove the cylinder', waiver_reason='authorized_removal'),
            source.SupportBinding('preservation', 'presence', 'context')])


def test_all_support_checks_need_explicit_declarations_and_valid_quotes(tmp_path):
    b, _ = bundle(tmp_path)
    with pytest.raises(ValueError, match='Exactly every'):
        source.compile_support(b['original_program'], b['source_inventory'], [])
    with pytest.raises(ValueError, match='quoted from this instruction'):
        source.compile_support(b['original_program'], b['source_inventory'], [
            source.SupportBinding('identity', 'counterpart', 'subject', authorization_quote='replace anything'),
            source.SupportBinding('preservation', 'presence', 'context')])


def test_old_observations_and_modified_bundle_are_rejected(tmp_path):
    b, _ = bundle(tmp_path)
    with pytest.raises(ValueError):
        source.normalize_observation(b, observation(b['original_program']), 'pair')
    damaged = deepcopy(b); damaged['program']['checks'][0]['question'] = 'Changed'
    with pytest.raises(ValueError, match='bundle changed'):
        source.validate_bundle(damaged)
    assert source.validate_bundle(json.loads(json.dumps(b))) == b


def test_unknown_inventory_origin_cannot_claim_identification(tmp_path):
    image = tmp_path / 'source'; image.write_bytes(b'source')
    with pytest.raises(ValueError, match='cannot certify'):
        source.inventory(image, {'a': source.SourceAnchor('object', 'identified', ('object',))}, origin='unverified_source_proposal')


def test_unverified_preview_cannot_trigger_observer_calls(tmp_path):
    b, evidence = bundle(tmp_path)
    inv = source.inventory(evidence['source_image'], {'subject': source.SourceAnchor('source cylinder', 'ambiguous', ('candidate',)),
        'context': source.SourceAnchor('source table', 'ambiguous', ('candidate',))}, origin='unverified_source_proposal')
    proposal = source.compile_support(b['original_program'], inv, [source.SupportBinding('identity', 'same_instance', 'subject'),
        source.SupportBinding('preservation', 'presence', 'context')])
    with pytest.raises(ValueError, match='source-only review'):
        source.SourceSupportObserver(None, proposal)


def test_source_pixel_mismatch_fails_before_any_model_call(tmp_path):
    b, evidence = bundle(tmp_path)
    class Calls:
        def call(self, *args, **kwargs):
            pytest.fail('A mismatched source reached the observer')
    observer = source.SourceSupportObserver(Calls(), b)
    (tmp_path / 'source.png').write_bytes(b'changed pixels')
    with pytest.raises(ValueError, match='different source pixels'):
        observer.observe(b['program'], evidence)


def test_observer_keeps_raw_response_and_bound_normalization(tmp_path):
    b, evidence = bundle(tmp_path, status='ambiguous')
    class Calls:
        def __init__(self):
            self.seen = []
        def call(self, stage, payload, schema, **kwargs):
            self.seen.append((stage, payload, kwargs))
            raw = observation(payload['program'])
            raw['image_pair_ref'] = payload['image_pair_ref']
            return raw, 'test-execution'
    calls = Calls(); result = source.SourceSupportObserver(calls, b).observe(b['program'], evidence)
    assert calls.seen[0][0] == 'source_support_observation_v17'
    assert set(calls.seen[0][1]) == {'program', 'image_pair_ref', 'source_inventory', 'source_bindings', 'source_dependencies', 'source_binding_ref'}
    assert result['raw_observation']['checks']['identity']['state'] == 'true'
    assert result['observation']['checks']['identity']['state'] == 'unknown'
    assert result['execution_ref'] == 'test-execution'
    assert result['source_binding_ref'] == b['binding_ref']


def test_atomic_property_mode_has_explicit_property_and_source_selector(tmp_path):
    b, _ = bundle(tmp_path)
    changed = source.compile_support(b['original_program'], b['source_inventory'], [
        source.SupportBinding('identity', 'same_instance', 'subject'),
        source.SupportBinding('preservation', 'property', 'context', property_name='shape')])
    check = next(c for c in changed['program']['checks'] if c['id'] == 'preservation')
    assert 'shape' in check['question'] and check['kind'] == 'attribute'
    assert check['dependencies'] == []
    with pytest.raises(ValueError):
        source.SupportBinding('preservation', 'property', 'context', property_name='shape and color')


def test_property_set_expands_atomically_and_preserves_conjunctive_dependencies(tmp_path):
    b, _ = bundle(tmp_path)
    d = source._draft(b['original_program'])
    next(c for c in d['checks'] if c['id'] == 'identity')['dependencies'] = []
    next(c for c in d['checks'] if c['id'] == 'preservation')['question'] = 'Are the original table shape and color preserved?'
    next(c for c in d['checks'] if c['id'] == 'endpoint')['dependencies'] = ['preservation']
    p = physical.bind_program(b['original_program']['instruction'], d)
    expanded = source.compile_support(p, b['source_inventory'], [
        source.SupportBinding('identity', 'same_instance', 'subject'),
        source.SupportBinding('preservation', 'properties', 'context', property_names=('shape', 'color'))])
    property_rows = [r for r in expanded['rendered_bindings'] if r['mode'] == 'property']
    assert {r['property_name'] for r in property_rows} == {'shape', 'color'}
    ids = {r['check_id'] for r in property_rows}
    assert len(ids) == 2 and 'preservation' not in {c['id'] for c in expanded['program']['checks']}
    assert set(next(c for c in expanded['program']['checks'] if c['id'] == 'endpoint')['dependencies']) == ids
    assert ids <= set(expanded['program']['requirements'][0]['check_ids'])
    raw = observation(expanded['program'])
    raw['checks'][next(iter(ids))]['state'] = 'false'
    normalized, _ = source.normalize_observation(expanded, raw, 'pair')
    assert physical.derive_record(expanded['program'], normalized, 'pair')['requirements'][0]['state'] == 'false'
    assert source.validate_bundle(json.loads(json.dumps(expanded))) == expanded


def test_property_expansion_respects_check_budget_without_dropping_properties(tmp_path):
    b, _ = bundle(tmp_path)
    d = source._draft(b['original_program'])
    extra = deepcopy(next(c for c in d['checks'] if c['id'] == 'preservation'))
    extra['id'] = 'second_preservation'; d['checks'].append(extra)
    original = physical.bind_program(b['original_program']['instruction'], d)
    bindings = [source.SupportBinding('identity', 'same_instance', 'subject')]
    bindings.extend(source.SupportBinding(k, 'properties', 'context', property_names=tuple(source.PROPERTIES))
                    for k in ('preservation', 'second_preservation'))
    with pytest.raises(ValueError, match='three to sixteen'):
        source.compile_support(original, b['source_inventory'], bindings)


def test_source_anchor_ids_do_not_become_question_conditions(tmp_path):
    b, evidence = bundle(tmp_path)
    inv = source.inventory(evidence['source_image'], {
        'renamed_subject': source.SourceAnchor('the original yellow cylinder', 'identified', ('source cylinder',)),
        'renamed_context': source.SourceAnchor('the original table', 'identified', ('source table',))}, origin='manual_source_review')
    renamed = source.compile_support(b['original_program'], inv, [
        source.SupportBinding('identity', 'same_instance', 'renamed_subject'),
        source.SupportBinding('preservation', 'presence', 'renamed_context')])
    assert renamed['program'] == b['program']
    assert renamed['binding_ref'] != b['binding_ref']


def test_unresolved_source_actor_cannot_create_a_definite_dependent_outcome(tmp_path):
    b, _ = bundle(tmp_path, status='ambiguous')
    linked = source.compile_support(b['original_program'], b['source_inventory'], [
        source.SupportBinding('identity', 'same_instance', 'subject'),
        source.SupportBinding('preservation', 'presence', 'context')], source_dependencies={'endpoint': ['subject']})
    raw = observation(linked['program'], endpoint='false', identity='true')
    normalized, decisions = source.normalize_observation(linked, raw, 'pair')
    assert normalized['checks']['endpoint']['state'] == 'unknown'
    assert physical.derive_record(linked['program'], normalized, 'pair')['requirements'][0]['state'] == 'unknown'
    assert {d['check_id'] for d in decisions} == {'endpoint', 'identity'}


def test_edited_identity_uncertainty_does_not_gate_known_source_geometry(tmp_path):
    b, _ = bundle(tmp_path)
    linked = source.compile_support(b['original_program'], b['source_inventory'], [
        source.SupportBinding('identity', 'same_instance', 'subject'),
        source.SupportBinding('preservation', 'presence', 'context')], source_dependencies={'endpoint': ['subject']})
    raw = observation(linked['program'], endpoint='true', identity='unknown')
    normalized, _ = source.normalize_observation(linked, raw, 'pair')
    assert normalized['checks']['endpoint']['state'] == 'true'
    assert normalized['checks']['identity']['state'] == 'unknown'
