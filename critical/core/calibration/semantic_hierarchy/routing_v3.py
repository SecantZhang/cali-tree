"""Shallow instruction-only routing, qualified outside each expert's fit sources."""
from collections import Counter
from copy import deepcopy
from fractions import Fraction
from itertools import combinations, product

from ...decision.artifacts import digest
from ..evidence_rules_v4 import classification_metrics
from .features_v2 import SCOPES, SCOPE_KINDS, CONTRACT_REF, validate_record
from .rule_search_v3 import SemanticRuleCalibrator

VERSION = 'instruction-scope-router-v3-conditional-partial'
LIMITS = {'max_scope_literals': 2, 'max_routes': 4, 'min_validation_sources': 6,
          'min_validation_per_class': 2, 'min_validation_batches': 2,
          'min_correct_per_scope_class': 1}


def scope_values(record):
    validate_record(record)
    return None if record is None else {k: record['features'][k] == 'true' for k in SCOPES}


def operation_signature(scope):
    return tuple(k for k in SCOPE_KINDS if scope['requires_' + k])


def matches(scope, conditions):
    return scope is not None and all(scope[c['flag']] == c['value'] for c in conditions)


def scope_candidates():
    yield []
    for n in (1, 2):
        for flags in combinations(SCOPES, n):
            for values in product((False, True), repeat=n):
                yield [{'flag': flag, 'value': value} for flag, value in zip(flags, values)]


def macro_fraction(metric):
    return sum((Fraction(2 * c['correct'], c['support'] + c['predicted'])
                for c in metric['per_class'].values()), Fraction()) / 3


def fit_router(experts, records, targets, source_groups, source_batches, pooled_oof, *, pooled_supported=None):
    """Labels are used here only. Each expert validates strictly outside its fit set.

    pooled_oof must be supplied by the study's inner source-grouped folds; this
    API does not manufacture in-sample pooled predictions for gate comparison.
    """
    n = len(targets)
    if not (len(records) == len(source_groups) == len(source_batches) == len(pooled_oof) == n) or len(set(source_groups)) != n:
        raise ValueError('Unpaired or repeated source records for routing selection')
    if any(p not in (-1, 0, 1, 2) for p in pooled_oof) or any(type(y) is not int or y not in (0, 1, 2) for y in targets):
        raise ValueError('Invalid reference or out-of-fold prediction')
    supported = [True] * n if pooled_supported is None else list(pooled_supported)
    if len(supported) != n or any(type(v) is not bool for v in supported):
        raise ValueError('Invalid pooled comparator availability')
    scopes = [scope_values(x) for x in records]; proposals = []; evaluations = []
    for expert_id, policy in sorted(experts.items()):
        model = SemanticRuleCalibrator.restore(policy)
        fitting_sources = set(policy['training']['source_groups'])
        outside = [i for i in range(n) if source_groups[i] not in fitting_sources and records[i] is not None and supported[i]]
        predictions = model.predict_records(records)
        coverage_seen = {}; rejected = Counter()
        for conditions in scope_candidates():
            indices = tuple(i for i in outside if matches(scopes[i], conditions))
            # Equal measured coverage does not justify a more specific gate.
            if indices in coverage_seen:
                continue
            coverage_seen[indices] = conditions
            if len(indices) < LIMITS['min_validation_sources']:
                rejected['source_support'] += 1; continue
            y = [targets[i] for i in indices]
            if min(y.count(k) for k in range(3)) < LIMITS['min_validation_per_class']:
                rejected['class_support'] += 1; continue
            batches = Counter(source_batches[i] for i in indices)
            if len(batches) < LIMITS['min_validation_batches']:
                rejected['batch_support'] += 1; continue
            raw = [predictions[i]['prediction'] for i in indices]
            base = [pooled_oof[i] for i in indices]
            # The runtime uses this exact, predeclared unresolved-expert fallback.
            routed = [p if p >= 0 else b for p, b in zip(raw, base)]
            em = classification_metrics(raw, y)[0]
            cm = classification_metrics(routed, y)[0]; bm = classification_metrics(base, y)[0]
            gain = macro_fraction(cm) - macro_fraction(bm)
            if min(c['correct'] for c in em['per_class'].values()) < LIMITS['min_correct_per_scope_class']:
                rejected['expert_class_collapse'] += 1; continue
            if gain <= 0:
                rejected['no_macro_gain'] += 1; continue
            if any(cm['per_class'][k]['correct'] < bm['per_class'][k]['correct'] for k in ('no', 'partial', 'yes')):
                rejected['class_regression'] += 1; continue
            if cm['unresolved'] > bm['unresolved']:
                rejected['coverage_regression'] += 1; continue
            signatures = sorted({operation_signature(scopes[i]) for i in indices})
            route = {'conditions': conditions, 'expert_id': expert_id, 'expert_ref': policy['artifact_ref'],
                     'validation': {'source_groups': [source_groups[i] for i in indices],
                                    'source_batches': dict(sorted(batches.items())), 'expert_metrics': em,
                                    'routed_metrics': cm, 'pooled_oof_metrics': bm,
                                    'gain_numerator': gain.numerator, 'gain_denominator': gain.denominator},
                     'supported_operation_signatures': [list(s) for s in signatures]}
            route['route_ref'] = digest(route); proposals.append(route)
        evaluations.append({'expert_id': expert_id, 'out_of_source_validation_cases': len(outside),
                            'unique_scopes_examined': len(coverage_seen), 'rejections': dict(rejected)})
    def priority(r):
        v = r['validation']
        return (-len(r['conditions']), -Fraction(v['gain_numerator'], v['gain_denominator']),
                -len(v['source_groups']), r['route_ref'])
    proposals.sort(key=priority)
    # Do not retain two experts behind exactly the same scope and operation set.
    routes = []; domains = set()
    for r in proposals:
        domain = digest([r['conditions'], r['supported_operation_signatures']])
        if domain not in domains:
            routes.append(r); domains.add(domain)
        if len(routes) == LIMITS['max_routes']:
            break
    value = {'version': VERSION, 'feature_contract_ref': CONTRACT_REF, 'limits': deepcopy(LIMITS),
             'routes': routes, 'qualified_proposals': len(proposals), 'selection_diagnostics': evaluations,
             'selection_source_groups': list(source_groups),
             'selection_target_ref': digest(list(targets)),
             'fallback': 'pooled_on_no_scope_or_unresolved_specialist',
             'scope': 'Instruction-only predicates; overlap chooses most-specific then frozen validation rank. Unseen operation combinations fall back. No label or dataset category is available at inference.'}
    value['router_ref'] = digest(value)
    return value


class RoutedSemanticJudge:
    def __init__(self, pooled_policy, experts, router):
        self.pooled = SemanticRuleCalibrator.restore(pooled_policy)
        self.experts = {k: SemanticRuleCalibrator.restore(v) for k, v in experts.items()}
        self.router = deepcopy(router)
        if (router.get('version') != VERSION or router.get('feature_contract_ref') != CONTRACT_REF
                or router.get('limits') != LIMITS or digest({k: v for k, v in router.items() if k != 'router_ref'}) != router.get('router_ref')):
            raise ValueError('Changed router contract')
        if len(router['routes']) > LIMITS['max_routes']:
            raise ValueError('Too many routing scopes')
        for r in router['routes']:
            if r['expert_id'] not in experts or r['expert_ref'] != experts[r['expert_id']]['artifact_ref']:
                raise ValueError('Router references an unknown expert')
            if digest({k: v for k, v in r.items() if k != 'route_ref'}) != r['route_ref']:
                raise ValueError('Route content changed')
            conditions = r['conditions']
            if len(conditions) > 2 or len({c['flag'] for c in conditions}) != len(conditions):
                raise ValueError('Invalid scope shape')
            if any(set(c) != {'flag', 'value'} or c['flag'] not in SCOPES or type(c['value']) is not bool for c in conditions):
                raise ValueError('Scope is not instruction-only')
            v = r['validation']; fitting = set(experts[r['expert_id']]['training']['source_groups'])
            if fitting & set(v['source_groups']) or len(v['source_groups']) != len(set(v['source_groups'])):
                raise ValueError('Expert validated on fitting sources')
            if len(v['source_groups']) < LIMITS['min_validation_sources'] or len(v['source_batches']) < 2:
                raise ValueError('Unsupported route')
            for name in ('no', 'partial', 'yes'):
                if v['expert_metrics']['per_class'][name]['support'] < 2 or v['expert_metrics']['per_class'][name]['correct'] < 1:
                    raise ValueError('Collapsed or unsupported expert class')
                if v['routed_metrics']['per_class'][name]['correct'] < v['pooled_oof_metrics']['per_class'][name]['correct']:
                    raise ValueError('Class-regressing route')
            gain = macro_fraction(v['routed_metrics']) - macro_fraction(v['pooled_oof_metrics'])
            if gain <= 0 or gain != Fraction(v['gain_numerator'], v['gain_denominator']):
                raise ValueError('Unverified route gain')
            if v['routed_metrics']['unresolved'] > v['pooled_oof_metrics']['unresolved']:
                raise ValueError('Coverage-regressing route')
            if any(not set(s) <= set(SCOPE_KINDS) for s in r['supported_operation_signatures']):
                raise ValueError('Unknown operation signature')

    def choose(self, scope):
        if scope is None:
            return None, 'missing_evidence'
        if set(scope) != set(SCOPES) or any(type(v) is not bool for v in scope.values()):
            raise ValueError('Only declared instruction-scope booleans accepted')
        signature = operation_signature(scope)
        for r in self.router['routes']:
            if matches(scope, r['conditions']) and list(signature) in r['supported_operation_signatures']:
                return r, 'validated_instruction_scope'
        return None, 'unsupported_scope'

    def predict_records(self, records):
        result = []
        for x in records:
            route, basis = self.choose(scope_values(x))
            if route is None:
                decision = self.pooled.predict_records([x])[0]
                result.append({**decision, 'expert_id': 'pooled', 'route_basis': basis, 'fallback': True,
                               'policy_evaluations': 1, 'route_ref': None})
            else:
                expert_id = route['expert_id']; decision = self.experts[expert_id].predict_records([x])[0]
                fallback = decision['prediction'] < 0
                if fallback:
                    decision = self.pooled.predict_records([x])[0]
                result.append({**decision, 'expert_id': expert_id, 'route_basis': basis,
                               'fallback': fallback, 'policy_evaluations': 2 if fallback else 1,
                               'route_ref': route['route_ref']})
        return result

    def export(self):
        bundle = {'version': VERSION, 'pooled': self.pooled.metadata(),
                  'experts': {k: m.metadata() for k, m in self.experts.items()}, 'router': deepcopy(self.router)}
        bundle['bundle_ref'] = digest(bundle)
        return bundle

    @classmethod
    def restore(cls, bundle):
        if bundle.get('version') != VERSION or digest({k: v for k, v in bundle.items() if k != 'bundle_ref'}) != bundle.get('bundle_ref'):
            raise ValueError('Changed routed bundle')
        return cls(bundle['pooled'], bundle['experts'], bundle['router'])
