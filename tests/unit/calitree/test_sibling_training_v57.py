import pytest

from run import calitree_sibling_training_v57 as sibling


def test_sibling_collection_requires_new_authorization_before_any_state_access(tmp_path):
    out = tmp_path / 'not-created'
    with pytest.raises(ValueError, match='authorization'):
        sibling.collect(out, live=True)
    assert not out.exists()
    assert sibling.MAX_CALLS == 1620 and sibling.MAX_OUTPUT == 14376960
    assert sibling.MAX_CALLS == sibling.CASES * 3
    assert sibling.MAX_OUTPUT == sibling.CASES * sibling.CASE_CAP


def test_shared_stop_latch_survives_late_success_and_resets_only_nonterminal_failure_count(tmp_path):
    circuit = sibling.StopCircuit(tmp_path / 'stop.json')
    circuit.failure(RuntimeError('SSL error'))
    circuit.failure(RuntimeError('SSL error'))
    circuit.success()
    circuit.failure(RuntimeError('SSL error'))
    circuit.check()
    circuit.failure(RuntimeError('SSL error'))
    circuit.failure(RuntimeError('SSL error'))
    with pytest.raises(RuntimeError, match='stop latch'):
        circuit.check()
    circuit.success()
    with pytest.raises(RuntimeError, match='stop latch'):
        circuit.check()
    assert sibling.StopCircuit(tmp_path / 'stop.json').stopped


def test_provider_rejection_stops_all_new_work_immediately(tmp_path):
    circuit = sibling.StopCircuit(tmp_path / 'stop.json')
    circuit.failure(RuntimeError('HTTP 401'))
    assert circuit.stopped == 'provider_rejected'
