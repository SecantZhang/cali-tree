import pytest

from critical.core.optimization.prompt.calitree.verified_semantic_judge import VerifiedSemanticJudge
from tests.unit.calitree.test_bound_input_cache import fixture, IDENTITY
from tests.unit.calitree.test_task_coverage import Calls


class Policy:
    def __init__(self):
        self.modes = []

    def resolve(self, program, record, regular, *, corrections=True):
        self.modes.append(corrections)
        return {'covered': corrections, 'prediction': 2 if corrections else -1, 'matches': []}


@pytest.mark.parametrize('enabled', [False, True])
def test_serving_selects_frozen_arm_with_one_regular_call(tmp_path, enabled):
    _, evidence, p, _, _, cache = fixture(tmp_path)
    calls, policy = Calls('no'), Policy()
    kwargs = {'enable_corrections': True} if enabled else {}
    result = VerifiedSemanticJudge(calls, policy, evidence_cache=cache, identity=IDENTITY, **kwargs).judge(p['instruction'], evidence)
    assert policy.modes == [enabled]
    assert len(calls.requests) == 1 and calls.requests[0][0] == 'flat_judge'
    assert result['judgment']['label'] == ('yes' if enabled else 'no')
    assert result['source'] == ('verified_semantic_policy' if enabled else 'regular_judge')
    assert result['regular_judgment']['label'] == 'no' and result['regular_execution_ref'] == 'execution'


def test_correction_mode_does_not_accept_truthy_strings():
    with pytest.raises(ValueError, match='Boolean'):
        VerifiedSemanticJudge(Calls(), Policy(), enable_corrections='false')
