from copy import deepcopy

import pytest

from critical.core.calibration import regular_aware_gate_v35 as aware
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import synthetic_record
from critical.core.decision.calls import BudgetExhausted, CallFailure, ProviderStopped
from critical.core.optimization.prompt.calitree.regular_aware_judge_v35 import RegularAwareJudge
from tests.unit.calitree.test_bound_input_cache import fixture, IDENTITY
from tests.unit.calitree.test_task_coverage import Calls


def values(**changes):
    result = dict.fromkeys(aware.NAMES, False)
    result.update(changes)
    return result


def test_judge_prediction_separates_unsafe_context_without_losing_correct_support():
    positive = [values(judge_predicts_yes=True), values(judge_predicts_partial=True)]
    negative = [values(judge_predicts_no=True)]
    clauses = aware.fit_label(positive, negative)
    assert all(aware.fixed.passes(clauses, v) for v in positive)
    assert not aware.fixed.passes(clauses, negative[0])
    assert any(c['feature'].startswith('judge_predicts_') for cs in clauses for c in cs)
    assert clauses == aware.fit_label(list(reversed(positive)), negative)


def test_fallback_domain_needs_two_sources_and_excludes_training_errors():
    name = 'meaning_progress_requested_endpoint_all'
    positive = [{'source_group': s, 'values': values(**{name: True})} for s in ('a', 'b')]
    negative = [{'values': values()}]
    terms, counts = aware.utility.fit_domain(positive, negative)
    assert terms and counts['covered'] == 2
    assert not any(all(n['values'][c['feature']] == c['value'] for c in t) for n in negative for t in terms)
    assert aware.utility.fit_domain([positive[0], positive[0]], negative)[0] == []
    assert terms == aware.utility.fit_domain(list(reversed(positive)), negative)[0]


class Base:
    def __init__(self, covered=False):
        self.covered = covered

    def select(self, *args):
        return {'covered': self.covered, 'prediction': 2 if self.covered else -1, 'matches': []}

    def export(self):
        return {'mock': True}


class Correction(Base):
    def resolve(self, *args):
        return {'covered': True, 'prediction': 0, 'matches': [], 'regular_needed': True}


def test_partial_to_no_requires_positive_incidental_or_wrong_target_evidence():
    gate = aware.RegularAwareGate(Base(), {str(k): [] for k in (0, 1, 2)}, Correction())
    record = synthetic_record(meaning_available=True, meaning_progress_none_all=True)
    assert not gate.resolve(None, record, 1)['covered']
    for flag in ('meaning_progress_incidental_change_only_all', 'meaning_endpoint_gap_wrong_direction_or_target_all'):
        changed = deepcopy(record)
        changed['features'][flag] = True
        assert gate.resolve(None, changed, 1)['prediction'] == 0
    assert not gate.resolve(None, record, 1, corrections=False)['covered']


def test_regular_failure_keeps_verified_route_and_runtime_rejects_reference_argument():
    gate = aware.RegularAwareGate(Base(True), {str(k): [] for k in (0, 1, 2)}, Correction())
    assert gate.resolve(None, None, -1)['prediction'] == 2
    with pytest.raises(TypeError):
        gate.resolve(None, None, -1, reference=2)


class Policy:
    def __init__(self, covered=True):
        self.covered = covered
        self.inputs = []

    def resolve(self, program, record, regular):
        self.inputs.append((program, record, regular))
        return {'covered': self.covered, 'prediction': 2 if self.covered else -1, 'matches': []}


def test_cached_wrapper_calls_only_regular_and_preserves_model_response_provenance(tmp_path):
    _, evidence, p, _, _, cache = fixture(tmp_path)
    calls, policy = Calls('no'), Policy()
    judge = RegularAwareJudge(calls, policy, evidence_cache=cache, identity=IDENTITY, regular_prompt='regular')
    result = judge.judge(p['instruction'], evidence, case_id='new-id')
    assert [r[0] for r in calls.requests] == ['flat_judge']
    assert calls.requests[0][1] == {'instruction': p['instruction']}
    assert calls.requests[0][3]['template'] == 'regular'
    assert policy.inputs[0][2] == 0 and 'reference' not in policy.inputs[0][1]
    assert result['judgment']['label'] == 'yes' and result['regular_judgment']['label'] == 'no'
    assert result['execution_ref'] is None and result['regular_execution_ref'] == 'execution'
    assert result['evidence_source'] == 'content_cache'


def test_invalid_evidence_uses_exact_regular_response_without_policy(tmp_path):
    _, evidence, p, obs, meaning, _ = fixture(tmp_path)
    obs['image_pair_ref'] = 'wrong-image'
    calls, policy = Calls('partial'), Policy()
    result = RegularAwareJudge(calls, policy).judge(p['instruction'], evidence, program=p,
                                                observation=obs, interpretation=meaning)
    assert result['source'] == 'regular_judge' and result['judgment']['label'] == 'partial'
    assert result['execution_ref'] == 'execution' and result['extraction_error']
    assert policy.inputs == [] and len(calls.requests) == 1


@pytest.mark.parametrize('error', [BudgetExhausted, ProviderStopped])
def test_wrapper_does_not_swallow_budget_or_provider_stop(tmp_path, error):
    _, evidence, p, _, _, cache = fixture(tmp_path)
    class Stop(Calls):
        def call(self, *args, **kwargs):
            raise error('stop')
    with pytest.raises(error):
        RegularAwareJudge(Stop(), Policy(), evidence_cache=cache, identity=IDENTITY).judge(p['instruction'], evidence)


def test_failed_regular_attempt_is_not_retried_and_can_retain_verified_tree(tmp_path):
    _, evidence, p, _, _, cache = fixture(tmp_path)
    class Failed(Calls):
        def call(self, *args, **kwargs):
            self.requests.append(args[0])
            raise CallFailure('mock transport failure')
    calls = Failed()
    result = RegularAwareJudge(calls, Policy(), evidence_cache=cache, identity=IDENTITY).judge(p['instruction'], evidence)
    assert calls.requests == ['flat_judge'] and result['judgment']['label'] == 'yes'
    assert result['regular_error'] == 'CallFailure' and result['regular_judgment']['label'] == 'unresolved'
