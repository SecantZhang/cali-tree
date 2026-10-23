from copy import deepcopy
from collections import Counter

import pytest

from critical.core.optimization.prompt.calitree import adjudication_examples_v38 as cards
from critical.lm_engine.provider_api import chat_request
from run import calitree_adjudicator_diagnostic_v38 as diagnostic
from tests.unit.calitree.test_task_coverage import program


def example(name, label, kind='absence', source=None):
    return {'case': name, 'source_group': source or name, 'reference': label,
            'instruction': 'A requested edit', 'program': program('A requested edit', kind),
            'evidence': {'source_image': name + '-source.png', 'edited_image': name + '-edited.png'}}


def fixture():
    query = example('query', 1)
    pool = [example(f'{label}-{i}', label, 'absence' if i < 2 else 'spatial_relation') for label in (0, 1, 2) for i in range(4)]
    pool += [example('query-sibling', label, source='query') for label in (0, 1, 2)]
    return query, pool


def test_source_exclusion_balance_operation_matching_and_query_label_independence():
    query, pool = fixture()
    chosen = cards.select(pool, query)
    assert len(chosen) == 6 and Counter(e['reference'] for e in chosen) == {0: 2, 1: 2, 2: 2}
    assert all(e['source_group'] != query['source_group'] for e in chosen)
    assert all(cards.operation_types(e['program']) == {'absence'} for e in chosen)
    changed = {**query, 'reference': 2, 'editing_model': 'secret', 'human_score': 5}
    assert cards.select(pool, changed) == chosen
    assert cards.select(list(reversed(pool)), query) == chosen


def test_request_sanitizes_query_metadata_and_keeps_all_visual_pairs_bound():
    query, pool = fixture()
    chosen = cards.select(pool, query)
    request = cards.request(query, chosen)
    assert set(request['payload']) == {'instruction', 'calibration_examples'}
    assert all(set(e) == {'example_id', 'instruction', 'human_label', 'requested_operation_types'} for e in request['payload']['calibration_examples'])
    assert [m['path'] for m in request['media'] if m['type'] == 'image'][-2:] == list(query['evidence'].values())
    assert len([m for m in request['media'] if m['type'] == 'image']) == 14
    assert request['media'][-4]['text'] == 'QUERY SOURCE image'
    assert request['media'][-2]['text'] == 'QUERY EDITED image'
    assert cards.request({**query, 'reference': 0}, chosen) == request


def test_direct_request_is_unchanged_and_reject_query_or_duplicate_source_examples():
    query, pool = fixture()
    direct = cards.request(query)
    assert direct['payload'] == {'instruction': query['instruction']}
    assert [m['text'] for m in direct['media'] if m['type'] == 'text'] == ['SOURCE image', 'EDITED image']
    with pytest.raises(ValueError, match='source'):
        cards.request(query, [query])
    with pytest.raises(ValueError, match='source'):
        cards.request(query, [pool[0], deepcopy(pool[0])])


def test_insufficient_source_support_is_not_silently_filled_with_query_examples():
    query, _ = fixture()
    with pytest.raises(ValueError, match='Insufficient'):
        cards.select([query], query)


def test_paid_guard_and_exact_sol_wire_settings_without_network(tmp_path):
    with pytest.raises(ValueError, match='authorization'):
        diagnostic.collect(tmp_path / 'not-prepared')
    assert list(tmp_path.iterdir()) == []
    _, payload, _, _ = chat_request('https://api.openai.com/v1', 'dummy-test-token', 'gpt-6.1-sol', [],
                                    8192, None, provider='openai', reasoning_effort='medium')
    assert payload['reasoning_effort'] == 'medium' and 'temperature' not in payload
    assert payload['max_completion_tokens'] == 8192
    assert diagnostic.MAX_REQUESTS == 48 and diagnostic.MAX_OUTPUT == 393216
