"""Independent label-free compilation and label-blind semantic audits."""
from pathlib import Path
from .models import ProgramSpec, STATES, APPLICABILITY
from .validation import validate_program

TEMPLATES = Path(__file__).parents[1] / 'prompts/templates/decision_program_v2'
TEXT = {'type': 'string'}
def object_schema(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}
def array(schema):
    return {'type': 'array', 'items': schema}
def enum(values):
    return {'type': 'string', 'enum': list(values)}
def template(name):
    return (TEMPLATES / (name + '.txt')).read_text()
REQUIREMENT_SCHEMA = object_schema({k: TEXT for k in ('id', 'text', 'source_phrase')})
OUTCOME_SCHEMA = object_schema({'id': TEXT, 'requirement_ids': array(TEXT), 'description': TEXT,
                                'target': TEXT, 'reference': TEXT, 'applicability': enum(APPLICABILITY)})
CHECK_SCHEMA = object_schema({**{k: TEXT for k in ('id', 'outcome_id', 'question', 'complete_when', 'partial_when', 'absent_when', 'unknown_when')},
                             'role': enum(('requested', 'support')), 'dependencies': array(TEXT)})
GRAPH_SCHEMA = object_schema({'requirements': array(REQUIREMENT_SCHEMA), 'outcomes': array(OUTCOME_SCHEMA), 'checks': array(CHECK_SCHEMA)})
AUDIT_SCHEMA = object_schema({'accepted': {'type': 'boolean'}, 'reason': TEXT})

def media_inputs(evidence):
    return [{'type': 'text', 'text': 'SOURCE image'}, {'type': 'image', 'path': evidence['source_image']},
            {'type': 'text', 'text': 'EDITED image'}, {'type': 'image', 'path': evidence['edited_image']}]

class ProgramCompiler:
    def __init__(self, calls):
        self.calls = calls
    def compile(self, instruction, rubric, *, slot):
        graph, _ = self.calls.call('compile', {'instruction': instruction, 'rubric': rubric, 'max_checks': 4},
                                   GRAPH_SCHEMA, template=template('compile'), slot=slot)
        return ProgramSpec.from_dict({**graph, 'instruction': instruction, 'rubric': rubric,
                                      'checker_template': template('check'), 'version': 'decision-leaf-v2',
                                      'aggregation': 'requested-all-some-none-v2'})
    def audit(self, program, *, slot):
        # No target label, optimization rationale, case metrics or prior audit feedback.
        value, ref = self.calls.call('audit', {'instruction': program.instruction, 'rubric': program.rubric,
                                      'program': program.to_dict()}, AUDIT_SCHEMA, template=template('audit'), slot=slot)
        if type(value.get('accepted')) is not bool or not isinstance(value.get('reason'), str):
            raise ValueError('Invalid semantic audit response')
        return {**value, 'execution_ref': ref}
