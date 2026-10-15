"""Independent M2–M4 prediction, support, metric, and nested-split audit."""
import argparse
from collections import Counter
from fractions import Fraction
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from run.calitree_single_call import ROOT, read, fingerprint


def reference_predict(policy, record):
    if record is None or policy is None:
        return -1
    bounds = {}
    for boundary in ('yes', 'partial'):
        lows, highs = [], []
        for clause in policy[boundary]:
            lows.append(all(record['features'][a['feature']] == a['test'] for a in clause))
            highs.append(all(record['features'][a['feature']] in (a['test'], 'unknown') for a in clause))
        bounds[boundary] = any(lows), any(highs)
    low = 2 if bounds['yes'][0] else 1 if bounds['partial'][0] else 0
    high = 2 if bounds['yes'][1] else 1 if bounds['partial'][1] else 0
    return low if low == high else -1


def check_metrics(predictions, rows, actual):
    y = [r['reference'] for r in rows]; labels = ('no', 'partial', 'yes')
    tp = [sum(p == t == k for p, t in zip(predictions, y)) for k in range(3)]
    assert actual['total'] == len(rows) and actual['correct'] == sum(tp)
    assert actual['accuracy'] == sum(tp) / len(rows) and actual['unresolved'] == predictions.count(-1)
    macro = Fraction()
    for k, name in enumerate(labels):
        n, predicted = y.count(k), predictions.count(k)
        assert actual['per_class'][name]['support'] == n
        assert actual['per_class'][name]['correct'] == tp[k]
        assert actual['per_class'][name]['predicted'] == predicted
        assert actual['per_class'][name]['recall'] == tp[k] / n
        macro += Fraction(2 * tp[k], n + predicted) / 3
    assert abs(actual['macro_f1'] - float(macro)) < 1e-12


def check_policy(policy, rows):
    selected = [r for r in rows if r['source_group'] in policy['training']['source_groups']]
    selected.sort(key=lambda r: r['source_group'])
    assert [r['source_group'] for r in selected] == policy['training']['source_groups']
    assert [r['batch'] for r in selected] == policy['training']['source_batches']
    assert digest([r['features'] for r in selected]) == policy['training']['feature_ref']
    assert digest([r['reference'] for r in selected]) == policy['training']['target_ref']
    assert digest({k: v for k, v in policy.items() if k != 'artifact_ref'}) == policy['artifact_ref']
    preds = [reference_predict(policy, r['features']) for r in selected]
    check_metrics(preds, selected, policy['training']['metrics'])
    for boundary in ('yes', 'partial'):
        for clause, support in zip(policy[boundary], policy['support'][boundary]):
            covered = [r for r in selected if r['features'] is not None and all(r['features']['features'][a['feature']] == a['test'] for a in clause)]
            assert len({r['source_group'] for r in covered}) == support['distinct_sources']
            assert dict(Counter(r['batch'] for r in covered)) == support['originating_batches']
    return preds


def reference_route(context, record, scope_flags, operation_kinds):
    if context['pooled'] is None:
        return -1, 'pooled', True, None
    if record is None:
        return -1, 'pooled', True, None
    scope = {k: record['features'][k] == 'true' for k in scope_flags}
    sig = [k for k in operation_kinds if scope['requires_' + k]]
    for route in context['router']['routes']:
        if all(scope[c['flag']] == c['value'] for c in route['conditions']) and sig in route['supported_operation_signatures']:
            p = reference_predict(context['experts'][route['expert_id']], record)
            return (reference_predict(context['pooled'], record) if p < 0 else p,
                    route['expert_id'], p < 0, route['route_ref'])
    return reference_predict(context['pooled'], record), 'pooled', True, None


def audit(output):
    from critical.core.calibration.semantic_hierarchy.features_v2 import SCOPES, SCOPE_KINDS
    m, data, result = read(output / 'manifest.json'), read(output / 'data.json'), read(output / 'results.json')
    assert digest(m) == read(output / 'seal.json')['manifest_ref'] and digest(data) == m['data_ref']
    for p, h in m['source_hashes'].items():
        assert fingerprint(p) == h, p
    for rel, h in m['code_hashes'].items():
        assert fingerprint(ROOT / rel) == fingerprint(output / 'source_snapshot' / rel) == h, rel
    training, dev = data['train'], data['validation']; all_sources = {r['source_group'] for r in training}
    final_sources = {r['group'] for r in read(ROOT / 'logs/exps/261014-semantic-hierarchy-m0-fifty-v1/splits/test.json')['cases']}
    assert len(training) == len(all_sources) == 48 and len(dev) == 12
    assert not final_sources & ({r['source_group'] for r in training + dev})
    fits = {read(p)['fit_ref']: read(p) for p in (output / 'fits').glob('*/fit.json')}
    policies = {}; fit_count = 0; policy_count = 0
    for fit in fits.values():
        fit_count += 1
        assert set(fit['fit_sources']) <= all_sources
        for p in fit['policies']:
            check_policy(p, training); policies[p['artifact_ref']] = p; policy_count += 1
    total_prediction_checks = 0; route_checks = 0; inner_splits = 0; outer_cases = []
    contexts = [(k, f['context'], [r for r in training if r['case'] in f['evaluation_cases']], f['result']) for k, f in result['folds'].items()]
    contexts.append(('full_training', result['final_context'], dev, result['development12']))
    for name, context, evaluation, scores in contexts:
        eval_sources = {r['source_group'] for r in evaluation}; fitting_sources = set(context['fit_sources'])
        assert not eval_sources & fitting_sources
        fit_rows = [r for r in training if r['source_group'] in fitting_sources]
        base_oof = {}; supported_oof = {}
        for inner in context['inner_pooled_oof']:
            inner_splits += 1
            assert not set(inner['fit_sources']) & set(inner['validation_sources'])
            assert not eval_sources & (set(inner['fit_sources']) | set(inner['validation_sources']))
            assert set(inner['fit_sources']) | set(inner['validation_sources']) == fitting_sources
            f = fits[inner['fit_ref']]; p = f['policies'][0] if f['policies'] else None
            rows = [r for r in fit_rows if r['case'] in inner['validation_cases']]
            preds = [reference_predict(p, r['features']) for r in rows]
            assert preds == inner['predictions']
            for r, prediction in zip(rows, preds):
                base_oof[r['source_group']] = prediction; supported_oof[r['source_group']] = p is not None
        assert set(base_oof) == fitting_sources
        for route in context['router']['routes']:
            route_checks += 1
            expert = context['experts'][route['expert_id']]
            assert set(expert['training']['source_groups']) <= fitting_sources
            v = route['validation']; ids = set(v['source_groups'])
            assert not ids & set(expert['training']['source_groups'])
            assert ids <= fitting_sources and not ids & eval_sources
            selected = [r for r in fit_rows if r['source_group'] in ids]
            assert all(supported_oof[r['source_group']] for r in selected)
            assert dict(Counter(r['batch'] for r in selected)) == v['source_batches']
            for r in selected:
                assert all((r['features']['features'][c['flag']] == 'true') == c['value'] for c in route['conditions'])
            pred = [reference_predict(expert, r['features']) for r in selected]
            base = [base_oof[r['source_group']] for r in selected]
            combined = [p if p >= 0 else b for p, b in zip(pred, base)]
            check_metrics(pred, selected, v['expert_metrics'])
            check_metrics(base, selected, v['pooled_oof_metrics'])
            check_metrics(combined, selected, v['routed_metrics'])
            assert min(c['correct'] for c in v['expert_metrics']['per_class'].values()) >= 1
        p = [reference_predict(context['pooled'], r['features']) for r in evaluation]
        routes = [reference_route(context, r['features'], SCOPES, SCOPE_KINDS) for r in evaluation]
        assert p == scores['pooled']
        for expected, actual in zip(routes, scores['routed']):
            assert expected == (actual['prediction'], actual['expert_id'], actual['fallback'], actual['route_ref'])
        check_metrics(p, evaluation, scores['pooled_metrics'])
        check_metrics([x[0] for x in routes], evaluation, scores['routed_metrics'])
        for i, r in enumerate(evaluation):
            bank = [context['pooled'], *context['experts'].values()]
            oracle = any(reference_predict(policy, r['features']) == r['reference'] for policy in bank)
            assert oracle == scores['oracle_correct'][i]
        total_prediction_checks += len(evaluation) * (2 + len(context['experts']))
        if name != 'full_training':
            outer_cases.extend(r['case'] for r in evaluation)
    assert Counter(outer_cases) == Counter(r['case'] for r in training)
    expected_p = [r['pooled'] for r in result['oof_cases']]; expected_r = [r['routed']['prediction'] for r in result['oof_cases']]
    assert [r['case'] for r in result['oof_cases']] == [r['case'] for r in training]
    check_metrics(expected_p, training, result['pooled_oof_metrics'])
    check_metrics(expected_r, training, result['routed_oof_metrics'])
    assert result['new_model_calls'] == result['reserved_test_cases_scored'] == 0
    audit_result = {'passed': True, 'fits_checked': fit_count, 'policy_artifacts_checked': policy_count,
                    'prediction_checks': total_prediction_checks, 'outer_folds': 4, 'inner_source_separations_checked': inner_splits,
                    'qualified_route_gates_recomputed': route_checks, 'reserved_source_overlap': 0,
                    'reserved_test_predictions': 0, 'new_model_calls': 0,
                    'limitations': 'Checks arithmetic, provenance and execution. It does not certify human accuracy or generalization.'}
    path = output / 'independent_audit.json'
    if path.exists():
        assert read(path) == audit_result
    else:
        save_json(path, audit_result)
    print(audit_result)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('output_dir', type=Path)
    audit(p.parse_args().output_dir.resolve())
