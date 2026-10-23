from copy import deepcopy
import json

import pytest

from critical.core.calibration import evidence_coverage_v20 as gate_module
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import synthetic_record
from critical.core.decision.artifacts import digest
from critical.core.decision.bound_evidence_v2 import bind_program, image_identity
from critical.core.decision.semantic_interpretation_v5 import make_input
from critical.core.optimization.prompt.calitree.evidence_covered_judge import EvidenceCoveredJudge, BoundEvidencePipeline
from tests.unit.calitree.test_task_coverage import program, Calls
from tests.unit.calitree.test_bound_evidence_v2 import draft
from tests.unit.calitree.test_bound_evidence import observation
from tests.unit.calitree.test_semantic_stability_audit_v14 import requirement
from tests.unit.calitree.test_regularized_tree_v13 import rows
from tests.unit.calitree.test_local_compression_v18 import fitted


def simple():
    data = rows(12); programs = {r['source_group']: program(r['instruction']) for r in data}
    return data, programs, [fitted(data)]


def test_local_predictions_are_exact_frozen_expert_outputs():
    data, programs, models = simple()
    gate, report = gate_module.build(models, data, programs)
    assert report['covered_sources'] == 12 and report['selected_rules'] == 3
    for row in data:
        route = gate.select(programs[row['source_group']], row['features'])
        assert route['covered'] and route['prediction'] == row['reference']
        for match in route['matches']:
            executor = gate.experts[match['expert_ref']]
            assert executor.predict_records([row['features']])[0]['prediction'] == route['prediction']


def guarded_data(xor=False):
    data = rows(8)
    for i, row in enumerate(data):
        a, b = bool(i & 2), bool(i & 4)
        row['reference'] = int(a != b) if xor else int(a)
        row['features'] = synthetic_record(meaning_available=True,
            meaning_identity_evidence_same_instance_all=a, meaning_evidence_consistency_coherent_all=b)
    models = [fitted([r for r in data if r['reference'] == k]) for k in (0, 1)]
    programs = {r['source_group']: program(r['instruction']) for r in data}
    return data, programs, models


def test_guards_reject_known_wrong_expert_without_using_membership():
    data, programs, models = guarded_data()
    gate, report = gate_module.build(models, data, programs)
    assert report['covered_sources'] == 8
    assert all(rule['guards'] for rule in gate.artifact['rules'])
    for row in data:
        assert gate.select(programs[row['source_group']], row['features'])['prediction'] == row['reference']


def test_scope_direction_resolves_evidence_collision_without_object_names():
    data, programs, models = guarded_data()
    for row in data:
        row['features'] = synthetic_record(meaning_available=True)
        d = draft(row['instruction'], kind='attribute')
        d['contract']['authorized_changes'] = [('Increase' if row['reference'] == 0 else 'Reduce') + ' the requested property.']
        programs[row['source_group']] = bind_program(row['instruction'], d)
    models = [fitted([r for r in data if r['reference'] == k]) for k in (0, 1)]
    gate, report = gate_module.build(models, data, programs)
    assert report['covered_sources'] == 8
    assert all(c['feature'].startswith('task_explicit_') for r in gate.artifact['rules'] for c in r['guards'])
    for row in data:
        assert gate.select(programs[row['source_group']], row['features'])['prediction'] == row['reference']


@pytest.mark.parametrize('text,increase,decrease', [('Increase brightness.', True, False), ('Reduce the size.', False, True),
    ('Do not reduce the size.', False, False), ('Preserve the object named Increase.', False, False),
    ('Make the object smaller.', False, False), ('  EXPAND the region.', True, False)])
def test_direction_flags_are_conservative_compiler_directives(text, increase, decrease):
    d = draft('Generic instruction', kind='attribute'); d['contract']['authorized_changes'] = [text]
    values = gate_module.task_features(bind_program('Generic instruction', d))
    assert values['task_explicit_increase'] is increase and values['task_explicit_decrease'] is decrease


def test_unseen_task_missing_evidence_and_missing_interpretation_defer():
    data, ps, models = simple(); gate, _ = gate_module.build(models, data, ps)
    p = program('Add a new object', kind='presence')
    assert not gate.accepts_task(p)
    assert gate.select(p, data[0]['features'])['reason'] == 'unseen_task_profile'
    for record in (None, synthetic_record(meaning_available=False), {}):
        assert not gate.select(ps[data[0]['source_group']], record)['covered']


def test_unseparable_conflict_is_not_memorized_as_source_ids():
    data, ps, models = guarded_data()
    for row in data:
        row['features'] = synthetic_record(meaning_available=True)
    models = [fitted([r for r in data if r['reference'] == k]) for k in (0, 1)]
    gate, report = gate_module.build(models, data, ps)
    assert report['covered_sources'] == 0 and not gate.artifact['rules']
    assert all(not gate.select(ps[r['source_group']], r['features'])['covered'] for r in data)


def test_exhausted_guard_budget_defers_instead_of_accepting_counterexamples():
    data, ps, models = guarded_data(xor=True)
    gate, report = gate_module.build(models, data, ps, gate_module.Config(max_pair_states=1))
    assert report['exhausted_pairs'] > 0 and report['covered_sources'] == 0
    assert not gate.select(ps[data[0]['source_group']], data[0]['features'])['covered']


def test_inference_disagreement_abstains_instead_of_arbitrary_expert_priority():
    data, ps, models = guarded_data(); gate, _ = gate_module.build(models, data, ps)
    artifact = gate.export()
    # Two disjoint observed contexts can overlap on an unseen conjunction.
    for i, rule in enumerate(artifact['rules']):
        feature = ('meaning_identity_evidence_same_instance_all', 'meaning_evidence_consistency_coherent_all')[i]
        rule['guards'] = [{'feature': feature, 'value': True}]
    artifact['artifact_ref'] = digest({k: v for k, v in artifact.items() if k != 'artifact_ref'})
    gate = gate_module.EvidenceCoverageGate(artifact)
    new = synthetic_record(meaning_available=True, meaning_identity_evidence_same_instance_all=True,
                           meaning_evidence_consistency_coherent_all=True)
    assert gate.select(ps[data[0]['source_group']], new)['reason'] == 'conflicting_supported_experts'


def test_roundtrip_and_id_renaming_do_not_change_runtime():
    data, ps, models = guarded_data(xor=True); gate, _ = gate_module.build(models, data, ps)
    copy = gate_module.EvidenceCoverageGate(json.loads(json.dumps(gate.export())))
    assert copy.export() == gate.export()
    changed = deepcopy(list(reversed(data))); changed_ps = {}
    for i, row in enumerate(changed):
        p = ps[row['source_group']]; row['source_group'] = f'renamed-{i}'; row['case'] = 'irrelevant'
        row['batch'] = {'G0': 'A', 'G1': 'B', 'G2': 'C', 'G3': 'D'}[row['batch']]
        changed_ps[row['source_group']] = p
    changed_models = [fitted([r for r in changed if r['reference'] == k]) for k in (0, 1)]
    renamed, _ = gate_module.build(changed_models, changed, changed_ps)
    assert renamed.export() == gate.export()
    encoded = json.dumps(gate.export())
    assert 'source_group' not in encoded and 'distinct request' not in encoded


def bound_fixture(tmp_path):
    evidence = {k: str(tmp_path / k) for k in ('source_image', 'edited_image')}
    for k, path in evidence.items():
        from pathlib import Path
        Path(path).write_bytes(k.encode())
    pair = image_identity(evidence)[1]; data = []; programs = {}; observations = {}; interpretations = {}
    for i in range(4):
        p = program(f'Change object {i}'); obs = observation(p); obs['image_pair_ref'] = pair
        payload = make_input(p, obs, pair)
        meaning = {'evidence_ref': payload['evidence_ref'], 'requirements': {'r1': {
            **requirement(), 'support_check_ids': [p['checks'][0]['id']], 'explanation': 'Established endpoint.'}}}
        key = str(i); programs[key] = p; observations[key] = obs; interpretations[key] = meaning
        data.append({'source_group': key, 'case': key, 'instruction': p['instruction'], 'batch': 'G1', 'reference': 2,
                     'features': gate_module.project(p, obs, pair, meaning)})
    gate, _ = gate_module.build([fitted(data)], data, programs)
    return gate, evidence, programs['0'], observations['0'], interpretations['0']


def test_bound_covered_path_never_calls_judge_and_preserves_tree_label(tmp_path):
    gate, evidence, p, obs, meaning = bound_fixture(tmp_path); calls = Calls('no')
    result = EvidenceCoveredJudge(calls, gate).judge(p['instruction'], evidence, program=p, observation=obs, interpretation=meaning)
    assert result['source'] == 'frozen_tree' and result['judgment']['label'] == 'yes'
    assert calls.requests == []


def test_wrong_image_binding_or_instruction_uses_exact_regular_fallback(tmp_path):
    gate, evidence, p, obs, meaning = bound_fixture(tmp_path); calls = Calls('partial')
    broken = deepcopy(obs); broken['image_pair_ref'] = 'different images'
    judge = EvidenceCoveredJudge(calls, gate, regular_prompt='regular')
    result = judge.judge(p['instruction'], evidence, program=p, observation=broken, interpretation=meaning)
    assert result['source'] == 'regular_judge' and result['extraction_error'] is not None
    assert calls.requests[0][0] == 'flat_judge' and calls.requests[0][1] == {'instruction': p['instruction']}
    assert calls.requests[0][3]['template'] == 'regular'
    result = judge.judge('different instruction', evidence, program=p, observation=obs, interpretation=meaning)
    assert result['source'] == 'regular_judge'


def test_fresh_pipeline_keeps_original_observer_and_interpretation_stages(tmp_path):
    gate, evidence, p, obs, meaning = bound_fixture(tmp_path)
    class ExtractionCalls(Calls):
        def call(self, stage, payload, schema, **kwargs):
            self.requests.append((stage, deepcopy(payload)))
            if stage == 'bound_visual_observation_v2':
                return obs, 'observation'
            if stage == 'instruction_relative_interpretation':
                return meaning, 'interpretation'
            raise AssertionError('Covered inference attempted a final judge call')
    calls = ExtractionCalls()
    result = EvidenceCoveredJudge(calls, gate).judge(p['instruction'], evidence, program=p)
    assert result['source'] == 'frozen_tree' and result['judgment']['label'] == 'yes'
    assert [s for s, _ in calls.requests] == ['bound_visual_observation_v2', 'instruction_relative_interpretation']


def test_unseen_task_skips_observer_and_interpretation(tmp_path):
    gate, evidence, _, _, _ = bound_fixture(tmp_path); calls = Calls(); p = program('Add something', kind='presence')
    result = EvidenceCoveredJudge(calls, gate).judge(p['instruction'], evidence, program=p)
    assert result['route']['reason'] == 'unseen_task_profile'
    assert len(calls.requests) == 1 and calls.requests[0][0] == 'flat_judge'


def test_runtime_rejects_tampering_and_prohibited_input_fields():
    data, ps, models = simple(); gate, _ = gate_module.build(models, data, ps)
    artifact = gate.export(); artifact['rules'][0]['guards'] = [{'feature': 'source_id', 'value': True}]
    artifact['artifact_ref'] = digest({k: v for k, v in artifact.items() if k != 'artifact_ref'})
    with pytest.raises(ValueError, match='Undeclared'):
        gate_module.EvidenceCoverageGate(artifact)
    with pytest.raises(TypeError):
        gate.select(ps[data[0]['source_group']], data[0]['features'], reference=2)
