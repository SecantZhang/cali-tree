from copy import deepcopy
import json

import pytest

from critical.core.calibration import evidence_coverage_v20 as base, evidence_support_v21 as supported
from critical.core.decision.artifacts import digest
from tests.unit.calitree.test_evidence_coverage_v20 import simple, guarded_data


def test_envelope_preserves_every_original_local_acceptance_and_verdict():
    data, programs, models = guarded_data(xor=True)
    gate, _ = base.build(models, data, programs); filtered = supported.build(gate, data, programs)
    for row in data:
        a, b = [g.select(programs[row['source_group']], row['features']) for g in (gate, filtered)]
        assert a['covered'] == b['covered'] and a['prediction'] == b['prediction'] == row['reference']


def test_unseen_semantic_state_defers_without_relabeling_tree():
    data, programs, models = simple(); gate, _ = base.build(models, data, programs)
    filtered = supported.build(gate, data, programs)
    record = deepcopy(data[0]['features'])
    # This coordinate is unused by the perfect three-label tree but outside
    # every training region's recorded semantic support.
    record['features']['meaning_identity_evidence_uncertain_all'] = True
    assert gate.select(programs[data[0]['source_group']], record)['covered']
    decision = filtered.select(programs[data[0]['source_group']], record)
    assert not decision['covered'] and decision['reason'] == 'outside_semantic_support'


def test_envelope_never_turns_a_base_rejection_into_an_acceptance():
    data, programs, models = simple(); gate, _ = base.build(models, data, programs)
    filtered = supported.build(gate, data, programs)
    class RejectingGate:
        def select(self, program, record):
            return {'covered': False, 'prediction': -1, 'reason': 'conflicting_supported_experts',
                    'matches': [{'rule_ref': 'deliberately not resolved', 'prediction': 0}]}
    filtered.base = RejectingGate()
    assert filtered.select(programs[data[0]['source_group']], data[0]['features'])['reason'] == 'conflicting_supported_experts'


def test_roundtrip_keeps_complete_model_and_no_source_memberships():
    data, programs, models = simple(); gate, _ = base.build(models, data, programs)
    filtered = supported.build(gate, data, programs); serialized = json.dumps(filtered.export())
    restored = supported.SupportedCoverageGate(json.loads(serialized))
    assert restored.export() == filtered.export()
    assert all(word not in serialized for word in ('source_group', 'distinct request', 'case_id'))


def test_envelope_cannot_smuggle_a_case_identifier_or_drop_a_region():
    data, programs, models = simple(); gate, _ = base.build(models, data, programs)
    artifact = supported.build(gate, data, programs).export()
    key = next(iter(artifact['envelopes']))
    artifact['envelopes'][key]['conditions'] = [{'feature': 'case_id', 'value': True}]
    artifact['artifact_ref'] = digest({k: v for k, v in artifact.items() if k != 'artifact_ref'})
    with pytest.raises(ValueError, match='Undeclared'):
        supported.SupportedCoverageGate(artifact)
    del artifact['envelopes'][key]
    artifact['artifact_ref'] = digest({k: v for k, v in artifact.items() if k != 'artifact_ref'})
    with pytest.raises(ValueError, match='Incomplete'):
        supported.SupportedCoverageGate(artifact)
