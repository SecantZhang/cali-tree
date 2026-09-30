"""Offline acceptance of manual scopes, staged execution and durable pins."""
from copy import deepcopy
from dataclasses import replace
import json
import pytest
from critical.interface.node_calibration.calitree_manual_nodes import (
    CaliTreePartitionNodeExecutor, CaliTreeLeafNodeExecutor, CaliTreeMergeNodeExecutor,
)
from critical.interface.node_calibration.calitree_nodes import CaliTreeJudgeNodeExecutor, _CaliTreeRuntime
from critical.interface.server.artifacts import load_artifact
from critical.interface.server import run_manager
from .test_calitree_modular_nodes import OfflineEngine as DecompositionEngine, dataset, RUBRIC

class Engine(DecompositionEngine):
    def generate(self, prompt, system=None, **kwargs):
        if system == RUBRIC:
            self.calls.append((prompt, system))
            return {"content": json.dumps({"label": "yes", "rationale": "offline raw judgment"}), "completionTokens": 1}
        return super().generate(prompt, system=system, **kwargs)

@pytest.fixture
def setup(make_ctx, monkeypatch, tmp_path):
    engine = Engine()
    monkeypatch.setattr('critical.interface.node_calibration.calitree_nodes._engine_from', lambda *_: engine)
    monkeypatch.setattr(run_manager, 'run_dir_for', lambda identity: tmp_path / identity)
    samples, labels = dataset()
    partition_result = CaliTreePartitionNodeExecutor().run(make_ctx(inputs={"samples": samples, "labels": labels}))
    assert partition_result.status == 'done', partition_result.error
    partition = partition_result.outputs['partition']
    def build(node_id='leaf', ids=None, params=None, children=None, options=None):
        settings = {'initial_prompt': RUBRIC, 'decomposition_strategy': 'two_way', 'optimizer_plan': 'evaluate_only',
                    'selected_ids': ids or partition['fit_ids'][:1], 'output_mode': 'decision_sets', **(params or {})}
        ctx = make_ctx(node_id=node_id, params=settings, inputs={'partition': partition, 'judge_engine': {'model': 'offline'},
            'optimizer_engine': {'model': 'offline'}, **({'children': children} if children is not None else {})}, dry_run=False, allow_live=True)
        ctx.execution_options = options or {}
        result = (CaliTreeMergeNodeExecutor() if children is not None else CaliTreeLeafNodeExecutor()).run(ctx)
        return ctx, result
    return engine, partition, build


def refs(result):
    return {key: value['artifact_ref'] for key, value in result.outputs['calitree_report']['stages'].items()}


def test_partition_is_task_disjoint_and_preserves_official_test(setup):
    _, part, _ = setup
    assert set(part['fit_ids']).isdisjoint(part['validation_ids'])
    assert part['test_ids'] == ['task12::editor']
    assert set(part['fit_ids'] + part['validation_ids'] + part['test_ids']) == set(part['samples'])


def test_leaf_exports_reload_and_direct_judging(setup, make_ctx):
    engine, part, build = setup
    ctx, result = build()
    assert result.status == 'done', result.error
    node = json.loads(json.dumps(result.outputs['node']))
    assert node['validation_state'] == 'accepted'
    assert node['correct_ids'] == node['scope_ids']
    assert 'optimized_prompt' not in result.outputs
    assert load_artifact(refs(result)['compilation'])['data'] == node['decision_sets']
    before = len(engine.calls)
    judged = CaliTreeJudgeNodeExecutor().run(make_ctx(inputs={'calitree_node': node, 'samples': {'test': part['samples'][part['test_ids'][0]]},
        'judge_engine': {'model': 'offline'}}, dry_run=False, allow_live=True))
    assert judged.status == 'done', judged.error
    assert judged.outputs['judge_result']['test']['calitree']['label'] == 'yes'
    assert not any(system == __import__('critical.core.optimization.prompt.calitree.decomposition', fromlist=['load_templates']).load_templates().compile_policy for _, system in engine.calls[before:])


def test_frozen_predecessors_metrics_and_fresh_evaluation(setup, monkeypatch):
    engine, _, build = setup
    _, initial = build()
    assert initial.status == 'done', initial.error
    cached = refs(initial)
    pins = {key: cached[key] for key in ['optimization', 'compilation']}
    before = len(engine.calls)
    _, rerun = build(params={'stage_cache': cached, 'stage_pins': pins}, options={'run_from': 'instruction_decomposition'})
    assert rerun.status == 'done', rerun.error
    assert rerun.outputs['node']['stages']['optimization']['source'] == 'pinned'
    templates = __import__('critical.core.optimization.prompt.calitree.decomposition', fromlist=['load_templates']).load_templates()
    assert not any(system == templates.compile_policy for _, system in engine.calls[before:])
    before = len(engine.calls)
    _, metrics = build(params={'stage_cache': refs(rerun), 'stage_pins': pins}, options={'action': 'metrics'})
    assert metrics.status == 'done', metrics.error
    assert len(engine.calls) == before
    _, fresh = build(params={'stage_cache': refs(metrics), 'stage_pins': pins}, options={'action': 'fresh'})
    assert fresh.status == 'done', fresh.error
    assert len(engine.calls) > before
    assert fresh.outputs['node']['stages']['evidence_checks']['source'] == 'computed'
    before = len(engine.calls)
    _, blocked = build(params={'stage_cache': refs(fresh), 'stage_pins': {**pins, 'evidence_checks': refs(fresh)['evidence_checks']}}, options={'action': 'fresh'})
    assert blocked.status == 'error' and 'Unfreeze' in blocked.error
    assert len(engine.calls) == before


def test_prompt_pin_can_rebind_new_data_but_observations_cannot(setup):
    engine, part, build = setup
    _, initial = build()
    cached = refs(initial)
    before = len(engine.calls)
    _, new = build(ids=part['fit_ids'][1:2], params={'stage_cache': cached, 'stage_pins': {'optimization': cached['optimization']}})
    assert new.status == 'done', new.error
    assert new.outputs['node']['stages']['optimization']['stale_inputs']
    _, bad = build(ids=part['fit_ids'][1:2], params={'stage_cache': cached, 'stage_pins': {'optimization': cached['optimization'], 'evidence_checks': cached['evidence_checks']}})
    assert bad.status == 'error' and 'incompatible' in bad.error


def test_selection_candidate_children_multi_merge_and_rejection(setup):
    _, part, build = setup
    _, forbidden = build(ids=part['validation_ids'])
    assert forbidden.status == 'error' and 'fit cases' in forbidden.error
    leaves = []
    for index in range(3):
        _, result = build(f'leaf{index}', ids=part['fit_ids'][index:index+2], params={'run_until': 'optimization', 'output_mode': 'raw_prompt'})
        assert result.status == 'done', result.error
        assert result.outputs['node']['decision_sets'] is None
        leaves.append(result.outputs['node'])
    _, result = build('parent', children=leaves)
    assert result.status == 'done', result.error
    parent = result.outputs['node']
    assert parent['validation_state'] == 'accepted'
    assert len(parent['children']) == 3
    assert parent['scope_ids'] == part['fit_ids'][:4]
    _, mixed = build('upper', children=[parent, leaves[0]])
    assert mixed.status == 'error' and 'ancestor' in mixed.error
    _, duplicate = build('bad', children=[leaves[0], leaves[0]])
    assert duplicate.status == 'error' and 'Duplicate' in duplicate.error
    original = deepcopy(leaves)
    # A high floor is rejected on measured held-out results, leaving supplied children intact.
    badpart = deepcopy(part)
    for key in badpart['validation_ids']: badpart['labels'][key]['target_label'] = 'no'
    from critical.core.optimization.prompt.calitree.decomposition.artifacts import digest
    badpart['id'] = digest({k: v for k, v in badpart.items() if k != 'id'})
    ctx, _ = build('rejected', children=leaves)
    ctx.inputs['partition'] = badpart
    for child in ctx.inputs['children']: child['partition_id'] = badpart['id']
    rejected = CaliTreeMergeNodeExecutor().run(ctx)
    assert rejected.status == 'done', rejected.error
    assert rejected.outputs['node']['validation_state'] == 'rejected'
    assert len(rejected.outputs['node']['children']) == 3
    assert [c['prompt'] for c in leaves] == [c['prompt'] for c in original]


def test_pin_hash_and_missing_pin_stop_before_calls(setup):
    engine, _, build = setup
    _, initial = build()
    cached = refs(initial)
    before = len(engine.calls)
    _, changed = build(params={'initial_prompt': 'changed', 'stage_cache': cached, 'stage_pins': {'compilation': cached['compilation']}})
    assert changed.status == 'error' and 'changed' in changed.error
    _, missing = build(params={'stage_pins': {'optimization': {**cached['optimization'], 'digest': '0'*64}}})
    assert missing.status == 'error' and 'Missing pinned artifact' in missing.error
    assert len(engine.calls) == before


def test_raw_output_stopping_and_direct_judge(setup, make_ctx):
    engine, part, build = setup
    _, result = build(params={'output_mode': 'raw_prompt', 'run_until': 'optimization'})
    assert result.status == 'done', result.error
    assert result.outputs['optimized_prompt'] == RUBRIC
    assert 'decision_sets' not in result.outputs
    assert result.outputs['node']['validation_state'] == 'candidate'
    judged = CaliTreeJudgeNodeExecutor().run(make_ctx(inputs={'calitree_node': result.outputs['node'],
        'samples': {part['test_ids'][0]: part['samples'][part['test_ids'][0]]}, 'judge_engine': {'model': 'offline'}}, dry_run=False, allow_live=True))
    assert judged.status == 'done', judged.error
    assert judged.outputs['judge_result'][part['test_ids'][0]]['calitree']['label'] == 'yes'
    bad = deepcopy(result.outputs['node']); bad['output_mode'] = 'decision_sets'
    before = len(engine.calls)
    judged = CaliTreeJudgeNodeExecutor().run(make_ctx(inputs={'calitree_node': bad, 'samples': {}, 'judge_engine': {'model': 'offline'}}, dry_run=False, allow_live=True))
    assert judged.status == 'error' and 'unavailable' in judged.error
    assert len(engine.calls) == before


def test_three_child_dry_run_does_not_create_engines(setup, make_ctx, monkeypatch):
    _, part, _ = setup
    monkeypatch.setattr('critical.interface.node_calibration.calitree_nodes._engine_from', lambda *_: pytest.fail('Dry run created an engine'))
    leaves = []
    for index in range(3):
        ctx = make_ctx(node_id=f'dry{index}', params={'selected_ids': part['fit_ids'][index:index+1]}, inputs={'partition': part})
        result = CaliTreeLeafNodeExecutor().run(ctx)
        assert result.status == 'done', result.error
        leaves.append(result.outputs['node'])
    result = CaliTreeMergeNodeExecutor().run(make_ctx(inputs={'partition': part, 'children': leaves}))
    assert result.status == 'done', result.error
    assert result.outputs['node']['children'] == ['dry0', 'dry1', 'dry2']


def test_changed_vision_bytes_invalidate_evidence_pin_before_calls(setup, make_ctx, monkeypatch, tmp_path):
    from tests.unit.calitree.test_decomposition_vision import Engine as VisionEngine, INSTRUCTION, RUBRIC as VISION_RUBRIC
    from critical.core.optimization.prompt.calitree.decomposition.artifacts import digest
    engine, part, _ = setup
    engine = VisionEngine()
    monkeypatch.setattr('critical.interface.node_calibration.calitree_nodes._engine_from', lambda *_: engine)
    source, edited = tmp_path / 'source.png', tmp_path / 'edited.png'
    source.write_bytes(b'source'); edited.write_bytes(b'edited')
    part = deepcopy(part)
    for sample in part['samples'].values():
        sample['input'] = {'instruction': INSTRUCTION, 'source_image_path': str(source)}
        sample['output'] = {'edited_image_path': str(edited)}
        sample.pop('evidence', None)
    part['id'] = digest({k: v for k, v in part.items() if k != 'id'})
    params = {'initial_prompt': VISION_RUBRIC, 'selected_ids': part['fit_ids'][:1], 'decomposition_strategy': 'two_way_vision',
              'output_mode': 'decision_sets', 'optimizer_plan': 'evaluate_only', 'optimization_evaluator': 'decomposed'}
    ctx = make_ctx(node_id='vision', params=params, inputs={'partition': part, 'judge_engine': {'model': 'offline'}}, dry_run=False, allow_live=True)
    first = CaliTreeLeafNodeExecutor().run(ctx)
    assert first.status == 'done', first.error
    cached = refs(first)
    ctx.params = {**params, 'stage_cache': cached, 'stage_pins': {'optimization': cached['optimization'], 'compilation': cached['compilation'], 'evidence_checks': cached['evidence_checks']}}
    edited.write_bytes(b'changed bytes at same path')
    before = len(engine.calls)
    invalid = CaliTreeLeafNodeExecutor().run(ctx)
    assert invalid.status == 'error' and 'evidence_checks' in invalid.error
    assert len(engine.calls) == before


def test_cancelled_action_reuses_completed_stages_on_recovery(setup):
    engine, _, build = setup
    ctx, initial = build()
    ctx.params['stage_cache'] = refs(initial)
    ctx.execution_options = {'run_from': 'compilation', 'execution_id': 'same-action'}
    # Stop after compilation using the durable stage event, then resume the same action.
    stopped = {'value': False}
    ctx.should_stop = lambda: stopped['value']
    ctx.progress_cb = lambda event, row: stopped.update(value=True) if event == 'calitree_stage' and row.get('stage') == 'compilation' and row.get('state') == 'complete' else None
    interrupted = CaliTreeLeafNodeExecutor().run(ctx)
    assert interrupted.status == 'error' and 'stopped' in interrupted.error
    ctx.should_stop = None; ctx.progress_cb = None
    before = len(engine.calls)
    recovered = CaliTreeLeafNodeExecutor().run(ctx)
    assert recovered.status == 'done', recovered.error
    assert recovered.outputs['node']['stages']['compilation']['source'] == 'checkpoint'
    assert len(engine.calls) >= before


def test_frozen_textgrad_does_not_call_optimizer_and_records_evaluators(setup, monkeypatch):
    engine, _, build = setup
    updates = []
    original_generate = engine.generate
    def generate(prompt, system=None, **kwargs):
        if system and system.startswith('Always no'):
            engine.calls.append((prompt, system))
            return {'content': json.dumps({'label': 'no', 'rationale': 'seed failure'})}
        return original_generate(prompt, system=system, **kwargs)
    engine.generate = generate
    def optimize(runtime, prompt, feedback):
        updates.append((prompt, feedback))
        runtime._record({'completionTokens': 1}, 'optimizer')
        return RUBRIC
    monkeypatch.setattr(_CaliTreeRuntime, 'optimize', optimize)
    settings = {'initial_prompt': 'Always no\nAll edits fail.', 'optimizer_plan': 'textgrad'}
    _, initial = build(params=settings)
    assert initial.status == 'done', initial.error
    assert len(updates) == 1
    assert initial.outputs['node']['optimization']['evaluator'] == 'raw_prompt'
    assert initial.outputs['node']['optimization']['report']['history'][0]['accuracy'] == 0
    cached = refs(initial)
    _, rerun = build(params={**settings, 'stage_cache': cached,
        'stage_pins': {'optimization': cached['optimization'], 'compilation': cached['compilation']}}, options={'run_from': 'instruction_decomposition'})
    assert rerun.status == 'done', rerun.error
    assert len(updates) == 1
    assert rerun.meta['usage']['optimizer_calls'] == 0


def test_disjoint_mixed_depth_merge_and_policy_tampering(setup, make_ctx):
    _, part, build = setup
    leaves = [build(f'mixed{index}', ids=[part['fit_ids'][index]])[1].outputs['node'] for index in range(3)]
    parent = build('mixed_parent', children=leaves[:2])[1].outputs['node']
    _, result = build('mixed_upper', children=[parent, leaves[2]])
    assert result.status == 'done', result.error
    assert result.outputs['node']['depth'] == 2
    assert result.outputs['node']['children'] == ['mixed_parent', 'mixed2']
    bad = deepcopy(result.outputs['node'])
    bad['decision_sets']['prompt_sha256'] = 'tampered'
    judged = CaliTreeJudgeNodeExecutor().run(make_ctx(inputs={'calitree_node': bad, 'samples': {}, 'judge_engine': {'model': 'offline'}}, dry_run=False, allow_live=True))
    assert judged.status == 'error' and 'binding mismatch' in judged.error


def test_partition_quarantines_uncertain_annotations_without_deleting_records(make_ctx):
    from tests.unit.calitree.test_annotation_quality import REVIEW
    samples, labels = dataset()
    labels['task0::editor']['annotation_review'] = REVIEW
    labels['task12::editor']['annotation_review'] = REVIEW
    result = CaliTreePartitionNodeExecutor().run(make_ctx(inputs={'samples': samples, 'labels': labels}))
    assert result.status == 'done', result.error
    part = result.outputs['partition']
    assert 'task0::editor' not in part['fit_ids'] + part['validation_ids']
    assert 'task0::editor' in part['samples'] and part['labels']['task0::editor']['target_label'] == 'yes'
    assert part['test_ids'] == ['task12::editor']
    assert set(part['annotation_quarantine']) == {'task0::editor', 'task12::editor'}
