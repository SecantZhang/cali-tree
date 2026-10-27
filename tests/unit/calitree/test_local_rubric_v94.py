from copy import deepcopy

import pytest

from critical.lm_engine.local_qwen_v94 import LocalQwenEngine, local_messages, parse_json
from critical.core.decision import local_rubric_evidence_v94 as facts
from critical.core.decision.bound_evidence_v2 import bind_program
from tests.unit.calitree.test_bound_evidence_v2 import draft


def value():
    return {'target': 'corresponding', 'endpoint': 'achieved', 'progress': 'goal_directed',
            'collateral': 'deletion', 'preservation_explicit': 'no', 'collateral_affects_goal': 'no',
            'same_instance_essential': 'yes', 'evidence': 'The target reaches the requested position; a separate utensil is missing.'}


def test_goal_and_collateral_are_distinct_claims_without_automatic_downgrade():
    p = bind_program('Move the bowl left', draft()); v = value()
    record = facts.bind(p, 'pair', 'model', 'prompt', v)
    flags = facts.project(p, 'pair', 'model', 'prompt', record)
    assert flags['local_endpoint_achieved'] and flags['local_collateral_deletion']
    assert flags['local_collateral_affects_goal_no'] and 'prediction' not in flags
    for pair, model, prompt in [('other', 'model', 'prompt'), ('pair', 'other', 'prompt'), ('pair', 'model', 'other')]:
        with pytest.raises(ValueError, match='binding'):
            facts.project(p, pair, model, prompt, record)
    bad = deepcopy(record); bad['observation']['endpoint'] = 'absent'
    with pytest.raises(ValueError, match='binding'):
        facts.project(p, 'pair', 'model', 'prompt', bad)


def test_unknown_evidence_remains_unknown_and_extra_grade_is_rejected():
    v = {key: 'uncertain' for key in facts.FIELDS}; v['evidence'] = 'The target relation is occluded.'
    facts.validate(v)
    with pytest.raises(ValueError, match='fields'):
        facts.validate({**v, 'label': 'no'})
    with pytest.raises(ValueError, match='state'):
        facts.validate({**v, 'endpoint': 'failed'})


def test_local_engine_rejects_remote_images_before_loading_any_model(tmp_path):
    path = tmp_path/'local.png'; path.write_bytes(b'local fixture')
    messages, paths = local_messages('Observe.', [{'type': 'text', 'text': 'SOURCE'}, {'type': 'image', 'path': str(path)}])
    assert paths == [path] and messages[0]['content'][0]['text'] == 'SOURCE'
    with pytest.raises(ValueError, match='local image'):
        local_messages('Observe.', [{'type': 'image', 'path': 'https://example.com/image.png'}])


def test_local_engine_never_accesses_credentials_or_transport(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError('Remote credentials/transport forbidden')
    monkeypatch.setattr(LocalQwenEngine, 'creds', property(forbidden))
    monkeypatch.setattr('critical.lm_engine.openai_compat.chat_completion', forbidden)
    engine = LocalQwenEngine(tmp_path, {'revision': 'fixture'})
    monkeypatch.setattr(engine, '_complete', lambda messages, paths: ('{"endpoint":"uncertain"}', 10, 5))
    result = engine.generate('Observe.', schema={'type': 'object'})
    assert result['parsed'] == {'endpoint': 'uncertain'} and result['endpointHost'] == 'local-mps'
    with pytest.raises(ValueError, match='substitution'):
        engine.generate('Observe.', model='remote-model')
    with pytest.raises(ValueError, match='advisory'):
        engine.generate('Observe.', strict_schema=True)


def test_json_fences_are_presentation_only_and_bad_content_is_not_repaired():
    assert parse_json('```json\n{"x":1}\n```') == {'x': 1}
    assert parse_json('Maybe {"x":1}') is None
