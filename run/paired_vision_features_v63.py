"""Dependency-light, input-relative visual scores; no raw embeddings in policies.

Text identifies the current input's intended target/property. Only reusable
scalar comparisons and fixed Boolean thresholds reach the calibration model.
"""
import hashlib
import json
import re

import numpy as np

MODEL = 'google/siglip2-base-patch16-224'
REVISION = '75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2'
VERSION = 'paired-semantic-vision-v63'
GRIDS = (1, 2, 3)
COLORS = ('red', 'green', 'blue', 'yellow', 'purple', 'orange', 'brown', 'gray', 'black', 'white')
FINISHES = ('matte', 'glossy')
MATERIALS = ('metallic', 'rubber', 'wooden', 'plastic', 'glass')
PRESERVATION = ('global_preservation', 'patch_preservation_min', 'patch_preservation_q25', 'patch_preservation_median', 'target_match')
GROUNDING = ('target_source', 'target_edited', 'goal_global_source', 'goal_global_edited', 'goal_patch_source', 'goal_patch_edited')
DELTAS = ('goal_global_delta', 'goal_patch_delta', 'property_delta_min', 'property_delta_mean', 'property_delta_max')
MARGINS = ('target_source_margin', 'property_margin_source', 'property_margin_edited')
BOUNDS = {**{name: (.5, .7, .8, .85, .9, .93, .95, .97, .99) for name in PRESERVATION},
          **{name: (-.1, 0., .1, .15, .2, .25, .3, .4, .5) for name in GROUNDING},
          **{name: (-.1, -.05, -.02, -.01, 0., .01, .02, .05, .1) for name in DELTAS + MARGINS}}
SPECS = {'vision_available': 'A valid frozen-encoder comparison is available.',
         'vision_property_probe_available': 'At least one explicitly parsed requested color/finish/material property probe is available.'}
SPECS.update({f'vision_{name}_ge_{threshold}': f'The input-relative {name} score is at least {threshold}; model similarity is not a factual oracle.'
              for name, thresholds in BOUNDS.items() for threshold in thresholds})


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


CONTRACT_REF = digest({'version': VERSION, 'model': MODEL, 'revision': REVISION, 'grids': GRIDS,
                       'colors': COLORS, 'finishes': FINISHES, 'materials': MATERIALS, 'bounds': BOUNDS,
                       'target_match': 'Best source local patch for compiled target; match edited patch by source-patch cosine, with no coordinate predictors.',
                       'property': 'Requested endpoint versus alternative attribute values on corresponding target patches; all labels/data references excluded.',
                       'prohibited': 'Raw embeddings, file names, IDs, coordinates or object/property-value identity flags as learned predictors.'})


def query_plan(program):
    outcome = [c for c in program['checks'] if c['role'] == 'outcome']
    target = outcome[0]['target'] if outcome else 'the scene'
    base = re.sub(r'\b(?:the|a|an|original|source|existing)\b', ' ', target, flags=re.I)
    primary = [re.split(r'\b(?:while|without|but|retaining|preserving|keeping)\b', text, maxsplit=1, flags=re.I)[0].strip()
               for text in program['contract']['authorized_changes']]
    probes = []
    if any(c['kind'] == 'attribute' for c in outcome):
        for text in primary:
            lower = text.lower().replace('grey', 'gray').rstrip(' .')
            colors = re.findall(r'\b(?:' + '|'.join(COLORS) + r')\b', lower)
            families = []
            if colors and (re.search(r'\bcolou?r\b', lower) or len(set(colors)) > 1 or lower.endswith(colors[-1])):
                families.append(('color', colors[-1], COLORS, 'A photo of a {value} {target}.'))
            finishes = re.findall(r'\b(?:matte|glossy|shiny|reflective)\b', lower)
            if finishes and (re.search(r'\b(?:finish|surface)\b', lower) or lower.endswith(finishes[-1])):
                desired = 'matte' if finishes[-1] == 'matte' else 'glossy'
                families.append(('finish', desired, FINISHES, 'A photo of a {target} with a {value} surface.'))
            materials = re.findall(r'\b(?:' + '|'.join(MATERIALS) + r')\b', lower)
            if materials and lower.endswith(materials[-1]):
                families.append(('material', materials[-1], MATERIALS, 'A photo of a {value} {target}.'))
            for family, desired, choices, template in families:
                cleaned = re.sub(r'\b(?:' + '|'.join(choices) + r')\b', ' ', base, flags=re.I)
                cleaned = re.sub(r'\s+', ' ', cleaned).strip(' .-')
                probes.append({'family': family, 'positive': template.format(value=desired, target=cleaned),
                               'negative': [template.format(value=value, target=cleaned) for value in choices if value != desired]})
    return {'target': 'A photo of ' + target.strip(' .') + '.',
            'goal': 'A picture showing this edit: ' + program['instruction'], 'probes': probes}


def crop_boxes(width, height):
    return [(round(x * width / grid), round(y * height / grid), round((x + 1) * width / grid), round((y + 1) * height / grid))
            for grid in GRIDS for y in range(grid) for x in range(grid)]


def normalized(values):
    values = np.asarray(values, dtype=np.float64)
    norm = np.linalg.norm(values, axis=-1, keepdims=True)
    if np.any(~np.isfinite(values)) or np.any(norm <= 0):
        raise ValueError('Finite nonzero encoder vectors required')
    return values / norm


def statistics(source, edited, text):
    a, b = normalized(source), normalized(edited)
    if a.shape != b.shape or a.ndim != 2 or len(a) != 14:
        raise ValueError('Aligned full-image plus 2x2/3x3 patch vectors required')
    target, goal = normalized(text['target']), normalized(text['goal'])
    affinity = a[1:] @ b[1:].T
    best = affinity.max(axis=1)
    target_scores = a[1:] @ target
    source_index = int(np.argmax(target_scores))
    edited_index = int(np.argmax(affinity[source_index]))
    left, right = a[source_index + 1], b[edited_index + 1]
    ordered = np.sort(target_scores)
    result = {'global_preservation': float(a[0] @ b[0]), 'patch_preservation_min': float(best.min()),
              'patch_preservation_q25': float(np.quantile(best, .25)), 'patch_preservation_median': float(np.median(best)),
              'target_match': float(affinity[source_index, edited_index]), 'target_source': float(left @ target),
              'target_edited': float(right @ target), 'target_source_margin': float(ordered[-1] - ordered[-2]),
              'goal_global_source': float(a[0] @ goal), 'goal_global_edited': float(b[0] @ goal),
              'goal_patch_source': float(left @ goal), 'goal_patch_edited': float(right @ goal)}
    result['goal_global_delta'] = result['goal_global_edited'] - result['goal_global_source']
    result['goal_patch_delta'] = result['goal_patch_edited'] - result['goal_patch_source']
    margins = []
    for probe in text['probes']:
        positive, negative = normalized(probe['positive']), normalized(probe['negative'])
        margins.append((float(left @ positive - np.max(negative @ left)), float(right @ positive - np.max(negative @ right))))
    result['property_probe_available'] = bool(margins)
    if margins:
        before, after = np.asarray(margins).T
        result.update(property_margin_source=float(before.mean()), property_margin_edited=float(after.mean()),
                      property_delta_min=float((after - before).min()), property_delta_mean=float((after - before).mean()),
                      property_delta_max=float((after - before).max()))
    else:
        result.update({name: 0. for name in ('property_margin_source', 'property_margin_edited', 'property_delta_min', 'property_delta_mean', 'property_delta_max')})
    return result


def predicates(measurements):
    if measurements is None:
        return dict.fromkeys(SPECS, False)
    values = {'vision_available': True, 'vision_property_probe_available': bool(measurements['property_probe_available'])}
    for name, thresholds in BOUNDS.items():
        value = float(measurements[name])
        if not np.isfinite(value):
            raise ValueError('Finite visual scores required')
        for threshold in thresholds:
            values[f'vision_{name}_ge_{threshold}'] = bool(value >= threshold)
    return values
