"""M3 local alternatives and M4 nested, source-excluding routing experiments."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import json
import time

from ...decision.artifacts import digest, save_json
from .portable_features_v8 import CONTRACT_REF
from .portable_runtime_v8 import PortableRuleExecutor
from .portable_tree_v8 import PortableSemanticTree
from .hierarchy_fit_v9 import fit, complexity
from .hierarchy_protocol_v9 import PROFILES, ROUTING, macro_fraction, score, sealed, content_ref
from .hierarchy_scopes_v9 import proposals, matches
from .hierarchy_runtime_v9 import HierarchyExecutor, export_bundle


def guarded_routes(pooled, candidates, proposed, rows, extraction):
    """Choose the entire router jointly, rather than trusting isolated gains.

    This is training selection, not a held-out claim. Outer fold rows are absent
    from the inputs. The empty route set is the explicit pooled comparator.
    """
    base = score(rows, _predict(pooled, rows))
    options = []
    for mask in range(1 << len(proposed)):
        selected = [r for i, r in enumerate(proposed) if mask & (1 << i)]
        routes = [{'node_id': r['node_id'], 'scope': r['scope']} for r in selected]
        nodes = {r['node_id']: {'policy': candidates[r['node_id']]['runtime'], 'children': [], 'depth': 0} for r in selected}
        bundle = export_bundle(pooled, nodes, routes, extraction)
        decisions = HierarchyExecutor(bundle).predict_records([r['features'] for r in rows], [r['scope'] for r in rows])
        m = score(rows, decisions)
        if (m['correct'] < base['correct'] or macro_fraction(m) < macro_fraction(base)
                or m['unresolved'] > base['unresolved']
                or any(m['per_class'][k]['correct'] < base['per_class'][k]['correct'] for k in base['per_class'])):
            continue
        active_nodes = sum(candidates[r['node_id']]['complexity']['nodes'] for r in selected)
        options.append(((-macro_fraction(m), -m['worst_present_class_recall'], -m['correct'],
                         active_nodes, len(routes), digest(routes)), selected, bundle, m))
    _, selected, bundle, metric = min(options, key=lambda v: v[0])
    return selected, bundle, {'considered_subsets': 1 << len(proposed), 'eligible_subsets': len(options),
                              'pooled_fit_metrics': base, 'selected_fit_metrics': metric,
                              'selection_scope': 'Fitting only; nested outer results reported separately.'}


class Fits:
    def __init__(self, output, replay=False):
        self.output = Path(output)
        self.replay = replay
        self.new_fits = 0

    def get(self, rows, profile, warm_policies=(), *, shared=False):
        rows = sorted(rows, key=lambda r: r['source_group'])
        identity = [CONTRACT_REF, PROFILES[profile], rows, [p['artifact_ref'] for p in warm_policies]]
        if shared:
            identity.append('shared-parent-search-v9.1')
        key = digest(identity)
        path = self.output / 'fits' / (key + '.json')
        if path.exists():
            artifact = json.loads(path.read_text())
            if artifact['fit_ref'] != key or artifact['content_ref'] != content_ref(artifact, 'content_ref'):
                raise ValueError('Changed fit cache')
            PortableSemanticTree.restore(artifact['result']['policy'])
            PortableRuleExecutor(artifact['result']['runtime'])
            return deepcopy(artifact['result'])
        if self.replay:
            raise ValueError('Offline replay cannot fit a missing policy: ' + key)
        start = time.monotonic()
        result = fit(rows, profile, warm_policies, shared=shared)
        artifact = sealed({'fit_ref': key, 'fit_sources': [r['source_group'] for r in rows],
                           'elapsed_seconds': time.monotonic() - start, 'result': result}, 'content_ref')
        save_json(path, artifact)
        self.new_fits += 1
        print({'fit_sources': len(rows), 'profile': profile, 'correct': result['metrics']['correct'],
               'rules': result['complexity']['rules'], 'seconds': round(artifact['elapsed_seconds'], 2)}, flush=True)
        return result


def _candidate_id(batch, profile):
    # Opaque node identity is audit metadata, never an inference predicate.
    return 'leaf-' + digest([batch, profile])[:16]


def _predict(runtime, rows):
    return PortableRuleExecutor(runtime).predict_records([r['features'] for r in rows])


def _eligible_metric(metric):
    return all(not c['support'] or c['correct'] > 0 for c in metric['per_class'].values())


def fit_routes(candidates, rows, pooled_oof):
    """Validate experts only on sources absent from their own fitting lineage.

    The pooled comparator is itself out of source. Outer evaluation cases never
    reach this function. Selecting these routes remains development selection.
    """
    bank, diagnostics = [], []
    values = [r['scope'] for r in rows]
    scope_bank = list(proposals(values))
    for node_id, candidate in sorted(candidates.items()):
        fitting = set(candidate['fit_sources'])
        outside = {i for i, r in enumerate(rows) if r['source_group'] not in fitting}
        predictions = _predict(candidate['runtime'], rows)
        rejected = Counter(); supported = []
        if not candidate['specialist_eligible']:
            diagnostics.append({'node_id': node_id, 'status': 'ineligible_fit',
                                'reasons': candidate['eligibility_reasons']})
            continue
        for scope, covered in scope_bank:
            inside_fit = [i for i in covered if rows[i]['source_group'] in fitting]
            indices = [i for i in covered if i in outside]
            if len(inside_fit) < ROUTING['min_fit_sources']:
                rejected['fit_scope_support'] += 1; continue
            if len(indices) < ROUTING['min_validation_sources']:
                rejected['validation_scope_support'] += 1; continue
            selected = [rows[i] for i in indices]
            counts = Counter(r['reference'] for r in selected)
            if min(counts[k] for k in range(3)) < ROUTING['min_validation_per_class']:
                rejected['class_support'] += 1; continue
            if len({r['batch'] for r in selected}) < ROUTING['min_validation_batches']:
                rejected['batch_support'] += 1; continue
            raw = [predictions[i] for i in indices]
            routed = [p['prediction'] if p['prediction'] >= 0 else pooled_oof[i] for i, p in zip(indices, raw)]
            m = score(selected, routed); base = score(selected, [pooled_oof[i] for i in indices])
            expert = score(selected, raw)
            summary = {'node_id': node_id, 'scope': scope, 'fit_scope_sources': len(inside_fit),
                       'validation_sources': [r['source_group'] for r in selected],
                       'validation_cases': [r['case'] for r in selected], 'expert_metrics': expert,
                       'routed_metrics': m, 'pooled_oof_metrics': base,
                       'macro_gain': float(macro_fraction(m) - macro_fraction(base))}
            supported.append(summary)
            if not _eligible_metric(expert):
                rejected['supported_label_collapse'] += 1; continue
            if macro_fraction(m) <= macro_fraction(base):
                rejected['no_macro_gain'] += 1; continue
            if any(m['per_class'][k]['correct'] < base['per_class'][k]['correct'] for k in base['per_class']):
                rejected['class_regression'] += 1; continue
            if m['unresolved'] > base['unresolved']:
                rejected['coverage_regression'] += 1; continue
            bank.append(summary)
        diagnostics.append({'node_id': node_id, 'status': 'evaluated', 'rejections': dict(rejected),
                            'supported_scopes': supported})
    bank.sort(key=lambda r: (-len(r['scope'][0]), -(macro_fraction(r['routed_metrics']) - macro_fraction(r['pooled_oof_metrics'])),
                            -len(r['validation_sources']), digest([r['scope'], r['node_id']])))
    selected, used_nodes, used_domains = [], set(), set()
    for proposal in bank:
        if proposal['node_id'] in used_nodes or digest(proposal['scope']) in used_domains:
            continue
        selected.append(proposal)
        used_nodes.add(proposal['node_id']); used_domains.add(digest(proposal['scope']))
        if len(selected) == ROUTING['max_routes']:
            break
    return selected, diagnostics


def build_context(rows, fits, extraction, pinned_pooled=None):
    rows = sorted(rows, key=lambda r: r['source_group'])
    batches = sorted({r['batch'] for r in rows})
    if len(batches) < 2:
        raise ValueError('Routing development requires multiple independent training batches')
    pooled = pinned_pooled or fits.get(rows, 'pooled')['runtime']
    PortableRuleExecutor(pooled)
    candidates, local_registry = {}, []
    for batch in batches:
        selected = [r for r in rows if r['batch'] == batch]
        seen = set()
        for profile in ('local_shallow', 'local_deeper'):
            fitted = fits.get(selected, profile)
            node_id = _candidate_id(batch, profile)
            candidate = {**fitted, 'node_id': node_id, 'fit_sources': [r['source_group'] for r in selected],
                         'fit_cases': [r['case'] for r in selected], 'originating_batches': [batch],
                         'children': [], 'depth': 0}
            duplicate = fitted['runtime']['artifact_ref'] in seen
            local_registry.append({**candidate, 'duplicate_runtime': duplicate})
            if not duplicate:
                candidates[node_id] = candidate
            seen.add(fitted['runtime']['artifact_ref'])
    # Leave an entire originating batch out of each pooled comparator. Local
    # expert validation already excludes its complete fitting batch separately.
    inner, by_source = [], {}
    for held in batches:
        fitting = [r for r in rows if r['batch'] != held]
        validation = [r for r in rows if r['batch'] == held]
        runtime = fits.get(fitting, 'pooled')['runtime']
        ps = _predict(runtime, validation)
        by_source.update({r['source_group']: p['prediction'] for r, p in zip(validation, ps)})
        inner.append({'fit_sources': [r['source_group'] for r in fitting],
                      'validation_sources': [r['source_group'] for r in validation],
                      'policy_ref': runtime['artifact_ref'], 'predictions': ps})
    selected, diagnostics = fit_routes(candidates, rows, [by_source[r['source_group']] for r in rows])
    proposed = selected
    selected, bundle, guard = guarded_routes(pooled, candidates, proposed, rows, extraction)
    return {'fit_sources': [r['source_group'] for r in rows], 'pooled': pooled,
            'candidates': candidates, 'local_registry': local_registry,
            'scope_diagnostics': diagnostics, 'selected_routes': selected,
            'individual_route_proposals': proposed, 'whole_system_guard': guard,
            'inner_pooled_oof': inner, 'bundle': bundle}


def evaluate(context, rows):
    decisions = HierarchyExecutor(context['bundle']).predict_records(
        [r['features'] for r in rows], [r['scope'] for r in rows])
    pooled = _predict(context['pooled'], rows)
    experts = {k: _predict(v['runtime'], rows) for k, v in context['candidates'].items()}
    return {'cases': [{'case': r['case'], 'source_group': r['source_group'], 'reference': r['reference'],
                      'pooled_prediction': p['prediction'], **d} for r, p, d in zip(rows, pooled, decisions)],
            'pooled_metrics': score(rows, pooled), 'routed_metrics': score(rows, decisions),
            'fallback_count': sum(d['fallback'] for d in decisions),
            'route_counts': dict(Counter(d['served_node'] for d in decisions)),
            'oracle_correct_count': sum(any(p[i]['prediction'] == r['reference'] for p in [pooled, *experts.values()])
                                        for i, r in enumerate(rows)),
            'oracle_scope': 'Diagnostic only: reference-dependent best expert is never used by routing.'}

