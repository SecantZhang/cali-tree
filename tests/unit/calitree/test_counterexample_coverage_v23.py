from copy import deepcopy
import json

import pytest

from critical.core.calibration import counterexample_coverage_v23 as rejection
from critical.core.calibration import evidence_coverage_v20 as base, evidence_support_v21 as support
from critical.core.decision.artifacts import digest
from tests.unit.calitree.test_evidence_coverage_v20 import simple


def fixture():
    data, programs, models = simple(); original, _ = base.build(models, data, programs)
    gate = support.build(original, data, programs)
    positives = [{'case': r['case'], 'program': programs[r['source_group']], 'features': r['features'], 'reference': r['reference']} for r in data]
    # A physical cue unused by the expert and semantic filter distinguishes
    # these reviewed errors without changing an expert's existing prediction.
    f = next(k for k in base.FEATURES if k.startswith('intermediate_contact_unknown_all'))
    negative = deepcopy(positives[0]); negative['case'] = 'reviewed-error'; negative['reference'] = 1
    negative['features']['features'][f] = True
    assert gate.select(negative['program'], negative['features'])['prediction'] == 0
    return gate, positives, [negative], f


def test_reviewed_error_rejected_and_all_protected_routes_kept():
    gate, positives, negatives, _ = fixture(); calibrated, report = rejection.fit(gate, positives, negatives)
    assert report['rejected_errors'] == 1 and report['clauses'] == 1
    assert not calibrated.select(negatives[0]['program'], negatives[0]['features'])['covered']
    for p in positives:
        assert calibrated.select(p['program'], p['features']) == gate.select(p['program'], p['features'])


def test_rejection_is_feature_based_and_survives_id_renaming():
    gate, positives, negatives, feature = fixture(); a, _ = rejection.fit(gate, positives, negatives)
    changed = deepcopy(positives); changed_negatives = deepcopy(negatives)
    for i, p in enumerate(changed + changed_negatives):
        p['case'] = f'unrelated-id-{i}'
    b, _ = rejection.fit(gate, list(reversed(changed)), changed_negatives)
    assert a.export() == b.export()
    probe = deepcopy(positives[3]['features']); probe['features'][feature] = True
    assert not a.select(positives[3]['program'], probe)['covered']
    serialized = json.dumps(a.export())
    assert 'reviewed-error' not in serialized and 'case_id' not in serialized


def test_identical_observable_inputs_cannot_be_blacklisted_by_case_id():
    gate, positives, negatives, _ = fixture()
    negatives[0]['features'] = deepcopy(positives[0]['features'])
    with pytest.raises(ValueError, match='indistinguishable'):
        rejection.fit(gate, positives, negatives)


def test_empty_protection_and_mislabeled_calibration_groups_fail():
    gate, positives, negatives, _ = fixture()
    with pytest.raises(ValueError, match='protected'):
        rejection.fit(gate, [], negatives)
    with pytest.raises(ValueError, match='Calibration groups'):
        rejection.fit(gate, positives, [positives[0]])


def test_empty_error_set_is_exact_passthrough():
    gate, positives, _, _ = fixture(); calibrated, report = rejection.fit(gate, positives, [])
    assert report['clauses'] == 0
    for p in positives:
        assert calibrated.select(p['program'], p['features']) == gate.select(p['program'], p['features'])


def test_existing_rejections_cannot_become_acceptances():
    gate, positives, negatives, _ = fixture(); calibrated, _ = rejection.fit(gate, positives, negatives)
    p = positives[0]
    assert calibrated.select(p['program'], None) == gate.select(p['program'], None)


def test_roundtrip_and_declared_predicate_contract():
    gate, positives, negatives, _ = fixture(); calibrated, _ = rejection.fit(gate, positives, negatives)
    artifact = json.loads(json.dumps(calibrated.export()))
    restored = rejection.RejectionCoverageGate(artifact)
    assert restored.export() == calibrated.export()
    artifact['support_clauses'][0][0]['feature'] = 'source_group'
    artifact['artifact_ref'] = digest({k:v for k,v in artifact.items() if k != 'artifact_ref'})
    with pytest.raises(ValueError, match='Undeclared'):
        rejection.RejectionCoverageGate(artifact)


def test_two_literal_clause_preserves_two_distinct_positive_patterns():
    gate, positives, negatives, f = fixture()
    g = 'intermediate_orientation_not_applicable_all'
    # Every positive has f OR g; the error has neither. The expert's semantic
    # prediction and all previous semantic-support predicates remain unchanged.
    for i, p in enumerate(positives):
        p['features']['features'][f] = i % 2 == 0
        p['features']['features'][g] = i % 2 != 0
    negatives[0]['features']['features'][f] = False
    negatives[0]['features']['features'][g] = False
    calibrated, report = rejection.fit(gate, positives, negatives)
    assert report['literal_tests'] == 2
    assert not calibrated.select(negatives[0]['program'], negatives[0]['features'])['covered']
    with pytest.raises(ValueError, match='clause-size'):
        rejection.fit(gate, positives, negatives, rejection.Config(max_literals=1))
    with pytest.raises(ValueError, match='search budget'):
        rejection.fit(gate, positives, negatives, rejection.Config(max_states_per_example=1))
