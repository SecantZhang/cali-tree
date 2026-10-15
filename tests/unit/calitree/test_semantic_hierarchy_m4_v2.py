from copy import deepcopy
import json

import pytest

from critical.core.calibration.semantic_hierarchy.features_v2 import synthetic_record, SCOPES
from critical.core.calibration.semantic_hierarchy.rule_search_v2 import SemanticRuleCalibrator
from critical.core.calibration.semantic_hierarchy.routing_v2 import (
    RoutedSemanticJudge, fit_router, scope_values, matches,
)
from critical.core.decision.artifacts import digest


def dataset(prefix, n, mode, *, split_batches=False):
    X = []; y = []; groups = []; batches = []
    for i in range(n):
        label = i % 3
        X.append(synthetic_record(all_requested_grounded='true' if label == 2 else 'false',
                                 any_outcome_direct='true' if label == 2 or label == 1 and mode == 'direct' else 'false',
                                 any_intermediate='true' if label == 1 and mode == 'intermediate' else 'false',
                                 requires_attribute='true'))
        y.append(label); groups.append(prefix + str(i)); batches.append(prefix + str(i // 12 if split_batches else 0))
    return X, y, groups, batches


@pytest.fixture
def fixture():
    a = dataset('expert-fit-', 12, 'intermediate')
    b = dataset('pooled-fit-', 12, 'direct')
    fit = lambda data: SemanticRuleCalibrator().fit(data[0], data[1], source_groups=data[2], source_batches=data[3]).metadata()
    expert, pooled = fit(a), fit(b)
    X, y, groups, batches = dataset('validation-', 24, 'intermediate', split_batches=True)
    comparator = [r['prediction'] for r in SemanticRuleCalibrator.restore(pooled).predict_records(X)]
    router = fit_router({'expert': expert}, X, y, groups, batches, comparator)
    assert router['routes']
    return pooled, {'expert': expert}, router, X, y, groups, batches, comparator


def test_actual_router_selects_qualified_expert_and_restores_exactly(fixture):
    pooled, experts, router, X, y, *_ = fixture
    judge = RoutedSemanticJudge(pooled, experts, router)
    r = judge.predict_records(X)
    assert [v['prediction'] for v in r] == y
    assert all(v['expert_id'] == 'expert' and not v['fallback'] and v['policy_evaluations'] == 1 for v in r)
    restored = RoutedSemanticJudge.restore(json.loads(json.dumps(judge.export())))
    assert restored.predict_records(X) == r


def test_unsupported_mixed_operation_scope_and_missing_evidence_fall_back(fixture):
    pooled, experts, router, X, *_ = fixture
    judge = RoutedSemanticJudge(pooled, experts, router)
    new = deepcopy(X[1]); new['features']['requires_pose'] = 'true'
    r = judge.predict_records([new, None])
    assert r[0]['expert_id'] == 'pooled' and r[0]['route_basis'] == 'unsupported_scope'
    assert r[1]['prediction'] == -1 and r[1]['route_basis'] == 'missing_evidence'


def test_unresolved_expert_uses_exactly_one_pooled_fallback(fixture):
    pooled, experts, router, X, *_ = fixture
    judge = RoutedSemanticJudge(pooled, experts, router)
    x = deepcopy(X[1]); x['features']['any_intermediate'] = 'unknown'
    r = judge.predict_records([x])[0]
    assert r['fallback'] and r['policy_evaluations'] == 2 and r['expert_id'] == 'expert'
    assert r['prediction'] == SemanticRuleCalibrator.restore(pooled).predict_records([x])[0]['prediction']


def test_router_does_not_choose_a_more_favorable_label_from_another_policy(fixture):
    pooled, experts, router, X, *_ = fixture
    judge = RoutedSemanticJudge(pooled, experts, router)
    x = deepcopy(X[1]); x['features'].update(any_intermediate='false', any_outcome_direct='true')
    assert SemanticRuleCalibrator.restore(pooled).predict_records([x])[0]['prediction'] == 1
    r = judge.predict_records([x])[0]
    assert r['prediction'] == 0 and not r['fallback'] and r['policy_evaluations'] == 1


def test_primary_routing_is_invariant_to_observed_quality_and_rejects_labels(fixture):
    pooled, experts, router, X, *_ = fixture
    judge = RoutedSemanticJudge(pooled, experts, router)
    a = deepcopy(X[0]); b = deepcopy(a)
    b['features'].update(all_requested_grounded='true', any_intermediate='unknown')
    assert judge.choose(scope_values(a)) == judge.choose(scope_values(b))
    bad = scope_values(a); bad['reference'] = True
    with pytest.raises(ValueError, match='instruction-scope'):
        judge.choose(bad)


def test_overlap_uses_more_specific_qualified_scope(fixture):
    pooled, experts, _, X, y, groups, batches, comparator = fixture
    for i, x in enumerate(X):
        x['features']['requires_style'] = 'true' if i % 2 else 'false'
        if i % 2 == 0:
            comparator[i] = y[i]
    router = fit_router(experts, X, y, groups, batches, comparator)
    judge = RoutedSemanticJudge(pooled, experts, router)
    route, basis = judge.choose(scope_values(X[1]))
    assert basis == 'validated_instruction_scope' and len(route['conditions']) >= 1
    assert matches(scope_values(X[1]), route['conditions'])


def test_unsupported_pooled_oof_is_not_used_to_manufacture_expert_gain(fixture):
    pooled, experts, _, X, y, groups, batches, comparator = fixture
    router = fit_router(experts, X, y, groups, batches, [-1] * len(X), pooled_supported=[False] * len(X))
    assert not router['routes']
    assert all(r['expert_id'] == 'pooled' for r in RoutedSemanticJudge(pooled, experts, router).predict_records(X))


def test_validation_source_overlap_is_rejected_even_after_hashes_are_recomputed(fixture):
    pooled, experts, router, *_ = fixture
    r = deepcopy(router)
    r['routes'][0]['validation']['source_groups'][0] = experts['expert']['training']['source_groups'][0]
    r['routes'][0]['route_ref'] = digest({k: v for k, v in r['routes'][0].items() if k != 'route_ref'})
    r['router_ref'] = digest({k: v for k, v in r.items() if k != 'router_ref'})
    with pytest.raises(ValueError, match='fitting sources'):
        RoutedSemanticJudge(pooled, experts, r)
