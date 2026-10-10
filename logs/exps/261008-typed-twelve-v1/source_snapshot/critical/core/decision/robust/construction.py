"""Models describe ordered evidence; code constructs the executable chain."""
from dataclasses import replace
from copy import deepcopy
from pathlib import Path

from critical.core.decision.artifacts import save_json
from critical.core.decision.compiler import array, object_schema, TEXT
from .models import Node, GATES, export_program
from .refinement import EvidenceRefinementCompiler, validate_refinement, template as execution_template
from .errors import GraphValidationError

PROTOCOL = 'typed-evidence-v1'
TEMPLATES = Path(__file__).parents[2] / 'prompts/templates/typed_evidence_v1'


def template(name):
    return (TEMPLATES / (name + '.txt')).read_text()


SUPPORT_SPEC_SCHEMA = object_schema({**{k: TEXT for k in ('requirement_id','question','criteria','binding')},
                                    'evidence_from': array({'type':'integer'})})
ORDERED_SCHEMA = object_schema({'supports': array(SUPPORT_SPEC_SCHEMA), 'fulfillment_criteria': TEXT})


def construct_ordered_program(original, specification):
    if set(specification) != {'supports','fulfillment_criteria'} or len(original.outcomes) != 1:
        raise ValueError('Ordered compilation needs support specifications and one original outcome')
    specs = specification['supports']
    if not isinstance(specs, list) or not 2 <= len(specs) <= 3:
        raise ValueError('Need two or three support specifications; never truncate')
    if not isinstance(specification['fulfillment_criteria'], str) or not specification['fulfillment_criteria'].strip():
        raise ValueError('Explicit fulfillment criteria required')
    requirements = {r.id:r for r in original.requirements}
    supports, provenance = [], []
    for index, spec in enumerate(specs, 1):
        if set(spec) != set(SUPPORT_SPEC_SCHEMA['properties']):
            raise ValueError('Support specifications cannot contain manual graph fields')
        if any(not isinstance(spec[k], str) or not spec[k].strip() for k in ('question','criteria','binding','requirement_id')):
            raise ValueError('Missing support semantics or provenance')
        req = requirements.get(spec['requirement_id'])
        if req is None:
            raise ValueError('Support refers to an absent original requirement')
        refs = spec['evidence_from']
        if not isinstance(refs,list) or len(set(refs)) != len(refs) or any(type(i) is not int or not 1 <= i < index for i in refs):
            raise GraphValidationError('forward_evidence_reference', f's{index} may reference only earlier support indices', node_id=f's{index}')
        nid = f's{index}'
        supports.append(Node(nid,'support','',f's{index-1}' if index>1 else '',GATES if index>1 else (),
            tuple(f's{i}' for i in sorted(refs)),spec['question'],spec['criteria'],spec['binding']))
        provenance.append({'node_id':nid,'requirement_id':req.id,'source_phrase':req.source_phrase})
    requested = next(n for n in original.nodes if n.role=='requested')
    readout = replace(requested,id='fulfillment',parent=supports[-1].id,active_on=GATES,
        dependencies=tuple(n.id for n in supports),criteria=specification['fulfillment_criteria'],inferences=())
    program = validate_refinement(replace(original,nodes=(*supports,readout),mode='tree',
        checker_template=execution_template('check')),original)
    return program, provenance


class TypedEvidenceCompiler(EvidenceRefinementCompiler):
    def __init__(self,calls,original,*,support_count=None):
        super().__init__(calls,original)
        if support_count is not None and (type(support_count) is not int or support_count not in (2,3)):
            raise ValueError('Requested support count must be two or three')
        self.support_count=support_count

    def compile(self, instruction, rubric, *, slot):
        if (instruction,rubric)!=(self.original.instruction,self.original.rubric):
            raise ValueError('Instruction or rubric changed')
        payload={'instruction':instruction,'rubric':rubric,
            'requirements':[{'id':r.id,'text':r.text,'source_phrase':r.source_phrase} for r in self.original.requirements],
            'outcome':self.original.to_dict()['outcomes'][0], 'protocol':PROTOCOL, 'max_checks':4}
        schema=ORDERED_SCHEMA;instructions=template('compile')
        if self.support_count is not None:
            schema=deepcopy(ORDERED_SCHEMA)
            schema['properties']['supports'].update(minItems=self.support_count,maxItems=self.support_count)
            payload['required_supports']=self.support_count
            instructions+=f'\nThis experiment requires EXACTLY {self.support_count} support specifications; do not return a different count.'
        spec, ref = self.calls.call('compile_typed',payload,schema,template=instructions,slot=slot,max_tokens=2048)
        if self.support_count is not None and len(spec.get('supports',[]))!=self.support_count:
            raise ValueError('Compiler did not return the required support count')
        program, provenance = construct_ordered_program(self.original,spec)
        save_json(self.calls.directory/'constructions'/f'{ref}.json',{'protocol':PROTOCOL,
            'specification':spec,'program':export_program(program),'provenance':provenance})
        return program
