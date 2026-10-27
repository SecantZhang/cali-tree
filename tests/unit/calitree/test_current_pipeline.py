import json
from pathlib import Path

import pytest

from critical.config import CALITREE_SELECTION
from critical.core.optimization.prompt.calitree import CaliTreeJudge, load_current_policy
from critical.core.optimization.prompt.calitree.current import selected_pipeline
from run.calitree_current import cached_predictions, main


def missing_request():
    return {'instruction': 'Move the bowl left.', 'evidence': {}, 'program': None,
            'observation': None, 'interpretation': None, 'vision_record': None,
            'regular_judgment': {'label': 'partial', 'rationale': 'Visible progress remains incomplete.'},
            'local_record': None}


def test_default_selects_exact_shared_v112_stack():
    selected, _ = selected_pipeline()
    policy = load_current_policy()
    assert selected['selected_version'] == 'v112'
    assert policy.artifact['artifact_ref'] == selected['artifacts']['semantic_review']['artifact_ref']
    assert policy.artifact['rubric']['compilation']['version'] == 'semantic-polynomial-v111'
    assert len(policy.artifact['rubric']['clauses']) == 60
    assert len(policy.artifact['rubric']['features']) == 28


def test_changed_selected_component_fails_instead_of_loading_another_version(tmp_path):
    selected = json.loads(CALITREE_SELECTION.read_text())
    selected['artifacts']['semantic_review']['path'] = 'examples/calitree_weighted_semantic_v105/policy.json'
    path = tmp_path/'selection.json'; path.write_text(json.dumps(selected))
    with pytest.raises(ValueError, match='differs'):
        load_current_policy(path)
    selected['selected_version'] = 'v141'; path.write_text(json.dumps(selected))
    with pytest.raises(ValueError, match='v112'):
        load_current_policy(path)


def test_default_missing_evidence_retains_regular_without_any_model_interface():
    judge = CaliTreeJudge()
    result = cached_predictions([missing_request()], judge)[0]
    assert result['pipeline_version'] == 'v112'
    assert result['judgment']['label'] == 'partial' and result['source'] == 'regular_judge'
    assert result['route']['covered'] is False
    with pytest.raises(ValueError, match='references'):
        cached_predictions([{**missing_request(), 'reference': 'yes'}], judge)


def test_canonical_entrypoint_uses_selected_v112_and_explicit_cached_stages(tmp_path, capsys):
    source = tmp_path/'request.json'; source.write_text(json.dumps([missing_request()]))
    out = tmp_path/'predictions'
    main(['--input', str(source), '--output-dir', str(out)])
    result = json.loads((out/'predictions.json').read_text())[0]
    assert result['pipeline_version'] == 'v112' and result['judgment']['label'] == 'partial'
    assert json.loads((out/'config.json').read_text())['new_model_calls'] == 0
    assert (out/'run.log').is_file() and (out/'llm-histories.log').is_file()
