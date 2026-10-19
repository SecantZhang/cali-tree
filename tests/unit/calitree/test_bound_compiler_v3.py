from copy import deepcopy

import pytest
from jsonschema import ValidationError

from critical.core.decision.bound_compiler_v3 import BoundInstructionCompilerV3, checked_program, schema_for
from critical.core.decision.bound_evidence_v2 import bind_program, validate_program
from critical.core.decision.bound_evidence import EvidenceContractError
from tests.unit.calitree.test_bound_evidence_v2 import draft


def valid():
    instruction = 'Move the bowl left'
    value = draft(instruction)
    remap = {c['id']: f'c{i:02}' for i, c in enumerate(value['checks'], 1)}
    value['requirements'][0]['id'] = 'r1'
    for c in value['checks']:
        c['id'] = remap[c['id']]; c['requirement_ids'] = ['r1']; c['dependencies'] = []
    return instruction, value


def test_valid_output_binds_to_unchanged_v2_contract():
    instruction, value = valid()
    program = checked_program(instruction, value)
    assert program == bind_program(instruction, value)
    assert validate_program(program) == program


@pytest.mark.parametrize('failure', ['intermediate_dependency', 'identifier', 'quote', 'preservation_polarity'])
def test_schema_blocks_the_recorded_failure_families(failure):
    instruction, value = valid()
    if failure == 'intermediate_dependency':
        value['checks'][0]['dependencies'] = [value['checks'][-1]['id']]
    elif failure == 'identifier':
        value['checks'][0]['id'] = 'a-hyphenated-id'
    elif failure == 'quote':
        value['checks'][0]['source_quote'] = instruction.lower()
    else:
        value['checks'][0].update(role='preservation', expected_state='false')
    with pytest.raises(ValidationError):
        checked_program(instruction, value)


def test_dangling_membership_and_absence_contract_still_fail_original_validator():
    instruction, value = valid()
    value['checks'][0]['requirement_ids'] = ['r1', 'r6']
    with pytest.raises(EvidenceContractError, match='dangling_link'):
        checked_program(instruction, value)
    instruction, value = valid(); value['checks'][1].update(kind='absence', absence_when='never')
    with pytest.raises(EvidenceContractError, match='absence_contract_missing'):
        checked_program(instruction, value)


class Calls:
    def __init__(self, responses):
        self.responses = iter(responses); self.seen = []
    def call(self, stage, payload, schema, **kwargs):
        self.seen.append((stage, deepcopy(payload), schema, kwargs))
        return deepcopy(next(self.responses)), 'ref' + str(len(self.seen))


def test_valid_first_draft_needs_no_repair():
    instruction, value = valid(); calls = Calls([value])
    result = BoundInstructionCompilerV3(calls).compile(instruction)
    assert len(calls.seen) == 1 and result['repair_execution_ref'] is None
    assert calls.seen[0][1] == {'instruction': instruction, 'max_checks': 16}


def test_bounded_repair_is_label_blind_and_retains_both_references():
    instruction, value = valid(); bad = deepcopy(value); bad['checks'][0]['requirement_ids'] = ['r1', 'r6']
    calls = Calls([bad, value]); result = BoundInstructionCompilerV3(calls).compile(instruction)
    assert len(calls.seen) == 2 and result['initial_execution_ref'] == 'ref1' and result['repair_execution_ref'] == 'ref2'
    payload = calls.seen[1][1]
    assert set(payload) == {'instruction', 'max_checks', 'draft', 'validation_error'}
    assert payload['draft'] == bad and payload['validation_error']['code'] == 'dangling_link'


def test_second_invalid_draft_is_rejected_without_more_attempts():
    instruction, value = valid(); value['checks'][0]['requirement_ids'] = ['r1', 'r6']; calls = Calls([value, value])
    with pytest.raises(EvidenceContractError):
        BoundInstructionCompilerV3(calls).compile(instruction)
    assert len(calls.seen) == 2


def test_schema_does_not_modify_original_global_schema():
    from critical.core.decision.bound_evidence_v2 import COMPILER_SCHEMA
    before = deepcopy(COMPILER_SCHEMA)
    schema_for('Remove the book'); schema_for('Change the style')
    assert COMPILER_SCHEMA == before


def test_transport_failure_does_not_trigger_compiler_repair():
    from critical.core.decision.calls import CallFailure
    class Failed:
        count = 0
        def call(self, *args, **kwargs):
            self.count += 1
            raise CallFailure('Transport failed')
    calls = Failed()
    with pytest.raises(CallFailure):
        BoundInstructionCompilerV3(calls).compile('Move the bowl left')
    assert calls.count == 1


def test_preservation_and_identity_remain_required_with_empty_dependencies():
    instruction, value = valid()
    c = deepcopy(value['checks'][0]); c.update(id='c16', role='preservation', question='Is the original table still present?', expected_state='true')
    value['checks'].append(c)
    program = checked_program(instruction, value)
    assert 'c16' in program['requirements'][0]['check_ids']
    from tests.unit.calitree.test_bound_evidence import observation
    from critical.core.decision.bound_evidence_v2 import derive_record
    record = derive_record(program, observation(program, c16='false'), 'pair')
    assert record['requirements'][0]['state'] == 'false'
