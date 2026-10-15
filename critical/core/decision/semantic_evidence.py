"""Instruction-contract and graded visual evidence, with no reference labels."""
from pathlib import Path
from .compiler import TEXT, array, enum, media_inputs, object_schema

VERSION = 'semantic-contract-evidence-v5'
TEMPLATE = Path(__file__).parents[1] / 'prompts/templates/semantic_evidence_v5/extract.txt'
OPERATIONS = ('appearance', 'style', 'background', 'spatial_move', 'orientation',
              'state_action', 'addition', 'removal', 'replacement')
DESCRIPTORS = OPERATIONS + ('identity_required', 'relation_required', 'quantity_required', 'global_scope_explicit')
QUALITIES = ('progress', 'endpoint', 'identity', 'relation', 'attribute', 'scope', 'quantity', 'preservation')
GRADE = {'type': ['integer', 'null'], 'minimum': 0, 'maximum': 4}
FACT = object_schema({'applicability': enum(('applicable','not_applicable')), 'grade': GRADE, 'evidence': TEXT})
SCHEMA = object_schema({
    'contract': object_schema({'meaning': TEXT, **{name:{'type':'boolean'} for name in DESCRIPTORS}}),
    'aspects': {**array(object_schema({'source_quote': TEXT,
        'kind': enum(('identity','attribute','relation','state_action','presence','absence','count','style','scene','other')),
        'requirement': TEXT, 'observed': TEXT, 'grade': GRADE, 'shortfall': TEXT})), 'minItems':1,'maxItems':6},
    'qualities': object_schema({name: FACT for name in QUALITIES}),
})


def prompt(): return TEMPLATE.read_text()


def _text(x): return isinstance(x,str) and bool(x.strip())
def _grade(x): return x is None or type(x) is int and 0<=x<=4


def validate(value,instruction):
    if not _text(instruction) or not isinstance(value,dict) or set(value)!=set(SCHEMA['properties']):
        raise ValueError('Invalid semantic observation fields')
    c=value['contract']
    if (not isinstance(c,dict) or set(c)!={'meaning',*DESCRIPTORS} or not _text(c['meaning'])
            or any(type(c[k]) is not bool for k in DESCRIPTORS) or not any(c[k] for k in OPERATIONS)):
        raise ValueError('Invalid instruction-only semantic contract')
    aspects=value['aspects']
    if not isinstance(aspects,list) or not 1<=len(aspects)<=6:raise ValueError('One to six grounded aspects required')
    for a in aspects:
        if (not isinstance(a,dict) or set(a)!=set(SCHEMA['properties']['aspects']['items']['properties'])
                or not all(_text(a[k]) for k in ('source_quote','requirement','observed','shortfall'))
                or a['source_quote'] not in instruction or not _grade(a['grade'])
                or a['kind'] not in SCHEMA['properties']['aspects']['items']['properties']['kind']['enum']):
            raise ValueError('Invalid grounded semantic aspect')
    if not isinstance(value['qualities'],dict) or set(value['qualities'])!=set(QUALITIES):
        raise ValueError('All shared quality facts required')
    for f in value['qualities'].values():
        if (not isinstance(f,dict) or set(f)!={'applicability','grade','evidence'} or not _text(f['evidence'])
                or f['applicability'] not in ('applicable','not_applicable') or not _grade(f['grade'])
                or f['applicability']=='not_applicable' and f['grade']!=4):
            raise ValueError('Invalid quality fact; inapplicable means no unmet requirement (grade four)')
    return value


def feature_record(value,instruction):
    validate(value,instruction)
    facts=value['qualities']
    return {'lower':[0 if facts[k]['grade'] is None else facts[k]['grade'] for k in QUALITIES],
            'upper':[4 if facts[k]['grade'] is None else facts[k]['grade'] for k in QUALITIES],
            'descriptor':[int(value['contract'][k]) for k in DESCRIPTORS]}


class SemanticEvidenceExtractor:
    def __init__(self,calls): self.calls=calls
    def extract(self,instruction,evidence,*,case_id=None,max_tokens=16384):
        kwargs={'case_id':case_id} if case_id is not None else {}
        value,ref=self.calls.call('semantic_evidence_v5',{'instruction':instruction},SCHEMA,
            template=prompt(),media=media_inputs(evidence),slot='once',max_tokens=max_tokens,**kwargs)
        validate(value,instruction)
        return {'observations':value,'execution_ref':ref,'version':VERSION}
