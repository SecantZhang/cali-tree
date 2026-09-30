"""Annotation review and quarantine, separate from prediction uncertainty.

Unreviewed annotations retain legacy eligibility but are not certified truth.
Only an explicit review marks a case uncertain; model disagreement is never an
exclusion rule here. Keep the original record for audit and re-adjudication.
"""
from copy import deepcopy


def annotation_review(record):
    value = record.get('annotation_review') if isinstance(record, dict) else None
    if value is None:
        if record == 'uncertain' or (isinstance(record, dict) and record.get('target_label') == 'uncertain'):
            return {'status': 'uncertain', 'reason': 'Record explicitly marks its target uncertain',
                    'source': 'input_annotation', 'reviewer_recorded': False}
        return {'status': 'unreviewed'}
    if not isinstance(value, dict) or value.get('status') not in {'unreviewed', 'usable', 'uncertain'}:
        raise ValueError('annotation_review requires status unreviewed, usable, or uncertain')
    if isinstance(record, dict) and record.get('target_label') == 'uncertain' and value['status'] != 'uncertain':
        raise ValueError('An uncertain target conflicts with a non-uncertain review; adjudicate the target explicitly')
    if value['status'] != 'unreviewed':
        for field in ('reason', 'reviewed_by'):
            if not isinstance(value.get(field), str) or not value[field].strip():
                raise ValueError(f'Annotation review requires {field}')
    return deepcopy(value)


def partition_annotations(records):
    eligible, quarantined = {}, {}
    for case, record in records.items():
        review = annotation_review(record)
        if review['status'] == 'uncertain':
            quarantined[case] = {'review': review, 'original_annotation': deepcopy(record)}
        else:
            eligible[case] = record
    return eligible, quarantined
