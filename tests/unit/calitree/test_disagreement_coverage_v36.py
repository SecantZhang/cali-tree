from copy import deepcopy

import pytest

from critical.core.calibration import disagreement_coverage_v36 as risk
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import synthetic_record
from critical.core.decision.artifacts import digest
from tests.unit.calitree.test_task_coverage import program


class Parent:
    def __init__(self, covered=True):
        self.covered = covered

    def resolve(self, *args, **kwargs):
        return {'covered': self.covered, 'prediction': 1 if self.covered else -1, 'matches': []}

    def export(self):
        return {'mock_parent': True}


def row(source, *, absence=True, identity=True, reference=1, regular=2):
    p = program('Generic requested edit', kind='absence' if absence else 'spatial_relation')
    return {'program': p, 'features': synthetic_record(meaning_available=True, identity_all_true_all=identity),
            'regular': regular, 'reference': reference, 'source_group': source}


def fitted():
    parent = Parent()
    positive = [row('correct-removal', identity=False), row('correct-spatial', absence=False)]
    negative = row('harmful-removal', reference=2)
    gate = risk.fit(parent, risk.prepare(parent, positive), risk.prepare(parent, [negative]))
    return parent, positive, negative, gate


def test_short_semantic_veto_removes_harm_and_retains_correct_counterexamples():
    _, positive, negative, gate = fitted()
    for e in positive:
        assert gate.resolve(e['program'], e['features'], e['regular'])['covered']
    result = gate.resolve(negative['program'], negative['features'], 2)
    assert not result['covered'] and result['reason'] == 'outside_disagreement_support'
    assert result['rejected_route']['prediction'] == 1 and result['regular_prediction'] == 2
    assert gate.support['training_counts']['1:2']['rejected_harmful'] == 1
    assert sum(len(cs) for cs in gate.support['clauses']['1:2']) <= 2


def test_agreement_failed_regular_other_pairs_and_parent_deferral_remain_unchanged():
    parent, _, negative, gate = fitted()
    for regular in (-1, 0, 1):
        assert gate.resolve(negative['program'], negative['features'], regular) == parent.resolve()
    parent.covered = False
    assert gate.resolve(negative['program'], negative['features'], 2) == parent.resolve()


def test_inseparable_harm_is_disclosed_without_case_or_source_exceptions():
    parent = Parent()
    positive, negative = row('positive'), row('negative', reference=2)
    gate = risk.fit(parent, risk.prepare(parent, [positive]), risk.prepare(parent, [negative]))
    assert gate.support['training_counts']['1:2']['unseparated_harmful'] == 1
    assert gate.resolve(negative['program'], negative['features'], 2)['covered']
    assert 'positive' not in str(gate.support) and 'negative' not in str(gate.support)


def test_both_wrong_is_not_a_harmful_override_target_and_no_positives_do_not_blanket_veto():
    parent = Parent()
    positive, both_wrong, harmful = row('positive'), row('both', reference=0), row('harm', reference=2)
    protected = risk.prepare(parent, [positive])
    assert risk.fit(parent, protected, risk.prepare(parent, [both_wrong])).support == risk.fit(parent, protected, []).support
    gate = risk.fit(parent, [], risk.prepare(parent, [harmful]))
    assert gate.resolve(harmful['program'], harmful['features'], 2)['covered']
    assert gate.support['training_counts']['1:2']['unseparated_harmful'] == 1


def test_order_invariance_invalid_protection_and_runtime_reference_rejected():
    parent, positive, negative, gate = fitted()
    assert gate.support == risk.fit(parent, list(reversed(risk.prepare(parent, positive))), risk.prepare(parent, [negative])).support
    with pytest.raises(ValueError, match='correct'):
        risk.fit(parent, risk.prepare(parent, [negative]), [])
    with pytest.raises(TypeError):
        gate.resolve(negative['program'], negative['features'], 2, reference=2)
    with pytest.raises(ValueError, match='regular'):
        gate.resolve(negative['program'], negative['features'], True)


def test_roundtrip_and_predicate_whitelist():
    from tests.unit.calitree.test_semantic_regions_v26 import fixture
    rows, programs, _, original = fixture()
    shared, _ = risk.aware.fixed.shared.build(original, rows, programs)
    protected = [{'prediction': r['reference'], 'reference': r['reference'],
                  'values': risk.aware.fixed.shared.evidence.feature_values(programs[r['source_group']], r['features'])} for r in rows]
    verified = risk.aware.fixed.VerifiedRegionGate(shared, risk.aware.fixed.fit_verifier(protected, []))
    parent = risk.aware.RegularAwareGate(verified, {str(k): [] for k in (0, 1, 2)}, risk.aware.utility.fit(verified, []))
    gate = risk.fit(parent, [], [])
    assert risk.DisagreementCoverageGate.restore(gate.export()).export() == gate.export()
    artifact = deepcopy(gate.export())
    artifact['support']['clauses']['1:2'] = [[{'feature': 'case_id', 'value': False}]]
    artifact['support']['artifact_ref'] = digest({k: v for k, v in artifact['support'].items() if k != 'artifact_ref'})
    artifact['artifact_ref'] = digest({k: v for k, v in artifact.items() if k != 'artifact_ref'})
    with pytest.raises(ValueError, match='predicate'):
        risk.DisagreementCoverageGate.restore(artifact)


def test_protected_judge_variants_prevent_new_loss_when_regular_changes_its_mind():
    from run.calitree_disagreement_coverage_v36r1 import protected_variants
    parent = Parent()
    local = row('local', regular=1)
    negative = row('new-source', reference=2, regular=2)
    # The actual local judgment agrees, so disagreement-only preparation would
    # omit it. A later Yes draw must not let the added guard lose this Partial.
    assert risk.prepare(parent, [local]) == []
    protected = protected_variants(parent, [local])
    gate = risk.fit(parent, protected, risk.prepare(parent, [negative]))
    for regular in (-1, 0, 1, 2):
        assert gate.resolve(local['program'], local['features'], regular)['covered']
    assert gate.support['training_counts']['1:2']['unseparated_harmful'] == 1
