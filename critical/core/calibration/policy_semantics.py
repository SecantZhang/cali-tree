"""Compile a learned shared ordinal policy into explicit semantic conditions.

Minimal sufficient condition sets preserve the teacher's actual interactions.
No new vetoes are invented and no weights or score arithmetic enter execution.
"""
from copy import deepcopy
from itertools import product
import math

from .base import Calibrator
from .visibility_calibration import VisibilityOrdinalCalibrator
from ..decision.artifacts import digest
from ..decision.semantic_evidence import QUALITIES

VERSION='learned-policy-semantic-conditions-v8'
GENERAL_STATES=('absent','trace','substantial','near_complete','complete')
STATES={k:GENERAL_STATES for k in QUALITIES}
STATES['identity']=('wrong_target','weak_correspondence','category_or_redesign','plausible_instance','distinctive_instance')
STATES['preservation']=('meaning_destroyed','major_damage','noticeable_collateral','incidental_deviation','compatible_changes')
GENERAL_MEANINGS=('No meaningful realization, or an outcome that contradicts the request.',
    'A weak trace toward the request with its defining aspect missing.',
    'Substantial recognizable progress with a material portion missing.',
    'Near-complete requested meaning with limited remaining deviation.',
    'Requested meaning coherently achieved within ordinary tolerance.')
FEATURE_MEANINGS={'progress':'Meaningful progress toward the defining requested intent, not unrelated activity.',
    'endpoint':'Realization of the actual requested resulting state, including material actions and relations.',
    'identity':'Correspondence of the intended original instance under the authorized transformation.',
    'relation':'Fulfillment of explicitly requested spatial, contact, containment, or interaction relations.',
    'attribute':'Fulfillment of requested colors, materials, shapes, styles, or other attributes.',
    'scope':'Coverage of the intended target, region, or scene; coverage and success are distinct.',
    'quantity':'Requested counts and identity-preserving changes; a duplicate can defeat relocating an original.',
    'preservation':'Compatibility of other changes with the instruction, not a count of changed pixels.'}
MEANINGS={k:dict(zip(STATES[k],GENERAL_MEANINGS)) for k in QUALITIES}
MEANINGS['identity']=dict(zip(STATES['identity'],(
    'Clearly wrong intended target.','Weak correspondence to the intended original instance.',
    'Only class or category correspondence, or conspicuous redesign.',
    'Plausible retained original instance with limited drift.',
    'Distinctive correspondence retained under the authorized transformation.')))
MEANINGS['preservation']=dict(zip(STATES['preservation'],(
    'Collateral changes defeat the core intended meaning.','Major unrequested semantic destruction.',
    'Noticeable collateral change with some intended meaning retained.',
    'Incidental deviations that leave the intended edit coherent.',
    'No defeating collateral change; explicitly authorized transformations are allowed.')))


def semantic_record(feature):
    """Convert existing bounds into named states without consulting any label."""
    if set(feature)!={'lower','upper','descriptor'}:raise ValueError('Expected anonymous evidence bounds')
    if any(len(feature[k])!=len(QUALITIES) for k in ('lower','upper')):raise ValueError('Eight facts required')
    if any(type(v) is not int or not 0<=v<=4 for k in ('lower','upper') for v in feature[k]):raise ValueError('Invalid grade')
    if any(a>b for a,b in zip(feature['lower'],feature['upper'])):raise ValueError('Reversed bounds')
    return {'has_observation':feature['descriptor'] is not None,
        'lower':{k:STATES[k][v] for k,v in zip(QUALITIES,feature['lower'])},
        'upper':{k:STATES[k][v] for k,v in zip(QUALITIES,feature['upper'])}}


def frontier(weights,cut):
    active=[i for i,w in enumerate(weights) if w]
    result=[]
    for values in product(range(5),repeat=len(active)):
        score=sum(weights[i]*v for i,v in zip(active,values))
        if score<cut or any(v and score-weights[i]>=cut for i,v in zip(active,values)):continue
        result.append([{'feature':QUALITIES[i],'minimum_state':STATES[QUALITIES[i]][v]}
                       for i,v in zip(active,values) if v])
    return result


class SemanticConditionPolicy(Calibrator):
    version=VERSION
    def fit(self,X,y,*,sample_weight=None):
        raise NotImplementedError('Compile from a learned teacher; this transformation never fits labels')

    @classmethod
    def from_teacher(cls,artifact):
        # Reuse the original strict artifact validator before compiling.
        VisibilityOrdinalCalibrator.restore(artifact)
        if any(artifact['offsets']):raise ValueError('This compiler supports shared teachers without cluster offsets')
        w=artifact['weights'];lo,hi=artifact['cutpoints']
        obj=cls();obj._artifact={'version':VERSION,'teacher_ref':digest(artifact),
            'feature_names':list(QUALITIES),'states':{k:list(v) for k,v in STATES.items()},
            'meanings':deepcopy(MEANINGS),'at_least_partial':frontier(w,lo),'yes':frontier(w,hi),
            'uninspectable_label':artifact['uninspectable_label'],
            'execution':'Missing response -> unresolved. Learned uninspectability branch first. Otherwise Yes if any Yes conjunction holds; Partial if any at-least-Partial conjunction holds; No otherwise.',
            'scope':'Exact semantic-state translation, not a new claim about materiality or generalization.'}
        return obj

    @staticmethod
    def _validate(x):
        if not isinstance(x,dict) or set(x)!={'has_observation','lower','upper'} or type(x['has_observation']) is not bool:
            raise ValueError('Only anonymous named semantic states allowed')
        for bound in ('lower','upper'):
            if not isinstance(x[bound],dict) or set(x[bound])!=set(QUALITIES) or any(x[bound][k] not in STATES[k] for k in QUALITIES):
                raise ValueError('Invalid semantic state')
        if any(STATES[k].index(x['lower'][k])>STATES[k].index(x['upper'][k]) for k in QUALITIES):raise ValueError('Reversed states')

    def _label(self,values):
        for key,label in (('yes',2),('at_least_partial',1)):
            if any(all(STATES[t['feature']].index(values[t['feature']])>=STATES[t['feature']].index(t['minimum_state']) for t in clause)
                   for clause in self._artifact[key]):return label
        return 0

    def predict_records(self,X):
        result=[]
        for x in X:
            self._validate(x)
            if not x['has_observation']:
                result.append({'prediction':-1,'branch':'missing_response'});continue
            guard=self._artifact['uninspectable_label']
            unknown=lambda k:x['lower'][k]==STATES[k][0] and x['upper'][k]==STATES[k][-1]
            if guard is not None and unknown('progress') and unknown('endpoint'):
                result.append({'prediction':guard,'branch':'learned_uninspectability'});continue
            a,b=self._label(x['lower']),self._label(x['upper'])
            result.append({'prediction':a if a==b else -1,'branch':'semantic_conditions','label_bounds':[a,b]})
        return result

    def predict(self,X):
        return [math.nan if x['prediction']<0 else float(x['prediction']) for x in self.predict_records(X)]

    def metadata(self):return deepcopy(self._artifact)

    def render(self):
        a=self._artifact;used=sorted({t['feature'] for key in ('at_least_partial','yes') for clause in a[key] for t in clause})
        lines=['Apply the following learned semantic rule exactly. Every listed combination is a sufficient condition; all terms inside a combination must hold. Higher states satisfy lower minimum states. Do not add identity, endpoint, preservation, or other vetoes absent from this rule.']
        if a['uninspectable_label'] is not None:
            lines.append('If a completed evidence record cannot assess either progress or endpoint, return '+('No','Partial','Yes')[a['uninspectable_label']]+'. This is a learned evaluation convention, not a physical-state assertion.')
        for key,title in (('yes','Return Yes if any of these combinations holds:'),('at_least_partial','Otherwise return Partial if any of these combinations holds:')):
            lines.append(title)
            for clause in a[key]:lines.append('- '+' AND '.join(t['feature']+' is at least '+t['minimum_state'] for t in clause)+'.')
        lines.append('Otherwise return No. If unknown evidence permits different labels, return unresolved.')
        lines.append('Ordered semantic states, from least to greatest:')
        for k in used:
            lines.append(k+': '+FEATURE_MEANINGS[k]+' Ordered states: '+' < '.join(STATES[k])+'.')
            for state,meaning in MEANINGS[k].items():lines.append(state+': '+meaning)
        return '\n'.join(lines)

    @classmethod
    def restore(cls,artifact):
        a=deepcopy(artifact)
        if a.get('version')!=VERSION or a.get('feature_names')!=list(QUALITIES) or a.get('states')!={k:list(v) for k,v in STATES.items()} or a.get('meanings')!=MEANINGS:
            raise ValueError('Changed semantic vocabulary')
        if a.get('uninspectable_label') is not None and (type(a['uninspectable_label']) is not int or a['uninspectable_label'] not in range(3)):raise ValueError('Invalid semantic branch label')
        for key in ('at_least_partial','yes'):
            if not isinstance(a.get(key),list) or not a[key]:raise ValueError('Nonempty conditions required')
            for clause in a[key]:
                if not isinstance(clause,list) or not clause:raise ValueError('Nonempty conjunction required')
                seen=set()
                for term in clause:
                    if (not isinstance(term,dict) or set(term)!={'feature','minimum_state'} or term['feature'] not in STATES
                        or term['minimum_state'] not in STATES[term['feature']][1:] or term['feature'] in seen):raise ValueError('Invalid semantic term')
                    seen.add(term['feature'])
        obj=cls();obj._artifact=a;return obj
