"""Schemas and label-blind compilation/auditing for robust leaves."""
from pathlib import Path
from critical.core.decision.compiler import object_schema, array, enum, TEXT, REQUIREMENT_SCHEMA, OUTCOME_SCHEMA, AUDIT_SCHEMA
from .models import RobustProgram, STATES, GATES

TEMPLATES = Path(__file__).parents[2] / 'prompts/templates/robust_leaf_v3'
def template(name):
    return (TEMPLATES / (name + '.txt')).read_text()

INFERENCE_SCHEMA = object_schema({'when': enum((*STATES, 'pass', 'fail')), 'outcome_id': TEXT,
    'status': enum(STATES), 'applicability': enum(('applicable', 'not_applicable', 'unknown')), 'justification': TEXT})
NODE_SCHEMA = object_schema({**{k: TEXT for k in ('id', 'outcome_id', 'parent', 'question', 'criteria', 'binding')},
    'role': enum(('requested', 'support')), 'active_on': array(TEXT), 'dependencies': array(TEXT), 'inferences': array(INFERENCE_SCHEMA)})
GRAPH_SCHEMA = object_schema({'requirements': array(REQUIREMENT_SCHEMA), 'outcomes': array(OUTCOME_SCHEMA), 'nodes': array(NODE_SCHEMA)})

class RobustCompiler:
    def __init__(self, calls):
        self.calls = calls
    def compile(self, instruction, rubric, *, slot):
        graph, _ = self.calls.call('compile', {'instruction': instruction, 'rubric': rubric, 'max_checks': 4},
                                  GRAPH_SCHEMA, template=template('compile'), slot=slot, max_tokens=2048)
        return RobustProgram.from_dict({**graph, 'instruction': instruction, 'rubric': rubric, 'checker_template': template('check')})
    def audit(self, program, *, slot):
        value, ref = self.calls.call('audit', {'instruction': program.instruction, 'rubric': program.rubric,
                                  'program': program.to_dict()}, AUDIT_SCHEMA, template=template('audit'), slot=slot, max_tokens=2048)
        return checked_audit(value, ref)
    def audit_views(self, program, *, slot):
        schema = object_schema({'flat': AUDIT_SCHEMA, 'tree': AUDIT_SCHEMA})
        value, ref = self.calls.call('audit_views', {'instruction': program.instruction, 'rubric': program.rubric,
            'programs': {mode: program.view(mode).to_dict() for mode in ('flat', 'tree')}}, schema,
            template=template('audit'), slot=slot, max_tokens=2048)
        return {mode: checked_audit(value[mode], ref) for mode in ('flat', 'tree')}

def checked_audit(value, ref):
    if type(value.get('accepted')) is not bool or not isinstance(value.get('reason'), str) or not value['reason'].strip():
        raise ValueError('Invalid audit response')
    return {**value, 'execution_ref': ref}
