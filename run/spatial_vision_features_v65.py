"""Goal-oriented relative geometry from frozen text-guided local patches.

Absolute coordinates and entity names never reach the grade learner. These are
coarse localization signals, not certified boxes or three-dimensional facts.
"""
import re

import numpy as np

from run.paired_vision_features_v63 import normalized, digest

VERSION = 'goal-relative-patch-geometry-v65'
AXES = {'left': (-1., 0.), 'right': (1., 0.), 'above': (0., -1.), 'below': (0., 1.)}
TYPES = ('axis', 'proximity', 'motion')
SCORES = tuple(f'spatial_{kind}_{stat}' for kind in TYPES for stat in ('source_margin_min', 'edited_margin_min', 'delta_min', 'delta_mean')) + ('spatial_grounding_min', 'spatial_grounding_margin_min')
CONTRACT_REF = digest({'version': VERSION, 'axes': AXES, 'types': TYPES, 'scores': SCORES,
                       'localizer': 'Softmax40 of query cosine on nine equal3x3 crops; relative margins only, no absolute coordinate predictors.',
                       'limits': 'No front/behind/depth, certified segmentation, raw embeddings, source IDs or label-based entity selection.'})


def caption(value):
    return 'A photo of ' + value.strip(' .') + '.'


def probes(program):
    result = []
    for check in program['checks']:
        if check['role'] != 'outcome' or check['kind'] != 'spatial_relation':
            continue
        clauses = [r['source_quote'] for r in program['requirements'] if r['id'] in check['requirement_ids']]
        text = ' '.join(clauses).lower()
        if re.search(r"\b(?:not|don't|never|avoid)\b", text):
            continue
        text = re.split(r'\b(?:while|without|rather than)\b', text, maxsplit=1)[0]
        target, reference = check['target'], check['reference']
        if ' and ' in reference.lower() and re.search(r'\b(?:position|location|source)\b', reference.split(' and ', 1)[-1], re.I):
            reference = reference.split(' and ', 1)[0]
        generic = re.search(r'\b(?:position|distance|locations?|image|scene|instruction|request|camera|viewer)\b', reference, re.I) or re.match(r'\s*(?:its|their)\b', reference, re.I)
        closer, farther = re.search(r'\b(?:closer|nearer|next to|near|beside|against|onto|into)\b', text), re.search(r'\b(?:farther|further apart|away from)\b', text)
        if generic and (closer or farther):
            pair = re.split(r'\s+and\s+', target, flags=re.I)
            if len(pair) == 2:
                target, reference, generic = pair[0], pair[1], False
        patterns = {'left': r'\bleft(?:\s+side)?\s+of\b', 'right': r'\bright(?:\s+side)?\s+of\b',
                    'above': r'\b(?:above|over|on top of)\b', 'below': r'\b(?:below|under|beneath)\b'}
        directions = [key for key, pattern in patterns.items() if re.search(pattern, text)]
        if not generic and len(directions) == 1:
            result.append({'type': 'axis', 'axis': directions[0], 'target': caption(target), 'reference': caption(reference)})
        elif not generic and bool(closer) != bool(farther):
            result.append({'type': 'proximity', 'sign': 1. if closer else -1., 'target': caption(target), 'reference': caption(reference)})
        elif generic:
            up = re.search(r'\b(?:up|upward|upwards|lift|raise)\b', text)
            down = re.search(r'\b(?:down|downward|downwards|fall|drop|lower)\b', text)
            if bool(up) != bool(down):
                result.append({'type': 'motion', 'axis': 'above' if up else 'below', 'target': caption(target)})
    return result


def locate(image_vectors, query):
    scores = normalized(image_vectors)[-9:] @ normalized(query)
    weights = np.exp(40. * (scores - scores.max()))
    weights /= weights.sum()
    centers = np.asarray([((x + .5) / 3, (y + .5) / 3) for y in range(3) for x in range(3)])
    ordered = np.sort(scores)
    return weights @ centers, float(ordered[-1]), float(ordered[-1] - ordered[-2])


def relative_margin(target, reference, axis):
    return float((np.asarray(target) - np.asarray(reference)) @ np.asarray(AXES[axis]))


def statistics(source, edited, embedded_probes):
    collected = {kind: [] for kind in TYPES}
    grounding, gaps = [], []
    for probe in embedded_probes:
        a, a_score, a_gap = locate(source, probe['target_vector'])
        b, b_score, b_gap = locate(edited, probe['target_vector'])
        grounding += [a_score, b_score]; gaps += [a_gap, b_gap]
        if probe['type'] == 'motion':
            before, after = 0., relative_margin(b, a, probe['axis'])
        else:
            c, c_score, c_gap = locate(source, probe['reference_vector'])
            d, d_score, d_gap = locate(edited, probe['reference_vector'])
            grounding += [c_score, d_score]; gaps += [c_gap, d_gap]
            if probe['type'] == 'axis':
                before, after = relative_margin(a, c, probe['axis']), relative_margin(b, d, probe['axis'])
            else:
                before, after = probe['sign'] * (1 - np.linalg.norm(a - c)), probe['sign'] * (1 - np.linalg.norm(b - d))
        collected[probe['type']].append((before, after))
    result = {}
    for kind, values in collected.items():
        result['spatial_' + kind + '_available'] = bool(values)
        if values:
            before, after = np.asarray(values).T
            scores = (before.min(), after.min(), (after - before).min(), (after - before).mean())
        else:
            scores = (0.,) * 4
        for name, value in zip(('source_margin_min', 'edited_margin_min', 'delta_min', 'delta_mean'), scores):
            result[f'spatial_{kind}_{name}'] = float(value)
    result['spatial_grounding_min'] = min(grounding) if grounding else 0.
    result['spatial_grounding_margin_min'] = min(gaps) if gaps else 0.
    return result
