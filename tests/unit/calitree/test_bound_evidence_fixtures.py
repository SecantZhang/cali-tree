import json
from pathlib import Path

import pytest

from critical.core.decision.bound_evidence_v2 import derive_record, diagnostic_readout


FIXTURE = json.loads((Path(__file__).parent / 'fixtures/bound_evidence_m1_regressions.json').read_text())


@pytest.mark.parametrize('case', FIXTURE['cases'], ids=lambda row: row['name'])
def test_saved_semantic_regression_fixture(case):
    record = derive_record(case['program'], case['observation'], case['observation']['image_pair_ref'])
    assert diagnostic_readout(record)['label'] == case['expected_diagnostic']
    for name, expected in case['expected_features'].items():
        assert record['features'][name] == expected
