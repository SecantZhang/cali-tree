"""Source-excluded visual training examples for a calibrated image judge.

Retrieval uses coarse requested operation types, not observed case signatures.
Labels belong only to provided training examples. Query labels and editing-model
metadata are never read or passed to the adjudicator.
"""
from ....decision.artifacts import digest
from ....decision.compiler import media_inputs

VERSION = 'visual-training-examples-v38'
LABELS = ('no', 'partial', 'yes')


def operation_types(program):
    if program is None:
        return frozenset()
    return frozenset(c['kind'] for c in program['checks'] if c['role'] == 'outcome')


def select(pool, query, *, per_label=2):
    if type(per_label) is not int or not 1 <= per_label <= 3:
        raise ValueError('One to three examples per label are supported')
    operations = operation_types(query.get('program'))
    chosen, seen = [], {query['source_group']}
    for label in (0, 1, 2):
        candidates = [e for e in pool if e['reference'] == label and e['source_group'] not in seen]
        candidates.sort(key=lambda e: (-len(operations & operation_types(e.get('program'))),
                                       len(operations ^ operation_types(e.get('program'))),
                                       digest([VERSION, e['source_group'], e['case']])))
        count = 0
        for e in candidates:
            if e['source_group'] in seen:
                continue
            chosen.append(e)
            seen.add(e['source_group'])
            count += 1
            if count == per_label:
                break
        if count != per_label:
            raise ValueError('Insufficient distinct-source training examples for each label')
    return chosen


def request(query, examples=()):
    examples = list(examples)
    if len({e['source_group'] for e in examples}) != len(examples) or any(e['source_group'] == query['source_group'] for e in examples):
        raise ValueError('A query source or sibling cannot be a calibration example')
    if not examples:
        return {'payload': {'instruction': query['instruction']}, 'media': media_inputs(query['evidence'])}
    payload = {'instruction': query['instruction'], 'calibration_examples': []}
    media = []
    for i, e in enumerate(examples, 1):
        if type(e['reference']) is not int or e['reference'] not in (0, 1, 2):
            raise ValueError('Invalid training example label')
        name = f'E{i}'
        payload['calibration_examples'].append({'example_id': name, 'instruction': e['instruction'],
                                                'human_label': LABELS[e['reference']],
                                                'requested_operation_types': sorted(operation_types(e.get('program')))})
        media += [{'type': 'text', 'text': name + ' SOURCE image'}, {'type': 'image', 'path': e['evidence']['source_image']},
                  {'type': 'text', 'text': name + ' EDITED image'}, {'type': 'image', 'path': e['evidence']['edited_image']}]
    media += [{'type': 'text', 'text': 'QUERY SOURCE image'}, {'type': 'image', 'path': query['evidence']['source_image']},
              {'type': 'text', 'text': 'QUERY EDITED image'}, {'type': 'image', 'path': query['evidence']['edited_image']}]
    return {'payload': payload, 'media': media}
