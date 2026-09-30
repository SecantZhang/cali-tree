from copy import deepcopy
import json
import pytest
from critical.core.optimization.prompt.calitree.annotation_quality import annotation_review, partition_annotations
from .test_casewise_fitting import Engine
from .casewise_fitting import CasewiseExperiment

REVIEW = {'status': 'uncertain', 'reason': 'Instruction admits two incompatible interpretations', 'reviewed_by': 'reviewer-1'}


def test_explicit_quarantine_retains_originals_and_does_not_infer_from_disagreement():
    labels = {'a': {'target_label': 'yes', 'annotation_review': REVIEW},
              'b': {'target_label': 'no', 'model_prediction': 'yes'}}
    original = deepcopy(labels)
    eligible, quarantined = partition_annotations(labels)
    assert set(eligible) == {'b'} and set(quarantined) == {'a'}
    assert quarantined['a']['original_annotation']['target_label'] == 'yes'
    assert labels == original and annotation_review(labels['b']) == {'status': 'unreviewed'}
    with pytest.raises(ValueError, match='reason'):
        annotation_review({'annotation_review': {'status': 'uncertain', 'reviewed_by': 'reviewer'}})


def test_uncertain_label_cannot_drive_casewise_feedback(tmp_path):
    engine = Engine([])
    with pytest.raises(ValueError, match='Uncertain annotations'):
        CasewiseExperiment(engine, tmp_path).fit('instruction', 'rubric', [], 'yes', annotation_review=REVIEW)
    assert not engine.calls


def test_builder_rejects_reviewed_uncertain_targets_before_calls():
    from critical.core.optimization.prompt.calitree import CaliTreeBuilder
    def forbidden(*args, **kwargs):
        pytest.fail('Quarantined labels must stop before callbacks')
    builder = CaliTreeBuilder(judge=forbidden, optimize=forbidden, extract_components=forbidden,
                              embed=forbidden, merge_prompts=forbidden)
    with pytest.raises(ValueError, match='Uncertain annotations'):
        builder.build(initial_prompt='rubric', samples={'a': {}}, targets={'a': 'yes'}, annotation_reviews={'a': REVIEW})


def test_explicit_uncertain_category_is_quarantined_without_inventing_a_reviewer():
    eligible, quarantine = partition_annotations({'a': {'target_label': 'uncertain'}, 'b': 'uncertain'})
    assert not eligible and set(quarantine) == {'a', 'b'}
    assert quarantine['a']['review']['reviewer_recorded'] is False
    assert 'reviewed_by' not in quarantine['a']['review']


def test_review_cannot_silently_turn_uncertain_target_into_usable_training_data():
    with pytest.raises(ValueError, match='conflicts'):
        partition_annotations({'a': {'target_label': 'uncertain', 'annotation_review': {
            'status': 'usable', 'reason': 'Reviewed', 'reviewed_by': 'reviewer'}}})


def test_pilot_review_is_explicit_bound_and_retains_original_target(tmp_path):
    from .assumption3_probe import apply_pilot_reviews
    row = {'instruction': 'Edit instruction', 'human_label': 'partial',
           'images': [{'sha256': 'a'*64}, {'sha256': 'b'*64}]}
    record = {'instruction': row['instruction'], 'target_label': 'partial',
              'image_sha256': ['a'*64, 'b'*64], 'annotation_review': {**REVIEW, 'category': 'weird_case'}}
    path = tmp_path/'reviews.json'
    path.write_text(json.dumps({'version': 'calitree-pilot-case-reviews-v1', 'cases': {'a': record}}))
    with pytest.raises(ValueError, match='user-reviewed uncertain'):
        apply_pilot_reviews({'a': deepcopy(row)}, reviews_path=path)
    rows = apply_pilot_reviews({'a': deepcopy(row)}, reviews_path=path, allow_uncertain_diagnostic=True)
    assert rows['a']['human_label'] == 'partial'
    assert rows['a']['annotation_review']['status'] == 'uncertain'
    eligible, quarantined = partition_annotations({'a': {'target_label': rows['a']['human_label'],
                                                       'annotation_review': rows['a']['annotation_review']}})
    assert not eligible and set(quarantined) == {'a'}
    changed = {**row, 'images': [{'sha256': 'c'*64}, {'sha256': 'b'*64}]}
    with pytest.raises(ValueError, match='identity mismatch'):
        apply_pilot_reviews({'a': changed}, reviews_path=path)
    untouched = apply_pilot_reviews({'b': deepcopy(row)}, reviews_path=path)
    assert 'annotation_review' not in untouched['b']
