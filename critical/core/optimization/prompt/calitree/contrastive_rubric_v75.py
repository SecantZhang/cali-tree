"""Source-excluded matched-edit contrasts and an explicit grading certificate."""
from itertools import combinations

from ....decision.artifacts import digest
from ....decision.compiler import object_schema, enum, array, TEXT
from ....calibration.judge_semantics_v60 import project as intent_features

VERSION = 'matched-edit-semantic-judge-v75'
LABELS = ('no', 'partial', 'yes')


def profile(program):
    kinds = {'outcome:' + c['kind'] for c in program['checks'] if c['role'] == 'outcome'}
    kinds |= {n for n, value in intent_features(program, None).items() if n.startswith('intent_') and n != 'intent_available' and value}
    return frozenset(kinds)


def contrasts(pool, query, excluded_sources):
    excluded = set(excluded_sources) | {query['source_group']}
    grouped = {}
    for example in pool:
        if example['source_group'] not in excluded and example.get('usable', True):
            grouped.setdefault((example['source_group'], example['program']['instruction']), []).append(example)
    output, used = [], set(excluded)
    query_profile = profile(query['program'])
    for lower, upper in ((0, 1), (1, 2)):
        candidates = []
        for (source, _), examples in grouped.items():
            if source in used:
                continue
            for a, b in combinations(examples, 2):
                if {a['reference'], b['reference']} != {lower, upper}:
                    continue
                a, b = sorted((a, b), key=lambda e: e['reference'])
                if a['evidence']['edited_image'] == b['evidence']['edited_image']:
                    continue
                if a.get('edited_pixel_hash') is not None and a['edited_pixel_hash'] == b.get('edited_pixel_hash'):
                    continue
                shared = query_profile & profile(a['program'])
                difference = query_profile ^ profile(a['program'])
                candidates.append(((-len(shared), len(difference), digest([VERSION, source, a['case'], b['case']])), a, b))
        if not candidates:
            raise ValueError('Insufficient source-excluded matched contrasts for both grade boundaries')
        _, a, b = min(candidates, key=lambda row: row[0])
        used.add(a['source_group'])
        output.append((a, b))
    return output


def request(query, selected):
    if len(selected) != 2 or len({a['source_group'] for a, _ in selected}) != 2:
        raise ValueError('Two distinct contrast sources required')
    payload = {'instruction': query['program']['instruction'], 'authorized_changes': query['program']['contract'],
               'requirements': [{k: r[k] for k in ('id', 'description')} for r in query['program']['requirements']],
               'query_checks': [{k: c[k] for k in ('id', 'requirement_ids', 'role', 'kind', 'question', 'target', 'reference', 'expected_state')}
                                for c in query['program']['checks']], 'calibration_contrasts': []}
    media = []
    for i, (a, b) in enumerate(selected, 1):
        if a['source_group'] != b['source_group'] or a['source_group'] == query['source_group'] or a['program']['instruction'] != b['program']['instruction']:
            raise ValueError('Contrast source or instruction mismatch')
        prefix = 'CONTRAST_' + str(i)
        payload['calibration_contrasts'].append({'contrast': prefix, 'instruction': a['program']['instruction'],
                'edited_A_human_label': LABELS[a['reference']], 'edited_B_human_label': LABELS[b['reference']],
                'operation_profile': sorted(profile(a['program']))})
        for name, path in (('SOURCE', a['evidence']['source_image']), ('EDITED_A', a['evidence']['edited_image']), ('EDITED_B', b['evidence']['edited_image'])):
            media += [{'type': 'text', 'text': prefix + ' ' + name}, {'type': 'image', 'path': path}]
    for name, path in (('SOURCE', query['evidence']['source_image']), ('EDITED', query['evidence']['edited_image'])):
        media += [{'type': 'text', 'text': 'QUERY ' + name}, {'type': 'image', 'path': path}]
    return {'payload': payload, 'media': media}


def schema(payload):
    witness = object_schema({'check_id': enum([c['id'] for c in payload['query_checks']]),
                             'state': enum(('true', 'false', 'unknown')), 'source_observation': TEXT, 'edited_observation': TEXT})
    return object_schema({'target_status': enum(('intended_counterpart', 'authorized_transformation', 'partly_corresponding', 'wrong_or_missing', 'uncertain', 'not_relevant')),
        'endpoint_status': enum(('achieved', 'incomplete', 'absent', 'wrong_target_or_direction', 'uncertain')),
        'progress_status': enum(('goal_directed', 'incidental_only', 'none', 'uncertain')),
        'collateral_status': enum(('none_or_minor', 'material_unrequested', 'uncertain')),
        'criterion': enum(('successful_endpoint', 'meaningful_incomplete', 'failed_target_or_goal', 'insufficient_visual_evidence')),
        'witnesses': {**array(witness), 'minItems': 1, 'maxItems': 6}, 'label': enum((*LABELS, 'unresolved')), 'rationale': TEXT})


def validate_certificate(payload, value):
    if set(value) != set(schema(payload)['properties']):
        raise ValueError('Changed semantic certificate fields')
    for field, spec in schema(payload)['properties'].items():
        if 'enum' in spec and value[field] not in spec['enum']:
            raise ValueError('Invalid certificate category')
    witnesses = value['witnesses'];checks = {c['id']: c for c in payload['query_checks']}
    if not isinstance(witnesses, list) or not 1 <= len(witnesses) <= 6:
        raise ValueError('Bound query witnesses required')
    for witness in witnesses:
        if (set(witness) != {'check_id', 'state', 'source_observation', 'edited_observation'} or
                witness['check_id'] not in checks or witness['state'] not in ('true', 'false', 'unknown') or
                any(not isinstance(witness[k], str) or not witness[k].strip() for k in ('source_observation', 'edited_observation'))):
            raise ValueError('Invalid query witness')
    if not any(checks[w['check_id']]['role'] == 'outcome' for w in witnesses):
        raise ValueError('A requested outcome witness is required')
    known_outcomes=[w for w in witnesses if checks[w['check_id']]['role']=='outcome' and w['state']!='unknown']
    expected = {'no': 'failed_target_or_goal', 'partial': 'meaningful_incomplete',
                'yes': 'successful_endpoint', 'unresolved': 'insufficient_visual_evidence'}
    if value['criterion'] != expected[value['label']] or not isinstance(value['rationale'], str) or not value['rationale'].strip():
        raise ValueError('Certificate criterion and grade disagree')
    if value['label'] == 'yes' and (value['endpoint_status'] != 'achieved' or value['target_status'] in ('wrong_or_missing', 'uncertain', 'partly_corresponding') or value['collateral_status'] != 'none_or_minor'):
        raise ValueError('Yes lacks an endpoint/identity/preservation warrant')
    if value['label']=='yes':
        supported={rid for w in known_outcomes if w['state']==checks[w['check_id']]['expected_state'] for rid in checks[w['check_id']]['requirement_ids']}
        if supported!={r['id'] for r in payload['requirements']}:
            raise ValueError('Yes lacks a positive endpoint witness for every requirement')
    if value['label'] == 'partial' and not (value['progress_status'] == 'goal_directed' or
            (value['endpoint_status'] == 'achieved' and (value['collateral_status'] == 'material_unrequested' or value['target_status'] == 'partly_corresponding'))):
        raise ValueError('Partial lacks meaningful fulfillment')
    if value['label']=='partial' and not known_outcomes:
        raise ValueError('Partial cannot rely only on unknown outcome evidence')
    if value['label']=='partial' and (value['target_status']=='wrong_or_missing' or value['endpoint_status']=='wrong_target_or_direction'):
        raise ValueError('Partial cannot treat a wrong target/direction as meaningful fulfillment')
    if value['label'] == 'no' and not (value['target_status'] == 'wrong_or_missing' or value['endpoint_status'] == 'wrong_target_or_direction' or
            (value['endpoint_status'] == 'absent' and value['progress_status'] in ('none', 'incidental_only'))):
        raise ValueError('No lacks affirmative failure evidence')
    if value['label']=='no' and not any(w['state']!=checks[w['check_id']]['expected_state'] for w in known_outcomes):
        raise ValueError('No lacks an explicitly failed requested outcome witness')
    return value
