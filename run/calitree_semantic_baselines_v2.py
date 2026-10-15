"""M3/M4 pooled/local baselines and nested source-grouped routing evaluation."""
import argparse
from collections import Counter
from copy import deepcopy
from pathlib import Path
import shutil
import time

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence_v2 import VERSION as EVIDENCE_VERSION
from critical.core.calibration.evidence_rules_v4 import classification_metrics
from critical.core.calibration.registry import CalibrationRegistry
from critical.core.calibration.semantic_hierarchy.features_v2 import project, CONTRACT_REF, SPECS, SCOPES
from critical.core.calibration.semantic_hierarchy.rule_search_v2 import SemanticRuleCalibrator, UnsupportedPolicyError, LIMITS
from critical.core.calibration.semantic_hierarchy.routing_v2 import RoutedSemanticJudge, fit_router, LIMITS as ROUTER_LIMITS
from run.calitree_single_call import ROOT, read, fingerprint

VERSION = 'm2-m4-semantic-baselines-v2-positive-change'
M0 = ROOT / 'logs/exps/261014-semantic-hierarchy-m0-fifty-v1'
M1 = ROOT / 'logs/exps/261014-m1-bound-evidence-development12-v2'
TRAIN = ROOT / 'logs/exps/261014-m2-m4-bound-training48-v1'
LABELS = ('no', 'partial', 'yes')


def exact(path, value):
    if path.exists():
        if read(path) != value:
            raise ValueError('Changed saved baseline artifact: ' + str(path))
    else:
        save_json(path, value)


def load_data():
    forbidden = {c['group'] for c in read(M0 / 'splits/test.json')['cases']}
    result = {}
    for partition, source in (('train', TRAIN), ('validation', M1)):
        cases = read(M0 / 'splits' / (partition + '.json'))['cases']
        manifest = read(source / 'manifest.json'); observed = read(source / 'observations.json')
        if manifest['evidence_version'] != EVIDENCE_VERSION or manifest['cases'] != cases or len(observed) != len(cases):
            raise ValueError('Unmatched frozen M1 representation')
        rows = []
        for c, r in zip(cases, observed):
            if c['case'] != r['case'] or c['group'] in forbidden:
                raise ValueError('Mispaired or reserved source')
            record = None
            if r['compilation'] is not None and r['observation'] is not None:
                p = r['compilation']['program']; v = r['observation']['observation']
                pair_ref = digest([EVIDENCE_VERSION, 'source_first', c['image_hashes']['source_image'], c['image_hashes']['edited_image']])
                if p['instruction'] != c['instruction']:
                    raise ValueError('Instruction mismatch')
                record = project(p, v, pair_ref)
            rows.append({'case': c['case'], 'id': c['id'], 'source_group': c['group'],
                         'batch': c.get('batch', 'development12'), 'reference': LABELS.index(c['reference']),
                         'instruction': c['instruction'], 'features': record,
                         'program_ref': r['compilation']['program']['program_ref'] if r['compilation'] else None,
                         'observation_ref': r['observation']['execution_ref'] if r['observation'] else None,
                         'extraction_error': r['error']})
        result[partition] = rows
    if {r['source_group'] for r in result['train']} & {r['source_group'] for r in result['validation']}:
        raise ValueError('Training/development source overlap')
    return result


def prepare(output):
    protocol = read(output / 'preregistered_protocol.json')
    if digest(protocol) != read(output / 'protocol_seal.json')['protocol_ref'] or protocol['feature_contract_ref'] != CONTRACT_REF:
        raise ValueError('Feature protocol changed')
    if any(protocol['learner'][k] != v for k, v in LIMITS.items()) or any(protocol['routing'][k] != v for k, v in ROUTER_LIMITS.items()):
        raise ValueError('Search/routing settings differ from preregistration')
    if (output / 'manifest.json').exists():
        m = read(output / 'manifest.json'); verify(output, m); return m
    data = load_data()
    files = sorted((ROOT / 'critical/core/calibration/semantic_hierarchy').glob('*.py'))
    files += [Path(__file__).resolve(), ROOT / 'critical/core/calibration/evidence_rules_v4.py',
              ROOT / 'critical/core/decision/bound_evidence_v2.py', ROOT / 'critical/core/decision/bound_evidence.py']
    code = {}
    for path in files:
        rel = str(path.relative_to(ROOT)); dst = output / 'source_snapshot' / rel
        dst.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, dst); code[rel] = fingerprint(path)
    pins = [TRAIN / 'manifest.json', TRAIN / 'results.json', TRAIN / 'observations.json',
            M1 / 'manifest.json', M1 / 'observations.json', M0 / 'seal.json', M0 / 'completion_seal.json',
            M0 / 'splits/train.json', M0 / 'splits/validation.json', M0 / 'splits/test.json',
            M0 / 'selection_protocol.json', output / 'preregistered_protocol.json']
    m = {'version': VERSION, 'feature_contract_ref': CONTRACT_REF, 'feature_specs': SPECS,
         'learner_limits': LIMITS, 'router_limits': ROUTER_LIMITS, 'source_hashes': {str(p): fingerprint(p) for p in pins},
         'code_hashes': code, 'data_ref': digest(data), 'train_cases': 48, 'development_cases': 12,
         'reserved_test_cases_scored': 0, 'new_model_calls': 0,
         'selection': 'Local alternatives selected on their own fitting data only. Each router uses outside-fit expert predictions and inner grouped out-of-fold pooled comparators. Outer batch never reaches any fit or router selection.',
         'limitation': 'Historical development evidence and representation; grouped estimates are development evidence, not globally untouched performance.'}
    exact(output / 'data.json', data); save_json(output / 'manifest.json', m); save_json(output / 'seal.json', {'manifest_ref': digest(m)})
    verify(output, m); return m


def verify(output, m):
    if digest(m) != read(output / 'seal.json')['manifest_ref'] or m['version'] != VERSION or m['feature_contract_ref'] != CONTRACT_REF:
        raise ValueError('Changed baseline protocol')
    for p, h in m['source_hashes'].items():
        if fingerprint(p) != h:
            raise ValueError('Frozen input changed: ' + p)
    for rel, h in m['code_hashes'].items():
        if fingerprint(ROOT / rel) != h or fingerprint(output / 'source_snapshot' / rel) != h:
            raise ValueError('Frozen baseline implementation changed: ' + rel)
    if digest(load_data()) != m['data_ref'] or digest(read(output / 'data.json')) != m['data_ref']:
        raise ValueError('Projected evidence changed')
    if (M0 / 'predictions.json').exists() or list(M0.glob('ledgers/**/jobs/*.json')):
        raise ValueError('Final reservation was evaluated')


def score(rows, predictions):
    return classification_metrics(predictions, [r['reference'] for r in rows])[0]


def policy_predictions(policy, rows):
    if policy is None:
        return [-1] * len(rows)
    model = SemanticRuleCalibrator.restore(policy)
    return [r['prediction'] for r in model.predict_records([x['features'] for x in rows])]


class Fits:
    def __init__(self, output, replay=False):
        self.output, self.replay = output, replay
        self.registry = CalibrationRegistry(output / 'registry')

    def get(self, rows):
        rows = sorted(rows, key=lambda r: r['source_group'])
        key = digest([CONTRACT_REF, LIMITS, [(r['source_group'], r['batch'], r['reference'], r['features']) for r in rows]])
        path = self.output / 'fits' / key / 'fit.json'
        if path.exists():
            artifact = read(path)
            if artifact['fit_sources'] != [r['source_group'] for r in rows]:
                raise ValueError('Fit cache source mismatch')
            for p in artifact['policies']:
                SemanticRuleCalibrator.restore(p)
            return artifact
        if self.replay:
            raise ValueError('Replay lacks a fitted artifact: ' + key)
        model = SemanticRuleCalibrator(); start = time.monotonic(); error = None; policies = []
        try:
            model.fit([r['features'] for r in rows], [r['reference'] for r in rows],
                      source_groups=[r['source_group'] for r in rows], source_batches=[r['batch'] for r in rows])
            policies = model.candidates()
        except UnsupportedPolicyError as exc:
            error = str(exc)
        artifact = {'fit_ref': key, 'fit_sources': [r['source_group'] for r in rows],
                    'fit_cases': [r['case'] for r in rows], 'fit_batches': sorted({r['batch'] for r in rows}),
                    'policies': policies, 'status': 'supported' if policies else 'unsupported', 'error': error,
                    'search': model.search_diagnostic, 'elapsed_seconds': time.monotonic() - start}
        for i, p in enumerate(policies):
            self.registry.publish(p)
            (path.parent / f'candidate_{i}.txt').parent.mkdir(parents=True, exist_ok=True)
            (path.parent / f'candidate_{i}.txt').write_text(SemanticRuleCalibrator.restore(p).render() + '\n')
        exact(path, artifact)
        print({'fit_rows': len(rows), 'batches': artifact['fit_batches'], 'status': artifact['status'],
               'candidates': len(policies), 'seconds': round(artifact['elapsed_seconds'], 2)}, flush=True)
        return artifact


def build_context(rows, fits):
    pooled_fit = fits.get(rows); pooled = pooled_fit['policies'][0] if pooled_fit['policies'] else None
    experts, local = {}, {}
    for batch in sorted({r['batch'] for r in rows}):
        selected = [r for r in rows if r['batch'] == batch]
        fitted = fits.get(selected); local[batch] = fitted
        for i, p in enumerate(fitted['policies']):
            experts[f'{batch}_candidate_{i}'] = p
    pooled_oof = [-1] * len(rows); supported = [False] * len(rows); inner = []
    for held in sorted({r['batch'] for r in rows}):
        fit_rows = [r for r in rows if r['batch'] != held]
        validation = [r for r in rows if r['batch'] == held]
        model_fit = fits.get(fit_rows)
        p = model_fit['policies'][0] if model_fit['policies'] else None
        predictions = policy_predictions(p, validation)
        assigned = {r['case']: prediction for r, prediction in zip(validation, predictions)}
        for i, r in enumerate(rows):
            if r['batch'] == held:
                pooled_oof[i] = assigned[r['case']]; supported[i] = p is not None
        inner.append({'held_batch': held, 'fit_ref': model_fit['fit_ref'],
                      'fit_sources': model_fit['fit_sources'], 'validation_sources': [r['source_group'] for r in validation],
                      'validation_cases': [r['case'] for r in validation], 'predictions': predictions, 'supported': p is not None})
    router = fit_router(experts, [r['features'] for r in rows], [r['reference'] for r in rows],
                        [r['source_group'] for r in rows], [r['batch'] for r in rows], pooled_oof, pooled_supported=supported)
    bundle = RoutedSemanticJudge(pooled, experts, router).export() if pooled is not None else None
    return {'pooled_fit_ref': pooled_fit['fit_ref'], 'pooled': pooled, 'experts': experts,
            'local_fit_refs': {b: f['fit_ref'] for b, f in local.items()},
            'inner_pooled_oof': inner, 'router': router, 'bundle': bundle,
            'fit_sources': [r['source_group'] for r in rows]}


def context_predictions(context, rows):
    pooled = policy_predictions(context['pooled'], rows)
    if context['bundle'] is not None:
        judge = RoutedSemanticJudge.restore(context['bundle'])
        routed = judge.predict_records([r['features'] for r in rows])
    else:
        routed = [{'prediction': -1, 'reason': 'unsupported_pooled_fallback', 'expert_id': 'pooled',
                   'fallback': True, 'route_basis': 'unsupported_pooled_fit', 'policy_evaluations': 0, 'route_ref': None} for _ in rows]
    expert = {k: policy_predictions(p, rows) for k, p in context['experts'].items()}
    # An upper bound only. It never selects the deployed route or enters fitting.
    oracle_correct = [any(predictions[i] == r['reference'] for predictions in [pooled, *expert.values()]) for i, r in enumerate(rows)]
    return {'pooled': pooled, 'routed': routed, 'experts': expert, 'oracle_correct': oracle_correct,
            'pooled_metrics': score(rows, pooled), 'routed_metrics': score(rows, [r['prediction'] for r in routed]),
            'oracle_correct_count': sum(oracle_correct),
            'route_counts': dict(Counter(r['expert_id'] for r in routed)),
            'fallback_count': sum(r['fallback'] for r in routed)}


def run(output, replay=False):
    m = prepare(output); data = read(output / 'data.json'); training, dev = data['train'], data['validation']
    fits = Fits(output, replay); folds = {}; pooled_oof, routed_oof, oracle_oof = {}, {}, {}
    for held in ('G1', 'G2', 'G3', 'G4'):
        fitting = [r for r in training if r['batch'] != held]
        evaluation = [r for r in training if r['batch'] == held]
        context = build_context(fitting, fits)
        result = context_predictions(context, evaluation)
        assert not set(context['fit_sources']) & {r['source_group'] for r in evaluation}
        folds[held] = {'context': context, 'evaluation_cases': [r['case'] for r in evaluation],
                       'evaluation_sources': [r['source_group'] for r in evaluation], 'result': result}
        for c, p, route, oracle in zip(evaluation, result['pooled'], result['routed'], result['oracle_correct']):
            pooled_oof[c['case']] = p; routed_oof[c['case']] = route; oracle_oof[c['case']] = oracle
        print({'outer_fold': held, 'pooled_correct': result['pooled_metrics']['correct'],
               'routed_correct': result['routed_metrics']['correct'], 'routes': len(context['router']['routes'])}, flush=True)
    final = build_context(training, fits)
    if final['bundle'] is None:
        raise RuntimeError('No supported full-training pooled fallback; M4 deployment is incomplete')
    exact(output / 'frozen_bundle.json', final['bundle'])
    full_local = {}
    for name, policy in final['experts'].items():
        sources = set(policy['training']['source_groups'])
        fitting = [r for r in training if r['source_group'] in sources]
        outside = [r for r in training if r['source_group'] not in sources]
        ip, op = policy_predictions(policy, fitting), policy_predictions(policy, outside)
        full_local[name] = {'policy_ref': policy['artifact_ref'], 'fitting': score(fitting, ip),
                            'outside_fitting': score(outside, op), 'outside_cases': [r['case'] for r in outside],
                            'outside_predictions': op}
    dev_result = context_predictions(final, dev)
    p = [pooled_oof[r['case']] for r in training]; rt = [routed_oof[r['case']] for r in training]
    result = {'version': VERSION, 'manifest_ref': digest(m), 'folds': folds, 'final_context': final,
              'local_candidates': full_local,
              'training_pooled_metrics': score(training, policy_predictions(final['pooled'], training)),
              'pooled_oof_metrics': score(training, p), 'routed_oof_metrics': score(training, [r['prediction'] for r in rt]),
              'oof_cases': [{'case': r['case'], 'reference': r['reference'], 'pooled': pooled_oof[r['case']],
                             'routed': routed_oof[r['case']], 'oracle_correct': oracle_oof[r['case']]} for r in training],
              'oof_oracle_correct': sum(oracle_oof.values()), 'development12': dev_result,
              'development12_cases': [r['case'] for r in dev],
              'oof_fallback_count': sum(r['fallback'] for r in rt),
              'oof_route_counts': dict(Counter(r['expert_id'] for r in rt)),
              'available_training_records': sum(r['features'] is not None for r in training),
              'new_model_calls': 0, 'reserved_test_cases_scored': 0,
              'scope': m['limitation']}
    verify(output, m); exact(output / 'results.json', result)
    report(output, result)
    if replay:
        exact(output / 'replay.json', {'exact_replay': True, 'new_fits': 0, 'new_model_calls': 0,
                                      'results_sha256': fingerprint(output / 'results.json')})
    return result


def report(output, r):
    lines = ['# M2–M4: pooled and local semantic policies with instruction-only routing', '',
             'Frozen M1 v2 evidence. Four outer source-grouped folds exclude one entire original batch from policy fitting and all routing selection. Each router uses inner pooled out-of-fold predictions and local experts only on sources outside their own fit sets.', '',
             '| Evaluation | Pooled correct | Routed correct | Pooled macro-F1 | Routed macro-F1 |', '|---|---:|---:|---:|---:|']
    for label, a, b in [('Training48 grouped OOF', r['pooled_oof_metrics'], r['routed_oof_metrics']),
                         ('Already-observed development12', r['development12']['pooled_metrics'], r['development12']['routed_metrics'])]:
        lines.append(f"| {label} | {a['correct']}/{a['total']} | {b['correct']}/{b['total']} | {a['macro_f1']:.3f} | {b['macro_f1']:.3f} |")
    lines += ['', '| Evaluation / method | No recall | Partial recall | Yes recall | Unresolved |', '|---|---:|---:|---:|---:|']
    for label, m in [('OOF pooled', r['pooled_oof_metrics']), ('OOF routed', r['routed_oof_metrics']),
                     ('Development pooled', r['development12']['pooled_metrics']), ('Development routed', r['development12']['routed_metrics'])]:
        rates = ' | '.join(f"{m['per_class'][k]['recall']:.1%}" for k in LABELS)
        lines.append(f"| {label} | {rates} | {m['unresolved']} |")
    lines += ['', f"Available training observations: {r['available_training_records']}/48. Failures remain in every denominator.",
              f"OOF oracle correctness upper bound: {r['oof_oracle_correct']}/48. This uses reference labels for diagnostic scoring only and is not the deployed router.",
              f"Actual OOF fallback count: {r['oof_fallback_count']}/48. Route assignments: `{r['oof_route_counts']}`.",
              f"Final fitted router has {len(r['final_context']['router']['routes'])} accepted routes.", '',
              '| Local candidate | Fitting correct | Outside-fit correct | Outside-fit macro-F1 |', '|---|---:|---:|---:|']
    for name, v in r['local_candidates'].items():
        a, b = v['fitting'], v['outside_fitting']
        lines.append(f"| {name} | {a['correct']}/{a['total']} | {b['correct']}/{b['total']} | {b['macro_f1']:.3f} |")
    lines += ['', 'These local rows overlap in their validation examples and are not independent replications. Grouped results are development evidence; all sixty cases have historical research exposure. The fifty-case reservation was not evaluated. No merges or final-test policy selection occurred.',
              'No new model calls occur in fitting, routing, or replay. Only one chosen expert and, if necessary, the pooled fallback execute at inference on the shared evidence record.']
    (output / 'report.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    g = p.add_mutually_exclusive_group(required=True)
    for k in ('preflight', 'fit', 'replay'):
        g.add_argument('--' + k, action='store_true')
    args = p.parse_args(); output = args.output_dir.resolve()
    if args.preflight:
        m = prepare(output); print({'train': m['train_cases'], 'development': m['development_cases'], 'new_model_calls': 0})
    else:
        r = run(output, args.replay)
        print({'pooled_oof': r['pooled_oof_metrics'], 'routed_oof': r['routed_oof_metrics'], 'development': r['development12']['routed_metrics']})
