"""Closed task-intent and regular-explanation cues for semantic calibration.

These are language mentions, not independently verified image facts. No learned
vocabulary, object/color names, source identifiers or example matching.
"""
import re

from ..decision.artifacts import digest
from ..decision.bound_evidence_v2 import validate_program

VERSION = 'intent-and-judge-explanation-v60'
INTENTS = {
    'color': r'\b(?:colou?r|recolou?r(?:ed|ing)?|hue|saturation)\b',
    'finish': r'\b(?:matte|glossy|gloss|shine|shiny|reflective|reflectivity|surface\s+finish)\b',
    'material_texture': r'\b(?:material|texture|textured|smooth|rough|transparent|translucent|opaque)\b',
    'size': r'\b(?:size|smaller|larger|bigger|shrink|enlarge|expand|scale|resize|shorter|taller|wider|narrower)\b',
    'shape': r'\b(?:shape|reshape|deform|distort|flatten|thicken|thin)\b',
    'orientation': r'\b(?:rotate|rotation|orientation|upright|upside.down|horizontal|vertical|tilt|turn\s+over)\b',
    'count': r'\b(?:number|count|duplicate|duplication|multiply|additional|one\s+more)\b',
    'all_targets': r'\b(?:all|every|each)\b',
    'addition': r'^\s*(?:add|insert|include|create|introduce)\b',
    'removal': r'\b(?:remove|delete|disappear|erase|eliminate)\b',
    'replacement': r'\b(?:replace|transform|convert|turn\s+.+\s+into)\b',
    'style': r'\b(?:style|restyle|pictograph|painting|watercolor|watercolour|sketch|cartoon|drawing|illustration)\b',
    'background': r'\bbackground\b',
    'global_scene': r'\b(?:entire\s+(?:image|scene|picture)|whole\s+(?:image|scene|picture)|remake\s+(?:this|the)\s+image)\b',
    'increase': r'^\s*(?:increase|enlarge|expand|raise|grow)\b',
    'decrease': r'^\s*(?:reduce|decrease|shrink|lower)\b',
    'opening': r'\b(?:open|opening|unfasten|unseal)\b',
    'closing': r'\b(?:close|closing|closed|shut|seal)\b',
    'movement': r'\b(?:move|moving|step|walk|pull|push|lift|raise|lower|bring)\b',
    'contact': r'\b(?:touch|touching|contact|lick|licking|kiss|bite|hold|holding|grasp|grasping)\b',
}
CUES = {
    'completion': r'\b(?:fully|complete(?:ly)?|entire(?:ly)?|achieved|fulfilled|realized|realised|accomplished)\b',
    'qualified_extent': r'\b(?:largely|mostly|substantially|predominantly|essentially)\b',
    'partial_extent': r'\b(?:partial(?:ly)?|partly|incomplete(?:ly)?|partway|somewhat)\b',
    'minor_extent': r'\b(?:minor|slight(?:ly)?|small\s+(?:change|deviation|difference)|subtle|limited|modest)\b',
    'major_extent': r'\b(?:major|severe(?:ly)?|significant(?:ly)?|substantial\s+(?:change|deviation|distortion)|dramatic(?:ally)?|dominated)\b',
    'unchanged': r'\b(?:unchanged|remains?\s+(?:the\s+)?same|no\s+(?:clear|visible|discernible)?\s*change)\b',
    'missing': r'\b(?:missing|absent|disappeared|removed|lost|no\s+longer\s+(?:visible|present|recognizable))\b',
    'retention': r'\b(?:recognizable|recognisable|retained|preserved|intact|consistent)\b',
    'collateral': r'\b(?:unrelated|surrounding|collateral|rest\s+of\s+the\s+scene|other\s+objects)\b',
    'identity_shape': r'\b(?:identity|shape|form|structure|geometry|layout|deformed|distorted|replaced|replacement)\b',
    'wrong_target': r'\b(?:wrong\s+(?:target|object|entity)|instead|elsewhere|unintended)\b',
    'uncertainty': r'\b(?:unclear|uncertain|ambiguous|appears?|seems?|suggesting|suggests|cannot\s+(?:confirm|tell|determine|verify))\b|\b[a-z]+-like\b',
    'visibility': r'\b(?:visible|shown|depicted|depicting|identifiable|obscured|occluded)\b',
}
NEGATION = re.compile(r"\b(?:not|no|never|without|cannot|can't|doesn't|isn't|hasn't|neither)\b", re.I)
PRESERVATION_CLAUSE = re.compile(r'\b(?:while|without|but|retaining|preserving|keeping)\b', re.I)
SPECS = {'intent_available': 'A valid compiled instruction is available.',
         'rationale_available': 'A valid regular-judge explanation is available.'}
SPECS.update({'intent_' + name: 'An authorized primary change mentions the fixed ' + name + ' operation.' for name in INTENTS})
for name in CUES:
    for polarity in ('mentioned', 'unnegated', 'negated'):
        SPECS[f'rationale_{name}_{polarity}'] = f'The regular explanation has a {polarity} {name} language cue, not an image-truth claim.'
CONTRACT_REF = digest({'version': VERSION, 'intents': INTENTS, 'cues': CUES, 'specs': SPECS,
                       'polarity': 'Negation within the four previous tokens in the same clause. No-longer-visible is a missing mention.',
                       'intent_scope': 'Authorized change prefix before while/without/but/retaining/preserving/keeping.',
                       'prohibited': 'Learned text vocabulary, object/color names, labels/references, IDs, hashes and signature lookup.'})


def project(program, judgment):
    values = dict.fromkeys(SPECS, False)
    if program is not None:
        validate_program(program)
        values['intent_available'] = True
        clauses = [PRESERVATION_CLAUSE.split(text, maxsplit=1)[0] for text in program['contract']['authorized_changes']]
        for name, pattern in INTENTS.items():
            values['intent_' + name] = any(re.search(pattern, text, re.I) is not None for text in clauses)
    if judgment is not None:
        if not isinstance(judgment, dict) or not isinstance(judgment.get('rationale'), str) or not judgment['rationale'].strip():
            raise ValueError('A valid regular explanation is required')
        values['rationale_available'] = True
        # Preserve but/although within a clause, but do not carry their preceding
        # negation to a separate proposition. Four words is a declared heuristic.
        clauses = re.split(r'[.!?;]|\b(?:but|however|although|whereas)\b', judgment['rationale'], flags=re.I)
        for text in clauses:
            for name, pattern in CUES.items():
                for match in re.finditer(pattern, text, re.I):
                    previous = ' '.join(re.findall(r"[a-z]+(?:'[a-z]+)?", text[:match.start()].lower())[-4:])
                    negated = NEGATION.search(previous) is not None
                    if name == 'missing' and match.group().lower().startswith('no longer'):
                        negated = False
                    values[f'rationale_{name}_mentioned'] = True
                    values[f'rationale_{name}_' + ('negated' if negated else 'unnegated')] = True
    return values
