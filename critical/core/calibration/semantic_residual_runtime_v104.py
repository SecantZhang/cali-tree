"""Portable weighted semantic clauses with bound local evidence and safe fallback.

The exported clauses exactly execute the small residual booster. They are
statistical grade adjustments, not independent claims about image truth.
"""
from copy import deepcopy
import math
import struct

from . import local_warranted_rubric_v97 as local
from . import visual_semantic_policy_v69 as visual
from .local_semantic_runtime_v99 import LocalSemanticPolicy, content_ref, checkpoint_compute_ref
from ..decision import local_rubric_evidence_v94 as facts
from ..decision.artifacts import digest

VERSION = 'bound-weighted-semantic-rubric-v104'
SUPPORT = {'teacher_support_'+label: 'The existing teacher assigns this model support to '+label+'; it is not calibrated correctness.' for label in local.LABELS}


def f32(value):
    return struct.unpack('f', struct.pack('f', value))[0]


def admissible(values, teacher, regular, proposed):
    """A changed grade needs a positive warrant or independent-judge review."""
    if values['local_'+local.LABELS[proposed]+'_ready']:
        return 'affirmative_local_grade_warrant'
    views = local.view_flags(values, teacher, regular)
    reason = (values['local_any_uncertainty'] or values['local_claim_conflict'] or values['local_progress_witness'] or
              (views['local_view_teacher_unwarranted'] and views['local_view_regular_warranted']))
    return 'independent_regular_review' if proposed == regular and regular != teacher and reason else None


def render(artifact):
    lines = ['Within the existing review region, begin with the three teacher class masses.',
             'Add strength times the bias and every matching weighted clause below; floor each mass at 1e-9, normalize, and choose the largest mass (No, Partial, Yes order breaks ties).',
             'Change the grade only with an affirmative local grade warrant, or to the existing regular judgment with a positive independent-review reason. Otherwise retain the existing decision.',
             'These weights predict human grades; they are not physical certificates or calibrated correctness probabilities.',
             'Strength: '+str(artifact['strength'])+'. Bias [No, Partial, Yes]: '+str(artifact['bias'])+'.']
    for i, clause in enumerate(artifact['clauses'], 1):
        terms = []
        for t in clause['conditions']:
            desc = artifact['feature_descriptions'][t['feature']]
            if t['feature'] not in SUPPORT:
                terms.append(desc if t['greater'] else 'Not established: '+desc)
            else:
                terms.append(desc+' '+('>' if t['greater'] else '<=')+' '+str(t['border'])+' after float32 conversion')
        lines.append(str(i)+'. IF '+(' AND '.join(terms) or 'always')+' THEN add [No, Partial, Yes] '+str(clause['weights'])+'.')
    return '\n'.join(lines)+'\n'


def compile_residual(native, metadata):
    if metadata['version'] != 'source-held-semantic-residual-v103' or metadata['depth'] not in (2, 3) or metadata['iterations'] != 128:
        raise ValueError('Frozen small semantic residual required')
    features = metadata['features']; descriptions = metadata['feature_descriptions']
    if len(features) != len(set(features)) or set(descriptions) != set(features):
        raise ValueError('Named semantic vocabulary required')
    scale, bias = native['scale_and_bias']
    if len(bias) != 3 or not math.isfinite(scale) or any(not math.isfinite(b) for b in bias):
        raise ValueError('Finite three-dimensional residual required')
    mapping = {f['feature_index']: features[f['flat_feature_index']] for f in native['features_info']['float_features']}
    merged = {}
    if len(native['oblivious_trees']) != metadata['iterations']:
        raise ValueError('Frozen tree count differs')
    for tree in native['oblivious_trees']:
        splits = tree.get('splits') or []
        if len(splits) > metadata['depth'] or len(tree['leaf_values']) != 3*(2**len(splits)):
            raise ValueError('Invalid shallow regression tree')
        for leaf in range(2**len(splits)):
            conditions = []
            for j, split in enumerate(splits):
                if split['split_type'] != 'FloatFeature':
                    raise ValueError('Only semantic numeric/Boolean splits supported')
                conditions.append((mapping[split['float_feature_index']], f32(split['border']), bool(leaf & (1 << j))))
            # Equivalent branches of different trees share one weighted clause.
            key = tuple(sorted(set(conditions)))
            weights = merged.setdefault(key, [0., 0., 0.])
            for c in range(3):
                weights[c] += scale*tree['leaf_values'][3*leaf+c]
    clauses = [{'conditions': [{'feature': n, 'border': b, 'greater': g} for n, b, g in key], 'weights': value}
               for key, value in sorted(merged.items()) if any(value)]
    used = sorted({t['feature'] for clause in clauses for t in clause['conditions']})
    artifact = {'version': VERSION+'-clauses', 'features': used, 'feature_descriptions': {n: descriptions[n] for n in used},
                'clauses': clauses, 'bias': bias, 'strength': metadata['strength'], 'max_conditions': metadata['depth'],
                'source_tree_count': metadata['iterations'], 'native_model_ref': digest(native),
                'review_threshold': .8, 'guarded': True}
    artifact['rubric'] = render(artifact); artifact['artifact_ref'] = content_ref(artifact)
    return artifact


class ResidualExecutor:
    def __init__(self, artifact):
        allowed = {**local.DESCRIPTIONS, **SUPPORT}
        if (artifact.get('version') != VERSION+'-clauses' or artifact.get('artifact_ref') != content_ref(artifact) or
                artifact.get('review_threshold') != .8 or artifact.get('guarded') is not True or
                artifact.get('max_conditions') not in (2, 3) or artifact.get('source_tree_count') != 128 or
                type(artifact.get('strength')) not in (float, int) or artifact['strength'] not in (0., .25, .5, .75, 1.)):
            raise ValueError('Changed weighted semantic rubric')
        if (len(artifact['bias']) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in artifact['bias']) or
                not 1 <= len(artifact['clauses']) <= 1024):
            raise ValueError('Finite bounded clauses required')
        used = set()
        for clause in artifact['clauses']:
            if set(clause) != {'conditions', 'weights'} or len(clause['weights']) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in clause['weights']):
                raise ValueError('Finite three-grade clause weights required')
            if len(clause['conditions']) > artifact['max_conditions']:
                raise ValueError('Clause exceeds the shallow semantic bound')
            for t in clause['conditions']:
                if (set(t) != {'feature', 'border', 'greater'} or t['feature'] not in allowed or type(t['greater']) is not bool or
                        type(t['border']) not in (int, float) or not math.isfinite(t['border']) or
                        (t['feature'] not in SUPPORT and t['border'] != .5)):
                    raise ValueError('Closed semantic predicate required')
                used.add(t['feature'])
        if (artifact['features'] != sorted(used) or artifact['feature_descriptions'] != {n: allowed[n] for n in sorted(used)} or
                artifact['rubric'] != render(artifact)):
            raise ValueError('Rendered weighted rubric differs from executable clauses')
        self.artifact = deepcopy(artifact)

    def evaluate(self, values, support):
        if (len(support) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in support) or
                not math.isclose(sum(support), 1., abs_tol=1e-6)):
            raise ValueError('Normalized teacher support required')
        numeric = {}
        for n in self.artifact['features']:
            value = values.get(n)
            if (n not in SUPPORT and type(value) is not bool) or (n in SUPPORT and (type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1)):
                raise ValueError('Required semantic value unavailable')
            numeric[n] = f32(value)
        delta = list(self.artifact['bias']); matched = []
        for i, clause in enumerate(self.artifact['clauses']):
            if all((numeric[t['feature']] > f32(t['border'])) == t['greater'] for t in clause['conditions']):
                matched.append(i)
                for c in range(3):
                    delta[c] += clause['weights'][c]
        masses = [max(support[c]+self.artifact['strength']*delta[c], 1e-9) for c in range(3)]
        normalized = [v/sum(masses) for v in masses]
        return {'prediction': max(range(3), key=lambda c: normalized[c]), 'residual': delta,
                'corrected_model_mass': normalized, 'matching_clauses': matched}


def export_policy(base, native, metadata, profile, template, checkpoint):
    if digest(checkpoint) != profile['checkpoint_ref'] or metadata['observer_identity_ref'] != digest(profile):
        raise ValueError('Observer differs from the fitted residual')
    rubric = compile_residual(native, metadata)
    artifact = {'version': VERSION, 'base_ref': base.artifact['artifact_ref'], 'base_teacher_ref': base.artifact['base_teacher_ref'],
                'native_teacher_ref': metadata['teacher_ref'], 'rubric': rubric, 'observer_profile': deepcopy(profile),
                'observer_template': template, 'observer_template_ref': digest(template),
                'observer_checkpoint_compute_ref': checkpoint_compute_ref(checkpoint), 'local_contract_ref': local.CONTRACT_REF,
                'encoder_spec': deepcopy(base.artifact['encoder_spec'])}
    artifact['artifact_ref'] = content_ref(artifact); SemanticResidualPolicy(base, artifact)
    return artifact


class SemanticResidualPolicy(LocalSemanticPolicy):
    def __init__(self, base, artifact):
        profile = artifact['observer_profile']
        if (artifact.get('version') != VERSION or artifact.get('artifact_ref') != content_ref(artifact) or
                artifact.get('base_ref') != base.artifact['artifact_ref'] or artifact.get('base_teacher_ref') != base.artifact['base_teacher_ref'] or
                artifact.get('local_contract_ref') != local.CONTRACT_REF or digest(artifact['observer_template']) != artifact['observer_template_ref'] or
                profile['contract_ref'] != facts.CONTRACT_REF or profile['schema_ref'] != digest(facts.schema()) or
                profile['engine'] != 'local_qwen_grammar_v95' or artifact['encoder_spec'] != base.artifact['encoder_spec']):
            raise ValueError('Changed observer, base or semantic contract')
        self.base, self.artifact, self.rubric = base, deepcopy(artifact), ResidualExecutor(artifact['rubric'])

    def _resolve_from_base(self, base, inputs, local_record):
        if not self.review_route(base) or local_record is None:
            return base
        try:
            values = self._values(*inputs, base, local_record)
            values.update(zip(SUPPORT, base['class_support']))
            result = self.rubric.evaluate(values, base['class_support'])
            guard = admissible(values, int(base['prediction']), visual.regular_label(inputs[4]), result['prediction'])
        except (ValueError, KeyError, TypeError, IndexError, OverflowError):
            return {**base, 'local_review_error': 'invalid_or_unbound_local_observation'}
        if result['prediction'] == base['prediction'] or guard is None:
            return {**base, 'semantic_residual_agreement' if guard else 'semantic_residual_guard_rejected': result}
        return {'covered': True, 'prediction': result['prediction'], 'reason': 'semantic_residual_override',
                'semantic_residual': {**result, 'guard': guard}, 'local_observation_ref': local_record['record_ref'],
                'local_evidence': local_record['observation']['evidence'],
                'observer_identity_ref': digest(self.artifact['observer_profile']), 'base_route': base}
