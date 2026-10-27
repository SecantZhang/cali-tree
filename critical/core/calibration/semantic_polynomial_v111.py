"""Exact shared semantic terms from shallow residual trees.

A depth-two tree equals a baseline, two single-condition effects and their
interaction. Merge equal conditions across trees rather than listing all four
branches separately. No data-dependent pruning or score refitting occurs.
"""
from .semantic_residual_runtime_v104 import compile_residual, f32, render, ResidualExecutor
from .local_semantic_runtime_v99 import content_ref
from ..decision.artifacts import digest


def compile_polynomial(native, metadata):
    reference = compile_residual(native, metadata)
    mapping = {r['feature_index']: metadata['features'][r['flat_feature_index']] for r in native['features_info']['float_features']}
    scale, native_bias = native['scale_and_bias']; bias = list(native_bias); terms = {}
    for tree in native['oblivious_trees']:
        splits = tree.get('splits') or []; depth = len(splits)
        for subset in range(1 << depth):
            coefficient = [0., 0., 0.]
            for vertex in range(1 << depth):
                if vertex & ~subset:
                    continue
                sign = (-1)**(subset.bit_count()-vertex.bit_count())
                for c in range(3):
                    coefficient[c] += sign*scale*tree['leaf_values'][3*vertex+c]
            # Several thresholds on the same value reduce to the strictest
            # lower bound; this is an algebraic identity over all finite inputs.
            bounds = {}
            for j, split in enumerate(splits):
                if subset & (1 << j):
                    name = mapping[split['float_feature_index']]; border = f32(split['border'])
                    bounds[name] = max(bounds.get(name, border), border)
            key = tuple(sorted(bounds.items())); destination = terms.setdefault(key, [0., 0., 0.]) if key else bias
            for c in range(3):
                destination[c] += coefficient[c]
    clauses = [{'conditions': [{'feature': n, 'border': b, 'greater': True} for n, b in key], 'weights': values}
               for key, values in sorted(terms.items()) if any(values)]
    if not clauses:
        # A constant model still uses the existing executor's closed artifact
        # format. An explicit zero clause leaves its entire effect in the bias.
        clauses = [{'conditions': [], 'weights': [0., 0., 0.]}]
    used = sorted({t['feature'] for clause in clauses for t in clause['conditions']})
    result = {k: v for k, v in reference.items() if k not in ('artifact_ref', 'rubric', 'features', 'feature_descriptions', 'clauses', 'bias')}
    result.update(features=used, feature_descriptions={n: metadata['feature_descriptions'][n] for n in used}, clauses=clauses, bias=bias,
        compilation={'version': 'semantic-polynomial-v111', 'method': 'Exact Boolean-lattice/Mobius expansion, merging equivalent positive conjunctions. No pruning, fitting or new observations.',
                     'source_clauses_ref': reference['artifact_ref'], 'source_clauses': len(reference['clauses']), 'native_ref': digest(native)})
    result['rubric'] = render(result); result['artifact_ref'] = content_ref(result)
    ResidualExecutor(result)
    return result
