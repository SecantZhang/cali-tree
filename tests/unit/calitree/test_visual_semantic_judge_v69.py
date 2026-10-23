from types import SimpleNamespace

from critical.core.optimization.prompt.calitree.visual_semantic_judge_v69 import VisualSemanticJudge


def test_cached_bound_path_uses_current_input_and_makes_no_model_calls():
    seen = []
    program = {'instruction': 'Move the book left', 'program_ref': 'p'}
    judgment = {'label': 'yes', 'rationale': 'Regular visual judgment.'}
    extractor = SimpleNamespace(extract=lambda *args, **kwargs: ({'obs': True}, {'meaning': True}, 'pair'))
    encoder = SimpleNamespace(compute=lambda p, e: seen.append((p, e)) or {'image_pair_ref': 'pair'})
    policy = SimpleNamespace(resolve_bound=lambda *args: {'covered': True, 'prediction': 1})
    runner = VisualSemanticJudge(None, policy, encoder, extractor=extractor)
    result = runner.judge(program['instruction'], {'source_image': 's', 'edited_image': 'e'}, program=program,
                          observation={}, interpretation={}, regular_judgment=judgment)
    assert result['judgment']['label'] == 'partial' and result['source'] == 'visual_policy'
    assert seen == [(program, {'source_image': 's', 'edited_image': 'e'})]
    assert result['regular_execution_ref'] is None


def test_retained_failed_slot_falls_back_without_retrying_extraction():
    def forbidden(*args, **kwargs):
        raise AssertionError('Failed cache slot must not be retried')
    regular = {'label': 'yes', 'rationale': 'Regular visual judgment.'}
    runner = VisualSemanticJudge(None, None, None, extractor=SimpleNamespace(extract=forbidden))
    result = runner.judge('Move the book left', {}, program={'instruction': 'Move the book left'},
                          observation=None, interpretation=None, regular_judgment=regular)
    assert result['judgment'] == regular and result['source'] == 'regular_judge' and not result['route']['covered']
