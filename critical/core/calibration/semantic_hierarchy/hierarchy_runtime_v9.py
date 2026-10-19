"""Frozen instruction routing and deterministic portable evidence execution."""
from copy import deepcopy

from .portable_features_v8 import CONTRACT_REF, validate_record
from .portable_runtime_v8 import PortableRuleExecutor
from .hierarchy_scopes_v9 import CONTRACT_REF as SCOPE_REF, matches, validate_scope, validate_values
from .hierarchy_protocol_v9 import VERSION, SEARCH, ROUTING, content_ref, sealed


def export_bundle(pooled, nodes, routes, extraction):
    value = {'version': VERSION, 'feature_contract_ref': CONTRACT_REF, 'scope_contract_ref': SCOPE_REF,
             'pooled': deepcopy(pooled), 'nodes': deepcopy(nodes), 'routes': deepcopy(routes),
             'unresolved_specialist': 'pooled_fallback', 'extraction': deepcopy(extraction),
             'limits': deepcopy(SEARCH)}
    bundle = sealed(value, 'bundle_ref')
    HierarchyExecutor(bundle)
    return bundle


class HierarchyExecutor:
    """Neither labels nor training memberships are accepted by prediction APIs."""
    def __init__(self, bundle):
        required = {'version', 'feature_contract_ref', 'scope_contract_ref', 'pooled', 'nodes', 'routes',
                    'unresolved_specialist', 'extraction', 'limits', 'bundle_ref'}
        if (not isinstance(bundle, dict) or set(bundle) != required or bundle['version'] != VERSION
                or bundle['feature_contract_ref'] != CONTRACT_REF or bundle['scope_contract_ref'] != SCOPE_REF
                or bundle['limits'] != SEARCH or bundle['unresolved_specialist'] != 'pooled_fallback'
                or len(bundle['routes']) > ROUTING['max_routes']
                or content_ref(bundle, 'bundle_ref') != bundle['bundle_ref']):
            raise ValueError('Changed frozen hierarchy contract')
        self.pooled = PortableRuleExecutor(bundle['pooled'])
        self.nodes = {}
        for name, node in bundle['nodes'].items():
            if (not isinstance(name, str) or set(node) != {'policy', 'children', 'depth'}
                    or not isinstance(node['children'], list) or len(set(node['children'])) != len(node['children'])
                    or len(node['children']) not in (0, 2)
                    or type(node['depth']) is not int or not 0 <= node['depth'] <= SEARCH['max_hierarchy_depth']):
                raise ValueError('Invalid hierarchy node')
            self.nodes[name] = PortableRuleExecutor(node['policy'])
        seen, visiting = set(), set()
        def visit(name):
            if name not in self.nodes or name in visiting:
                raise ValueError('Dangling or cyclic hierarchy edge')
            if name in seen:
                return
            visiting.add(name)
            node = bundle['nodes'][name]
            for child in node['children']:
                visit(child)
            depth = 1 + max(bundle['nodes'][c]['depth'] for c in node['children']) if node['children'] else 0
            if node['depth'] != depth:
                raise ValueError('Incorrect hierarchy depth')
            visiting.remove(name); seen.add(name)
        for name in self.nodes:
            visit(name)
        routed = set()
        for route in bundle['routes']:
            if (set(route) != {'node_id', 'scope'} or route['node_id'] not in self.nodes
                    or route['node_id'] in routed):
                raise ValueError('Invalid or duplicate routed policy')
            validate_scope(route['scope']); routed.add(route['node_id'])
        reachable = set()
        def collect(name):
            if name in reachable:
                return
            reachable.add(name)
            for child in bundle['nodes'][name]['children']:
                collect(child)
        for name in routed:
            collect(name)
        if reachable != set(self.nodes):
            raise ValueError('Deployment contains unused training policies')
        self.bundle = deepcopy(bundle)

    def predict_records(self, records, scopes):
        records, scopes = list(records), list(scopes)
        if len(records) != len(scopes):
            raise ValueError('Unpaired evidence and instruction scopes')
        result = []
        for record, scope in zip(records, scopes):
            validate_record(record); validate_values(scope)
            route = next((r for r in self.bundle['routes'] if matches(scope, r['scope'])), None)
            selected = route['node_id'] if route else 'pooled'
            decision = (self.nodes[selected] if route else self.pooled).predict_records([record])[0]
            fallback = route is None or decision['prediction'] < 0
            evaluations = 1
            if route is not None and decision['prediction'] < 0:
                decision = self.pooled.predict_records([record])[0]; evaluations = 2
            result.append({**decision, 'selected_node': selected, 'served_node': 'pooled' if fallback else selected,
                           'fallback': fallback, 'policy_evaluations': evaluations,
                           'route_scope': deepcopy(route['scope']) if route else None,
                           'route_reason': 'instruction_scope' if route else 'no_supported_instruction_scope'})
        return result

    def export(self):
        return deepcopy(self.bundle)

    def predict_bound(self, program, observation, pair_ref, interpretation):
        """Execute cached/fresh upstream outputs after authenticating bindings.

        Images are read once by the upstream M1 observer. This layer never
        receives a reference label and never calls a model or optimizer.
        """
        from .portable_features_v8 import project
        from .hierarchy_scopes_v9 import project as project_scope
        record = project(program, observation, pair_ref, interpretation) if observation is not None else None
        return self.predict_records([record], [project_scope(program)])[0]

