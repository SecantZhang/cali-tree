from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from critical.core.calibration.facet_selector_v162 import FacetSelector, LABELS
from critical.core.calibration import facet_runtime_v166 as runtime
from critical.core.decision import facet_observation_v165 as facts
from critical.core.optimization.prompt.calitree import facet_semantic_judge_v166 as judge_module
from tests.unit.calitree.test_facet_observation_v165 import inputs, value


def setup(tmp_path, monkeypatch):
    p, evidence, hashes, pair = inputs(tmp_path)
    names = ['facet_'+label+'_outcome_ready' for label in LABELS]+['view_disagrees']
    X = np.zeros((9, 4), dtype=bool); y = np.repeat(np.arange(3), 3); base = y.copy(); base[6:] = 0
    for i, grade in enumerate(y):
        X[i, grade] = True; X[i, 3] = grade == 2
    model = FacetSelector(names).fit(X, y, base=base, eligible=np.ones(9, dtype=bool), groups=list('abcdefghi'),
        protected_X=[[False, False, True, False]], protected_y=np.array([0]), protected_base=np.array([0]), protected_eligible=np.array([True]))
    state = {'disagrees': True, 'covered': True}
    class Base:
        def resolve_bound(self, *args, **kwargs):
            return {'covered': state['covered'], 'prediction': 0 if state['covered'] else 1,
                    'reason': 'fixture-parent', 'class_support': [.8, .1, .1]}
    parent = SimpleNamespace(artifact={'artifact_ref': 'fixture-parent'}, base=Base(),
        review_route=lambda route: False, _resolve_from_base=lambda prior, args, record: prior)
    artifact = model.artifact()
    binding = {'fold': 5, 'deployment_parent_artifact_ref': parent.artifact['artifact_ref'],
        'selector_artifact_ref': artifact['artifact_ref'], 'priority': 'learned_semantic_precedence', 'legacy_float32_border': .5}
    exported = runtime.FacetRegionPolicy.export(parent, artifact, 'learned_semantic_precedence', training_binding=binding)
    policy = runtime.FacetRegionPolicy(parent, exported)
    def flags(*args, **kwargs):
        return {'view_disagrees': state['disagrees']}
    monkeypatch.setattr(runtime, 'legacy_values', flags); monkeypatch.setattr(judge_module, 'legacy_values', flags)
    record = facts.bind(p, pair, facts.make_profile(), 'case', hashes, value(),
        facts.request_ref(p, facts.make_profile(), 'case', facts.media_identity(hashes)))
    count = []
    observer = SimpleNamespace(profile=facts.make_profile(), observe=lambda *args, **kwargs: (count.append(1), record)[1])
    extractor = SimpleNamespace(extract=lambda *args, **kwargs: ({}, {}, pair))
    judge = judge_module.FacetSemanticJudge(policy, facet_observer=observer, extractor=extractor)
    kwargs = {'case_id': 'case', 'program': p, 'observation': {}, 'interpretation': {}, 'vision_record': {},
        'regular_judgment': {'label': 'partial', 'rationale': 'fixture regular'}, 'local_record': None}
    return p, evidence, kwargs, judge, state, count, record, policy


def test_inference_routes_only_when_a_legacy_region_can_match_and_calls_once(tmp_path, monkeypatch):
    p, evidence, kwargs, judge, state, count, _, _ = setup(tmp_path, monkeypatch)
    state['disagrees'] = False
    result = judge.judge(p['instruction'], evidence, **kwargs)
    assert result['judgment']['label'] == 'no' and not count
    assert result['facet_observation_status'] == 'outside_semantic_region'
    state['disagrees'] = True
    result = judge.judge(p['instruction'], evidence, **kwargs)
    assert result['judgment']['label'] == 'yes' and len(count) == 1
    assert result['source'] == 'semantic_facet_rule' and result['route']['covered']
    assert 'class_support' not in result['route']


def test_missing_or_foreign_records_preserve_parent_without_resampling(tmp_path, monkeypatch):
    p, evidence, kwargs, judge, state, count, record, _ = setup(tmp_path, monkeypatch)
    result = judge.judge(p['instruction'], evidence, facet_record=None, **kwargs)
    assert result['judgment']['label'] == 'no' and not count
    wrong = deepcopy(record); wrong['image_pair_ref'] = 'different-pair'
    result = judge.judge(p['instruction'], evidence, facet_record=wrong, **kwargs)
    assert result['judgment']['label'] == 'no' and not count and result['route']['covered']
    assert result['route']['facet_review_error'] == 'invalid_or_unbound_facet_evidence'
    state['covered'] = False
    result = judge.judge(p['instruction'], evidence, **kwargs)
    assert result['judgment']['label'] == 'partial' and result['source'] == 'regular_judge' and not count


def test_fold_specific_evaluation_selector_cannot_deploy_on_full_parent(tmp_path, monkeypatch):
    _, _, _, _, _, _, _, policy = setup(tmp_path, monkeypatch)
    bad = deepcopy(policy.artifact['training_binding']); bad['fold'] = 0; bad['deployment_parent_artifact_ref'] = None
    with pytest.raises(ValueError, match='full-fit selector'):
        runtime.FacetRegionPolicy.export(policy.parent, policy.artifact['selector'], policy.artifact['priority'], training_binding=bad)
