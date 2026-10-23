from copy import deepcopy
import json

import pytest

from critical.core.optimization.prompt.calitree import task_coverage as coverage
from critical.core.decision.bound_evidence_v2 import bind_program
from tests.unit.calitree.test_bound_evidence_v2 import draft
from tests.unit.calitree.test_local_compression_v18 import fitted
from tests.unit.calitree.test_regularized_tree_v13 import rows


def program(instruction, kind='attribute'):
    return bind_program(instruction, draft(instruction, kind=kind))


def fixture():
    data = rows(12)
    ps = {r['source_group']: program(r['instruction']) for r in data}
    return data, ps, coverage.build([fitted(data)], data, ps)


class Calls:
    def __init__(self, label='partial'):
        self.requests = []; self.label = label

    def call(self, stage, payload, schema, **kwargs):
        self.requests.append((stage, deepcopy(payload), deepcopy(schema), deepcopy(kwargs)))
        return {'label': self.label, 'rationale': 'Observed image evidence.'}, 'execution'


def test_new_objects_with_same_task_structure_get_conditional_rules():
    _, _, gate = fixture()
    selected = gate.select('Make the new object purple', program('Make the new object purple'))
    assert selected['covered'] and len(selected['reference']['rules']) == 3
    assert set(r['conclusion_if_all_established'] for r in selected['reference']['rules']) == {'yes', 'partial', 'no'}
    assert 'prediction' not in selected and 'label' not in selected


def test_different_operation_and_novel_compound_scope_fall_back():
    _, _, gate = fixture()
    assert not gate.select('Add an object', program('Add an object', 'presence'))['covered']
    d = draft('Change color and add object', kind='attribute')
    d['requirements'].append({'id': 'r2', 'description': 'Add object', 'source_quote': 'Change color and add object'})
    extra = deepcopy(d['checks'][0]); extra.update(id='second', requirement_ids=['r2'], kind='presence')
    d['checks'].append(extra)
    p = bind_program('Change color and add object', d)
    assert not gate.select(p['instruction'], p)['covered']


@pytest.mark.parametrize('p', [None, {}, {'instruction': 'invalid'}])
def test_missing_invalid_or_mismatched_program_uses_regular_request(p):
    _, _, gate = fixture(); judge = coverage.TaskCoveredJudge(Calls(), gate, regular_prompt='original prompt')
    request = judge.request('New instruction', p)
    assert request['stage'] == 'flat_judge' and request['template'] == 'original prompt'
    assert request['payload'] == {'instruction': 'New instruction'}
    assert not judge.request('Mismatch', program('Different instruction'))['route']['covered']


def test_uncovered_call_is_exact_regular_judge_and_source_image_first():
    _, _, gate = fixture(); calls = Calls(); judge = coverage.TaskCoveredJudge(calls, gate, regular_prompt='regular')
    result = judge.judge('Add object', {'source_image': 'source', 'edited_image': 'edited'}, program=program('Add object', 'presence'))
    stage, payload, schema, kwargs = calls.requests[0]
    assert stage == 'flat_judge' and payload == {'instruction': 'Add object'} and kwargs['template'] == 'regular'
    assert schema == coverage.SCHEMA and [m.get('path') for m in kwargs['media'] if m['type'] == 'image'] == ['source', 'edited']
    assert result['judgment']['label'] == 'partial' and len(calls.requests) == 1


def test_covered_judge_uses_model_answer_instead_of_forcing_tree_label():
    _, _, gate = fixture(); calls = Calls('unresolved'); judge = coverage.TaskCoveredJudge(calls, gate)
    p = program('New color request')
    result = judge.judge(p['instruction'], {'source_image': 'source', 'edited_image': 'edited'}, program=p)
    assert result['route']['covered'] and result['judgment']['label'] == 'unresolved'
    assert calls.requests[0][0] == 'tree_reference_judge' and 'tree_reference' in calls.requests[0][1]
    assert len(calls.requests) == 1


def test_instruction_only_gate_cannot_read_outcomes_labels_or_case_ids():
    _, _, gate = fixture(); p = program('New task')
    packet = coverage.TaskCoveredJudge(Calls(), gate).request(p['instruction'], p)['payload']
    encoded = json.dumps(packet)
    for forbidden in ('source_group', 'source_batches', 'reference_label', 'correct_sources', 's000', 'distinct request'):
        assert forbidden not in encoded
    with pytest.raises(TypeError):
        gate.select(p['instruction'], p, reference=2)


def test_duplicate_instructions_do_not_establish_rule_support():
    data, ps, _ = fixture(); model = fitted(data)
    for row in data:
        row['instruction'] = 'same instruction'
        ps[row['source_group']] = program(row['instruction'])
    # Gate rechecks instruction support, rather than accepting old model flags.
    with pytest.raises(ValueError, match='Invalid source policy'):
        coverage.build([model], data, ps)


def test_singletons_are_not_covered_and_budget_never_truncates_rules():
    data, ps, _ = fixture(); model = fitted(data)
    gate = coverage.build([model], data, ps, coverage.Config(min_sources=5))
    assert not gate.select('New task', program('New task'))['covered']
    gate = coverage.build([model], data, ps, coverage.Config(max_rules=1))
    assert gate.select('New task', program('New task'))['reason'] == 'reference_budget_exceeded'


def test_artifact_roundtrip_preserves_route_and_rejects_tampering():
    _, _, gate = fixture(); exported = json.loads(json.dumps(gate.export()))
    assert coverage.TaskCoverageGate(exported).select('New task', program('New task')) == gate.select('New task', program('New task'))
    exported['entries'][0]['rule']['conclusion_if_all_established'] = 'unresolved'
    with pytest.raises(ValueError, match='Changed'):
        coverage.TaskCoverageGate(exported)


def test_known_counterexample_in_other_training_scope_removes_reference_rule():
    data, ps, initial = fixture(); model = fitted(data)
    extra = deepcopy(data[0]); extra.update(source_group='outside', instruction='Different object same task', reference=2)
    ps[extra['source_group']] = program(extra['instruction'])
    gate = coverage.build([model], data + [extra], ps)
    old = initial.select('New task', program('New task'))['reference']['rules']
    new = gate.select('New task', program('New task'))['reference']['rules']
    assert len(old) == 3 and len(new) == 2
    assert all(r['conclusion_if_all_established'] != 'no' for r in new)


def test_compiler_failure_defers_to_regular_judge_without_observation_calls():
    class Compiler:
        def compile(self, *args, **kwargs):
            raise ValueError('invalid program')
    _, _, gate = fixture(); calls = Calls()
    result = coverage.TaskCoveredJudge(calls, gate, compiler=Compiler()).judge('New task', {'source_image': 'source', 'edited_image': 'edited'})
    assert result['compiler_error'] == 'ValueError' and not result['route']['covered']
    assert len(calls.requests) == 1 and calls.requests[0][0] == 'flat_judge'
