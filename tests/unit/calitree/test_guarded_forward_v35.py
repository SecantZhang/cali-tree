from itertools import product

import pytest

from critical.core.decision.artifacts import save_json
from run import analyze_calitree_guarded_forward_v35 as forward
from run.collect_calitree_guarded_forward_v32 import collect


class Policy:
    def __init__(self):
        self.regular_labels = []

    def resolve(self, program, record, regular, *, corrections=True):
        self.regular_labels.append(regular)
        return {'covered': corrections, 'prediction': 2 if regular == -1 else 0,
                'reason': 'test_policy', 'matches': []}


def inputs():
    return [{'case': k, 'source_group': k, 'program': None, 'features': {}} for k in ('a', 'b')]


def frozen():
    return {k: {'routes': {'v27_split1': {'covered': k == 'a', 'prediction': 2 if k == 'a' else -1}}} for k in ('a', 'b')}


def test_bounds_are_exact_extrema_over_all_regular_labels_and_keep_unresolved():
    gate = Policy()
    result = forward.scenario_table({1: gate}, inputs(), frozen(), {'a': 'no', 'b': 'yes'})
    assert gate.regular_labels == [-1, 0, 1, 2] * 2
    rows = result['cases']
    for baseline in ('regular', 'v27'):
        field = f'accuracy_delta_vs_{baseline}'
        exhaustive = [sum(s[field] for s in combination) for combination in product(*(r['banks']['1'] for r in rows))]
        bounds = result['bounds']['1'][f'versus_{baseline}']
        assert bounds['minimum_correct_delta'] == min(exhaustive)
        assert bounds['maximum_correct_delta'] == max(exhaustive)
    assert set(result['bounds']['1']['versus_regular']['cases_with_possible_loss']) == {'b'}


def test_no_evidence_does_not_create_hypothetical_tree_coverage():
    e = {**inputs()[0], 'features': None}
    gate = Policy()
    for label in (-1, 0, 1, 2):
        selection = forward.route(gate, e, label)
        assert not selection['covered'] and forward.predict(selection, label) == label
    assert gate.regular_labels == []


def test_matched_report_keeps_failed_baseline_case_and_model_provenance(tmp_path, monkeypatch):
    gate = Policy()
    monkeypatch.setattr(forward, 'policies', lambda out: {1: gate})
    monkeypatch.setattr(forward, 'verify_collection', lambda out: {'passed': True})
    examples = inputs()
    save_json(tmp_path / 'inputs.json', examples)
    save_json(tmp_path / 'references.json', {'a': 'no', 'b': 'yes'})
    rows = []
    for e, reference, regular in zip(examples, (0, 2), (0, -1)):
        routes = {f'{v}_split1': {'covered': False, 'prediction': -1} for v in ('v27', 'v28')}
        rows.append({'case': e['case'], 'source_group': e['source_group'], 'reference': reference,
                     'regular': regular, 'v27_split1': regular, 'v28_split1': regular, 'routes': routes})
    save_json(tmp_path / 'full_predictions.json', rows)
    save_json(tmp_path / 'full_results.json', {})
    save_json(tmp_path / 'supplemental_v35/freeze.json', {})
    save_json(tmp_path / 'regular_responses/a.json', {'judgment': {'label': 'no', 'rationale': 'Visible failure.'}, 'error': None})
    save_json(tmp_path / 'regular_responses/b.json', {'judgment': None, 'error': 'CallFailure'})
    result = forward.report(tmp_path)
    arm = result['metrics']['regular_aware_correction_split1']
    assert arm['total'] == 2 and arm['correct'] == 2
    assert result['metrics']['regular']['unresolved'] == 1
    assert result['paired']['1']['regular'] == {'wins': 1, 'losses': 0}


def test_paid_collector_requires_explicit_live_before_accessing_any_state(tmp_path):
    with pytest.raises(ValueError, match='authorization'):
        collect(tmp_path / 'nonexistent')
    assert list(tmp_path.iterdir()) == []


def test_collection_audit_reconstructs_slots_and_rejects_budget_tampering(tmp_path):
    from critical.core.decision.calls import DurableCalls
    from critical.core.decision.compiler import media_inputs
    from run.calitree_aurora_pilot_v29 import IDENTITY, read

    class Engine:
        def generate(self, *args, **kwargs):
            return {'parsed': {'label': 'no', 'rationale': 'Mock evidence.'},
                    'finishReason': 'stop', 'completionTokens': 3, 'promptTokens': 5}

    evidence = {}
    for kind in ('source_image', 'edited_image'):
        path = tmp_path / (kind + '.png')
        path.write_bytes(kind.encode())
        evidence[kind] = str(path)
    examples = [{'case': k, 'instruction': 'Test ' + k, 'evidence': evidence} for k in ('a', 'b')]
    save_json(tmp_path / 'inputs.json', examples)
    calls = DurableCalls(tmp_path / 'ledger', lambda _: Engine(), identity=IDENTITY,
                         max_calls=36, max_completion_tokens=73728, scope_limits={'search': 1, 'final': 0})
    for e in examples:
        value, ref = calls.call('flat_judge', {'instruction': e['instruction']}, forward.task_schema(),
                                template=forward.regular_prompt(), media=media_inputs(evidence),
                                case_id=e['case'], slot='once', max_tokens=2048)
        save_json(tmp_path / 'regular_responses' / (e['case'] + '.json'),
                  {'judgment': value, 'execution_ref': ref, 'error': None})
    report = forward.verify_collection(tmp_path)
    assert report['attempts'] == 2 and report['completion_tokens_or_reserved'] == 6
    budget = read(tmp_path / 'ledger/budget.json')
    budget['limits']['max_calls'] = 37
    save_json(tmp_path / 'ledger/budget.json', budget)
    with pytest.raises(AssertionError):
        forward.verify_collection(tmp_path)


def test_collection_audit_retains_failed_attempt_and_its_token_reservation(tmp_path):
    from critical.core.decision.calls import DurableCalls, CallFailure
    from critical.core.decision.compiler import media_inputs
    from run.calitree_aurora_pilot_v29 import IDENTITY
    class FailedEngine:
        def generate(self, *args, **kwargs):
            raise ConnectionError('Mock failure')
    evidence = {}
    for kind in ('source_image', 'edited_image'):
        path = tmp_path / (kind + '.png')
        path.write_bytes(kind.encode())
        evidence[kind] = str(path)
    e = {'case': 'a', 'instruction': 'Test failure', 'evidence': evidence}
    save_json(tmp_path / 'inputs.json', [e])
    calls = DurableCalls(tmp_path / 'ledger', lambda _: FailedEngine(), identity=IDENTITY,
                         max_calls=36, max_completion_tokens=73728, scope_limits={'search': 1, 'final': 0})
    with pytest.raises(CallFailure):
        calls.call('flat_judge', {'instruction': e['instruction']}, forward.task_schema(),
                   template=forward.regular_prompt(), media=media_inputs(evidence),
                   case_id=e['case'], slot='once', max_tokens=2048)
    save_json(tmp_path / 'regular_responses/a.json', {'judgment': None, 'execution_ref': None, 'error': 'CallFailure'})
    report = forward.verify_collection(tmp_path)
    assert report['attempts'] == 1 and report['completion_tokens_or_reserved'] == 2048
    assert report['outcomes'] == {'transport_error': 1}


def test_historical_cache_requires_same_prompt_and_image_pair(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from critical.core.decision.calls import DurableCalls
    from critical.core.decision.compiler import media_inputs
    from run import audit_calitree_forward_cache_v35 as cache_audit
    from run.calitree_aurora_pilot_v29 import IDENTITY
    class Engine:
        def generate(self, *args, **kwargs):
            return {'parsed': {'label': 'no', 'rationale': 'Mock evidence.'},
                    'finishReason': 'stop', 'completionTokens': 3, 'promptTokens': 5}
    evidence = {}
    for kind in ('source_image', 'edited_image'):
        path = tmp_path / (kind + '.png')
        path.write_bytes(kind.encode())
        evidence[kind] = str(path)
    future = tmp_path / 'forward'
    examples = [{'case': str(i), 'instruction': 'Same instruction', 'evidence': evidence} for i in range(36)]
    save_json(future / 'inputs.json', examples)
    paths = []
    for name in ('matching', 'different_prompt', 'different_image'):
        ledger = tmp_path / name
        calls = DurableCalls(ledger, lambda _: Engine(), identity=IDENTITY, max_calls=36,
                             max_completion_tokens=73728, scope_limits={'search': 1, 'final': 0})
        pair = dict(evidence)
        if name == 'different_image':
            path = tmp_path / 'changed.png'
            path.write_bytes(b'different pixels')
            pair['edited_image'] = str(path)
        calls.call('flat_judge', {'instruction': 'Same instruction'}, forward.task_schema(),
                   template='Other prompt' if name == 'different_prompt' else forward.regular_prompt(),
                   media=media_inputs(pair), case_id='unrelated-id', slot='once', max_tokens=2048)
        paths.append(str(ledger / 'budget.json'))
    monkeypatch.setattr(cache_audit, 'verify', lambda out: None)
    monkeypatch.setattr(cache_audit.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout='\n'.join(paths)))
    result = cache_audit.audit(future, [tmp_path], tmp_path / 'cache_audit')
    assert result['matched_cases'] == 36
    assert all(len(matches) == 1 and '/matching/' in matches[0]['job'] for matches in result['matches'].values())
    assert result['counts']['prompt_schema_or_identity_hash_mismatches'] == 1
    assert result['counts']['different_media_pairs'] == 36
