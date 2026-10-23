import numpy as np

from critical.core.calibration.semantic_hierarchy.portable_features_v8 import synthetic_record
from run import calitree_accuracy_headroom_v37 as headroom
from tests.unit.calitree.test_task_coverage import program


class Expert:
    def predict_records(self, records):
        return [{'prediction': 2 if r is not None else -1} for r in records]


def test_encoding_never_uses_case_source_category_editor_or_reference_labels():
    row = {'case': 'a', 'source_group': 'source', 'program': program('Edit'),
           'features': synthetic_record(meaning_available=True), 'reference': 0, 'regular': 1}
    changed = {**row, 'case': 'b', 'source_group': 'other', 'reference': 2, 'task': 'different', 'editor': 'different'}
    names, encoded, actions = headroom.encoded([row, changed], {'fixed': Expert()})
    assert np.array_equal(encoded[0], encoded[1]) and actions == [[1, 2], [1, 2]]
    assert not any(n in names for n in ('case', 'source_group', 'reference', 'task', 'editor'))


def test_oracle_is_only_action_availability_and_uses_full_denominator():
    examples = [{'case': 'a', 'cohort': 'pilot80', 'reference': 0},
                {'case': 'b', 'cohort': 'forward36', 'reference': 1}]
    result = headroom.headroom(examples, [[0, 2], [-1, 2]])
    assert result['all']['oracle_correct'] == 1 and result['all']['total'] == 2
    assert result['all']['unavailable_correct_label_cases'] == ['b']
    assert result['all']['strictly_over_85_percent_requires'] == 2
